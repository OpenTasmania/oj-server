# processors/gtfs/environment.py
# -*- coding: utf-8 -*-
"""
Handles environment setup for GTFS processing, including logging and
setting OS environment variables required by the pipeline.
"""

import logging
import os
from getpass import getuser
from grp import getgrgid
from typing import Any, Dict, Optional

from common.command_utils import log_map_server, run_elevated_command
from common.core_utils import setup_logging as common_setup_logging
from installer.config_models import AppSettings  # Import AppSettings

module_logger = logging.getLogger(__name__)

DEFAULT_GTFS_PROCESSOR_LOG_FILE = "/var/log/gtfs_processor_app.log"


def setup_gtfs_environment(
    app_settings: AppSettings,
    current_logger_for_setup: Optional[logging.Logger] = None,
    **kwargs: Dict[str, Any],
) -> None:
    """
    Sets up the GTFS environment by configuring logging, ensuring the log file's existence and
    permissions, and setting necessary OS environment variables for the GTFS processing pipeline.

    The function processes application settings, prepares logging for the GTFS pipeline, and ensures
    environment variables required for GTFS tasks are correctly set. Additionally, the function verifies
    that the specified log file exists, is writable, and is properly owned by the current user and group.

    Parameters:
        app_settings (AppSettings): The application settings containing configuration for GTFS as well
            as PostgreSQL connection details.
        current_logger_for_setup (Optional[logging.Logger]): The logger to use for logging messages
            within this setup function. If None, the module's default logger will be used.
        **kwargs (Dict[str, Any]): Accepts additional keyword arguments that are not used in this function.
            This is necessary because the orchestrator passes a standard context object.


    Raises:
        Any exceptions related to file creation, permissions, or environment variable setting will not
        be explicitly raised but are instead logged through the provided or default logger.

    Returns:
        None
    """
    logger_to_use = (
        current_logger_for_setup
        if current_logger_for_setup
        else module_logger
    )
    symbols = app_settings.symbols
    # TODO: Document a bunch of stuff
    # Extract necessary values from app_settings
    # Assuming gtfs specific settings might be nested, e.g., app_settings.gtfs.app_log_file
    # For now, let's assume top-level or derive if not explicitly in a gtfs sub-model.
    # If no specific gtfs log settings in AppSettings, use defaults or pass them explicitly
    # from the orchestrator if they are not part of AppSettings.
    # Let's assume orchestrator passes specific log_file_path, log_level, log_prefix for GTFS app.
    # For this refactor, we'll assume these are passed via app_settings or orchestrator.
    # The orchestrator will get them from AppSettings if we add them there.
    # Example: if these were in AppSettings.gtfs:
    # effective_log_file = str(app_settings.gtfs.app_log_file) if hasattr(app_settings, 'gtfs') and app_settings.gtfs.app_log_file else DEFAULT_GTFS_PROCESSOR_LOG_FILE
    # effective_log_level = app_settings.gtfs.app_log_level if hasattr(app_settings, 'gtfs') and app_settings.gtfs.app_log_level else logging.INFO
    # effective_log_prefix = app_settings.gtfs.app_log_prefix if hasattr(app_settings, 'gtfs') and app_settings.gtfs.app_log_prefix else "[GTFS-PROCESSOR]"
    # For now, keep as passed from orchestrator, which will source from AppSettings:
    # These parameters will be added to the process_and_setup_gtfs and passed here.
    # We'll use placeholder names that the orchestrator will populate from app_settings.

    gtfs_feed_url = str(app_settings.gtfs_feed_url)
    db_params = {
        "PGHOST": app_settings.pg.host,
        "PGPORT": str(app_settings.pg.port),
        "PGDATABASE": app_settings.pg.database,
        "PGUSER": app_settings.pg.user,
        "PGPASSWORD": app_settings.pg.password,
    }
    # TODO: Allow overrides
    # Log file settings for the GTFS application itself (not this setup function's logger)
    # These could be specific fields in AppSettings, e.g., app_settings.gtfs_app_log_file
    # For now, using a default that could be overridden by orchestrator if it reads from AppSettings.
    effective_gtfs_app_log_file = DEFAULT_GTFS_PROCESSOR_LOG_FILE
    effective_gtfs_app_log_level = logging.INFO
    effective_gtfs_app_log_prefix = "[GTFS-ETL-PIPELINE]"

    common_setup_logging(
        log_level=effective_gtfs_app_log_level,
        log_file=effective_gtfs_app_log_file,
        log_to_console=True,  # GTFS pipeline might also log to console
        log_prefix=effective_gtfs_app_log_prefix,
    )
    log_map_server(
        f"{symbols.get('info', 'ℹ️')} GTFS Application logging configured by environment setup. Log file: {effective_gtfs_app_log_file}, Level: {logging.getLevelName(effective_gtfs_app_log_level)}",
        "info",
        logger_to_use,
        app_settings,
    )

    try:
        run_elevated_command(
            ["touch", effective_gtfs_app_log_file],
            app_settings,
            current_logger=logger_to_use,
        )
        current_user_name = getuser()
        try:
            current_group_info = getgrgid(os.getgid())
            current_group_name = current_group_info.gr_name
        except KeyError:
            current_group_name = str(os.getgid())

        run_elevated_command(
            [
                "chown",
                f"{current_user_name}:{current_group_name}",
                effective_gtfs_app_log_file,
            ],
            app_settings,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Ensured GTFS app log file '{effective_gtfs_app_log_file}' exists and is writable by '{current_user_name}'.",
            "info",
            logger_to_use,
            app_settings,
        )
    except Exception as e:
        log_map_server(
            f"{symbols.get('warning', '!')} Could not create/chown GTFS app log file {effective_gtfs_app_log_file}: {e}. Logging might fail or go to stdout/stderr.",
            "warning",
            logger_to_use,
            app_settings,
            exc_info=True,
        )

    log_map_server(
        f"{symbols.get('gear', '⚙️')} Setting OS environment variables for GTFS processing context...",
        "info",
        logger_to_use,
        app_settings,
    )
    os.environ["GTFS_FEED_URL"] = gtfs_feed_url
    os.environ["PG_OSM_PASSWORD"] = db_params.get("PGPASSWORD", "")
    os.environ["PG_OSM_USER"] = db_params.get("PGUSER", "")
    os.environ["PG_GIS_DB"] = db_params.get("PGDATABASE", "")
    os.environ["PG_HOST"] = db_params.get("PGHOST", "")
    os.environ["PG_PORT"] = db_params.get("PGPORT", "")

    os.environ["GTFS_PROCESSOR_LOG_FILE"] = effective_gtfs_app_log_file

    log_map_server(
        f"{symbols.get('info', 'ℹ️')} GTFS OS environment variables set. "
        f"GTFS_FEED_URL (for pipeline): {os.environ.get('GTFS_FEED_URL')}, "
        f"GTFS_PROCESSOR_LOG_FILE (for pipeline): {os.environ.get('GTFS_PROCESSOR_LOG_FILE')}",
        "info",
        logger_to_use,
        app_settings,
    )
