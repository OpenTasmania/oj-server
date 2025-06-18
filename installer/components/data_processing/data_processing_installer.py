"""
Installer for data processing dependencies.

This module provides a component for installing dependencies required for data processing.
"""

import logging
from typing import Optional

from common.command_utils import (
    check_package_installed,
    command_exists,
    log_map_server,
)
from common.debian.apt_manager import AptManager
from installer import config
from installer.base_component import BaseComponent
from installer.config_models import AppSettings
from installer.registry import ComponentRegistry


@ComponentRegistry.register(
    name="data_processing_dependencies",
    metadata={
        "dependencies": [
            "prerequisites",
            "docker",
        ],
        "estimated_time": 60,
        "required_resources": {
            "memory": 512,
            "disk": 1024,
            "cpu": 1,
        },
        "description": "Data Processing Dependencies",
    },
)
class DataProcessingInstaller(BaseComponent):
    """
    Installer for data processing dependencies.

    This installer ensures that dependencies required for data processing
    (like osmium-tool, osmctools, and jq) are installed.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the data processing dependencies installer.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)
        self.apt_manager = AptManager(logger=self.logger)

    def install(self) -> bool:
        """
        Install data processing dependencies.

        Returns:
            True if the installation was successful, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Installing data processing dependencies...",
                "info",
                self.logger,
            )

            # Install required packages
            packages = ["osmium-tool", "osmctools", "jq"]
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
                    f"{config.SYMBOLS['error']} Failed to install all required data processing dependencies.",
                    "error",
                    self.logger,
                )
                return False

            # Check for required commands
            required_commands = ["osmium", "osmconvert", "jq"]
            for cmd in required_commands:
                if not command_exists(cmd):
                    log_map_server(
                        f"{config.SYMBOLS['error']} Required command '{cmd}' not found.",
                        "error",
                        self.logger,
                    )
                    return False

            log_map_server(
                f"{config.SYMBOLS['success']} All data processing dependencies are installed.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error installing data processing dependencies: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def configure(self) -> bool:
        """
        Configure data processing dependencies.

        This is a no-op as there's no configuration needed for these dependencies.

        Returns:
            True always.
        """
        return True

    def uninstall(self) -> bool:
        """
        Uninstall data processing dependencies.

        Returns:
            True if the uninstallation was successful, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Uninstalling data processing dependencies...",
                "info",
                self.logger,
            )

            # Uninstall packages
            packages = ["osmium-tool", "osmctools"]
            self.apt_manager.remove(packages, self.app_settings)

            log_map_server(
                f"{config.SYMBOLS['success']} Data processing dependencies uninstalled successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error uninstalling data processing dependencies: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def unconfigure(self) -> bool:
        """
        Unconfigure data processing dependencies.

        This is a no-op as there's no configuration to undo.

        Returns:
            True always.
        """
        return True

    def is_installed(self) -> bool:
        """
        Check if data processing dependencies are installed.

        Returns:
            True if all dependencies are installed, False otherwise.
        """
        # Check if all packages are installed
        packages = ["osmium-tool", "osmctools", "jq"]
        for pkg in packages:
            if not check_package_installed(
                pkg,
                app_settings=self.app_settings,
                current_logger=self.logger,
            ):
                return False

        # Check if all commands are available
        required_commands = ["osmium", "osmconvert", "jq"]
        for cmd in required_commands:
            if not command_exists(cmd):
                return False

        return True

    def is_configured(self) -> bool:
        """
        Check if data processing dependencies are configured.

        This is a no-op as there's no configuration needed for these dependencies.

        Returns:
            True if the dependencies are installed.
        """
        return self.is_installed()
