# installers/prerequisites_installer.py
# -*- coding: utf-8 -*-
"""
Installer for core system prerequisites required by all other installers.

This module provides the PrerequisitesInstaller class, which ensures that
essential system packages and tools are installed before any other installers
run. It serves as a foundational "Stage 0" for the installation process.
"""

import logging
from typing import Optional

from common.command_utils import check_package_installed
from common.debian.apt_manager import AptManager
from installer.base_component import BaseComponent
from installer.config_models import AppSettings
from installer.registry import InstallerRegistry


@InstallerRegistry.register(
    name="prerequisites",
    metadata={
        "dependencies": [],
        "estimated_time": 180,
        "required_resources": {
            "memory": 256,
            "disk": 512,
            "cpu": 1,
        },
        "description": "Installs core system packages and prerequisites required by other installers.",
    },
)
class PrerequisitesInstaller(BaseComponent):
    """
    Installer for core system prerequisites.

    This installer ensures that essential system packages and tools are
    installed before any other installers run. It serves as a foundational
    "Stage 0" for the installation process.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Prerequisites installer.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)
        self.apt_manager = AptManager(logger=self.logger)

        self.core_packages = [
            "git",
            "unzip",
            "vim",
            "build-essential",
            "gir1.2-packagekitglib-1.0",
            "gir1.2-glib-2.0",
            "packagekit",
            "python-apt-common",
            "dirmngr",
            "gnupg",
            "apt-transport-https",
            "lsb-release",
            "ca-certificates",
            "qemu-guest-agent",
            "ufw",
            "curl",
            "wget",
            "bash",
            "btop",
            "screen",
            "python3",
            "python3-pip",
            "python3-venv",
            "python3-dev",
            "python3-pydantic",
            "python3-pydantic-settings",
            "util-linux",
            "python3-apt",
            "unattended-upgrades",
            "tzdata",
        ]

    def install(self) -> bool:
        """
        Install core system prerequisites.

        Returns:
            True if the installation was successful, False otherwise.
        """
        from common.command_utils import run_elevated_command

        try:
            self.logger.info("Setting up core system prerequisites...")

            if not self.apt_manager.update(self.app_settings):
                self.logger.error("Failed to update package lists.")
                return False

            try:
                run_elevated_command(
                    ["apt-get", "-yq", "upgrade"],
                    self.app_settings,
                    current_logger=self.logger,
                )
            except Exception as e:
                self.logger.warning(
                    f"System upgrade failed: {str(e)}. Continuing with installation."
                )

            self.logger.info("Installing core system packages...")
            if not self.apt_manager.install(
                self.core_packages, self.app_settings
            ):
                self.logger.error("Failed to install core system packages.")
                return False

            try:
                run_elevated_command(
                    ["dpkg-reconfigure", "-f", "noninteractive", "tzdata"],
                    self.app_settings,
                    current_logger=self.logger,
                )
            except Exception as e:
                self.logger.warning(
                    f"Failed to reconfigure tzdata: {str(e)}. This is not critical."
                )

            self.logger.info(
                "Core system prerequisites installed successfully."
            )

            return True

        except Exception as e:
            self.logger.error(
                f"Error installing core system prerequisites: {str(e)}",
                exc_info=True,
            )
            return False

    def configure(self) -> bool:
        """
        Configure is not needed for prerequisites.

        Returns:
            True to indicate that the operation was acknowledged.
        """
        self.logger.info("Configuration for prerequisites is not required.")
        return True

    def uninstall(self) -> bool:
        """
        Uninstall is not implemented for core prerequisites.

        Returns:
            True to indicate that the operation was acknowledged.
        """
        self.logger.warning(
            "Uninstalling core prerequisites is not recommended and not implemented."
        )
        return True

    def unconfigure(self) -> bool:
        """
        Unconfigure is not needed for prerequisites.

        Returns:
            True to indicate that the operation was acknowledged.
        """
        self.logger.info("Unconfiguration for prerequisites is not required.")
        return True

    def is_installed(self) -> bool:
        """
        Check if core prerequisites are installed.

        Returns:
            True if all core packages are installed, False otherwise.
        """
        for package in self.core_packages:
            if not check_package_installed(
                package, self.app_settings, self.logger
            ):
                self.logger.info(
                    f"Core prerequisite package '{package}' is not installed."
                )
                return False

        self.logger.info("All core prerequisite packages are installed.")
        return True

    def is_configured(self) -> bool:
        """
        Check if prerequisites are configured.

        Since there is no configuration step, this is the same as being installed.

        Returns:
            True if the component is considered configured, False otherwise.
        """
        return self.is_installed()
