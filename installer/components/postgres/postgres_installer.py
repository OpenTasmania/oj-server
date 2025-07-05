"""
PostgreSQL installer module.
"""

import logging
from typing import List, Optional

from common.command_utils import check_package_installed, log_map_server
from common.debian.apt_manager import AptManager
from installer.config_models import AppSettings


class PostgresInstaller:
    """
    Installer for PostgreSQL packages.
    It does not act as a registered component.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize the PostgreSQL installer."""
        self.app_settings = app_settings
        self.logger = logger or logging.getLogger(__name__)
        self.apt_manager = AptManager(logger=self.logger)

    def _get_packages(self) -> List[str]:
        """Get the list of PostgreSQL packages to install."""
        pg_version = self.app_settings.pg.version
        return [
            f"postgresql-{pg_version}",
            f"postgresql-contrib-{pg_version}",
            f"postgresql-server-dev-{pg_version}",
            "postgis",
            f"postgresql-{pg_version}-postgis-3",
        ]

    def install(self) -> bool:
        """Install PostgreSQL packages."""
        symbols = self.app_settings.symbols
        try:
            log_map_server(
                f"{symbols.get('info', '')} Installing PostgreSQL packages...",
                "info",
                self.logger,
                self.app_settings,
            )
            packages = self._get_packages()
            self.apt_manager.install(
                packages, self.app_settings, update_first=True
            )
            if not all(
                check_package_installed(p, self.app_settings, self.logger)
                for p in packages
            ):
                raise RuntimeError(
                    "Not all PostgreSQL packages were installed successfully."
                )
            log_map_server(
                f"{symbols.get('success', '')} PostgreSQL packages installed.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Error installing PostgreSQL packages: {e}", exc_info=True
            )
            return False

    def uninstall(self) -> bool:
        """Uninstall PostgreSQL packages."""
        symbols = self.app_settings.symbols
        try:
            log_map_server(
                f"{symbols.get('info', '')} Uninstalling PostgreSQL packages...",
                "info",
                self.logger,
                self.app_settings,
            )
            self.apt_manager.purge(self._get_packages(), self.app_settings)
            self.apt_manager.autoremove(
                purge=True, app_settings=self.app_settings
            )
            log_map_server(
                f"{symbols.get('success', '')} PostgreSQL packages uninstalled.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Error uninstalling PostgreSQL packages: {e}", exc_info=True
            )
            return False

    def is_installed(self) -> bool:
        """Check if PostgreSQL packages are installed."""
        return all(
            check_package_installed(p, self.app_settings, self.logger)
            for p in self._get_packages()
        )
