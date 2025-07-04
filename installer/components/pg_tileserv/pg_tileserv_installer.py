"""
pg_tileserv installer module.

This module provides a self-contained installer for pg_tileserv, a PostGIS tile server.
"""

import logging
import os
import subprocess
import tempfile
from typing import Optional

from common.command_utils import (
    log_map_server,
    run_command,
    run_elevated_command,
)
from installer.config_models import AppSettings


class PgTileservInstaller:
    """
    Installer for pg_tileserv PostGIS tile server.

    This class handles downloading the binary and creating the system user.
    It does not act as a registered component.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the pg_tileserv installer.
        """
        self.app_settings = app_settings
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def install(self) -> bool:
        """
        Install pg_tileserv.
        """
        symbols = self.app_settings.symbols
        try:
            log_map_server(
                f"{symbols.get('info', '')} Installing pg_tileserv...",
                "info",
                self.logger,
                self.app_settings,
            )
            if not self._create_pg_tileserv_system_user():
                return False
            if not self._download_and_install_pg_tileserv_binary():
                return False

            log_map_server(
                f"{symbols.get('success', '')} pg_tileserv installed successfully.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(f"Error installing pg_tileserv: {str(e)}")
            return False

    def uninstall(self) -> bool:
        """
        Uninstall pg_tileserv.
        """
        symbols = self.app_settings.symbols
        try:
            log_map_server(
                f"{symbols.get('info', '')} Uninstalling pg_tileserv...",
                "info",
                self.logger,
                self.app_settings,
            )
            binary_location = str(
                self.app_settings.pg_tileserv.binary_install_path
            )
            if os.path.exists(binary_location):
                run_elevated_command(
                    ["rm", "-f", binary_location],
                    self.app_settings,
                    current_logger=self.logger,
                )

            try:
                run_elevated_command(
                    ["userdel", "-r", "pg_tileserv"],
                    self.app_settings,
                    check=False,
                    current_logger=self.logger,
                )
            except subprocess.CalledProcessError:
                self.logger.info(
                    "User 'pg_tileserv' did not exist, skipping deletion."
                )

            log_map_server(
                f"{symbols.get('success', '')} pg_tileserv uninstalled successfully.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(f"Error uninstalling pg_tileserv: {str(e)}")
            return False

    def is_installed(self) -> bool:
        """
        Check if pg_tileserv is installed.
        """
        binary_location = str(
            self.app_settings.pg_tileserv.binary_install_path
        )
        if not os.path.exists(binary_location):
            return False

        try:
            run_command(
                ["id", "pg_tileserv"],
                self.app_settings,
                check=True,
                capture_output=True,
                current_logger=self.logger,
            )
        except subprocess.CalledProcessError:
            return False

        return True

    def _create_pg_tileserv_system_user(self) -> bool:
        """
        Create the pg_tileserv system user if it doesn't exist.
        """
        try:
            run_command(
                ["id", "pg_tileserv"],
                self.app_settings,
                check=True,
                capture_output=True,
                current_logger=self.logger,
            )
        except subprocess.CalledProcessError:
            run_elevated_command(
                [
                    "useradd",
                    "--system",
                    "--no-create-home",
                    "--shell",
                    "/usr/sbin/nologin",
                    "pg_tileserv",
                ],
                self.app_settings,
                current_logger=self.logger,
            )
        return True

    def _download_and_install_pg_tileserv_binary(self) -> bool:
        """
        Download and install the pg_tileserv binary.
        """
        symbols = self.app_settings.symbols
        try:
            binary_url = self.app_settings.pg_tileserv.binary_url
            binary_location = str(
                self.app_settings.pg_tileserv.binary_install_path
            )
            binary_dir = os.path.dirname(binary_location)
            os.makedirs(binary_dir, exist_ok=True)

            with tempfile.NamedTemporaryFile(delete=True) as temp_file:
                temp_path = temp_file.name
                log_map_server(
                    f"{symbols.get('info', '')} Downloading pg_tileserv from {binary_url}...",
                    "info",
                    self.logger,
                    self.app_settings,
                )
                run_command(
                    ["wget", "-O", temp_path, str(binary_url)],
                    self.app_settings,
                    current_logger=self.logger,
                )
                run_elevated_command(
                    ["mv", temp_path, binary_location],
                    self.app_settings,
                    current_logger=self.logger,
                )

            run_elevated_command(
                ["chmod", "755", binary_location],
                self.app_settings,
                current_logger=self.logger,
            )
            run_elevated_command(
                ["chown", "pg_tileserv:pg_tileserv", binary_location],
                self.app_settings,
                current_logger=self.logger,
            )

            if not os.path.exists(binary_location):
                raise FileNotFoundError(
                    "Failed to install pg_tileserv binary."
                )

            return True
        except Exception as e:
            self.logger.error(
                f"Error downloading pg_tileserv binary: {str(e)}"
            )
            return False
