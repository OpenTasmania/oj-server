# installer/components/apache/apache_installer.py
# -*- coding: utf-8 -*-
"""
Apache installer module.

This module provides a self-contained installer for Apache web server packages.
"""

import logging
from typing import List, Optional

from common.command_utils import (
    check_package_installed,
    log_map_server,
)
from common.debian.apt_manager import AptManager
from installer.base_component import BaseComponent
from installer.config_models import AppSettings
from installer.registry import InstallerRegistry


@InstallerRegistry.register(
    name="apache-installer",
    metadata={
        "dependencies": ["prerequisites"],
        "estimated_time": 60,
        "description": "Package installer for Apache web server with mod_tile",
    },
)
class ApacheInstaller(BaseComponent):
    """
    Installer for Apache web server packages (e.g., apache2, libapache2-mod-tile).

    This class handles the installation and uninstallation of software packages
    required for the Apache component. It does not handle configuration.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Apache installer.
        """
        super().__init__(app_settings, logger)
        self.apt_manager = AptManager(logger=self.logger)

    def install(self) -> bool:
        """
        Install Apache and related packages using APT.
        """
        try:
            log_map_server(
                f"{self.app_settings.symbols.get('info', '')} Installing Apache and related packages...",
                "info",
                self.logger,
                self.app_settings,
            )
            packages = self._get_apache_packages()
            if not packages:
                self.logger.warning(
                    "No Apache packages specified for installation."
                )
                return True  # Not an error if no packages are listed

            self.apt_manager.install(packages, self.app_settings)

            if not self._verify_packages_installed(packages):
                self.logger.error(
                    "Failed to install all required Apache packages."
                )
                return False

            self.logger.info(
                "Apache and related packages installed successfully."
            )
            return True
        except Exception as e:
            self.logger.error(f"Error installing Apache packages: {str(e)}")
            return False

    def uninstall(self) -> bool:
        """
        Uninstall (purge) Apache and related packages using APT.
        """
        try:
            log_map_server(
                f"{self.app_settings.symbols.get('info', '')} Uninstalling Apache and related packages...",
                "info",
                self.logger,
                self.app_settings,
            )
            packages = self._get_apache_packages()
            if not packages:
                self.logger.warning("No Apache packages to uninstall.")
                return True

            self.apt_manager.purge(packages, self.app_settings)
            self.apt_manager.autoremove(
                purge=True, app_settings=self.app_settings
            )
            self.logger.info(
                "Apache and related packages uninstalled successfully."
            )
            return True
        except Exception as e:
            self.logger.error(f"Error uninstalling Apache packages: {str(e)}")
            return False

    def is_installed(self) -> bool:
        """
        Check if all core Apache packages are installed.
        """
        packages = self._get_apache_packages()
        if not packages:
            return True  # If no packages required, it's "installed"
        return self._verify_packages_installed(packages)

    def configure(self) -> bool:
        """
        Configuration is handled by ApacheConfigurator. This method is a no-op.
        """
        self.logger.info(
            "ApacheInstaller does not handle configuration. Skipping."
        )
        return True

    def unconfigure(self) -> bool:
        """
        Unconfiguration is handled by ApacheConfigurator. This method is a no-op.
        """
        self.logger.info(
            "ApacheInstaller does not handle unconfiguration. Skipping."
        )
        return True

    def is_configured(self) -> bool:
        """
        Configuration status is checked by ApacheConfigurator. This method returns True.
        """
        self.logger.debug(
            "ApacheInstaller does not check configuration status."
        )
        return True  # Assumes not its responsibility

    def _get_apache_packages(self) -> List[str]:
        """
        Get the list of Apache packages to install from settings.
        """
        # FIX: Use getattr for attribute access on the Pydantic model
        return getattr(
            self.app_settings.apache,
            "packages",
            ["apache2", "libapache2-mod-tile"],
        )

    def _verify_packages_installed(self, packages: List[str]) -> bool:
        """
        Verify that all specified packages are installed.
        """
        return all(
            check_package_installed(
                pkg,
                app_settings=self.app_settings,
                current_logger=self.logger,
            )
            for pkg in packages
        )
