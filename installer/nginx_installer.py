# installer/nginx_installer.py
# -*- coding: utf-8 -*-
"""
Handles initial setup checks for Nginx.
Actual package installation is expected to be done by a core prerequisite step.
"""
import logging
from typing import Optional

from common.command_utils import log_map_server, check_package_installed, elevated_command_exists
from setup.config_models import AppSettings
# from setup import config as static_config # Not needed if package name is const

module_logger = logging.getLogger(__name__)

NGINX_PACKAGE_NAME = "nginx" # Nginx package name is static

def ensure_nginx_package_installed(
    app_settings: AppSettings,
    current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Confirms that the Nginx package is present.
    Uses app_settings for logging symbols.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols

    log_map_server(
        f"{symbols.get('info','ℹ️')} Checking Nginx package ('{NGINX_PACKAGE_NAME}') installation status...",
        "info", logger_to_use, app_settings)

    # elevated_command_exists and check_package_installed now take app_settings
    if elevated_command_exists("nginx", app_settings, current_logger=logger_to_use) and \
       check_package_installed(NGINX_PACKAGE_NAME, app_settings=app_settings, current_logger=logger_to_use):
        log_map_server(
            f"{symbols.get('success','✅')} Nginx package '{NGINX_PACKAGE_NAME}' is installed and command exists.",
            "success", logger_to_use, app_settings)
    else:
        log_map_server(
            f"{symbols.get('error','❌')} Nginx package '{NGINX_PACKAGE_NAME}' or command is NOT found/installed. "
            "This should have been handled by a core prerequisite installation step.",
            "error", logger_to_use, app_settings)
        raise EnvironmentError(
            f"Nginx package '{NGINX_PACKAGE_NAME}' or command not found. "
            "Please ensure core prerequisites (which installs from static_config.MAPPING_PACKAGES) ran successfully."
        )