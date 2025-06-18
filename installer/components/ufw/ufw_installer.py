"""
UFW installer module.

This module provides a self-contained installer for UFW (Uncomplicated Firewall).
"""

import logging
from typing import Optional

from common.command_utils import (
    check_package_installed,
    log_map_server,
    run_elevated_command,
)
from common.debian.apt_manager import AptManager
from installer import config
from installer.base_installer import BaseInstaller
from installer.config_models import AppSettings
from installer.registry import InstallerRegistry


@InstallerRegistry.register(
    name="ufw",
    metadata={
        "dependencies": [],  # UFW has no dependencies on other installers
        "estimated_time": 30,  # Estimated installation time in seconds
        "required_resources": {
            "memory": 128,  # Required memory in MB
            "disk": 256,  # Required disk space in MB
            "cpu": 1,  # Required CPU cores
        },
        "description": "UFW (Uncomplicated Firewall)",
    },
)
class UfwInstaller(BaseInstaller):
    """
    Installer for UFW (Uncomplicated Firewall).

    This installer ensures that UFW is installed and properly configured.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the UFW installer.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)
        self.apt_manager = AptManager(logger=self.logger)
        self.ufw_package_name = "ufw"

    def install(self) -> bool:
        """
        Install UFW.

        Returns:
            True if the installation was successful, False otherwise.
        """
        try:
            # Log the start of the installation
            log_map_server(
                f"{config.SYMBOLS['info']} Installing UFW (Uncomplicated Firewall)...",
                "info",
                self.logger,
            )

            # Install the UFW package
            self.apt_manager.install(self.ufw_package_name, self.app_settings)

            # Verify that the package was installed
            if not self._verify_ufw_installed():
                log_map_server(
                    f"{config.SYMBOLS['error']} Failed to install UFW package.",
                    "error",
                    self.logger,
                )
                return False

            log_map_server(
                f"{config.SYMBOLS['success']} UFW installed successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error installing UFW: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def uninstall(self) -> bool:
        """
        Uninstall UFW.

        Returns:
            True if the uninstallation was successful, False otherwise.
        """
        try:
            # Log the start of the uninstallation
            log_map_server(
                f"{config.SYMBOLS['info']} Uninstalling UFW...",
                "info",
                self.logger,
            )

            # Disable UFW before uninstalling
            run_elevated_command(
                ["ufw", "disable"],
                self.app_settings,
                current_logger=self.logger,
                check=False,  # Don't fail if UFW is already disabled
            )

            # Uninstall the UFW package
            self.apt_manager.purge(self.ufw_package_name, self.app_settings)

            # Clean up any remaining packages
            self.apt_manager.autoremove(
                purge=True, app_settings=self.app_settings
            )

            log_map_server(
                f"{config.SYMBOLS['success']} UFW uninstalled successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error uninstalling UFW: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def is_installed(self) -> bool:
        """
        Check if UFW is installed.

        Returns:
            True if UFW is installed, False otherwise.
        """
        return self._verify_ufw_installed()

    def _verify_ufw_installed(self) -> bool:
        """
        Verify that UFW is installed.

        Returns:
            True if UFW is installed, False otherwise.
        """
        if check_package_installed(
            self.ufw_package_name,
            app_settings=self.app_settings,
            current_logger=self.logger,
        ):
            log_map_server(
                f"{config.SYMBOLS['success']} UFW package '{self.ufw_package_name}' is installed.",
                "debug",
                self.logger,
            )
            return True
        else:
            log_map_server(
                f"{config.SYMBOLS['error']} UFW package '{self.ufw_package_name}' is NOT installed.",
                "debug",
                self.logger,
            )
            return False
