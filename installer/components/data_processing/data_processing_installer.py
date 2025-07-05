"""
Data processing dependencies installer module.
"""

import logging
from typing import Optional

from common.command_utils import check_package_installed
from common.debian.apt_manager import AptManager
from installer.config_models import AppSettings


class DataProcessingInstaller:
    """
    Installer for data processing dependencies.

    This class handles installing packages required for various data processing tasks.
    It does not act as a registered component.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialise the data processing installer."""
        self.app_settings = app_settings
        self.logger = logger or logging.getLogger(__name__)
        self.apt_manager = AptManager(logger=self.logger)
        self.packages = ["gdal-bin", "osmium-tool", "npm"]

    def install(self) -> bool:
        """Install data processing packages."""
        try:
            self.logger.info("Installing data processing dependencies...")
            self.apt_manager.install(self.packages, self.app_settings)
            if not all(
                check_package_installed(p, self.app_settings, self.logger)
                for p in self.packages
            ):
                raise RuntimeError(
                    "Failed to install all data processing packages."
                )
            self.logger.info(
                "Data processing dependencies installed successfully."
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Error installing data processing dependencies: {e}",
                exc_info=True,
            )
            return False

    def uninstall(self) -> bool:
        """Uninstall data processing packages."""
        try:
            self.logger.info("Uninstalling data processing dependencies...")
            self.apt_manager.purge(self.packages, self.app_settings)
            self.apt_manager.autoremove(
                purge=True, app_settings=self.app_settings
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Error uninstalling data processing dependencies: {e}",
                exc_info=True,
            )
            return False

    def is_installed(self) -> bool:
        """Check if data processing packages are installed."""
        return all(
            check_package_installed(p, self.app_settings, self.logger)
            for p in self.packages
        )
