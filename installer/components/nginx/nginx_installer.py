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
from installer.config_models import AppSettings


class NginxInstaller:
    """
    Installer for the Nginx web server package.

    This class handles the installation and uninstallation of Nginx.
    It does not act as a registered component.
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
        self.app_settings = app_settings
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.apt_manager = AptManager(logger=self.logger)
        self.nginx_package_name = "nginx"

    def install(self) -> bool:
        """
        Install Nginx web server.

        Returns:
            True if the installation was successful, False otherwise.
        """
        symbols = self.app_settings.symbols
        try:
            log_map_server(
                f"{symbols.get('info', '')} Installing Nginx web server...",
                "info",
                self.logger,
                self.app_settings,
            )
            self.apt_manager.install(
                self.nginx_package_name, self.app_settings
            )

            if not self.is_installed():
                log_map_server(
                    f"{symbols.get('error', '')} Failed to install Nginx package.",
                    "error",
                    self.logger,
                    self.app_settings,
                )
                return False

            log_map_server(
                f"{symbols.get('success', '')} Nginx web server installed successfully.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(f"Error installing Nginx: {str(e)}")
            return False

    def uninstall(self) -> bool:
        """
        Uninstall Nginx web server.

        Returns:
            True if the uninstallation was successful, False otherwise.
        """
        symbols = self.app_settings.symbols
        try:
            log_map_server(
                f"{symbols.get('info', '')} Uninstalling Nginx web server...",
                "info",
                self.logger,
                self.app_settings,
            )
            self.apt_manager.purge(self.nginx_package_name, self.app_settings)
            self.apt_manager.autoremove(
                purge=True, app_settings=self.app_settings
            )
            log_map_server(
                f"{symbols.get('success', '')} Nginx web server uninstalled successfully.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(f"Error uninstalling Nginx: {str(e)}")
            return False

    def is_installed(self) -> bool:
        """
        Check if Nginx is installed.

        Returns:
            True if Nginx is installed, False otherwise.
        """
        package_installed = check_package_installed(
            self.nginx_package_name,
            app_settings=self.app_settings,
            current_logger=self.logger,
        )
        command_exists = elevated_command_exists(
            "nginx",
            self.app_settings,
            current_logger=self.logger,
        )
        return package_installed and command_exists
