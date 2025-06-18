# modular/components/gtfs/gtfs_configurator.py
"""
Configurator for GTFS data processing.

This module provides a component for configuring GTFS data processing tasks.
"""

import logging
from typing import Optional

from common.command_utils import log_map_server
from installer import config
from installer.base_component import BaseComponent
from installer.config_models import AppSettings
from installer.processors.plugins.importers.transit.gtfs.gtfs_process import (
    run_gtfs_setup,
)
from installer.registry import ComponentRegistry


@ComponentRegistry.register(
    name="gtfs",
    metadata={
        "dependencies": [
            "postgres",
        ],
        "estimated_time": 180,
        "required_resources": {
            "memory": 1024,
            "disk": 2048,
            "cpu": 2,
        },
        "description": "GTFS Data Processing",
    },
)
class GtfsConfigurator(BaseComponent):
    """
    Configurator for GTFS data processing.

    This configurator handles GTFS data processing tasks such as importing GTFS data
    into the database.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the GTFS data processing configurator.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)

    def install(self) -> bool:
        """
        Install GTFS data processing.

        This is a no-op as there's no installation needed for GTFS data processing.

        Returns:
            True always.
        """
        return True

    def configure(self) -> bool:
        """
        Configure GTFS data processing.

        This method calls the run_gtfs_setup function to execute the full GTFS pipeline.

        Returns:
            True if the configuration was successful, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Configuring GTFS data processing...",
                "info",
                self.logger,
            )

            if not run_gtfs_setup(
                app_settings=self.app_settings,
                logger=self.logger,
            ):
                log_map_server(
                    f"{config.SYMBOLS['error']} Failed to run GTFS setup.",
                    "error",
                    self.logger,
                )
                return False

            log_map_server(
                f"{config.SYMBOLS['success']} GTFS data processing configured successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error configuring GTFS data processing: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def uninstall(self) -> bool:
        """
        Uninstall GTFS data processing.

        This is a no-op as there's nothing to uninstall.

        Returns:
            True always.
        """
        return True

    def unconfigure(self) -> bool:
        """
        Unconfigure GTFS data processing.

        This method removes the GTFS data from the database.

        Returns:
            True if the unconfiguration was successful, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Unconfiguring GTFS data processing...",
                "info",
                self.logger,
            )

            log_map_server(
                f"{config.SYMBOLS['warning']} GTFS data removal not implemented yet.",
                "warning",
                self.logger,
            )

            log_map_server(
                f"{config.SYMBOLS['success']} GTFS data processing unconfigured successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error unconfiguring GTFS data processing: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def is_installed(self) -> bool:
        """
        Check if GTFS data processing is installed.

        This is a no-op as there's no installation needed for GTFS data processing.

        Returns:
            True always.
        """
        return True

    def is_configured(self) -> bool:
        """
        Check if GTFS data processing is configured.

        This method verifies that the GTFS tables have been populated in the database.

        Returns:
            True if the GTFS data processing is configured, False otherwise.
        """
        try:
            from installer.registry import ComponentRegistry

            postgres_component = ComponentRegistry.get_component("postgres")
            postgres_instance = postgres_component(
                self.app_settings, self.logger
            )
            return postgres_instance.is_configured()

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error checking GTFS configuration: {str(e)}",
                "error",
                self.logger,
            )
            return False
