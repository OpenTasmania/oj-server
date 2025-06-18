# processors/gtfs/runner.py
# -*- coding: utf-8 -*-
"""
Handles the execution of the GTFS ETL pipeline and subsequent data verification.
"""

import logging
import os
from typing import Optional

from common.command_utils import log_map_server, run_command
from setup.config_models import AppSettings  # Import AppSettings

module_logger = logging.getLogger(__name__)


def run_gtfs_etl_pipeline_and_verify(
    app_settings: AppSettings,
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Runs the GTFS ETL pipeline and verifies the data import.

    This function serves as the main entry point for executing the GTFS ETL (Extract,
    Transform, Load) pipeline and validating its results. The pipeline processes the GTFS
    data using environment configurations and logs its execution. It also includes a
    verification step to ensure the success of the data import by querying relevant GTFS
    tables.

    Arguments:
        app_settings: An instance of AppSettings containing the application configuration.
        current_logger: An optional logger instance to use for logging. If not provided,
            a module-level logger will be used.

    Raises:
        ImportError: If the GTFS ETL pipeline core module cannot be imported.
        RuntimeError: If the GTFS ETL pipeline execution fails.

    Returns:
        None
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols

    log_map_server(
        f"{symbols.get('rocket', '🚀')} Running main GTFS ETL pipeline (runner)...",
        "info",
        logger_to_use,
        app_settings,
    )

    try:
        from .main_pipeline import run_full_gtfs_etl_pipeline as core_run_etl
    except ImportError as e:
        log_map_server(
            f"{symbols.get('critical', '🔥')} Critical: Could not import GTFS main_pipeline: {e}. ETL cannot run.",
            "critical",
            logger_to_use,
            app_settings,
        )
        raise ImportError(
            "processors.gtfs.main_pipeline.run_full_gtfs_etl_pipeline not available."
        ) from e

    feed_url_from_env = os.environ.get(
        "GTFS_FEED_URL", "Not Set by GTFS environment setup"
    )
    log_file_from_env = os.environ.get(
        "GTFS_PROCESSOR_LOG_FILE",
        "Log file not set by GTFS environment setup",
    )

    log_map_server(
        f"Starting GTFS ETL pipeline via core runner. Feed URL (from env): {feed_url_from_env}. "
        f"Detailed pipeline logs (from env): {log_file_from_env}",
        "info",
        logger_to_use,
        app_settings,
    )

    success = core_run_etl()

    if not success:
        log_map_server(
            f"{symbols.get('error', '❌')} GTFS ETL pipeline FAILED. Check logs at (from env): {log_file_from_env}.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise RuntimeError("GTFS ETL Pipeline Failed during core run.")

    log_map_server(
        f"{symbols.get('success', '✅')} GTFS ETL pipeline completed successfully (runner).",
        "success",
        logger_to_use,
        app_settings,
    )

    # Verification step using app_settings.pg
    log_map_server(
        f"{symbols.get('gear', '⚙️')} Verifying GTFS data import (table counts)...",
        "info",
        logger_to_use,
        app_settings,
    )
    try:
        psql_common_args = [
            "psql",
            "-h",
            app_settings.pg.host,
            "-p",
            str(app_settings.pg.port),
            "-U",
            app_settings.pg.user,
            "-d",
            app_settings.pg.database,
        ]
        run_command(
            psql_common_args + ["-c", "SELECT COUNT(*) FROM gtfs_stops;"],
            app_settings,
            capture_output=True,
            current_logger=logger_to_use,
        )
        run_command(
            psql_common_args + ["-c", "SELECT COUNT(*) FROM gtfs_routes;"],
            app_settings,
            capture_output=True,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} GTFS data verification counts queried successfully.",
            "success",
            logger_to_use,
            app_settings,
        )
    except Exception as e_psql:
        log_map_server(
            f"{symbols.get('warning', '!')} Could not verify GTFS counts with psql: {e_psql}. This might be non-critical if ETL reported success.",
            "warning",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
