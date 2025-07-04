"""
UFW (Uncomplicated Firewall) installer module.
"""

import logging
from typing import Optional

from common.command_utils import check_package_installed, log_map_server
from common.debian.apt_manager import AptManager
from installer.config_models import AppSettings


class UfwInstaller:
    """
    Installer for UFW (Uncomplicated Firewall).

    This class handles the installation of the UFW package.
    It does not act as a registered component.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the UFW installer.
        """
        self.app_settings = app_settings
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.apt_manager = AptManager(logger=self.logger)
        self.ufw_package_name = "ufw"

    def install(self) -> bool:
        """
        Install UFW.
        """
        symbols = self.app_settings.symbols
        try:
            log_map_server(
                f"{symbols.get('info', '')} Installing UFW (Uncomplicated Firewall)...",
                "info",
                self.logger,
                self.app_settings,
            )
            self.apt_manager.install(self.ufw_package_name, self.app_settings)

            if not self.is_installed():
                log_map_server(
                    f"{symbols.get('error', '')} Failed to install UFW package.",
                    "error",
                    self.logger,
                    self.app_settings,
                )
                return False

            log_map_server(
                f"{symbols.get('success', '')} UFW installed successfully.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(f"Error installing UFW: {str(e)}")
            return False

    def uninstall(self) -> bool:
        """
        Uninstall UFW.
        """
        symbols = self.app_settings.symbols
        try:
            log_map_server(
                f"{symbols.get('info', '')} Uninstalling UFW...",
                "info",
                self.logger,
                self.app_settings,
            )
            self.apt_manager.purge(self.ufw_package_name, self.app_settings)
            self.apt_manager.autoremove(
                purge=True, app_settings=self.app_settings
            )
            log_map_server(
                f"{symbols.get('success', '')} UFW uninstalled successfully.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(f"Error uninstalling UFW: {str(e)}")
            return False

    def is_installed(self) -> bool:
        """
        Check if UFW is installed.
        """
        return check_package_installed(
            self.ufw_package_name,
            app_settings=self.app_settings,
            current_logger=self.logger,
        )
