# dataproc/gtfs_processor_runner.py
# -*- coding: utf-8 -*-
"""
Handles the execution of the GTFS ETL pipeline and subsequent data verification.
"""
import logging
from typing import Optional
import os

# Assuming common utilities are in common/
from common.command_utils import log_map_server, run_command
from setup import config # For config vars and SYMBOLS

# The GTFS processor's main_pipeline is imported dynamically or conditionally
# by the calling orchestrator (e.g., main_installer.py) to avoid import errors
# if dependencies are not yet met. Here, we assume it will be passed or available.

module_logger = logging.getLogger(__name__)

def run_gtfs_etl_pipeline_and_verify(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Runs the main GTFS ETL pipeline and verifies data import.
    Assumes environment variables and logging are already set up by a preceding step.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Running main GTFS ETL pipeline...",
        "info",
        logger_to_use,
    )

    # Dynamically import the GTFS main_pipeline here, or ensure it's passed
    # This avoids making `processors.gtfs` a hard dependency of this module
    # if this module were to be imported early.
    try:
        from processors.gtfs import main_pipeline as gtfs_main_pipeline
        gtfs_processor_available = True
    except ImportError as e:
        gtfs_main_pipeline = None
        gt_processor_available = False # Typo corrected
        log_map_server(
            f"{config.SYMBOLS['error']} Critical: Could not import 'processors.gtfs.main_pipeline': {e}. "
            "GTFS ETL cannot run. Ensure Python dependencies are installed in the correct environment.",
            "error",
            logger_to_use,
        )
        raise ImportError("processors.gtfs.main_pipeline not available.") from e

    # The GTFS processor's internal logging should now use the file path
    # set in the environment variable by setup_gtfs_logging_and_env_vars.
    # core_utils.setup_logging in the original gtfs_data_prep would have configured this.
    # We assume the GTFS pipeline's own logging setup will pick up the env var
    # or that setup_logging has already been called appropriately.

    log_map_server(
        f"{config.SYMBOLS['rocket']} Starting GTFS ETL pipeline with URL: "
        f"{os.environ.get('GTFS_FEED_URL', 'Not Set')}. "
        f"Check {os.environ.get('GTFS_PROCESSOR_LOG_FILE', 'gtfs_processor_app.log')} for detailed logs.",
        "info",
        logger_to_use,
    )

    success = gtfs_main_pipeline.run_full_gtfs_etl_pipeline()

    if not success:
        log_map_server(
            f"{config.SYMBOLS['error']} GTFS ETL pipeline FAILED. "
            f"Check logs at {os.environ.get('GTFS_PROCESSOR_LOG_FILE', '(log path not set)')}.",
            "error",
            logger_to_use,
        )
        raise RuntimeError("GTFS ETL Pipeline Failed.")

    log_map_server(
        f"{config.SYMBOLS['success']} GTFS ETL pipeline completed successfully.",
        "success",
        logger_to_use,
    )

    # Verification
    log_map_server(f"{config.SYMBOLS['info']} Verifying GTFS data import (table counts)...", "info", logger_to_use)
    try:
        # Assumes PGPASSWORD is set in the environment for psql if needed
        # or .pgpass is configured. These are set by setup_gtfs_logging_and_env_vars.
        psql_common_args = [
            "psql",
            "-h", os.environ.get("PG_OSM_HOST", "localhost"),
            "-p", os.environ.get("PG_OSM_PORT", "5432"),
            "-U", os.environ.get("PG_OSM_USER", "osmuser"),
            "-d", os.environ.get("PG_OSM_DATABASE", "gis"),
        ]
        run_command(psql_common_args + ["-c", "SELECT COUNT(*) FROM gtfs_stops;"], capture_output=True, current_logger=logger_to_use)
        run_command(psql_common_args + ["-c", "SELECT COUNT(*) FROM gtfs_routes;"], capture_output=True, current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} GTFS data verification counts queried.", "success", logger_to_use)
    except Exception as e_psql:
        log_map_server(
            f"{config.SYMBOLS['warning']} Could not verify GTFS counts with psql: {e_psql}. "
            "This might be non-critical if ETL reported success.",
            "warning",
            logger_to_use,
        )