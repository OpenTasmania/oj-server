# installer/ufw_installer.py
# -*- coding: utf-8 -*-
"""
Handles setup checks for UFW (Uncomplicated Firewall).
The actual UFW package installation is expected to be done by a
core prerequisite step (core_prerequisites.py).
"""

import logging
from typing import Optional

from common.command_utils import check_package_installed, log_map_server
from setup.config_models import AppSettings

module_logger = logging.getLogger(__name__)

UFW_PACKAGE_NAME = "ufw"


def ensure_ufw_package_installed(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Ensures that the UFW package is installed on the system. Utilizes the provided application
    settings and an optional logger to verify the package's presence. Logs the findings at
    different stages of the operation and raises an error if the package is missing, as it is
    considered a core prerequisite.

    Parameters:
    app_settings : AppSettings
        Application settings instance required for retrieving configuration details such
        as symbols and logging configurations.
    current_logger : Optional[logging.Logger]
        Logger instance to use for logging output. If None, defaults to the module's logger.

    Raises:
    EnvironmentError
        If the UFW package is not installed on the system.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols

    log_map_server(
        f"{symbols.get('info', 'ℹ️')} Checking UFW package ('{UFW_PACKAGE_NAME}') installation status...",
        "info",
        logger_to_use,
        app_settings,
    )
    if check_package_installed(
        UFW_PACKAGE_NAME,
        app_settings=app_settings,
        current_logger=logger_to_use,
    ):
        log_map_server(
            f"{symbols.get('success', '✅')} UFW package '{UFW_PACKAGE_NAME}' is installed.",
            "success",
            logger_to_use,
            app_settings,
        )
    else:
        log_map_server(
            f"{symbols.get('error', '❌')} UFW package '{UFW_PACKAGE_NAME}' is NOT installed. "
            "This should have been handled by a core prerequisite installation step.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise EnvironmentError(
            f"UFW package '{UFW_PACKAGE_NAME}' not found, but is a core prerequisite."
        )
