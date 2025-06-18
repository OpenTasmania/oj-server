# modular/installers/certbot_installer.py
# -*- coding: utf-8 -*-
"""
Certbot installer module.

This module provides a self-contained installer for Certbot and its plugins.
"""

import logging
from typing import List, Optional

from common.command_utils import check_package_installed, log_map_server
from common.debian.apt_manager import AptManager
from installer import config
from installer.base_component import BaseComponent
from installer.config_models import AppSettings
from installer.registry import ComponentRegistry


@ComponentRegistry.register(
    name="certbot",
    metadata={
        "dependencies": ["prerequisites"],  # Depends on core prerequisites
        "estimated_time": 60,  # Estimated installation time in seconds
        "required_resources": {
            "memory": 256,  # Required memory in MB
            "disk": 512,  # Required disk space in MB
            "cpu": 1,  # Required CPU cores
        },
        "description": "Certbot SSL certificate manager",
    },
)
class CertbotInstaller(BaseComponent):
    """
    Installer for Certbot SSL certificate manager.

    This installer ensures that Certbot and its plugins are installed.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Certbot installer.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)
        self.apt_manager = AptManager(logger=self.logger)

    def install(self) -> bool:
        """
        Install Certbot and its plugins.

        Returns:
            True if the installation was successful, False otherwise.
        """
        try:
            # Log the start of the installation
            log_map_server(
                f"{config.SYMBOLS['info']} Installing Certbot and plugins...",
                "info",
                self.logger,
            )

            # Get the list of packages to install
            packages = self._get_certbot_packages()

            # Install the packages
            self.apt_manager.install(
                packages, self.app_settings, update_first=True
            )

            # Verify that all packages were installed
            if not self._verify_packages_installed(packages):
                log_map_server(
                    f"{config.SYMBOLS['error']} Failed to install all required Certbot packages.",
                    "error",
                    self.logger,
                )
                return False

            log_map_server(
                f"{config.SYMBOLS['success']} Certbot and plugins installed successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error installing Certbot: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def uninstall(self) -> bool:
        """
        Uninstall Certbot and its plugins.

        Returns:
            True if the uninstallation was successful, False otherwise.
        """
        try:
            # Log the start of the uninstallation
            log_map_server(
                f"{config.SYMBOLS['info']} Uninstalling Certbot and plugins...",
                "info",
                self.logger,
            )

            # Get the list of packages to uninstall
            packages = self._get_certbot_packages()

            # Uninstall the packages
            self.apt_manager.purge(packages, self.app_settings)

            # Clean up any remaining packages
            self.apt_manager.autoremove(
                purge=True, app_settings=self.app_settings
            )

            log_map_server(
                f"{config.SYMBOLS['success']} Certbot and plugins uninstalled successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error uninstalling Certbot: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def is_installed(self) -> bool:
        """
        Check if Certbot is installed.

        Returns:
            True if Certbot is installed, False otherwise.
        """
        packages = self._get_certbot_packages()
        return self._verify_packages_installed(packages)

    def _get_certbot_packages(self) -> List[str]:
        """
        Get the list of Certbot packages to install.

        Returns:
            A list of package names.
        """
        # Base package
        packages = ["certbot"]

        # Add plugins for Nginx and Apache
        plugins = ["nginx", "apache"]
        for plugin in plugins:
            packages.append(f"python3-certbot-{plugin}")

        return packages

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

    def configure(self) -> bool:
        """
        Configure Certbot.

        This is a placeholder implementation. In a real implementation, this method
        would configure Certbot after it has been installed.

        Returns:
            True if the configuration was successful, False otherwise.
        """
        # This is a placeholder implementation
        return True

    def unconfigure(self) -> bool:
        """
        Unconfigure Certbot.

        This is a placeholder implementation. In a real implementation, this method
        would unconfigure Certbot.

        Returns:
            True if the unconfiguration was successful, False otherwise.
        """
        # This is a placeholder implementation
        return True

    def is_configured(self) -> bool:
        """
        Check if Certbot is configured.

        This is a placeholder implementation. In a real implementation, this method
        would check if Certbot is configured.

        Returns:
            True if Certbot is configured, False otherwise.
        """
        # This is a placeholder implementation
        return self.is_installed()
