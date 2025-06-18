# modular/installers/prerequisites_installer.py
# -*- coding: utf-8 -*-
"""
Installer for core system prerequisites required by all other installers.

This module provides the PrerequisitesInstaller class, which ensures that
essential system packages and tools are installed before any other installers
run. It serves as a foundational "Stage 0" for the installation process.
"""

import logging
from typing import Optional

from common.command_utils import (
    check_package_installed,
    log_map_server,
    run_elevated_command,
)
from common.debian.apt_manager import AptManager
from modular.base_installer import BaseInstaller
from modular.registry import InstallerRegistry
from setup import config
from setup.config_models import AppSettings


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
class PrerequisitesInstaller(BaseInstaller):
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
        try:
            log_map_server(
                f"{config.SYMBOLS['info']} Setting up core system prerequisites...",
                "info",
                self.logger,
            )

            if not self.apt_manager.update(self.app_settings):
                log_map_server(
                    f"{config.SYMBOLS['error']} Failed to update package lists.",
                    "error",
                    self.logger,
                )
                return False

            try:
                run_elevated_command(
                    ["apt-get", "-yq", "upgrade"],
                    self.app_settings,
                    current_logger=self.logger,
                )
            except Exception as e:
                log_map_server(
                    f"{config.SYMBOLS['warning']} System upgrade failed: {str(e)}. Continuing with installation.",
                    "warning",
                    self.logger,
                )

            log_map_server(
                f"{config.SYMBOLS['package']} Installing core system packages...",
                "info",
                self.logger,
            )
            if not self.apt_manager.install(
                self.core_packages, self.app_settings
            ):
                log_map_server(
                    f"{config.SYMBOLS['error']} Failed to install core system packages.",
                    "error",
                    self.logger,
                )
                return False

            try:
                run_elevated_command(
                    ["dpkg-reconfigure", "-f", "noninteractive", "tzdata"],
                    self.app_settings,
                    current_logger=self.logger,
                )
            except Exception as e:
                log_map_server(
                    f"{config.SYMBOLS['warning']} Failed to reconfigure tzdata: {str(e)}. This is not critical.",
                    "warning",
                    self.logger,
                )

            log_map_server(
                f"{config.SYMBOLS['success']} Core system prerequisites installed successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error installing core system prerequisites: {str(e)}",
                "error",
                self.logger,
                exc_info=True,
            )
            return False

    def uninstall(self) -> bool:
        """
        Uninstall is not implemented for core prerequisites.

        Returns:
            True to indicate that the operation was acknowledged.
        """
        log_map_server(
            f"{config.SYMBOLS['warning']} Uninstalling core prerequisites is not recommended and not implemented.",
            "warning",
            self.logger,
        )
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
                log_map_server(
                    f"{config.SYMBOLS['info']} Core prerequisite package '{package}' is not installed.",
                    "info",
                    self.logger,
                )
                return False

        log_map_server(
            f"{config.SYMBOLS['success']} All core prerequisite packages are installed.",
            "success",
            self.logger,
        )
        return True
