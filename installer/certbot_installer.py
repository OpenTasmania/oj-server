# installer/certbot_installer.py
# -*- coding: utf-8 -*-
"""
This module handles the installation of Certbot and its plugins for Nginx and Apache.
"""

import logging
from typing import List, Optional

from common.debian.apt_manager import AptManager
from setup.config_models import AppSettings

module_logger = logging.getLogger(__name__)


def install_certbot(
    app_settings: AppSettings,
    plugins: Optional[List[str]] = None,
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Installs Certbot and specified plugins using the system's package manager.

    Args:
        app_settings (AppSettings): The application settings object.
        plugins (Optional[List[str]]): A list of plugins to install (e.g., ['nginx', 'apache']).
        current_logger (Optional[logging.Logger]): A logger instance for logging messages.
    """
    logger_to_use = current_logger or module_logger
    symbols = app_settings.symbols

    logger_to_use.info(f"{symbols.get('gear', '⚙️')} Installing Certbot...")

    packages_to_install = ["certbot"]
    if plugins:
        for plugin in plugins:
            packages_to_install.append(f"python3-certbot-{plugin}")

    try:
        apt = AptManager(logger=logger_to_use)
        apt.install(packages_to_install, app_settings, update_first=True)

        logger_to_use.info(
            f"{symbols.get('success', '✅')} Certbot and plugins installed successfully."
        )

    except Exception as e:
        logger_to_use.error(
            f"{symbols.get('error', '❌')} Failed to install Certbot: {e}",
            exc_info=True,
        )
        raise
