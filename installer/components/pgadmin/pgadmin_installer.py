"""
pgAdmin installer module.

This module provides a self-contained installer for pgAdmin, a PostgreSQL administration tool.
"""

import logging
from typing import Optional

from common.command_utils import check_package_installed, log_map_server
from common.constants_loader import is_feature_enabled
from common.debian.apt_manager import AptManager
from installer import config
from installer.base_component import BaseComponent
from installer.config_models import AppSettings
from installer.registry import InstallerRegistry


@InstallerRegistry.register(
    name="pgadmin",
    metadata={
        "dependencies": [
            "prerequisites",
            "postgres",
        ],  # pgAdmin depends on prerequisites and PostgreSQL
        "estimated_time": 60,  # Estimated installation time in seconds
        "required_resources": {
            "memory": 256,  # Required memory in MB
            "disk": 512,  # Required disk space in MB
            "cpu": 1,  # Required CPU cores
        },
        "description": "pgAdmin PostgreSQL administration tool",
    },
)
class PgAdminInstaller(BaseComponent):
    """
    Installer for pgAdmin PostgreSQL administration tool.

    This installer ensures that pgAdmin is installed and properly configured.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the pgAdmin installer.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)
        self.apt_manager = AptManager(logger=self.logger)

    def install(self) -> bool:
        """
        Install pgAdmin.

        Returns:
            True if the installation was successful, False otherwise.
        """
        try:
            # Check if pgAdmin installation is enabled
            pgadmin_enabled = is_feature_enabled("pgadmin_enabled", False)

            if not pgadmin_enabled or not self.app_settings.pgadmin.install:
                log_map_server(
                    f"{config.SYMBOLS['info']} pgAdmin installation is disabled. Skipping.",
                    "info",
                    self.logger,
                )
                return True  # Return True because this is not a failure

            # Log the start of the installation
            log_map_server(
                f"{config.SYMBOLS['info']} Installing pgAdmin...",
                "info",
                self.logger,
            )

            # Install pgAdmin4 package
            self.apt_manager.install(
                "pgadmin4", self.app_settings, update_first=True
            )

            # Verify that the package was installed
            if not check_package_installed(
                "pgadmin4",
                app_settings=self.app_settings,
                current_logger=self.logger,
            ):
                log_map_server(
                    f"{config.SYMBOLS['error']} Failed to install pgAdmin package.",
                    "error",
                    self.logger,
                )
                return False

            log_map_server(
                f"{config.SYMBOLS['success']} pgAdmin installed successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error installing pgAdmin: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def uninstall(self) -> bool:
        """
        Uninstall pgAdmin.

        Returns:
            True if the uninstallation was successful, False otherwise.
        """
        try:
            # Log the start of the uninstallation
            log_map_server(
                f"{config.SYMBOLS['info']} Uninstalling pgAdmin...",
                "info",
                self.logger,
            )

            # Uninstall pgAdmin4 package
            self.apt_manager.purge("pgadmin4", self.app_settings)

            # Clean up any remaining packages
            self.apt_manager.autoremove(
                purge=True, app_settings=self.app_settings
            )

            log_map_server(
                f"{config.SYMBOLS['success']} pgAdmin uninstalled successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error uninstalling pgAdmin: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def is_installed(self) -> bool:
        """
        Check if pgAdmin is installed.

        Returns:
            True if pgAdmin is installed, False otherwise.
        """
        # Check if pgAdmin installation is enabled
        pgadmin_enabled = is_feature_enabled("pgadmin_enabled", False)

        if not pgadmin_enabled or not self.app_settings.pgadmin.install:
            # If pgAdmin is not enabled, we consider it as "installed" (not needed)
            return True

        # Check if pgAdmin4 package is installed
        return check_package_installed(
            "pgadmin4",
            app_settings=self.app_settings,
            current_logger=self.logger,
        )
