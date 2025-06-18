"""
Renderd installer module.

This module provides a self-contained installer for Renderd, a map tile rendering daemon.
"""

import logging
import os
from typing import Optional

from common.command_utils import (
    check_package_installed,
    log_map_server,
    run_elevated_command,
)
from common.debian.apt_manager import AptManager
from installer import config
from installer.base_component import BaseComponent
from installer.config_models import AppSettings
from installer.registry import InstallerRegistry


@InstallerRegistry.register(
    name="renderd",
    metadata={
        "dependencies": ["apache"],  # Renderd depends on Apache
        "estimated_time": 120,  # Estimated installation time in seconds
        "required_resources": {
            "memory": 512,  # Required memory in MB
            "disk": 1024,  # Required disk space in MB
            "cpu": 2,  # Required CPU cores
        },
        "description": "Renderd map tile rendering daemon",
    },
)
class RenderdInstaller(BaseComponent):
    """
    Installer for Renderd map tile rendering daemon.

    This installer ensures that Renderd and its dependencies are installed
    and properly configured.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Renderd installer.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)
        self.apt_manager = AptManager(logger=self.logger)

    def install(self) -> bool:
        """
        Install Renderd and its dependencies.

        Returns:
            True if the installation was successful, False otherwise.
        """
        try:
            # Log the start of the installation
            log_map_server(
                f"{config.SYMBOLS['info']} Installing Renderd and its dependencies...",
                "info",
                self.logger,
            )

            # Ensure Renderd packages are installed
            if not self._ensure_renderd_packages_installed():
                return False

            # Create Renderd directories
            if not self._create_renderd_directories():
                return False

            # Create Renderd systemd service file
            if not self._create_renderd_systemd_service_file():
                return False

            log_map_server(
                f"{config.SYMBOLS['success']} Renderd and its dependencies installed successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error installing Renderd: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def uninstall(self) -> bool:
        """
        Uninstall Renderd and its dependencies.

        Returns:
            True if the uninstallation was successful, False otherwise.
        """
        try:
            # Log the start of the uninstallation
            log_map_server(
                f"{config.SYMBOLS['info']} Uninstalling Renderd...",
                "info",
                self.logger,
            )

            # Stop and disable Renderd service
            run_elevated_command(
                ["systemctl", "stop", "renderd"],
                self.app_settings,
                current_logger=self.logger,
                check=False,  # Don't fail if service doesn't exist
            )

            run_elevated_command(
                ["systemctl", "disable", "renderd"],
                self.app_settings,
                current_logger=self.logger,
                check=False,  # Don't fail if service doesn't exist
            )

            # Remove Renderd service file
            service_file = "/etc/systemd/system/renderd.service"
            if os.path.exists(service_file):
                run_elevated_command(
                    ["rm", "-f", service_file],
                    self.app_settings,
                    current_logger=self.logger,
                )

            # Reload systemd
            run_elevated_command(
                ["systemctl", "daemon-reload"],
                self.app_settings,
                current_logger=self.logger,
            )

            # Uninstall Renderd packages
            packages = [
                "renderd",
                "libmapnik3.1",
                "mapnik-utils",
                "python3-mapnik",
            ]
            self.apt_manager.purge(packages, self.app_settings)

            # Clean up any remaining packages
            self.apt_manager.autoremove(
                purge=True, app_settings=self.app_settings
            )

            # Remove Renderd directories
            renderd_dirs = [
                "/var/lib/mod_tile",
                "/var/run/renderd",
                "/var/cache/renderd",
            ]
            for directory in renderd_dirs:
                if os.path.exists(directory):
                    run_elevated_command(
                        ["rm", "-rf", directory],
                        self.app_settings,
                        current_logger=self.logger,
                    )

            log_map_server(
                f"{config.SYMBOLS['success']} Renderd uninstalled successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error uninstalling Renderd: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def is_installed(self) -> bool:
        """
        Check if Renderd is installed.

        Returns:
            True if Renderd is installed, False otherwise.
        """
        # Check if Renderd packages are installed
        packages = [
            "renderd",
            "libmapnik3.1",
            "mapnik-utils",
            "python3-mapnik",
        ]
        for pkg in packages:
            if not check_package_installed(
                pkg,
                app_settings=self.app_settings,
                current_logger=self.logger,
            ):
                return False

        # Check if Renderd service file exists
        service_file = "/etc/systemd/system/renderd.service"
        if not os.path.exists(service_file):
            return False

        # Check if Renderd directories exist
        renderd_dirs = [
            "/var/lib/mod_tile",
            "/var/run/renderd",
        ]
        for directory in renderd_dirs:
            if not os.path.exists(directory):
                return False

        return True

    def _ensure_renderd_packages_installed(self) -> bool:
        """
        Ensure that Renderd packages are installed.

        Returns:
            True if the packages were installed successfully, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Ensuring Renderd packages are installed...",
                "info",
                self.logger,
            )

            # Install required packages
            packages = [
                "renderd",
                "libmapnik3.1",
                "mapnik-utils",
                "python3-mapnik",
            ]
            self.apt_manager.install(packages, self.app_settings)

            # Verify that all packages were installed
            all_installed = True
            for pkg in packages:
                if not check_package_installed(
                    pkg,
                    app_settings=self.app_settings,
                    current_logger=self.logger,
                ):
                    log_map_server(
                        f"{config.SYMBOLS['error']} Package '{pkg}' is NOT installed.",
                        "error",
                        self.logger,
                    )
                    all_installed = False

            if not all_installed:
                log_map_server(
                    f"{config.SYMBOLS['error']} Failed to install all required Renderd packages.",
                    "error",
                    self.logger,
                )
                return False

            log_map_server(
                f"{config.SYMBOLS['success']} All Renderd packages are installed.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error ensuring Renderd packages: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def _create_renderd_directories(self) -> bool:
        """
        Create Renderd directories.

        Returns:
            True if the directories were created successfully, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Creating Renderd directories...",
                "info",
                self.logger,
            )

            # Create required directories
            directories = {
                "/var/lib/mod_tile": {
                    "owner": "www-data",
                    "group": "www-data",
                    "mode": "755",
                },
                "/var/run/renderd": {
                    "owner": "www-data",
                    "group": "www-data",
                    "mode": "755",
                },
                "/var/cache/renderd": {
                    "owner": "www-data",
                    "group": "www-data",
                    "mode": "755",
                },
            }

            for directory, permissions in directories.items():
                # Create directory if it doesn't exist
                if not os.path.exists(directory):
                    run_elevated_command(
                        ["mkdir", "-p", directory],
                        self.app_settings,
                        current_logger=self.logger,
                    )

                # Set ownership and permissions
                run_elevated_command(
                    [
                        "chown",
                        f"{permissions['owner']}:{permissions['group']}",
                        directory,
                    ],
                    self.app_settings,
                    current_logger=self.logger,
                )

                run_elevated_command(
                    ["chmod", permissions["mode"], directory],
                    self.app_settings,
                    current_logger=self.logger,
                )

                log_map_server(
                    f"{config.SYMBOLS['success']} Created directory {directory} with correct permissions.",
                    "debug",
                    self.logger,
                )

            log_map_server(
                f"{config.SYMBOLS['success']} Renderd directories created successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error creating Renderd directories: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def _create_renderd_systemd_service_file(self) -> bool:
        """
        Create Renderd systemd service file.

        Returns:
            True if the service file was created successfully, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Creating Renderd systemd service file...",
                "info",
                self.logger,
            )

            # Define the service file content
            service_content = """[Unit]
Description=Renderd - OSM tile rendering daemon
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=www-data
Group=www-data
ExecStart=/usr/bin/renderd -f -c /etc/renderd.conf
Restart=on-failure
RestartSec=5s

# Security hardening
ProtectSystem=full
ProtectHome=true
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
"""

            # Write the service file
            service_file = "/etc/systemd/system/renderd.service"
            with open("/tmp/renderd.service", "w") as f:
                f.write(service_content)

            run_elevated_command(
                ["mv", "/tmp/renderd.service", service_file],
                self.app_settings,
                current_logger=self.logger,
            )

            # Set permissions
            run_elevated_command(
                ["chmod", "644", service_file],
                self.app_settings,
                current_logger=self.logger,
            )

            # Reload systemd
            run_elevated_command(
                ["systemctl", "daemon-reload"],
                self.app_settings,
                current_logger=self.logger,
            )

            log_map_server(
                f"{config.SYMBOLS['success']} Renderd systemd service file created successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error creating Renderd systemd service file: {str(e)}",
                "error",
                self.logger,
            )
            return False
