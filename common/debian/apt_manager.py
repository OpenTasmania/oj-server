import logging
import os

import apt  # type: ignore
from aptsources import sourceslist  # type: ignore

from common.command_utils import run_command, run_elevated_command


class AptManager:
    """
    A centralized manager for Debian apt packages using the python-apt library.

    This class provides a high-level interface for common apt operations,
    wrapping the functionality of the python-apt library in a simple,
    easy-to-use class. It also includes helpers for related tasks like
    managing GPG keys.
    """

    def __init__(self, logger=None):
        """
        Initializes the AptManager.

        Args:
            logger: An optional logging object.
        """
        self.logger = logger or logging.getLogger(__name__)
        try:
            self.cache = apt.Cache()
        except apt.cache.LockingError as e:
            self.logger.error(
                f"Failed to lock apt cache. Is another package manager running? Error: {e}"
            )
            raise

    def update(self, raise_error=False):
        """
        Updates the list of available packages.

        Args:
            raise_error (bool): If True, will raise an exception on failure.
        """
        self.logger.info("Updating apt package lists...")
        try:
            self.cache.update(raise_on_error=raise_error)
            self.cache.open(None)  # Re-open the cache to see updates
            self.logger.info("Apt package lists updated successfully.")
        except apt.cache.FetchFailedException as e:
            self.logger.error(f"Failed to update apt cache: {e}")
            if raise_error:
                raise

    def install(self, packages, update_first=True):
        """
        Installs one or more packages.

        Args:
            packages (list): A list of package names to install.
            update_first (bool): If True, updates the package list first.
        """
        if not isinstance(packages, list):
            packages = [packages]

        if update_first:
            self.update()

        self.logger.info(
            f"Preparing to install packages: {', '.join(packages)}"
        )
        for pkg_name in packages:
            pkg = self.cache.get(pkg_name)
            if pkg is None:
                self.logger.error(
                    f"Package '{pkg_name}' not found in cache. Skipping."
                )
                continue

            if not pkg.is_installed:
                self.logger.info(
                    f"Marking package for installation: {pkg_name}"
                )
                pkg.mark_install()
            else:
                self.logger.info(
                    f"Package '{pkg_name}' is already installed. Skipping."
                )

        try:
            self.logger.info("Committing package installations...")
            self.cache.commit()
            self.logger.info("Packages installed successfully.")
        except Exception as e:
            self.logger.error(f"Failed to install packages: {e}")
            raise

    def add_repository(self, repo_string, update_after=True):
        """
        Adds a new apt repository.

        Args:
            repo_string (str): The repository string (e.g., 'ppa:user/repo' or a deb line).
            update_after (bool): If True, updates the package list after adding.
        """
        self.logger.info(f"Adding repository: {repo_string}")
        sources = sourceslist.SourcesList(backup=False)
        sources.add_source(repo_string)
        sources.save()
        if update_after:
            self.update()

    def add_gpg_key_from_url(self, key_url, keyring_path):
        """
        Downloads a GPG key from a URL and saves it to a specified keyring.

        Args:
            key_url (str): The URL of the GPG key.
            keyring_path (str): The full path to save the keyring file.
        """
        self.logger.info(f"Adding GPG key from {key_url} to {keyring_path}")
        os.makedirs(os.path.dirname(keyring_path), exist_ok=True)
        key_download_command = f"curl -fsSL {key_url}"
        gpg_command = f"sudo gpg --dearmor -o {keyring_path}"
        run_command(f"{key_download_command} | {gpg_command}", shell=True)
        run_command(f"sudo chmod a+r {keyring_path}")

    def remove(
        self, packages, purge=False, update_first=False, app_settings=None
    ):
        """
        Removes one or more packages.

        Args:
            packages (list or str): A list of package names to remove, or a single package name.
            purge (bool): If True, purges the packages (removes configuration files).
            update_first (bool): If True, updates the package list first.
            app_settings: Optional application settings for run_elevated_command.
        """
        if not isinstance(packages, list):
            packages = [packages]

        if update_first:
            self.update()

        self.logger.info(
            f"Preparing to remove packages: {', '.join(packages)}"
        )

        try:
            # Using python-apt to mark packages for removal
            for pkg_name in packages:
                pkg = self.cache.get(pkg_name)
                if pkg is None:
                    self.logger.warning(
                        f"Package '{pkg_name}' not found in cache. Skipping."
                    )
                    continue

                if pkg.is_installed:
                    self.logger.info(
                        f"Marking package for removal: {pkg_name}"
                    )
                    pkg.mark_delete(purge=purge)
                else:
                    self.logger.info(
                        f"Package '{pkg_name}' is not installed. Skipping."
                    )

            # Commit the changes
            self.logger.info("Committing package removals...")
            self.cache.commit()
            self.logger.info("Packages removed successfully.")
        except Exception as e:
            self.logger.error(
                f"Failed to remove packages using python-apt: {e}"
            )
            self.logger.info("Falling back to apt-get command...")

            # Fallback to apt-get command
            cmd = ["apt-get", "remove", "-yq"]
            if purge:
                cmd.append("--purge")
            cmd.extend(packages)

            try:
                run_elevated_command(
                    cmd, app_settings, current_logger=self.logger
                )
                self.logger.info(
                    "Packages removed successfully using apt-get."
                )
            except Exception as e2:
                self.logger.error(
                    f"Failed to remove packages using apt-get: {e2}"
                )
                raise

    def purge(self, packages, update_first=False, app_settings=None):
        """
        Purges one or more packages (removes packages and their configuration files).

        Args:
            packages (list or str): A list of package names to purge, or a single package name.
            update_first (bool): If True, updates the package list first.
            app_settings: Optional application settings for run_elevated_command.
        """
        return self.remove(
            packages,
            purge=True,
            update_first=update_first,
            app_settings=app_settings,
        )

    def autoremove(self, purge=False, app_settings=None):
        """
        Removes automatically installed packages that are no longer required.

        Args:
            purge (bool): If True, purges the packages (removes configuration files).
            app_settings: Optional application settings for run_elevated_command.
        """
        self.logger.info("Running autoremove to clean up unused packages...")

        try:
            # Fallback to apt-get command as python-apt doesn't have a direct autoremove method
            cmd = ["apt-get", "autoremove", "-yq"]
            if purge:
                cmd.append("--purge")

            run_elevated_command(
                cmd, app_settings, current_logger=self.logger
            )
            self.logger.info("Autoremove completed successfully.")
        except Exception as e:
            self.logger.error(f"Failed to run autoremove: {e}")
            raise
