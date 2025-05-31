# setup/nginx_installer.py
# -*- coding: utf-8 -*-
"""
Handles initial setup checks for Nginx.
Actual package installation is expected to be done by a core prerequisite step.
"""
import logging
from typing import Optional

from common.command_utils import log_map_server, check_package_installed, command_exists, elevated_command_exists
from setup import config  # For SYMBOLS

module_logger = logging.getLogger(__name__)

def ensure_nginx_package_installed(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Confirms that the Nginx package (expected to be installed by a core
    prerequisite step) is present.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['info']} Checking Nginx package installation status...",
        "info",
        logger_to_use
    )

    nginx_package_name = "nginx" # Common package name for Nginx

    if elevated_command_exists("nginx") and check_package_installed(nginx_package_name, current_logger=logger_to_use):
        log_map_server(
            f"{config.SYMBOLS['success']} Nginx package '{nginx_package_name}' is installed and command exists.",
            "success", # Changed from debug to success for the check itself
            logger_to_use
        )
    else:
        log_map_server(
            f"{config.SYMBOLS['error']} Nginx package '{nginx_package_name}' or command is NOT found/installed. "
            "This should have been handled by a core prerequisite installation step.",
            "error",
            logger_to_use
        )
        raise EnvironmentError(
            "Nginx package or command not found. "
            "Please ensure core prerequisites installation ran successfully."
        )

# No other specific "installation" steps for Nginx typically,
# as the package manager handles service file creation, log directories etc.