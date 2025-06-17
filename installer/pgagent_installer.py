# installer/pgagent_installer.py
# -*- coding: utf-8 -*-
"""
This module handles the installation of pgAgent, a job scheduler for PostgreSQL.
"""

import logging
from typing import Optional

from common.debian.apt_manager import AptManager
from setup.config_models import AppSettings

module_logger = logging.getLogger(__name__)


def install_pgagent(
    app_settings: AppSettings,
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Installs the pgAgent package using the system's package manager.

    Args:
        app_settings (AppSettings): The application settings object.
        current_logger (Optional[logging.Logger]): A logger instance for logging messages.
    """
    logger_to_use = current_logger or module_logger
    symbols = app_settings.symbols
    package_name = "pgagent"

    logger_to_use.info(
        f"{symbols.get('gear', '⚙️')} Installing {package_name}..."
    )

    try:
        apt = AptManager(logger=logger_to_use)
        apt.install(package_name, app_settings, update_first=True)

        logger_to_use.info(
            f"{symbols.get('success', '✅')} {package_name} installed successfully."
        )

    except Exception as e:
        logger_to_use.error(
            f"{symbols.get('error', '❌')} Failed to install {package_name}: {e}",
            exc_info=True,
        )
        raise
