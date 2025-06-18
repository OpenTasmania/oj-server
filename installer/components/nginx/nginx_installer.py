"""
Nginx installer module.

This module provides a self-contained installer for Nginx web server.
"""

import logging
from typing import Optional

from common.command_utils import (
    check_package_installed,
    elevated_command_exists,
    log_map_server,
)
from common.debian.apt_manager import AptManager
from installer import config
from installer.base_component import BaseComponent
from installer.config_models import AppSettings
from installer.registry import ComponentRegistry


@ComponentRegistry.register(
    name="nginx",
    metadata={
        "dependencies": ["prerequisites"],  # Depends on core prerequisites
        "estimated_time": 60,  # Estimated installation time in seconds
        "required_resources": {
            "memory": 256,  # Required memory in MB
            "disk": 512,  # Required disk space in MB
            "cpu": 1,  # Required CPU cores
        },
        "description": "Nginx web server",
    },
)
class NginxInstaller(BaseComponent):
    """
    Installer for Nginx web server.

    This installer ensures that Nginx is installed and properly configured.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Nginx installer.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)
        self.apt_manager = AptManager(logger=self.logger)
        self.nginx_package_name = "nginx"

    def install(self) -> bool:
        """
        Install Nginx web server.

        Returns:
            True if the installation was successful, False otherwise.
        """
        try:
            # Log the start of the installation
            log_map_server(
                f"{config.SYMBOLS['info']} Installing Nginx web server...",
                "info",
                self.logger,
            )

            # Install the Nginx package
            self.apt_manager.install(
                self.nginx_package_name, self.app_settings
            )

            # Verify that the package was installed
            if not self._verify_nginx_installed():
                log_map_server(
                    f"{config.SYMBOLS['error']} Failed to install Nginx package.",
                    "error",
                    self.logger,
                )
                return False

            log_map_server(
                f"{config.SYMBOLS['success']} Nginx web server installed successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error installing Nginx: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def uninstall(self) -> bool:
        """
        Uninstall Nginx web server.

        Returns:
            True if the uninstallation was successful, False otherwise.
        """
        try:
            # Log the start of the uninstallation
            log_map_server(
                f"{config.SYMBOLS['info']} Uninstalling Nginx web server...",
                "info",
                self.logger,
            )

            # Uninstall the Nginx package
            self.apt_manager.purge(self.nginx_package_name, self.app_settings)

            # Clean up any remaining packages
            self.apt_manager.autoremove(
                purge=True, app_settings=self.app_settings
            )

            log_map_server(
                f"{config.SYMBOLS['success']} Nginx web server uninstalled successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error uninstalling Nginx: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def is_installed(self) -> bool:
        """
        Check if Nginx is installed.

        Returns:
            True if Nginx is installed, False otherwise.
        """
        return self._verify_nginx_installed()

    def _verify_nginx_installed(self) -> bool:
        """
        Verify that Nginx is installed and the command exists.

        Returns:
            True if Nginx is installed and the command exists, False otherwise.
        """
        # Check if the package is installed
        package_installed = check_package_installed(
            self.nginx_package_name,
            app_settings=self.app_settings,
            current_logger=self.logger,
        )

        # Check if the command exists
        command_exists = elevated_command_exists(
            "nginx",
            self.app_settings,
            current_logger=self.logger,
        )

        if package_installed and command_exists:
            log_map_server(
                f"{config.SYMBOLS['success']} Nginx package '{self.nginx_package_name}' is installed and command exists.",
                "debug",
                self.logger,
            )
            return True
        else:
            log_map_server(
                f"{config.SYMBOLS['error']} Nginx package '{self.nginx_package_name}' or command is NOT found/installed.",
                "debug",
                self.logger,
            )
            return False

    def configure(self) -> bool:
        """
        Configure Nginx.

        This is a placeholder implementation. In a real implementation, this method
        would configure Nginx after it has been installed.

        Returns:
            True if the configuration was successful, False otherwise.
        """
        # This is a placeholder implementation
        return True

    def unconfigure(self) -> bool:
        """
        Unconfigure Nginx.

        This is a placeholder implementation. In a real implementation, this method
        would unconfigure Nginx.

        Returns:
            True if the unconfiguration was successful, False otherwise.
        """
        # This is a placeholder implementation
        return True

    def is_configured(self) -> bool:
        """
        Check if Nginx is configured.

        This is a placeholder implementation. In a real implementation, this method
        would check if Nginx is configured.

        Returns:
            True if Nginx is configured, False otherwise.
        """
        # This is a placeholder implementation
        return self.is_installed()
