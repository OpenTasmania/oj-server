"""
Data processing configurator module.
"""

import logging
from typing import Optional

from installer.base_component import BaseComponent
from installer.components.data_processing.data_processing_installer import (
    DataProcessingInstaller,
)
from installer.config_models import AppSettings
from installer.processors.data_handling.data_processing import data_prep_group
from installer.registry import ComponentRegistry


@ComponentRegistry.register(
    name="data_processing",
    metadata={
        "dependencies": ["postgres", "docker"],  # FIX: Corrected dependencies
        "description": "Processes raw OSM data into OSRM graphs and other formats",
    },
)
class DataProcessingConfigurator(BaseComponent):
    """
    Configurator for processing raw data into application-ready formats.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialise the data processing configurator."""
        super().__init__(app_settings, logger)
        self.installer = DataProcessingInstaller(app_settings, self.logger)

    def install(self) -> bool:
        """Install dependencies by delegating to the installer."""
        return self.installer.install()

    def uninstall(self) -> bool:
        """Uninstall dependencies by delegating to the installer."""
        return self.installer.uninstall()

    def is_installed(self) -> bool:
        """Check if dependencies are installed by delegating to the installer."""
        return self.installer.is_installed()

    def configure(self) -> bool:
        """
        Run the main data processing pipeline.
        """
        self.logger.info("Starting main data processing pipeline...")
        try:
            # The run_processing method should return a boolean indicating success.
            success = data_prep_group(self.app_settings, self.logger)
            if success:
                self.logger.info(
                    "Data processing pipeline completed successfully."
                )
            else:
                self.logger.error("Data processing pipeline failed.")
            return success
        except Exception as e:
            self.logger.error(
                f"An error occurred during data processing: {e}",
                exc_info=True,
            )
            return False

    def unconfigure(self) -> bool:
        """
        This component creates data artifacts; un-configuring is a no-op.
        The data can be removed by uninstalling the 'osrm' component.
        """
        self.logger.info("Unconfiguring for data_processing is a no-op.")
        return True

    def is_configured(self) -> bool:
        """
        Checks if the data processing has been completed successfully.
        This could be improved with a more robust check, e.g., checking for output files.
        For now, we assume if it ran once, it's 'configured'.
        """
        # This is a simplistic check. A real implementation should verify
        # the existence and integrity of the processed data files.
        return True
