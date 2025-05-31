# setup/gtfs_environment_setup.py
# -*- coding: utf-8 -*-
"""
Handles environment setup for GTFS processing, including logging and
environment variables.
"""
import logging
import os
from getpass import getuser
from grp import getgrgid
from pwd import getpwnam  # For checking user existence for cron
from typing import Optional

from common.command_utils import log_map_server, run_elevated_command
from setup import config

module_logger = logging.getLogger(__name__)

GTFS_LOG_FILE = "/var/log/gtfs_processor_app.log"


def setup_gtfs_logging_and_env_vars(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Sets up the log file for GTFS processing and exports necessary
    environment variables based on the main script's configuration.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Setting up logging and environment for GTFS processing...",
        "info",
        logger_to_use,
    )

    # 1. Setup Log File
    try:
        run_elevated_command(["touch", GTFS_LOG_FILE], current_logger=logger_to_use)
        # Attempt to chown to current user, so GTFS scripts (if run as user) can write.
        # If GTFS scripts are run as root (e.g. via root's cron), this might not be strictly necessary
        # but good practice if scripts are tested/run manually as non-root.
        current_user_name = getuser()
        try:
            current_group_info = getgrgid(os.getgid())
            current_group_name = current_group_info.gr_name
        except KeyError:
            current_group_name = str(os.getgid())  # Fallback to GID

        run_elevated_command(
            ["chown", f"{current_user_name}:{current_group_name}", GTFS_LOG_FILE],
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['info']} Ensured GTFS log file exists and is "
            f"writable by '{current_user_name}': {GTFS_LOG_FILE}",
            "info",
            logger_to_use,
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['warning']} Could not create/chown GTFS log "
            f"file {GTFS_LOG_FILE}: {e}. Logging from GTFS scripts might fail or go to stdout/stderr.",
            "warning",
            logger_to_use,
        )

    # 2. Set Environment Variables for the execution context of the ETL pipeline
    # These will be picked up by the gtfs_processor module when it's imported and run.
    log_map_server(f"{config.SYMBOLS['info']} Setting environment variables for GTFS processing...", "info",
                   logger_to_use)
    os.environ["GTFS_FEED_URL"] = config.GTFS_FEED_URL
    os.environ["PG_OSM_PASSWORD"] = config.PGPASSWORD
    os.environ["PG_OSM_USER"] = config.PGUSER
    os.environ["PG_OSM_HOST"] = config.PGHOST
    os.environ["PG_OSM_PORT"] = config.PGPORT
    os.environ["PG_OSM_DATABASE"] = config.PGDATABASE
    # Also export the log file path for the GTFS processor's own logging setup
    os.environ["GTFS_PROCESSOR_LOG_FILE"] = GTFS_LOG_FILE

    log_map_server(
        f"{config.SYMBOLS['success']} GTFS environment variables set for this session. "
        f"GTFS_FEED_URL: {config.GTFS_FEED_URL}, "
        f"GTFS_PROCESSOR_LOG_FILE: {os.environ.get('GTFS_PROCESSOR_LOG_FILE')}",
        "success",
        logger_to_use
    )