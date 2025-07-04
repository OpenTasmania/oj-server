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
from installer import config
from installer.config_models import AppSettings


class CartoInstaller:
    """
    Installer for Carto mapping and visualization tool.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Carto installer.
        """
        self.app_settings = app_settings
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def install(self) -> bool:
        """
        Install Carto and related components.
        """
        symbols = self.app_settings.symbols
        try:
            log_map_server(
                f"{symbols.get('info', '')} Installing Carto and related components...",
                "info",
                self.logger,
                self.app_settings,
            )

            if not self._install_carto_cli():
                return False
            if not self._setup_osm_carto_repository():
                return False
            if not self._prepare_carto_directory_for_processing():
                return False
            if not self._fetch_carto_external_data():
                return False

            log_map_server(
                f"{symbols.get('success', '')} Carto and related components installed successfully.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(f"Error installing Carto: {str(e)}")
            return False

    def uninstall(self) -> bool:
        """
        Uninstall Carto and related components.
        """
        symbols = self.app_settings.symbols
        try:
            log_map_server(
                f"{symbols.get('info', '')} Uninstalling Carto and related components...",
                "info",
                self.logger,
                self.app_settings,
            )

            # FIX: Correct call to command_exists
            if command_exists("carto"):
                run_elevated_command(
                    ["npm", "uninstall", "-g", "@mapbox/carto"],
                    self.app_settings,
                    current_logger=self.logger,
                )

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
                f"{symbols.get('success', '')} Carto and related components uninstalled successfully.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(f"Error uninstalling Carto: {str(e)}")
            return False

    def is_installed(self) -> bool:
        """
        Check if Carto is installed.
        """
        # FIX: Correct call to command_exists
        if not command_exists("carto"):
            return False

        osm_carto_dir = os.path.join(
            config.OSM_PROJECT_ROOT, "openstreetmap-carto"
        )
        if not os.path.exists(osm_carto_dir):
            return False

        return True

    def _install_carto_cli(self) -> bool:
        """
        Install the Carto CLI tool.
        """
        symbols = self.app_settings.symbols
        try:
            log_map_server(
                f"{symbols.get('info', '')} Installing Carto CLI...",
                "info",
                self.logger,
                self.app_settings,
            )
            # FIX: Correct call to command_exists
            if not command_exists("npm"):
                log_map_server(
                    f"{symbols.get('error', '')} npm is not installed. Please install Node.js first.",
                    "error",
                    self.logger,
                    self.app_settings,
                )
                return False

            run_elevated_command(
                ["npm", "install", "-g", "@mapbox/carto"],
                self.app_settings,
                current_logger=self.logger,
            )

            # FIX: Correct call to command_exists
            if not command_exists("carto"):
                log_map_server(
                    f"{symbols.get('error', '')} Failed to install Carto CLI.",
                    "error",
                    self.logger,
                    self.app_settings,
                )
                return False

            log_map_server(
                f"{symbols.get('success', '')} Carto CLI installed successfully.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(f"Error installing Carto CLI: {str(e)}")
            return False

    def _setup_osm_carto_repository(self) -> bool:
        """
        Set up the OSM Carto repository.
        """
        symbols = self.app_settings.symbols
        try:
            log_map_server(
                f"{symbols.get('info', '')} Setting up OSM Carto repository...",
                "info",
                self.logger,
                self.app_settings,
            )
            os.makedirs(config.OSM_PROJECT_ROOT, exist_ok=True)
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
                f"{symbols.get('success', '')} OSM Carto repository set up successfully.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Error setting up OSM Carto repository: {str(e)}"
            )
            return False

    def _prepare_carto_directory_for_processing(self) -> bool:
        """
        Prepare the Carto directory for processing.
        """
        symbols = self.app_settings.symbols
        try:
            log_map_server(
                f"{symbols.get('info', '')} Preparing Carto directory for processing...",
                "info",
                self.logger,
                self.app_settings,
            )
            osm_carto_dir = os.path.join(
                config.OSM_PROJECT_ROOT, "openstreetmap-carto"
            )
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
                f"{symbols.get('success', '')} Carto directory prepared successfully.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(f"Error preparing Carto directory: {str(e)}")
            return False

    def _fetch_carto_external_data(self) -> bool:
        """
        Fetch external data required by Carto.
        """
        symbols = self.app_settings.symbols
        try:
            log_map_server(
                f"{symbols.get('info', '')} Fetching Carto external data...",
                "info",
                self.logger,
                self.app_settings,
            )
            osm_carto_dir = os.path.join(
                config.OSM_PROJECT_ROOT, "openstreetmap-carto"
            )
            original_dir = os.getcwd()
            os.chdir(osm_carto_dir)
            try:
                run_command(
                    ["scripts/get-external-data.py", "-d", "data"],
                    self.app_settings,
                    current_logger=self.logger,
                )
            finally:
                os.chdir(original_dir)

            log_map_server(
                f"{symbols.get('success', '')} Carto external data fetched successfully.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(f"Error fetching Carto external data: {str(e)}")
            return False
