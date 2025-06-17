# common/debian/apt_manager.py
# -*- coding: utf-8 -*-
import logging
import os
import subprocess
from typing import Dict, List, Optional, Union

from common.command_utils import (
    command_exists,
    run_command,
    run_elevated_command,
)
from setup.config_models import AppSettings


class AptManager:
    """
    A centralized manager for Debian apt packages using command-line tools,
    updated to support the deb822 source format for Debian 13 (Trixie) and later.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initializes the AptManager.
        Args:
            logger: An optional logging object.
        """
        self.logger = logger or logging.getLogger(__name__)
        if not command_exists("apt-get"):
            self.logger.critical(
                "'apt-get' command not found. This manager cannot function."
            )
            raise FileNotFoundError(
                "'apt-get' not found. Is this a Debian-based system?"
            )

    def update(
        self, app_settings: AppSettings, raise_error: bool = False
    ) -> bool:
        """
        Updates the list of available packages using 'apt-get update'.

        Args:
            app_settings: The application settings.
            raise_error: Whether to raise an exception on failure.

        Returns:
            True if successful, False otherwise.
        """
        self.logger.info("Updating apt package lists via 'apt-get update'...")
        try:
            run_elevated_command(
                ["apt-get", "update", "-yq"],
                app_settings,
                current_logger=self.logger,
            )
            self.logger.info("Apt package lists updated successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to update apt cache: {e}")
            if raise_error:
                raise
            return False

    def install(
        self,
        packages: Union[List[str], str],
        app_settings: AppSettings,
        update_first: bool = True,
    ) -> bool:
        """
        Installs one or more packages using 'apt-get install'.

        Args:
            packages: A single package name or a list of package names.
            app_settings: The application settings.
            update_first: Whether to update the package lists before installing.

        Returns:
            True if successful, False otherwise.
        """
        if not isinstance(packages, list):
            packages = [packages]

        if update_first:
            if not self.update(app_settings):
                return False

        packages_to_install = []
        for pkg_name in packages:
            try:
                status_cmd = [
                    "dpkg-query",
                    "-W",
                    "-f=${db:Status-Status}",
                    pkg_name,
                ]
                result = run_command(
                    status_cmd,
                    app_settings,
                    capture_output=True,
                    check=True,
                    current_logger=self.logger,
                )
                if (
                    "installed" in result.stdout
                    and "not-installed" not in result.stdout
                ):
                    self.logger.info(
                        f"Package '{pkg_name}' is already installed. Skipping."
                    )
                else:
                    packages_to_install.append(pkg_name)
            except subprocess.CalledProcessError:
                self.logger.info(
                    f"Marking package for installation: {pkg_name}"
                )
                packages_to_install.append(pkg_name)

        if not packages_to_install:
            self.logger.info("All requested packages are already installed.")
            return True

        self.logger.info(
            f"Committing installation for: {', '.join(packages_to_install)}"
        )
        try:
            cmd = ["apt-get", "install", "-yq"] + packages_to_install
            run_elevated_command(
                cmd, app_settings, current_logger=self.logger
            )
            self.logger.info("Packages installed successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to install packages: {e}")
            return False

    def add_repository(
        self,
        repo_name: str,
        repo_details: Dict[str, str],
        app_settings: AppSettings,
        update_after: bool = True,
    ) -> bool:
        """
        Adds a new apt repository by creating a deb822-style .sources file.

        Args:
            repo_name: The name for the repository file.
            repo_details: A dictionary containing the repository configuration.
            app_settings: The application settings.
            update_after: Whether to update package lists after adding.

        Returns:
            True if successful, False otherwise.
        """
        self.logger.info(
            f"Adding repository '{repo_name}' using deb822 format..."
        )

        sources_dir = "/etc/apt/sources.list.d"
        repo_file_path = os.path.join(sources_dir, f"{repo_name}.sources")

        os.makedirs(sources_dir, exist_ok=True)

        deb822_content = ""
        for key, value in repo_details.items():
            deb822_content += f"{key}: {value}\n"

        try:
            with open("/tmp/deb822_content.tmp", "w") as f:
                f.write(deb822_content)

            run_elevated_command(
                ["mv", "/tmp/deb822_content.tmp", repo_file_path],
                app_settings,
                current_logger=self.logger,
            )
            run_elevated_command(
                ["chmod", "644", repo_file_path],
                app_settings,
                current_logger=self.logger,
            )
            self.logger.info(
                f"Successfully created repository file: {repo_file_path}"
            )

        except Exception as e:
            self.logger.error(
                f"Failed to create repository file '{repo_file_path}': {e}"
            )
            return False

        if update_after:
            return self.update(app_settings)
        return True

    def remove_repository(
        self,
        repo_name: str,
        app_settings: AppSettings,
        update_after: bool = True,
    ) -> bool:
        """
        Removes an apt repository by deleting its .sources file.

        Args:
            repo_name: The name of the repository file to remove.
            app_settings: The application settings.
            update_after: Whether to update package lists after removing.

        Returns:
            True if successful, False otherwise.
        """
        repo_file_path = f"/etc/apt/sources.list.d/{repo_name}.sources"
        self.logger.info(f"Removing repository file: {repo_file_path}")

        if not os.path.exists(repo_file_path):
            self.logger.warning(
                f"Repository file not found, cannot remove: {repo_file_path}"
            )
            return True

        try:
            run_elevated_command(
                ["rm", "-f", repo_file_path],
                app_settings,
                current_logger=self.logger,
            )
            self.logger.info(f"Successfully removed repository: {repo_name}")
        except Exception as e:
            self.logger.error(
                f"Failed to remove repository '{repo_name}': {e}"
            )
            return False

        if update_after:
            return self.update(app_settings)
        return True

    def add_gpg_key_from_url(
        self, key_url: str, keyring_path: str, app_settings: AppSettings
    ) -> bool:
        """
        Downloads a GPG key from a URL and saves it to a specified keyring.

        Args:
            key_url: The URL of the GPG key.
            keyring_path: The path to save the keyring file.
            app_settings: The application settings.

        Returns:
            True if successful, False otherwise.
        """
        self.logger.info(f"Adding GPG key from {key_url} to {keyring_path}")

        if not self.install(
            ["ca-certificates", "curl"], app_settings, update_first=True
        ):
            self.logger.error(
                "Failed to install required tools for GPG key download."
            )
            return False

        keyring_dir = os.path.dirname(keyring_path)
        if not os.path.exists(keyring_dir):
            try:
                run_elevated_command(
                    ["install", "-m", "0755", "-d", keyring_dir],
                    app_settings,
                    current_logger=self.logger,
                )
            except Exception as e:
                self.logger.error(f"Failed to create keyring directory: {e}")
                return False

        temp_key_path = f"/tmp/{os.path.basename(keyring_path)}"
        curl_cmd = ["curl", "-fsSL", key_url, "-o", temp_key_path]

        try:
            self.logger.info(f"Downloading GPG key to {temp_key_path}...")
            run_command(
                curl_cmd, app_settings, check=True, current_logger=self.logger
            )

            run_elevated_command(
                ["mv", temp_key_path, keyring_path],
                app_settings,
                current_logger=self.logger,
            )

            run_elevated_command(
                ["chmod", "a+r", keyring_path],
                app_settings,
                current_logger=self.logger,
            )
            self.logger.info("GPG key added and permissions set.")
            return True

        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            self.logger.error(f"Failed to add GPG key: {e}")
            return False

    def purge(
        self,
        packages: Union[List[str], str],
        app_settings: AppSettings,
        update_first: bool = True,
    ) -> bool:
        """
        Purges one or more packages using 'apt-get purge'.

        Args:
            packages: A single package name or a list of package names to purge.
            app_settings: The application settings.
            update_first: Whether to update the package lists before purging.

        Returns:
            True if successful, False otherwise.
        """
        if not isinstance(packages, list):
            packages = [packages]

        if update_first:
            if not self.update(app_settings):
                return False

        self.logger.info(f"Purging packages: {', '.join(packages)}")
        try:
            cmd = ["apt-get", "purge", "-yq"] + packages
            run_elevated_command(
                cmd, app_settings, current_logger=self.logger
            )
            self.logger.info("Packages purged successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to purge packages: {e}")
            return False

    def autoremove(
        self,
        purge: bool = False,
        app_settings: Optional[AppSettings] = None,
    ) -> bool:
        """
        Removes automatically installed packages that are no longer needed.

        Args:
            purge: Whether to purge configuration files as well.
            app_settings: The application settings.

        Returns:
            True if successful, False otherwise.
        """
        if app_settings is None:
            self.logger.error("app_settings must be provided for autoremove.")
            raise ValueError("app_settings must be provided")

        self.logger.info("Running autoremove to clean up unused packages...")
        try:
            cmd = ["apt-get", "autoremove", "-yq"]
            if purge:
                cmd.append("--purge")

            run_elevated_command(
                cmd, app_settings, current_logger=self.logger
            )
            self.logger.info("Autoremove completed successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to autoremove packages: {e}")
            return False
