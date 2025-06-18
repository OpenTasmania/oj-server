# modular/components/data_processing/data_processing_configurator.py
"""
Configurator for data processing.

This module provides a component for configuring data processing tasks.
"""

import logging
import os
from typing import Optional

from common.command_utils import log_map_server
from installer import config
from installer.base_component import BaseComponent
from installer.config_models import AppSettings
from installer.processors.data_handling.osrm_data_processor import (
    build_osrm_graphs_for_region,
    extract_regional_pbfs_with_osmium,
)
from installer.registry import ComponentRegistry


@ComponentRegistry.register(
    name="data_processing",
    metadata={
        "dependencies": [
            "data_processing_dependencies",
            "osrm",
            "postgres",
        ],
        "estimated_time": 300,
        "required_resources": {
            "memory": 2048,
            "disk": 10240,
            "cpu": 4,
        },
        "description": "Data Processing",
    },
)
class DataProcessingConfigurator(BaseComponent):
    """
    Configurator for data processing.

    This configurator handles data processing tasks such as extracting regional PBFs
    and building OSRM graphs.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the data processing configurator.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)

    def install(self) -> bool:
        """
        Install data processing.

        This is a no-op as the actual installation is handled by the DataProcessingInstaller.

        Returns:
            True always.
        """
        return True

    def configure(self) -> bool:
        """
        Configure data processing.

        This method calls the primary functions from the data_handling modules to
        extract regional PBFs and build OSRM graphs.

        Returns:
            True if the configuration was successful, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Configuring data processing...",
                "info",
                self.logger,
            )

            if not hasattr(self.app_settings, "osrm_data") or not hasattr(
                self.app_settings.osrm_data, "pbf_source_file"
            ):
                log_map_server(
                    f"{config.SYMBOLS['error']} PBF source file not configured in app_settings.",
                    "error",
                    self.logger,
                )
                return False

            base_pbf_path = self.app_settings.osrm_data.pbf_source_file
            if not base_pbf_path or not os.path.exists(base_pbf_path):
                log_map_server(
                    f"{config.SYMBOLS['error']} Base PBF file not found at '{base_pbf_path}'.",
                    "error",
                    self.logger,
                )
                return False

            extracted_pbfs = extract_regional_pbfs_with_osmium(
                base_pbf_full_path=str(base_pbf_path),
                app_settings=self.app_settings,
                current_logger=self.logger,
            )

            if not extracted_pbfs:
                log_map_server(
                    f"{config.SYMBOLS['error']} Failed to extract any regional PBFs.",
                    "error",
                    self.logger,
                )
                return False

            for region_key, pbf_host_path in extracted_pbfs.items():
                if not build_osrm_graphs_for_region(
                    region_name_key=region_key,
                    regional_pbf_host_path=pbf_host_path,
                    app_settings=self.app_settings,
                    current_logger=self.logger,
                ):
                    log_map_server(
                        f"{config.SYMBOLS['error']} Failed to build OSRM graphs for {region_key}.",
                        "error",
                        self.logger,
                    )
                    return False

            log_map_server(
                f"{config.SYMBOLS['success']} Data processing configured successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error configuring data processing: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def uninstall(self) -> bool:
        """
        Uninstall data processing.

        This is a no-op as there's nothing to uninstall.

        Returns:
            True always.
        """
        return True

    def unconfigure(self) -> bool:
        """
        Unconfigure data processing.

        This method removes the processed data files.

        Returns:
            True if the unconfiguration was successful, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Unconfiguring data processing...",
                "info",
                self.logger,
            )

            osrm_data_dir = self.app_settings.osrm_data.base_dir
            if osrm_data_dir.exists():
                regions_dir = osrm_data_dir / "regions"
                if regions_dir.exists():
                    import shutil

                    shutil.rmtree(regions_dir)
                    os.makedirs(regions_dir, exist_ok=True)

            log_map_server(
                f"{config.SYMBOLS['success']} Data processing unconfigured successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error unconfiguring data processing: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def is_installed(self) -> bool:
        """
        Check if data processing is installed.

        This is a no-op as the actual installation is handled by the DataProcessingInstaller.

        Returns:
            True always.
        """
        return True

    def is_configured(self) -> bool:
        """
        Check if data processing is configured.

        This method verifies that the processed OSRM data files exist in their final output directory.

        Returns:
            True if the data processing is configured, False otherwise.
        """
        osrm_data_dir = self.app_settings.osrm_data.base_dir
        if not osrm_data_dir.exists():
            return False

        regions_dir = osrm_data_dir / "regions"
        if not regions_dir.exists():
            return False

        region_dirs = [d for d in regions_dir.iterdir() if d.is_dir()]
        if not region_dirs:
            return False

        for region_dir in region_dirs:
            osrm_files = list(region_dir.glob("*.osrm"))
            if not osrm_files:
                return False

        return True
