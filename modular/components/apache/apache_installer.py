# modular/components/apache/apache_installer.py
# -*- coding: utf-8 -*-
"""
Apache installer module.

This module provides a self-contained installer for Apache web server.
"""

import logging
from typing import List, Optional

from common.command_utils import check_package_installed, log_map_server
from common.debian.apt_manager import AptManager
from modular.base_installer import BaseInstaller
from modular.registry import InstallerRegistry
from setup import config
from setup.config_models import AppSettings


@InstallerRegistry.register(
    name="apache",
    metadata={
        "dependencies": ["prerequisites"],  # Depends on core prerequisites
        "estimated_time": 60,  # Estimated installation time in seconds
        "required_resources": {
            "memory": 256,  # Required memory in MB
            "disk": 512,  # Required disk space in MB
            "cpu": 1,  # Required CPU cores
        },
        "description": "Apache web server with mod_tile for serving map tiles",
    },
)
class ApacheInstaller(BaseInstaller):
    """
    Installer for Apache web server with mod_tile for serving map tiles.

    This installer ensures that Apache and related packages are installed
    and properly configured.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Apache installer.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)
        self.apt_manager = AptManager(logger=self.logger)

    def install(self) -> bool:
        """
        Install Apache and related packages.

        Returns:
            True if the installation was successful, False otherwise.
        """
        try:
            # Log the start of the installation
            log_map_server(
                f"{config.SYMBOLS['info']} Installing Apache and related packages...",
                "info",
                self.logger,
            )

            # Get the list of packages to install
            packages = self._get_apache_packages()

            if not packages:
                log_map_server(
                    f"{config.SYMBOLS['warning']} No Apache packages specified.",
                    "warning",
                    self.logger,
                )
                return False

            # Install the packages
            self.apt_manager.install(packages, self.app_settings)

            # Verify that all packages were installed
            if not self._verify_packages_installed(packages):
                log_map_server(
                    f"{config.SYMBOLS['error']} Failed to install all required Apache packages.",
                    "error",
                    self.logger,
                )
                return False

            log_map_server(
                f"{config.SYMBOLS['success']} Apache and related packages installed successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error installing Apache: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def uninstall(self) -> bool:
        """
        Uninstall Apache and related packages.

        Returns:
            True if the uninstallation was successful, False otherwise.
        """
        try:
            # Log the start of the uninstallation
            log_map_server(
                f"{config.SYMBOLS['info']} Uninstalling Apache and related packages...",
                "info",
                self.logger,
            )

            # Get the list of packages to uninstall
            packages = self._get_apache_packages()

            if not packages:
                log_map_server(
                    f"{config.SYMBOLS['warning']} No Apache packages specified.",
                    "warning",
                    self.logger,
                )
                return False

            # Uninstall the packages
            self.apt_manager.purge(packages, self.app_settings)

            # Clean up any remaining packages
            self.apt_manager.autoremove(
                purge=True, app_settings=self.app_settings
            )

            log_map_server(
                f"{config.SYMBOLS['success']} Apache and related packages uninstalled successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error uninstalling Apache: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def is_installed(self) -> bool:
        """
        Check if Apache is installed.

        Returns:
            True if Apache is installed, False otherwise.
        """
        packages = self._get_apache_packages()

        if not packages:
            log_map_server(
                f"{config.SYMBOLS['warning']} No Apache packages specified.",
                "warning",
                self.logger,
            )
            return False

        return self._verify_packages_installed(packages)

    def _get_apache_packages(self) -> List[str]:
        """
        Get the list of Apache packages to install.

        Returns:
            A list of package names.
        """
        # Based on the original apache_installer.py
        return ["apache2", "libapache2-mod-tile"]

    def _verify_packages_installed(self, packages: List[str]) -> bool:
        """
        Verify that all specified packages are installed.

        Args:
            packages: A list of package names to verify.

        Returns:
            True if all packages are installed, False otherwise.
        """
        all_installed = True

        for pkg in packages:
            if check_package_installed(
                pkg,
                app_settings=self.app_settings,
                current_logger=self.logger,
            ):
                log_map_server(
                    f"{config.SYMBOLS['success']} Package '{pkg}' is installed.",
                    "debug",
                    self.logger,
                )
            else:
                log_map_server(
                    f"{config.SYMBOLS['error']} Package '{pkg}' is NOT installed.",
                    "error",
                    self.logger,
                )
                all_installed = False

        return all_installed
