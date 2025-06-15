# opentasmania-osm-osrm-server/installer/pgadmin_installer.py
# -*- coding: utf-8 -*-
import logging
from typing import Optional

from common.command_utils import log_map_server, run_command
from setup import config
from setup.config_models import AppSettings

module_logger = logging.getLogger(__name__)


def install_pgadmin(
    app_settings: AppSettings,
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Installs pgAdmin if enabled in the configuration.

    Args:
        app_settings: The application settings object containing the necessary configuration.
        current_logger: An optional logger instance to be used for logging messages. If not
            provided, the module-level logger is used instead.
    """
    logger_to_use = current_logger if current_logger else module_logger

    if not app_settings.pgadmin.install:
        log_map_server(
            f"{config.SYMBOLS['info']} pgAdmin installation is disabled in configuration. Skipping.",
            "info",
            logger_to_use,
        )
        return

    log_map_server(
        f"{config.SYMBOLS['info']} Installing pgAdmin...",
        "info",
        logger_to_use,
    )

    commands = [
        "sudo apt-get install -y pgadmin4",
    ]

    try:
        for cmd in commands:
            run_command(
                cmd,
                app_settings=app_settings,
                current_logger=logger_to_use,
                shell=True,
            )

        log_map_server(
            f"{config.SYMBOLS['success']} pgAdmin installation completed successfully.",
            "success",
            logger_to_use,
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} pgAdmin installation failed: {str(e)}",
            "error",
            logger_to_use,
        )
        raise
