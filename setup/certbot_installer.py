# setup/certbot_installer.py
# -*- coding: utf-8 -*-
"""
Handles installation of Certbot packages.
"""
import logging
from common.command_utils import log_map_server, run_elevated_command
from setup import config # For SYMBOLS

module_logger = logging.getLogger(__name__)

def install_certbot_packages(current_logger=None):
    """Installs Certbot and its Nginx plugin via apt."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['package']} Installing Certbot and Nginx plugin...",
        "info",
        logger_to_use,
    )
    try:
        # It's good practice to update apt cache before installing new packages,
        # though core_prerequisites.py might have already done this.
        # run_elevated_command(["apt", "update"], current_logger=logger_to_use)
        run_elevated_command(
            ["apt", "install", "-y", "certbot", "python3-certbot-nginx"],
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Certbot packages installed.", "success", logger_to_use
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to install Certbot packages: {e}",
            "error",
            logger_to_use,
        )
        raise # Certbot packages are critical for this service.