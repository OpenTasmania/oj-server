# opentasmania-osm-osrm-server/installer/pgagent_installer.py
# -*- coding: utf-8 -*-
import logging
from typing import Optional

from common.command_utils import log_map_server
from common.constants_loader import is_feature_enabled
from common.debian.apt_manager import AptManager
from setup import config
from setup.config_models import AppSettings

module_logger = logging.getLogger(__name__)


def install_pgagent(
    app_settings: AppSettings,
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Installs pgAgent if enabled in the configuration.

    Args:
        app_settings: The application settings object containing the necessary configuration.
        current_logger: An optional logger instance to be used for logging messages. If not
            provided, the module-level logger is used instead.
    """
    logger_to_use = current_logger if current_logger else module_logger

    # Check both the constant and the config setting
    pgagent_enabled = is_feature_enabled("pgagent_enabled", False)

    if not pgagent_enabled or not app_settings.pgagent.install:
        log_map_server(
            f"{config.SYMBOLS['info']} pgAgent installation is disabled. Skipping.",
            "info",
            logger_to_use,
        )
        return

    log_map_server(
        f"{config.SYMBOLS['info']} Installing pgAgent...",
        "info",
        logger_to_use,
    )

    try:
        # Use AptManager for package installation
        apt_manager = AptManager(logger=logger_to_use)

        # Install pgAgent
        apt_manager.install("pgagent", update_first=True)

        log_map_server(
            f"{config.SYMBOLS['success']} pgAgent installation completed successfully.",
            "success",
            logger_to_use,
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} pgAgent installation failed: {str(e)}",
            "error",
            logger_to_use,
        )
        raise
