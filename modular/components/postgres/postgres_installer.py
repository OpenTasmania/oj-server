"""
PostgreSQL installer module.

This module provides a self-contained installer for PostgreSQL.
"""

import logging
from typing import List, Optional

from common.command_utils import check_package_installed, log_map_server
from common.debian.apt_manager import AptManager
from modular.base_installer import BaseInstaller
from modular.registry import InstallerRegistry
from setup import config
from setup.config_models import AppSettings


@InstallerRegistry.register(
    name="postgres",
    metadata={
        "dependencies": ["prerequisites"],  # Depends on core prerequisites
        "estimated_time": 120,  # Estimated installation time in seconds
        "required_resources": {
            "memory": 512,  # Required memory in MB
            "disk": 1024,  # Required disk space in MB
            "cpu": 1,  # Required CPU cores
        },
        "description": "PostgreSQL database server with PostGIS extensions",
    },
)
class PostgresInstaller(BaseInstaller):
    """
    Installer for PostgreSQL database server with PostGIS extensions.

    This installer ensures that PostgreSQL and related packages are installed
    and properly configured.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the PostgreSQL installer.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)
        self.apt_manager = AptManager(logger=self.logger)

    def install(self) -> bool:
        """
        Install PostgreSQL and related packages.

        Returns:
            True if the installation was successful, False otherwise.
        """
        try:
            # Log the start of the installation
            log_map_server(
                f"{config.SYMBOLS['info']} Installing PostgreSQL and related packages...",
                "info",
                self.logger,
            )

            # Get the list of packages to install
            packages = self._get_postgres_packages()

            if not packages:
                log_map_server(
                    f"{config.SYMBOLS['warning']} No PostgreSQL packages specified in configuration.",
                    "warning",
                    self.logger,
                )
                return False

            # Install the packages
            self.apt_manager.install(packages, self.app_settings)

            # Verify that all packages were installed
            if not self._verify_packages_installed(packages):
                log_map_server(
                    f"{config.SYMBOLS['error']} Failed to install all required PostgreSQL packages.",
                    "error",
                    self.logger,
                )
                return False

            log_map_server(
                f"{config.SYMBOLS['success']} PostgreSQL and related packages installed successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error installing PostgreSQL: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def uninstall(self) -> bool:
        """
        Uninstall PostgreSQL and related packages.

        Returns:
            True if the uninstallation was successful, False otherwise.
        """
        try:
            # Log the start of the uninstallation
            log_map_server(
                f"{config.SYMBOLS['info']} Uninstalling PostgreSQL and related packages...",
                "info",
                self.logger,
            )

            # Get the list of packages to uninstall
            packages = self._get_postgres_packages()

            if not packages:
                log_map_server(
                    f"{config.SYMBOLS['warning']} No PostgreSQL packages specified in configuration.",
                    "warning",
                    self.logger,
                )
                return False

            # Uninstall the packages
            self.apt_manager.purge(packages, self.app_settings)

            # Clean up any remaining packages
            self.apt_manager.autoremove(
                purge=True, app_settings=self.app_settings
            )

            log_map_server(
                f"{config.SYMBOLS['success']} PostgreSQL and related packages uninstalled successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error uninstalling PostgreSQL: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def is_installed(self) -> bool:
        """
        Check if PostgreSQL is installed.

        Returns:
            True if PostgreSQL is installed, False otherwise.
        """
        packages = self._get_postgres_packages()

        if not packages:
            log_map_server(
                f"{config.SYMBOLS['warning']} No PostgreSQL packages specified in configuration.",
                "warning",
                self.logger,
            )
            return False

        return self._verify_packages_installed(packages)

    def _get_postgres_packages(self) -> List[str]:
        """
        Get the list of PostgreSQL packages to install.

        Returns:
            A list of package names.
        """
        return config.POSTGRES_PACKAGES

    def _verify_packages_installed(self, packages: List[str]) -> bool:
        """
        Verify that all specified packages are installed.

        Args:
            packages: A list of package names to verify.

        Returns:
            True if all packages are installed, False otherwise.
        """
        all_installed = True

        for pkg in packages:
            if check_package_installed(
                pkg,
                app_settings=self.app_settings,
                current_logger=self.logger,
            ):
                log_map_server(
                    f"{config.SYMBOLS['success']} Package '{pkg}' is installed.",
                    "debug",
                    self.logger,
                )
            else:
                log_map_server(
                    f"{config.SYMBOLS['error']} Package '{pkg}' is NOT installed.",
                    "error",
                    self.logger,
                )
                all_installed = False

        return all_installed
