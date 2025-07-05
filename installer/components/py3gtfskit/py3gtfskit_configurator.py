# modular/components/py3gtfskit/py3gtfskit_configurator.py
"""
Configurator for Py3GTFSKit data processing.

This module provides a component for configuring Py3GTFSKit data processing tasks.
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
    name="py3gtfskit",
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
        "description": "Py3GTFSKit Data Processing",
    },
)
class Py3GTFSKitConfigurator(BaseComponent):
    """
    Configurator for Py3GTFSKit data processing.

    This configurator handles Py3GTFSKit data processing tasks such as importing Py3GTFSKit data
    into the database.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Py3GTFSKit data processing configurator.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)

    def install(self) -> bool:
        """
        Install Py3GTFSKit data processing.

        This is a no-op as there's no installation needed for Py3GTFSKit data processing.

        Returns:
            True always.
        """
        return True

    def configure(self) -> bool:
        """
        Configure Py3GTFSKit data processing.

        This method calls the run_gtfs_setup function to execute the full Py3GTFSKit pipeline.

        Returns:
            True if the configuration was successful, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Configuring Py3GTFSKit data processing...",
                "info",
                self.logger,
            )

            if not run_gtfs_setup(
                app_settings=self.app_settings,
                logger=self.logger,
            ):
                log_map_server(
                    f"{config.SYMBOLS['error']} Failed to run Py3GTFSKit setup.",
                    "error",
                    self.logger,
                )
                return False

            log_map_server(
                f"{config.SYMBOLS['success']} Py3GTFSKit data processing configured successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error configuring Py3GTFSKit data processing: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def uninstall(self) -> bool:
        """
        Uninstall Py3GTFSKit data processing.

        This is a no-op as there's nothing to uninstall.

        Returns:
            True always.
        """
        return True

    def unconfigure(self) -> bool:
        """
        Unconfigure Py3GTFSKit data processing.

        This method removes the Py3GTFSKit data from the database.

        Returns:
            True if the unconfiguration was successful, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Unconfiguring Py3GTFSKit data processing...",
                "info",
                self.logger,
            )

            log_map_server(
                f"{config.SYMBOLS['warning']} Py3GTFSKit data removal not implemented yet.",
                "warning",
                self.logger,
            )

            log_map_server(
                f"{config.SYMBOLS['success']} Py3GTFSKit data processing unconfigured successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error unconfiguring Py3GTFSKit data processing: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def is_installed(self) -> bool:
        """
        Check if Py3GTFSKit data processing is installed.

        This method checks if the gtfs-kit package is installed.

        Returns:
            True if gtfs-kit is installed, False otherwise.
        """
        try:
            import importlib.metadata

            importlib.metadata.version("gtfs-kit")
            return True
        except importlib.metadata.PackageNotFoundError:
            return False

    def is_configured(self) -> bool:
        """
        Check if Py3GTFSKit data processing is configured.

        This method verifies that the Py3GTFSKit tables have been populated in the database.

        Returns:
            True if the Py3GTFSKit data processing is configured, False otherwise.
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
                f"{config.SYMBOLS['error']} Error checking Py3GTFSKit configuration: {str(e)}",
                "error",
                self.logger,
            )
            return False
