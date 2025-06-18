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
from common.debian.apt_manager import AptManager
from installer import config
from installer.base_installer import BaseInstaller
from installer.config_models import AppSettings
from installer.registry import InstallerRegistry


@InstallerRegistry.register(
    name="pg_tileserv",
    metadata={
        "dependencies": ["postgres"],  # pg_tileserv depends on PostgreSQL
        "estimated_time": 120,  # Estimated installation time in seconds
        "required_resources": {
            "memory": 256,  # Required memory in MB
            "disk": 512,  # Required disk space in MB
            "cpu": 1,  # Required CPU cores
        },
        "description": "pg_tileserv PostGIS tile server",
    },
)
class PgTileservInstaller(BaseInstaller):
    """
    Installer for pg_tileserv PostGIS tile server.

    This installer ensures that pg_tileserv is installed and properly configured.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the pg_tileserv installer.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)
        self.apt_manager = AptManager(logger=self.logger)

    def install(self) -> bool:
        """
        Install pg_tileserv.

        Returns:
            True if the installation was successful, False otherwise.
        """
        try:
            # Log the start of the installation
            log_map_server(
                f"{config.SYMBOLS['info']} Installing pg_tileserv...",
                "info",
                self.logger,
            )

            # Create pg_tileserv system user
            if not self._create_pg_tileserv_system_user():
                return False

            # Download and install pg_tileserv binary
            if not self._download_and_install_pg_tileserv_binary():
                return False

            # Set up pg_tileserv binary permissions
            if not self._setup_pg_tileserv_binary_permissions():
                return False

            log_map_server(
                f"{config.SYMBOLS['success']} pg_tileserv installed successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error installing pg_tileserv: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def uninstall(self) -> bool:
        """
        Uninstall pg_tileserv.

        Returns:
            True if the uninstallation was successful, False otherwise.
        """
        try:
            # Log the start of the uninstallation
            log_map_server(
                f"{config.SYMBOLS['info']} Uninstalling pg_tileserv...",
                "info",
                self.logger,
            )

            # Remove pg_tileserv binary
            binary_location = str(
                self.app_settings.pg_tileserv.binary_install_path
            )
            if os.path.exists(binary_location):
                run_elevated_command(
                    ["rm", "-f", binary_location],
                    self.app_settings,
                    current_logger=self.logger,
                )

            # Remove pg_tileserv user
            try:
                run_elevated_command(
                    ["userdel", "-r", "pg_tileserv"],
                    self.app_settings,
                    current_logger=self.logger,
                )
            except subprocess.CalledProcessError:
                # User might not exist, which is fine
                pass

            log_map_server(
                f"{config.SYMBOLS['success']} pg_tileserv uninstalled successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error uninstalling pg_tileserv: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def is_installed(self) -> bool:
        """
        Check if pg_tileserv is installed.

        Returns:
            True if pg_tileserv is installed, False otherwise.
        """
        # Check if pg_tileserv binary exists
        binary_location = str(
            self.app_settings.pg_tileserv.binary_install_path
        )
        if not os.path.exists(binary_location):
            return False

        # Check if pg_tileserv user exists
        try:
            run_command(
                ["id", "pg_tileserv"],
                self.app_settings,
                capture_output=True,
                check=True,
                current_logger=self.logger,
            )
        except subprocess.CalledProcessError:
            return False

        return True

    def _create_pg_tileserv_system_user(self) -> bool:
        """
        Create the pg_tileserv system user.

        Returns:
            True if the user was created successfully, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Creating pg_tileserv system user...",
                "info",
                self.logger,
            )

            # Check if user already exists
            try:
                run_command(
                    ["id", "pg_tileserv"],
                    self.app_settings,
                    capture_output=True,
                    check=True,
                    current_logger=self.logger,
                )
                log_map_server(
                    f"{config.SYMBOLS['info']} User pg_tileserv already exists.",
                    "info",
                    self.logger,
                )
                return True
            except subprocess.CalledProcessError:
                # User doesn't exist, create it
                pass

            # Create system user
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

            log_map_server(
                f"{config.SYMBOLS['success']} Created pg_tileserv system user.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error creating pg_tileserv system user: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def _download_and_install_pg_tileserv_binary(self) -> bool:
        """
        Download and install the pg_tileserv binary.

        Returns:
            True if the binary was installed successfully, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Downloading and installing pg_tileserv binary...",
                "info",
                self.logger,
            )

            # Get binary URL and destination
            binary_url = self.app_settings.pg_tileserv.binary_url
            binary_location = str(
                self.app_settings.pg_tileserv.binary_install_path
            )

            # Create directory for binary if it doesn't exist
            binary_dir = os.path.dirname(binary_location)
            os.makedirs(binary_dir, exist_ok=True)

            # Download the binary
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name

                log_map_server(
                    f"{config.SYMBOLS['info']} Downloading pg_tileserv from {binary_url}...",
                    "info",
                    self.logger,
                )

                run_command(
                    ["wget", "-O", temp_path, str(binary_url)],
                    self.app_settings,
                    current_logger=self.logger,
                )

                # Move the binary to its final location
                run_elevated_command(
                    ["mv", temp_path, binary_location],
                    self.app_settings,
                    current_logger=self.logger,
                )

                # Make the binary executable
                run_elevated_command(
                    ["chmod", "+x", binary_location],
                    self.app_settings,
                    current_logger=self.logger,
                )

            # Verify the binary
            if not os.path.exists(binary_location):
                log_map_server(
                    f"{config.SYMBOLS['error']} Failed to install pg_tileserv binary.",
                    "error",
                    self.logger,
                )
                return False

            log_map_server(
                f"{config.SYMBOLS['success']} pg_tileserv binary installed at {binary_location}.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error downloading and installing pg_tileserv binary: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def _setup_pg_tileserv_binary_permissions(self) -> bool:
        """
        Set up permissions for the pg_tileserv binary.

        Returns:
            True if the permissions were set up successfully, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Setting up pg_tileserv binary permissions...",
                "info",
                self.logger,
            )

            binary_location = str(
                self.app_settings.pg_tileserv.binary_install_path
            )

            # Set ownership
            run_elevated_command(
                ["chown", "pg_tileserv:pg_tileserv", binary_location],
                self.app_settings,
                current_logger=self.logger,
            )

            # Set permissions
            run_elevated_command(
                ["chmod", "755", binary_location],
                self.app_settings,
                current_logger=self.logger,
            )

            log_map_server(
                f"{config.SYMBOLS['success']} pg_tileserv binary permissions set up successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error setting up pg_tileserv binary permissions: {str(e)}",
                "error",
                self.logger,
            )
            return False
