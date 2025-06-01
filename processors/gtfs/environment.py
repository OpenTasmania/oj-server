# processors/gtfs/environment.py
# -*- coding: utf-8 -*-
"""
Handles environment setup for GTFS processing, including logging and
setting OS environment variables required by the pipeline.
"""
import logging
import os
from getpass import getuser
from grp import getgrgid # For getting group name
from typing import Optional, Dict

# Assuming common utilities are accessible from the project root
from common.command_utils import log_map_server, run_elevated_command
from common.core_utils import setup_logging as common_setup_logging
# No direct import of setup.config here; parameters will be passed in.

module_logger = logging.getLogger(__name__)

# Default log file path if not provided; could also be part of gtfs_config_params
DEFAULT_GTFS_PROCESSOR_LOG_FILE = "/var/log/gtfs_processor_app.log"

def setup_gtfs_environment(
    feed_url: str,
    db_params: Dict[str, str],
    log_file_path: Optional[str] = None,
    log_level: int = logging.INFO,
    log_prefix: str = "[GTFS-PROCESSOR]"
) -> None:
    """
    Sets up logging for GTFS processing and exports necessary OS environment
    variables for the GTFS pipeline based on provided parameters.

    Args:
        feed_url: The URL for the GTFS feed.
        db_params: Dictionary containing database connection parameters:
                   PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD.
        log_file_path: Optional path for the GTFS processing log file.
                       Defaults to DEFAULT_GTFS_PROCESSOR_LOG_FILE.
        log_level: The logging level for the GTFS processor.
        log_prefix: The prefix for log messages from the GTFS processor.
    """
    effective_log_file = log_file_path or DEFAULT_GTFS_PROCESSOR_LOG_FILE

    # 1. Setup Logging for GTFS operations using the common utility
    # This call will configure the root logger if this is the primary entry point,
    # or add its specific handlers if logging is already configured.
    # For GTFS processing, it's often useful to have its own dedicated log file.
    common_setup_logging(
        log_level=log_level,
        log_file=effective_log_file,
        log_to_console=True, # GTFS processor might also log to console
        log_prefix=log_prefix
    )
    module_logger.info(f"GTFS Processor logging configured. Log file: {effective_log_file}, Level: {logging.getLevelName(log_level)}")

    # Ensure log file exists and has appropriate permissions
    try:
        run_elevated_command(["touch", effective_log_file], current_logger=module_logger)
        current_user_name = getuser()
        try:
            current_group_info = getgrgid(os.getgid())
            current_group_name = current_group_info.gr_name
        except KeyError: # pragma: no cover
            current_group_name = str(os.getgid())

        run_elevated_command(
            ["chown", f"{current_user_name}:{current_group_name}", effective_log_file],
            current_logger=module_logger,
        )
        module_logger.info(
            f"Ensured GTFS log file '{effective_log_file}' exists and is writable by '{current_user_name}'."
        )
    except Exception as e: # pragma: no cover
        module_logger.warning(
            f"Could not create/chown GTFS log file {effective_log_file}: {e}. "
            "Logging from GTFS scripts might fail or go to stdout/stderr."
        )

    # 2. Set OS Environment Variables for the GTFS pipeline execution context
    # These will be picked up by modules within processors.gtfs.
    module_logger.info("Setting OS environment variables for GTFS processing context...")
    os.environ["GTFS_FEED_URL"] = feed_url
    os.environ["PG_OSM_PASSWORD"] = db_params.get("PGPASSWORD", "") # Use PGPASSWORD from dict key
    os.environ["PG_OSM_USER"] = db_params.get("PGUSER", "")
    os.environ["PG_OSM_HOST"] = db_params.get("PGHOST", "")
    os.environ["PG_OSM_PORT"] = str(db_params.get("PGPORT", "")) # Ensure it's a string
    os.environ["PG_OSM_DATABASE"] = db_params.get("PGDATABASE", "")
    # Export the log file path for any sub-processes or GTFS modules that might need it directly
    os.environ["GTFS_PROCESSOR_LOG_FILE"] = effective_log_file

    module_logger.info(
        f"GTFS OS environment variables set. "
        f"GTFS_FEED_URL: {os.environ.get('GTFS_FEED_URL')}, "
        f"GTFS_PROCESSOR_LOG_FILE: {os.environ.get('GTFS_PROCESSOR_LOG_FILE')}"
    )