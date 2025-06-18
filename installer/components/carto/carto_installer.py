"""
Carto installer module.

This module provides a self-contained installer for Carto, a mapping and visualization tool.
"""

import logging
import os
from typing import Optional

from common.command_utils import (
    command_exists,
    log_map_server,
    run_command,
    run_elevated_command,
)
from common.debian.apt_manager import AptManager
from installer import config
from installer.base_installer import BaseInstaller
from installer.config_models import AppSettings
from installer.registry import InstallerRegistry


@InstallerRegistry.register(
    name="carto",
    metadata={
        "dependencies": ["nodejs"],  # Carto depends on Node.js
        "estimated_time": 180,  # Estimated installation time in seconds
        "required_resources": {
            "memory": 512,  # Required memory in MB
            "disk": 1024,  # Required disk space in MB
            "cpu": 1,  # Required CPU cores
        },
        "description": "Carto mapping and visualization tool",
    },
)
class CartoInstaller(BaseInstaller):
    """
    Installer for Carto mapping and visualization tool.

    This installer ensures that Carto and related components are installed
    and properly configured.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Carto installer.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)
        self.apt_manager = AptManager(logger=self.logger)

    def install(self) -> bool:
        """
        Install Carto and related components.

        Returns:
            True if the installation was successful, False otherwise.
        """
        try:
            # Log the start of the installation
            log_map_server(
                f"{config.SYMBOLS['info']} Installing Carto and related components...",
                "info",
                self.logger,
            )

            # Install Carto CLI
            if not self._install_carto_cli():
                return False

            # Setup OSM Carto repository
            if not self._setup_osm_carto_repository():
                return False

            # Prepare Carto directory for processing
            if not self._prepare_carto_directory_for_processing():
                return False

            # Fetch Carto external data
            if not self._fetch_carto_external_data():
                return False

            log_map_server(
                f"{config.SYMBOLS['success']} Carto and related components installed successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error installing Carto: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def uninstall(self) -> bool:
        """
        Uninstall Carto and related components.

        Returns:
            True if the uninstallation was successful, False otherwise.
        """
        try:
            # Log the start of the uninstallation
            log_map_server(
                f"{config.SYMBOLS['info']} Uninstalling Carto and related components...",
                "info",
                self.logger,
            )

            # Remove Carto CLI
            if command_exists("carto"):
                run_elevated_command(
                    ["npm", "uninstall", "-g", "@mapbox/carto"],
                    self.app_settings,
                    current_logger=self.logger,
                )

            # Remove OSM Carto repository
            osm_carto_dir = os.path.join(
                config.OSM_PROJECT_ROOT, "openstreetmap-carto"
            )
            if os.path.exists(osm_carto_dir):
                run_elevated_command(
                    ["rm", "-rf", osm_carto_dir],
                    self.app_settings,
                    current_logger=self.logger,
                )

            log_map_server(
                f"{config.SYMBOLS['success']} Carto and related components uninstalled successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error uninstalling Carto: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def is_installed(self) -> bool:
        """
        Check if Carto is installed.

        Returns:
            True if Carto is installed, False otherwise.
        """
        # Check if Carto CLI is installed
        if not command_exists("carto"):
            return False

        # Check if OSM Carto repository exists
        osm_carto_dir = os.path.join(
            config.OSM_PROJECT_ROOT, "openstreetmap-carto"
        )
        if not os.path.exists(osm_carto_dir):
            return False

        return True

    def _install_carto_cli(self) -> bool:
        """
        Install the Carto CLI tool.

        Returns:
            True if the installation was successful, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Installing Carto CLI...",
                "info",
                self.logger,
            )

            # Check if npm is available
            if not command_exists("npm"):
                log_map_server(
                    f"{config.SYMBOLS['error']} npm is not installed. Please install Node.js first.",
                    "error",
                    self.logger,
                )
                return False

            # Install Carto CLI globally
            run_elevated_command(
                ["npm", "install", "-g", "@mapbox/carto"],
                self.app_settings,
                current_logger=self.logger,
            )

            # Verify installation
            if not command_exists("carto"):
                log_map_server(
                    f"{config.SYMBOLS['error']} Failed to install Carto CLI.",
                    "error",
                    self.logger,
                )
                return False

            log_map_server(
                f"{config.SYMBOLS['success']} Carto CLI installed successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error installing Carto CLI: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def _setup_osm_carto_repository(self) -> bool:
        """
        Set up the OSM Carto repository.

        Returns:
            True if the setup was successful, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Setting up OSM Carto repository...",
                "info",
                self.logger,
            )

            # Create OSM project root directory if it doesn't exist
            os.makedirs(config.OSM_PROJECT_ROOT, exist_ok=True)

            # Clone the OSM Carto repository
            osm_carto_dir = os.path.join(
                config.OSM_PROJECT_ROOT, "openstreetmap-carto"
            )
            if not os.path.exists(osm_carto_dir):
                run_command(
                    [
                        "git",
                        "clone",
                        "--depth",
                        "1",
                        "https://github.com/gravitystorm/openstreetmap-carto.git",
                        osm_carto_dir,
                    ],
                    self.app_settings,
                    current_logger=self.logger,
                )

            log_map_server(
                f"{config.SYMBOLS['success']} OSM Carto repository set up successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error setting up OSM Carto repository: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def _prepare_carto_directory_for_processing(self) -> bool:
        """
        Prepare the Carto directory for processing.

        Returns:
            True if the preparation was successful, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Preparing Carto directory for processing...",
                "info",
                self.logger,
            )

            osm_carto_dir = os.path.join(
                config.OSM_PROJECT_ROOT, "openstreetmap-carto"
            )

            # Set appropriate permissions
            run_elevated_command(
                [
                    "chown",
                    "-R",
                    f"{os.getuid()}:{os.getgid()}",
                    osm_carto_dir,
                ],
                self.app_settings,
                current_logger=self.logger,
            )

            log_map_server(
                f"{config.SYMBOLS['success']} Carto directory prepared successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error preparing Carto directory: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def _fetch_carto_external_data(self) -> bool:
        """
        Fetch external data required by Carto.

        Returns:
            True if the data was fetched successfully, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Fetching Carto external data...",
                "info",
                self.logger,
            )

            osm_carto_dir = os.path.join(
                config.OSM_PROJECT_ROOT, "openstreetmap-carto"
            )

            # Change to the OSM Carto directory
            original_dir = os.getcwd()
            os.chdir(osm_carto_dir)

            try:
                # Run the script to get external data
                run_command(
                    ["scripts/get-external-data.py", "-d", "data"],
                    self.app_settings,
                    current_logger=self.logger,
                )
            finally:
                # Change back to the original directory
                os.chdir(original_dir)

            log_map_server(
                f"{config.SYMBOLS['success']} Carto external data fetched successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error fetching Carto external data: {str(e)}",
                "error",
                self.logger,
            )
            return False
