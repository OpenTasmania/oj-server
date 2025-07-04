"""
Renderd installer module.

This module provides a self-contained installer for Renderd packages and directories.
"""

import logging
import os
from typing import Optional

from common.command_utils import (
    check_package_installed,
    log_map_server,
    run_elevated_command,
)
from common.debian.apt_manager import AptManager
from installer.config_models import AppSettings


class RenderdInstaller:
    """
    Installer for Renderd packages and directories.

    This class handles installing packages via APT and creating directories.
    It does not act as a registered component.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Renderd installer.
        """
        self.app_settings = app_settings
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.apt_manager = AptManager(logger=self.logger)
        self.packages = [
            "renderd",
            "libmapnik3.1",
            "mapnik-utils",
            "python3-mapnik",
        ]
        self.renderd_dirs = [
            "/var/lib/mod_tile",
            "/var/run/renderd",
            "/var/cache/renderd",
        ]

    def install(self) -> bool:
        """
        Install Renderd packages and create directories.
        """
        symbols = self.app_settings.symbols
        try:
            log_map_server(
                f"{symbols.get('info', '')} Installing Renderd packages and directories...",
                "info",
                self.logger,
                self.app_settings,
            )
            if not self._ensure_renderd_packages_installed():
                return False
            if not self._create_renderd_directories():
                return False
            return True
        except Exception as e:
            self.logger.error(
                f"Error installing Renderd prerequisites: {str(e)}"
            )
            return False

    def uninstall(self) -> bool:
        """
        Uninstall Renderd packages and remove directories.
        """
        symbols = self.app_settings.symbols
        try:
            log_map_server(
                f"{symbols.get('info', '')} Uninstalling Renderd packages and directories...",
                "info",
                self.logger,
                self.app_settings,
            )
            self.apt_manager.purge(self.packages, self.app_settings)
            self.apt_manager.autoremove(
                purge=True, app_settings=self.app_settings
            )
            for directory in self.renderd_dirs:
                if os.path.exists(directory):
                    # FIX: Use keyword argument for the logger
                    run_elevated_command(
                        ["rm", "-rf", directory],
                        self.app_settings,
                        current_logger=self.logger,
                    )
            return True
        except Exception as e:
            self.logger.error(f"Error uninstalling Renderd: {str(e)}")
            return False

    def is_installed(self) -> bool:
        """
        Check if Renderd packages are installed and directories exist.
        """
        packages_installed = all(
            check_package_installed(
                pkg,
                app_settings=self.app_settings,
                current_logger=self.logger,
            )
            for pkg in self.packages
        )
        dirs_exist = all(
            os.path.exists(d)
            for d in ["/var/lib/mod_tile", "/var/run/renderd"]
        )
        return packages_installed and dirs_exist

    def _ensure_renderd_packages_installed(self) -> bool:
        """
        Ensure that Renderd packages are installed via APT.
        """
        self.apt_manager.install(self.packages, self.app_settings)
        if not all(
            check_package_installed(
                p, app_settings=self.app_settings, current_logger=self.logger
            )
            for p in self.packages
        ):
            self.logger.error(
                "Failed to install all required Renderd packages."
            )
            return False
        return True

    def _create_renderd_directories(self) -> bool:
        """
        Create and set permissions for Renderd directories.
        """
        try:
            directories_to_setup = {
                "/var/lib/mod_tile": {
                    "owner": "www-data",
                    "group": "www-data",
                    "mode": "755",
                },
                "/var/run/renderd": {
                    "owner": "www-data",
                    "group": "www-data",
                    "mode": "755",
                },
                "/var/cache/renderd": {
                    "owner": "www-data",
                    "group": "www-data",
                    "mode": "755",
                },
            }
            for directory, perms in directories_to_setup.items():
                run_elevated_command(
                    ["mkdir", "-p", directory], self.app_settings
                )
                run_elevated_command(
                    [
                        "chown",
                        f"{perms['owner']}:{perms['group']}",
                        directory,
                    ],
                    self.app_settings,
                )
                run_elevated_command(
                    ["chmod", perms["mode"], directory], self.app_settings
                )
            return True
        except Exception as e:
            self.logger.error(f"Error creating Renderd directories: {str(e)}")
            return False
