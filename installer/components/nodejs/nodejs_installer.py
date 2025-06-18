"""
Node.js installer module.

This module provides a self-contained installer for Node.js LTS.
"""

import logging
from typing import Optional, Tuple

from common.command_utils import (
    check_package_installed,
    log_map_server,
    run_command,
    run_elevated_command,
)
from common.debian.apt_manager import AptManager
from installer import config
from installer.base_component import BaseComponent
from installer.config_models import AppSettings
from installer.registry import InstallerRegistry


@InstallerRegistry.register(
    name="nodejs",
    metadata={
        "dependencies": ["prerequisites"],  # Depends on core prerequisites
        "estimated_time": 120,  # Estimated installation time in seconds
        "required_resources": {
            "memory": 512,  # Required memory in MB
            "disk": 1024,  # Required disk space in MB
            "cpu": 1,  # Required CPU cores
        },
        "description": "Node.js JavaScript runtime",
    },
)
class NodejsInstaller(BaseComponent):
    """
    Installer for Node.js JavaScript runtime.

    This installer ensures that Node.js LTS and npm are installed
    using the NodeSource Node.js Binary Distributions.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Node.js installer.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)
        self.apt_manager = AptManager(logger=self.logger)

    def install(self) -> bool:
        """
        Install Node.js LTS and npm.

        Returns:
            True if the installation was successful, False otherwise.
        """
        try:
            # Log the start of the installation
            log_map_server(
                f"{config.SYMBOLS['info']} Installing Node.js LTS using NodeSource...",
                "info",
                self.logger,
            )

            # Download and execute NodeSource setup script
            if not self._setup_nodesource_repository():
                return False

            # Install Node.js
            if not self._install_nodejs_package():
                return False

            # Verify the installation
            node_ver, npm_ver = self._get_nodejs_versions()

            log_map_server(
                f"{config.SYMBOLS['success']} Node.js installed. Version: {node_ver}, NPM Version: {npm_ver}",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error installing Node.js: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def uninstall(self) -> bool:
        """
        Uninstall Node.js and npm.

        Returns:
            True if the uninstallation was successful, False otherwise.
        """
        try:
            # Log the start of the uninstallation
            log_map_server(
                f"{config.SYMBOLS['info']} Uninstalling Node.js and npm...",
                "info",
                self.logger,
            )

            # Uninstall Node.js package
            self.apt_manager.purge("nodejs", self.app_settings)

            # Remove NodeSource repository
            self.apt_manager.remove_repository(
                "nodesource", self.app_settings
            )

            # Clean up any remaining packages
            self.apt_manager.autoremove(
                purge=True, app_settings=self.app_settings
            )

            log_map_server(
                f"{config.SYMBOLS['success']} Node.js and npm uninstalled successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error uninstalling Node.js: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def is_installed(self) -> bool:
        """
        Check if Node.js is installed.

        Returns:
            True if Node.js is installed, False otherwise.
        """
        try:
            # Check if nodejs package is installed
            if not check_package_installed(
                "nodejs",
                app_settings=self.app_settings,
                current_logger=self.logger,
            ):
                return False

            # Check if node and npm commands exist
            node_ver, npm_ver = self._get_nodejs_versions()

            return node_ver != "N/A" and npm_ver != "N/A"

        except Exception:
            return False

    def _setup_nodesource_repository(self) -> bool:
        """
        Set up the NodeSource repository.

        Returns:
            True if the setup was successful, False otherwise.
        """
        try:
            # Get the NodeSource setup script URL
            nodesource_version_setup = getattr(
                self.app_settings,
                "nodejs_version_setup_script",
                "setup_lts.x",
            )
            nodesource_setup_url = (
                f"https://deb.nodesource.com/{nodesource_version_setup}"
            )

            log_map_server(
                f"{config.SYMBOLS['info']} Downloading NodeSource script from {nodesource_setup_url}...",
                "info",
                self.logger,
            )

            # Download the setup script
            curl_res = run_command(
                ["curl", "-fsSL", nodesource_setup_url],
                self.app_settings,
                capture_output=True,
                check=True,
                current_logger=self.logger,
            )

            log_map_server(
                f"{config.SYMBOLS['info']} Executing NodeSource setup script...",
                "info",
                self.logger,
            )

            # Execute the setup script
            run_elevated_command(
                ["bash", "-"],
                self.app_settings,
                cmd_input=curl_res.stdout,
                current_logger=self.logger,
            )

            # Update apt
            self.apt_manager.update(self.app_settings)

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to set up NodeSource repository: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def _install_nodejs_package(self) -> bool:
        """
        Install the Node.js package.

        Returns:
            True if the installation was successful, False otherwise.
        """
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Installing Node.js package...",
                "info",
                self.logger,
            )

            # Install Node.js
            self.apt_manager.install(
                "nodejs", self.app_settings, update_first=False
            )

            # Verify that the package was installed
            if not check_package_installed(
                "nodejs",
                app_settings=self.app_settings,
                current_logger=self.logger,
            ):
                log_map_server(
                    f"{config.SYMBOLS['error']} Failed to install Node.js package.",
                    "error",
                    self.logger,
                )
                return False

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error installing Node.js package: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def _get_nodejs_versions(self) -> Tuple[str, str]:
        """
        Get the installed Node.js and npm versions.

        Returns:
            A tuple containing the Node.js version and npm version.
        """
        try:
            # Get Node.js version
            node_ver_res = run_command(
                ["node", "--version"],
                self.app_settings,
                capture_output=True,
                check=False,
                current_logger=self.logger,
            )
            node_ver = (
                node_ver_res.stdout.strip()
                if node_ver_res.returncode == 0
                else "N/A"
            )

            # Get npm version
            npm_ver_res = run_command(
                ["npm", "--version"],
                self.app_settings,
                capture_output=True,
                check=False,
                current_logger=self.logger,
            )
            npm_ver = (
                npm_ver_res.stdout.strip()
                if npm_ver_res.returncode == 0
                else "N/A"
            )

            return node_ver, npm_ver

        except Exception:
            return "N/A", "N/A"
