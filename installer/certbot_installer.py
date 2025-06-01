# installer/certbot_installer.py
# -*- coding: utf-8 -*-
"""
Handles installation of Certbot packages.
"""
import logging
from typing import Optional  # Added Optional

from common.command_utils import log_map_server, run_elevated_command
from setup.config_models import AppSettings  # For type hinting

# from setup import config as static_config # Not strictly needed if symbols come from app_settings

module_logger = logging.getLogger(__name__)


def install_certbot_packages(
    app_settings: AppSettings,
    current_logger: Optional[logging.Logger] = None,  # Added Optional
) -> None:  # Added type hint for return
    """Installs Certbot and its Nginx plugin via apt. Uses app_settings for symbols."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols

    log_map_server(
        f"{symbols.get('package', '📦')} Installing Certbot and Nginx plugin...",
        "info",
        logger_to_use,
        app_settings,
    )
    try:
        # Update apt cache before installing, though core_prerequisites might have done this.
        # Consider if this update is always necessary here or should be ensured by a prior global step.
        # run_elevated_command(["apt", "update"], app_settings, current_logger=logger_to_use)

        run_elevated_command(
            ["apt", "install", "-y", "certbot", "python3-certbot-nginx"],
            app_settings,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Certbot packages installed.",
            "success",
            logger_to_use,
            app_settings,
        )
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to install Certbot packages: {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        raise  # Certbot packages are usually critical if SSL is intended.
