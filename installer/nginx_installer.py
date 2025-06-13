# installer/nginx_installer.py
# -*- coding: utf-8 -*-
"""
Handles initial setup checks for Nginx.
Actual package installation is expected to be done by a core prerequisite step.
"""

import logging
from typing import Optional

from common.command_utils import (
    check_package_installed,
    elevated_command_exists,
    log_map_server,
)
from setup.config_models import AppSettings

module_logger = logging.getLogger(__name__)

NGINX_PACKAGE_NAME = "nginx"


def ensure_nginx_package_installed(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Checks and ensures the Nginx package is installed and the associated command exists.

    This function verifies the installation status of the Nginx package by checking
    if the relevant command exists. It logs the status of the package installation and
    will raise an EnvironmentError if the package is not found or the command does not exist.
    Logging is performed using the provided logger or a default module-level logger.

    Arguments:
        app_settings (AppSettings): Application-specific settings needed for checking
            the package installation, including symbol definitions and configuration paths.
        current_logger (Optional[logging.Logger]): A logger instance for recording the
            operation's progress and status. If None, a default module-level logger is used.

    Raises:
        EnvironmentError: Raised if the Nginx package or command is not found/installed. This
            indicates a failure in the core prerequisite installation process.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols

    log_map_server(
        f"{symbols.get('info', 'ℹ️')} Checking Nginx package ('{NGINX_PACKAGE_NAME}') installation status...",
        "info",
        logger_to_use,
        app_settings,
    )

    if elevated_command_exists(
        "nginx", app_settings, current_logger=logger_to_use
    ) and check_package_installed(
        NGINX_PACKAGE_NAME,
        app_settings=app_settings,
        current_logger=logger_to_use,
    ):
        log_map_server(
            f"{symbols.get('success', '✅')} Nginx package '{NGINX_PACKAGE_NAME}' is installed and command exists.",
            "success",
            logger_to_use,
            app_settings,
        )
    else:
        log_map_server(
            f"{symbols.get('error', '❌')} Nginx package '{NGINX_PACKAGE_NAME}' or command is NOT found/installed. "
            "This should have been handled by a core prerequisite installation step.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise EnvironmentError(
            f"Nginx package '{NGINX_PACKAGE_NAME}' or command not found. "
            "Please ensure core prerequisites (which installs from static_config.MAPPING_PACKAGES) ran successfully."
        )
