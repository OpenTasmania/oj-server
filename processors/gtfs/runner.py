# processors/gtfs/runner.py
# -*- coding: utf-8 -*-
"""
Handles the execution of the GTFS ETL pipeline and subsequent data verification.
"""
import logging
import os
from typing import Optional, Dict

from common.command_utils import log_map_server, run_command

# setup.config is no longer imported here. log_map_server handles symbols.

module_logger = logging.getLogger(__name__)


def run_gtfs_etl_pipeline_and_verify(
        db_params: Dict[str, str],
        current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Runs the main GTFS ETL pipeline and verifies data import.
    Assumes OS environment variables for the pipeline (e.g., GTFS_FEED_URL,
    and DB credentials for the pipeline itself) are already set up by a
    preceding step (e.g., by processors.gtfs.environment.setup_gtfs_environment).

    Args:
        db_params: Dictionary containing database connection parameters for
                   psql verification (e.g., PGHOST, PGPORT, PGUSER, PGDATABASE).
        current_logger: Optional logger instance.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        "Running main GTFS ETL pipeline...",  # SYMBOLS are handled by log_map_server
        "info",
        logger_to_use,
    )

    try:
        # Assuming main_pipeline.py is in the same package (processors.gtfs)
        from .main_pipeline import run_full_gtfs_etl_pipeline as core_run_etl
    except ImportError as e:  # pragma: no cover
        log_map_server(
            (f"Critical: Could not import 'processors.gtfs.main_pipeline.run_full_gtfs_etl_pipeline': {e}. "
             "GTFS ETL cannot run. Ensure Python dependencies and paths are correct."),
            "error",
            logger_to_use,
        )
        raise ImportError("processors.gtfs.main_pipeline.run_full_gtfs_etl_pipeline not available.") from e

    # These environment variables are expected to be set by processors.gtfs.environment.setup_gtfs_environment()
    feed_url_from_env = os.environ.get('GTFS_FEED_URL', 'Not Set in Environment by setup_gtfs_environment')
    log_file_from_env = os.environ.get('GTFS_PROCESSOR_LOG_FILE',
                                       'Log file not set in Environment by setup_gtfs_environment')

    log_map_server(
        (f"Starting GTFS ETL pipeline. Feed URL (from env): {feed_url_from_env}. "
         f"Detailed logs for the pipeline itself are expected at (from env): {log_file_from_env}"),
        "info",
        logger_to_use,
    )

    success = core_run_etl()

    if not success:  # pragma: no cover
        log_map_server(
            (f"GTFS ETL pipeline FAILED. "
             f"Check logs at (from env): {log_file_from_env}."),  # SYMBOLS handled by log_map_server
            "error",
            logger_to_use,
        )
        raise RuntimeError("GTFS ETL Pipeline Failed.")

    log_map_server(
        "GTFS ETL pipeline completed successfully.",  # SYMBOLS handled by log_map_server
        "success",
        logger_to_use,
    )

    # Verification step using provided db_params
    log_map_server("Verifying GTFS data import (table counts)...", "info", logger_to_use)  # SYMBOLS handled
    try:
        # Use db_params for psql connection arguments
        # PGPASSWORD for psql tool is expected to be in OS environment,
        # set by processors.gtfs.environment.setup_gtfs_environment
        psql_common_args = [
            "psql",
            "-h", db_params.get("PGHOST", "localhost"),
            "-p", str(db_params.get("PGPORT", "5432")),
            "-U", db_params.get("PGUSER", "osmuser"),
            "-d", db_params.get("PGDATABASE", "gis"),
        ]

        run_command(psql_common_args + ["-c", "SELECT COUNT(*) FROM gtfs_stops;"], capture_output=True,
                    current_logger=logger_to_use)
        run_command(psql_common_args + ["-c", "SELECT COUNT(*) FROM gtfs_routes;"], capture_output=True,
                    current_logger=logger_to_use)
        log_map_server("GTFS data verification counts queried successfully.", "success",
                       logger_to_use)  # SYMBOLS handled
    except Exception as e_psql:  # pragma: no cover
        log_map_server(
            (f"Could not verify GTFS counts with psql: {e_psql}. "
             "This might be non-critical if ETL reported success."),  # SYMBOLS handled
            "warning",
            logger_to_use,
        )