"""
Certbot installer module.

This module provides a self-contained installer for Certbot and its plugins.
"""

import logging
from typing import List, Optional

from common.command_utils import check_package_installed, log_map_server
from common.debian.apt_manager import AptManager
from installer.config_models import AppSettings


class CertbotInstaller:
    """
    Installer for Certbot SSL certificate manager packages.

    This class handles the installation and uninstallation of Certbot and its
    plugins. It does not act as a registered component.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Certbot installer.
        """
        self.app_settings = app_settings
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.apt_manager = AptManager(logger=self.logger)

    def install(self) -> bool:
        """
        Install Certbot and its plugins.
        """
        symbols = self.app_settings.symbols
        try:
            log_map_server(
                f"{symbols.get('info', '')} Installing Certbot and plugins...",
                "info",
                self.logger,
                self.app_settings,
            )
            packages = self._get_certbot_packages()
            self.apt_manager.install(
                packages, self.app_settings, update_first=True
            )

            if not self._verify_packages_installed(packages):
                log_map_server(
                    f"{symbols.get('error', '')} Failed to install all required Certbot packages.",
                    "error",
                    self.logger,
                    self.app_settings,
                )
                return False

            log_map_server(
                f"{symbols.get('success', '')} Certbot and plugins installed successfully.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(f"Error installing Certbot: {str(e)}")
            return False

    def uninstall(self) -> bool:
        """
        Uninstall Certbot and its plugins.
        """
        symbols = self.app_settings.symbols
        try:
            log_map_server(
                f"{symbols.get('info', '')} Uninstalling Certbot and plugins...",
                "info",
                self.logger,
                self.app_settings,
            )
            packages = self._get_certbot_packages()
            self.apt_manager.purge(packages, self.app_settings)
            self.apt_manager.autoremove(
                purge=True, app_settings=self.app_settings
            )
            log_map_server(
                f"{symbols.get('success', '')} Certbot and plugins uninstalled successfully.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except Exception as e:
            self.logger.error(f"Error uninstalling Certbot: {str(e)}")
            return False

    def is_installed(self) -> bool:
        """
        Check if Certbot is installed.
        """
        packages = self._get_certbot_packages()
        return self._verify_packages_installed(packages)

    def _get_certbot_packages(self) -> List[str]:
        """
        Get the list of Certbot packages to install.
        """
        packages = ["certbot"]
        plugins = getattr(
            self.app_settings.certbot, "plugins", ["nginx", "apache"]
        )
        for plugin in plugins:
            packages.append(f"python3-certbot-{plugin}")
        return packages

    def _verify_packages_installed(self, packages: List[str]) -> bool:
        """
        Verify that all specified packages are installed.
        """
        return all(
            check_package_installed(
                pkg,
                app_settings=self.app_settings,
                current_logger=self.logger,
            )
            for pkg in packages
        )
