"""
OSRM installer module.

This module provides a self-contained installer for OSRM (Open Source Routing Machine).
"""

import logging
import os
from pathlib import Path
from shutil import copy2
from typing import Optional

from common.command_utils import (
    log_map_server,
    run_command,
    run_elevated_command,
)
from common.debian.apt_manager import AptManager
from common.file_utils import ensure_directory_owned_by_current_user
from common.json_utils import JsonFileType, check_json_file
from installer import config
from installer.base_installer import BaseInstaller
from installer.config_models import AppSettings
from installer.registry import InstallerRegistry


@InstallerRegistry.register(
    name="osrm",
    metadata={
        "dependencies": [
            "prerequisites",
            "docker",
            "data_processing_dependencies",
        ],  # OSRM depends on prerequisites, Docker, and data processing dependencies
        "estimated_time": 180,  # Estimated installation time in seconds
        "required_resources": {
            "memory": 1024,  # Required memory in MB
            "disk": 2048,  # Required disk space in MB
            "cpu": 2,  # Required CPU cores
        },
        "description": "Open Source Routing Machine (OSRM)",
    },
)
class OsrmInstaller(BaseInstaller):
    """
    Installer for Open Source Routing Machine (OSRM).

    This installer ensures that OSRM and its dependencies are installed
    and properly configured.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the OSRM installer.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)
        self.apt_manager = AptManager(logger=self.logger)

    def install(self) -> bool:
        """
        Install OSRM and its dependencies.

        Returns:
            True if the installation was successful, False otherwise.
        """
        try:
            # Log the start of the installation
            log_map_server(
                f"{config.SYMBOLS['info']} Installing OSRM...",
                "info",
                self.logger,
            )

            # Set up OSRM data directories
            if not self._setup_osrm_data_directories():
                return False

            # Download base PBF
            if not self._download_base_pbf():
                return False

            # Prepare region boundaries
            if not self._prepare_region_boundaries():
                return False

            log_map_server(
                f"{config.SYMBOLS['success']} OSRM installed successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error installing OSRM: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def uninstall(self) -> bool:
        """
        Uninstall OSRM.

        Returns:
            True if the uninstallation was successful, False otherwise.
        """
        try:
            # Log the start of the uninstallation
            log_map_server(
                f"{config.SYMBOLS['info']} Uninstalling OSRM...",
                "info",
                self.logger,
            )

            # Remove OSRM data directories
            osrm_data_dir = self.app_settings.osrm_data.base_dir
            if osrm_data_dir.exists():
                run_elevated_command(
                    ["rm", "-rf", str(osrm_data_dir)],
                    self.app_settings,
                    current_logger=self.logger,
                )

            log_map_server(
                f"{config.SYMBOLS['success']} OSRM uninstalled successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error uninstalling OSRM: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def is_installed(self) -> bool:
        """
        Check if OSRM is installed.

        Returns:
            True if OSRM is installed, False otherwise.
        """
        # Check if OSRM data directories exist
        osrm_data_dir = self.app_settings.osrm_data.base_dir
        if not osrm_data_dir.exists():
            return False

        return True

    def _setup_osrm_data_directories(self) -> bool:
        """
        Set up OSRM data directories.

        Returns:
            True if the directories were set up successfully, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Setting up OSRM data directories...",
                "info",
                self.logger,
            )

            # Create OSRM data directory
            osrm_data_dir = self.app_settings.osrm_data.base_dir
            os.makedirs(osrm_data_dir, exist_ok=True)

            # Create subdirectories
            subdirs = ["base", "regions", "profiles"]
            for subdir in subdirs:
                os.makedirs(osrm_data_dir / subdir, exist_ok=True)

            # Set appropriate permissions
            ensure_directory_owned_by_current_user(
                Path(osrm_data_dir),
                make_directory=True,
                world_access=False,
                app_settings=self.app_settings,
                current_logger=self.logger,
            )

            # Copy OSRM profiles
            profiles_dir = osrm_data_dir / "profiles"
            # Default profiles to copy
            profiles = ["car.lua", "foot.lua", "bicycle.lua"]
            # Default source directory for profiles
            profiles_source_dir = Path("/usr/share/osrm/profiles")
            for profile_file in profiles:
                source_path = profiles_source_dir / profile_file
                if source_path.exists():
                    copy2(source_path, profiles_dir / profile_file)
                    log_map_server(
                        f"{config.SYMBOLS['success']} Copied profile {profile_file} to {profiles_dir}",
                        "debug",
                        self.logger,
                    )
                else:
                    log_map_server(
                        f"{config.SYMBOLS['warning']} Profile {profile_file} not found at {source_path}",
                        "warning",
                        self.logger,
                    )

            log_map_server(
                f"{config.SYMBOLS['success']} OSRM data directories set up successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error setting up OSRM data directories: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def _download_base_pbf(self) -> bool:
        """
        Download base PBF file.

        Returns:
            True if the download was successful, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Downloading base PBF file...",
                "info",
                self.logger,
            )

            # Get base PBF URL and destination
            base_pbf_url = self.app_settings.osrm_data.base_pbf_url
            base_pbf_path = (
                self.app_settings.osrm_data.base_dir / "base" / "base.osm.pbf"
            )

            # Download the PBF file if it doesn't exist
            if not base_pbf_path.exists():
                log_map_server(
                    f"{config.SYMBOLS['info']} Downloading base PBF from {base_pbf_url}...",
                    "info",
                    self.logger,
                )

                run_command(
                    ["wget", "-O", str(base_pbf_path), str(base_pbf_url)],
                    self.app_settings,
                    current_logger=self.logger,
                )

                # Verify the download
                if (
                    not base_pbf_path.exists()
                    or base_pbf_path.stat().st_size == 0
                ):
                    log_map_server(
                        f"{config.SYMBOLS['error']} Failed to download base PBF file.",
                        "error",
                        self.logger,
                    )
                    return False
            else:
                log_map_server(
                    f"{config.SYMBOLS['info']} Base PBF file already exists at {base_pbf_path}.",
                    "info",
                    self.logger,
                )

            log_map_server(
                f"{config.SYMBOLS['success']} Base PBF file is available at {base_pbf_path}.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error downloading base PBF file: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def _prepare_region_boundaries(self) -> bool:
        """
        Prepare region boundaries.

        Returns:
            True if the preparation was successful, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Preparing region boundaries...",
                "info",
                self.logger,
            )

            # Get regions configuration
            regions_config = self.app_settings.osrm_service.region_port_map
            if not regions_config:
                log_map_server(
                    f"{config.SYMBOLS['warning']} No regions configured. Skipping region boundaries preparation.",
                    "warning",
                    self.logger,
                )
                return True

            # Create regions directory
            regions_dir = self.app_settings.osrm_data.base_dir / "regions"
            os.makedirs(regions_dir, exist_ok=True)

            # Process each region
            for region_name, region_config in regions_config.items():
                region_dir = regions_dir / region_name
                os.makedirs(region_dir, exist_ok=True)

                # Create region boundary file
                boundary_file = region_dir / f"{region_name}.geojson"
                if not boundary_file.exists():
                    log_map_server(
                        f"{config.SYMBOLS['info']} Creating boundary file for region {region_name}...",
                        "info",
                        self.logger,
                    )

                    # Write boundary GeoJSON
                    # Convert region_config to string if it's an int (port number)
                    boundary_content = getattr(
                        region_config, "boundary", str(region_config)
                    )
                    with open(boundary_file, "w") as f:
                        f.write(boundary_content)

                    # Verify the file
                    if (
                        check_json_file(Path(boundary_file))
                        != JsonFileType.VALID_JSON
                    ):
                        log_map_server(
                            f"{config.SYMBOLS['error']} Invalid GeoJSON boundary for region {region_name}.",
                            "error",
                            self.logger,
                        )
                        return False

                log_map_server(
                    f"{config.SYMBOLS['success']} Region {region_name} boundary prepared.",
                    "debug",
                    self.logger,
                )

            log_map_server(
                f"{config.SYMBOLS['success']} Region boundaries prepared successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error preparing region boundaries: {str(e)}",
                "error",
                self.logger,
            )
            return False
