# installer/ufw_installer.py
# -*- coding: utf-8 -*-
"""
Handles setup checks for UFW (Uncomplicated Firewall).
The actual UFW package installation is expected to be done by a
core prerequisite step (core_prerequisites.py).
"""
import logging
from typing import Optional

from common.command_utils import log_map_server, check_package_installed
from setup.config_models import AppSettings # For type hinting

# setup.config is aliased as static_config for truly static values like package names
# from setup import config as static_config # Not strictly needed if UFW_PACKAGE_NAME is const here

module_logger = logging.getLogger(__name__)

UFW_PACKAGE_NAME = "ufw" # UFW package name is static

def ensure_ufw_package_installed(
    app_settings: AppSettings,
    current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Confirms UFW package is installed.
    Uses app_settings for logging symbols.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols # Use symbols from AppSettings

    log_map_server(
        f"{symbols.get('info','')} Checking UFW package ('{UFW_PACKAGE_NAME}') installation status...",
        "info",
        logger_to_use
    )
    if check_package_installed(UFW_PACKAGE_NAME, current_logger=logger_to_use, app_settings=app_settings): # Pass app_settings
        log_map_server(
            f"{symbols.get('success','')} UFW package '{UFW_PACKAGE_NAME}' is installed.",
            "success", # Changed from 'debug' for clarity on successful check
            logger_to_use
        )
    else:
        # This should ideally not happen if core_prerequisites ran successfully,
        # as 'ufw' is in CORE_PREREQ_PACKAGES.
        log_map_server(
            f"{symbols.get('error','')} UFW package '{UFW_PACKAGE_NAME}' is NOT installed. "
            "This should have been handled by a core prerequisite installation step.",
            "error",
            logger_to_use
        )
        raise EnvironmentError(
            f"UFW package '{UFW_PACKAGE_NAME}' not found, but is a core prerequisite."
        )