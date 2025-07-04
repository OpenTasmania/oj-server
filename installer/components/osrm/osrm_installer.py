"""
OSRM installer module.

This module provides a self-contained installer for OSRM (Open Source Routing Machine) data.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from common.command_utils import (
    log_map_server,
    run_command,
    run_elevated_command,
)
from common.file_utils import ensure_directory_owned_by_current_user
from common.json_utils import JsonFileType, check_json_file
from installer.config_models import AppSettings


class OsrmInstaller:
    """
    Installer for Open Source Routing Machine (OSRM) data and directories.

    This class handles downloading PBF files and setting up the OSRM data structure.
    It does not act as a registered component.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the OSRM installer.
        """
        self.app_settings = app_settings
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def install(self) -> bool:
        """
        Install OSRM data.
        """
        symbols = self.app_settings.symbols
        try:
            log_map_server(
                f"{symbols.get('info', '')} Installing OSRM data...",
                "info",
                self.logger,
                self.app_settings,
            )
            if not self._setup_osrm_data_directories():
                return False
            if not self._download_base_pbf():
                return False
            if not self._prepare_region_boundaries():
                return False

            log_map_server(
                f"{symbols.get('success', '')} OSRM data installed successfully.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(f"Error installing OSRM data: {str(e)}")
            return False

    def uninstall(self) -> bool:
        """
        Uninstall OSRM data by removing the data directories.
        """
        symbols = self.app_settings.symbols
        try:
            log_map_server(
                f"{symbols.get('info', '')} Uninstalling OSRM data...",
                "info",
                self.logger,
                self.app_settings,
            )
            osrm_data_dir = Path(self.app_settings.osrm_data.base_dir)
            if osrm_data_dir.exists():
                run_elevated_command(
                    ["rm", "-rf", str(osrm_data_dir)],
                    self.app_settings,
                    current_logger=self.logger,
                )
            log_map_server(
                f"{symbols.get('success', '')} OSRM data uninstalled successfully.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(f"Error uninstalling OSRM data: {str(e)}")
            return False

    def is_installed(self) -> bool:
        """
        Check if the OSRM data directory exists.
        """
        return Path(self.app_settings.osrm_data.base_dir).is_dir()

    def _setup_osrm_data_directories(self) -> bool:
        """
        Set up OSRM data directories.
        """
        symbols = self.app_settings.symbols
        try:
            osrm_data_dir = Path(self.app_settings.osrm_data.base_dir)
            ensure_directory_owned_by_current_user(
                osrm_data_dir, True, False, self.app_settings, self.logger
            )
            for subdir in ["base", "regions", "profiles"]:
                os.makedirs(osrm_data_dir / subdir, exist_ok=True)
            log_map_server(
                f"{symbols.get('success', '')} OSRM data directories set up.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Error setting up OSRM data directories: {str(e)}"
            )
            return False

    def _download_base_pbf(self) -> bool:
        """
        Download base PBF file.
        """
        symbols = self.app_settings.symbols
        try:
            base_pbf_url = self.app_settings.osrm_data.base_pbf_url
            base_pbf_path = (
                Path(self.app_settings.osrm_data.base_dir)
                / "base"
                / "base.osm.pbf"
            )

            if not base_pbf_path.exists():
                log_map_server(
                    f"{symbols.get('info', '')} Downloading base PBF from {base_pbf_url}...",
                    "info",
                    self.logger,
                    self.app_settings,
                )
                run_command(
                    ["wget", "-O", str(base_pbf_path), str(base_pbf_url)],
                    self.app_settings,
                    current_logger=self.logger,
                )
                if (
                    not base_pbf_path.exists()
                    or base_pbf_path.stat().st_size == 0
                ):
                    raise FileNotFoundError(
                        "Failed to download base PBF file."
                    )

            log_map_server(
                f"{symbols.get('success', '')} Base PBF file is available.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(f"Error downloading base PBF file: {str(e)}")
            return False

    def _prepare_region_boundaries(self) -> bool:
        """
        Prepare region boundaries from configuration.
        """
        symbols = self.app_settings.symbols
        try:
            regions_config = self.app_settings.osrm_service.region_port_map
            if not regions_config:
                return True

            regions_dir = (
                Path(self.app_settings.osrm_data.base_dir) / "regions"
            )
            for region_name, region_data in regions_config.items():
                region_dir = regions_dir / region_name
                os.makedirs(region_dir, exist_ok=True)
                boundary_file = region_dir / f"{region_name}.geojson"
                if not boundary_file.exists():
                    boundary_content = getattr(region_data, "boundary", "{}")
                    boundary_file.write_text(boundary_content)
                    if (
                        check_json_file(boundary_file)
                        != JsonFileType.VALID_JSON
                    ):
                        raise ValueError(
                            f"Invalid GeoJSON boundary for region {region_name}."
                        )

            log_map_server(
                f"{symbols.get('success', '')} Region boundaries prepared successfully.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(f"Error preparing region boundaries: {str(e)}")
            return False
