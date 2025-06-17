# common/debian/apt_manager.py
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

    def update(self, app_settings: AppSettings, raise_error: bool = False):
        """
        Updates the list of available packages using 'apt-get update'.
        """
        self.logger.info("Updating apt package lists via 'apt-get update'...")
        try:
            run_elevated_command(
                ["apt-get", "update", "-yq"],
                app_settings,
                current_logger=self.logger,
            )
            self.logger.info("Apt package lists updated successfully.")
        except Exception as e:
            self.logger.error(f"Failed to update apt cache: {e}")
            if raise_error:
                raise

    def install(
        self,
        packages: Union[List[str], str],
        app_settings: AppSettings,
        update_first: bool = True,
    ):
        """
        Installs one or more packages using 'apt-get install'.
        """
        if not isinstance(packages, list):
            packages = [packages]

        if update_first:
            self.update(app_settings)

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
            return

        self.logger.info(
            f"Committing installation for: {', '.join(packages_to_install)}"
        )
        try:
            cmd = ["apt-get", "install", "-yq"] + packages_to_install
            run_elevated_command(
                cmd, app_settings, current_logger=self.logger
            )
            self.logger.info("Packages installed successfully.")
        except Exception as e:
            self.logger.error(f"Failed to install packages: {e}")
            raise

    def add_repository(
        self,
        repo_name: str,
        repo_details: Dict[str, str],
        app_settings: AppSettings,
        update_after: bool = True,
    ):
        """
        Adds a new apt repository by creating a deb822-style .sources file.
        This is the modern method for Debian 13 (Trixie) and later.
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
            raise

        if update_after:
            self.update(app_settings)

    def remove_repository(
        self,
        repo_name: str,
        app_settings: AppSettings,
        update_after: bool = True,
    ):
        """
        Removes an apt repository by deleting its .sources file.
        """
        repo_file_path = f"/etc/apt/sources.list.d/{repo_name}.sources"
        self.logger.info(f"Removing repository file: {repo_file_path}")

        if not os.path.exists(repo_file_path):
            self.logger.warning(
                f"Repository file not found, cannot remove: {repo_file_path}"
            )
            return

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
            raise

        if update_after:
            self.update(app_settings)

    def add_gpg_key_from_url(
        self, key_url: str, keyring_path: str, app_settings: AppSettings
    ):
        """
        Downloads a GPG key from a URL and saves it to a specified keyring.
        """
        self.logger.info(f"Adding GPG key from {key_url} to {keyring_path}")

        self.install(
            ["ca-certificates", "curl"], app_settings, update_first=True
        )

        keyring_dir = os.path.dirname(keyring_path)
        if not os.path.exists(keyring_dir):
            run_elevated_command(
                ["install", "-m", "0755", "-d", keyring_dir],
                app_settings,
                current_logger=self.logger,
            )

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

        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            self.logger.error(f"Failed to add GPG key: {e}")
            raise

    def purge(
        self,
        packages: Union[List[str], str],
        app_settings: AppSettings,
        update_first: bool = True,
    ):
        """
        Purges one or more packages using 'apt-get purge'.

        Args:
            packages: A single package name or a list of package names to purge.
            app_settings: The application settings.
            update_first: Whether to update the package lists before purging.
        """
        if not isinstance(packages, list):
            packages = [packages]

        if update_first:
            self.update(app_settings)

        self.logger.info(f"Purging packages: {', '.join(packages)}")
        try:
            cmd = ["apt-get", "purge", "-yq"] + packages
            run_elevated_command(
                cmd, app_settings, current_logger=self.logger
            )
            self.logger.info("Packages purged successfully.")
        except Exception as e:
            self.logger.error(f"Failed to purge packages: {e}")
            raise

    def autoremove(
        self,
        purge: bool = False,
        app_settings: Optional[AppSettings] = None,
    ):
        """
        Removes automatically installed packages that are no longer needed.

        Args:
            purge: Whether to purge configuration files as well.
            app_settings: The application settings.
        """
        if app_settings is None:
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
        except Exception as e:
            self.logger.error(f"Failed to autoremove packages: {e}")
            raise
