# installer/certbot_installer.py
# -*- coding: utf-8 -*-
"""
Handles installation of Certbot packages.
"""

import logging
from typing import Optional  # Added Optional

from common.command_utils import log_map_server, run_elevated_command
from setup.config_models import AppSettings  # For type hinting

module_logger = logging.getLogger(__name__)


def install_certbot_packages(
    app_settings: AppSettings,
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Installs Certbot and its Nginx plugin through apt package manager.

    This function attempts to install Certbot and its Nginx plugin using elevated permissions. It uses a
    logger to output structured status messages. Should an error occur during the installation, it logs
    the error and raises the encountered exception to propagate the issue further up the call stack.
    Considerations include whether or not the apt cache update should always be performed here.

    Args:
        app_settings (AppSettings): Configuration settings that include operational parameters, such as
            symbols and additional environment variables.
        current_logger (Optional[logging.Logger]): Logger instance for capturing logs. If not provided,
            the default module logger is used.

    Raises:
        Exception: Propagates any exception that occurs during the installation process.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols

    log_map_server(
        f"{symbols.get('package', '📦')} Installing Certbot and Nginx plugin...",
        "info",
        logger_to_use,
        app_settings,
    )
    try:
        # TODO: Consider
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
        raise
