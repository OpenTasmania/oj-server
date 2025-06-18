#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GTFS Update Module for Standalone Execution.

This module provides a command-line interface for running the main GTFS ETL
pipeline.
"""

import argparse
import logging
import os
import sys
from typing import Dict, Optional

# common.core_utils will be imported for the new logging setup
from common.core_utils import setup_logging as common_setup_logging

# Relative import for the main pipeline function
from . import main_pipeline as core_gtfs_pipeline

module_logger = logging.getLogger(__name__)  # Standard module logger

DB_PARAMS: Dict[str, str] = {
    "dbname": os.environ.get("PG_GIS_DB", "gis"),
    "user": os.environ.get("PG_OSM_USER", "osmuser"),
    "password": os.environ.get("PG_OSM_PASSWORD", "yourStrongPasswordHere"),
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": os.environ.get("PG_PORT", "5432"),
}

LOG_FILE = "/var/log/update_gtfs_cli.log"

DEFAULT_GTFS_URL_CONFIG = "https://example.com/default_gtfs_feed.zip"

DEFAULT_GTFS_URL = os.environ.get("GTFS_FEED_URL", DEFAULT_GTFS_URL_CONFIG)


def run_gtfs_etl_via_core_pipeline(
    feed_url_override: Optional[str] = None,
) -> bool:
    """
    Runs the GTFS ETL process using the core pipeline.

    Summary:
    This function executes the GTFS (General Transit Feed Specification) ETL
    (Extract, Transform, Load) process utilizing the core pipeline module. It
    configures necessary environment variables, including the GTFS feed URL and
    database connection parameters, to ensure proper execution of the pipeline.

    Args:
        feed_url_override (Optional[str]): Overrides the default GTFS feed URL
            if specified. Defaults to None.

    Returns:
        bool: Indicates whether the GTFS ETL process completed successfully.
    """
    effective_feed_url = feed_url_override or DEFAULT_GTFS_URL

    os.environ["GTFS_FEED_URL"] = effective_feed_url
    module_logger.info(
        f"GTFS_FEED_URL set for core pipeline: {effective_feed_url}"
    )

    os.environ["PG_GIS_DB"] = DB_PARAMS["dbname"]
    os.environ["PG_OSM_USER"] = DB_PARAMS["user"]
    os.environ["PG_OSM_PASSWORD"] = DB_PARAMS["password"]
    os.environ["PG_HOST"] = DB_PARAMS["host"]
    os.environ["PG_PORT"] = DB_PARAMS["port"]

    if hasattr(
        core_gtfs_pipeline, "GTFS_FEED_URL_MODULE_LEVEL_VAR"
    ):  # pragma: no cover
        # Todo: Be better
        # This line attempts to modify a variable in the imported main_pipeline module.
        # While it might work, it's generally better for main_pipeline to solely rely on
        # os.environ.get("GTFS_FEED_URL") for its configuration if it's meant to be
        # configurable externally. The main_pipeline.py was already modified to do so.
        # We can keep this for now if it serves a specific purpose for GTFS_FEED_URL_MODULE_LEVEL_VAR
        # in main_pipeline, though that variable itself became less critical after main_pipeline changes.
        core_gtfs_pipeline.GTFS_FEED_URL_MODULE_LEVEL_VAR = effective_feed_url

    return core_gtfs_pipeline.run_full_gtfs_etl_pipeline()


def setup_update_gtfs_logging(
    log_level_str: str = "INFO",
    log_file_path: Optional[
        str
    ] = LOG_FILE,  # Use the module's LOG_FILE constant
    log_to_console: bool = True,
) -> None:
    """
    Configures logging for the GTFS update process.

    This function sets up logging for the GTFS update command-line interface (CLI),
    allowing logs to be written to a file, output to the console, and tagged with
    a distinct prefix for easier identification. The logging level and target log
    file can be customized using parameters, while invalid logging levels default
    to INFO.

    Parameters:
        log_level_str: str
            The logging level as a string, e.g., 'DEBUG', 'INFO', 'WARNING', etc.
            Defaults to 'INFO'.
        log_file_path: Optional[str]
            Path to the log file where logs will be written. If None, uses the default
            value defined by the module's LOG_FILE constant.
        log_to_console: bool
            Whether to also output logs to the console. Defaults to True.

    Returns:
        None
    """
    log_level_val = getattr(logging, log_level_str.upper(), logging.INFO)
    if not isinstance(log_level_val, int):  # Ensure it's a valid level
        print(
            f"Warning: Invalid log_level_str '{log_level_str}'. Defaulting to INFO.",
            file=sys.stderr,
        )
        log_level_val = logging.INFO

    common_setup_logging(
        log_level=log_level_val,
        log_file=log_file_path,
        log_to_console=log_to_console,
        log_prefix="[GTFS-UPDATE-CLI]",
    )
    module_logger.info(
        f"update_gtfs.py CLI logging configured. Level: {logging.getLevelName(log_level_val)}, File: {log_file_path}"
    )


def main_cli() -> None:  # pragma: no cover
    """
    Parse command-line arguments and execute the GTFS ETL pipeline via the core processing module.

    This function sets up the command-line interface (CLI) for configuring and running
    the GTFS processing pipeline. It allows for specifying the GTFS feed URL, logging
    parameters, and controls whether logs are redirected to the console. The function
    handles setting up the logging configuration and initiates the GTFS processing logic.

    Raises
    ------
    SystemExit
        Raised to exit the program with status code 0 for success or 1 for failure, based
        on the outcome of the GTFS processing.

    Parameters
    ----------
    None

    Returns
    -------
    None
    """
    parser = argparse.ArgumentParser(
        description="Run the GTFS ETL pipeline using the core processing module."
    )
    parser.add_argument(
        "--gtfs-url",
        dest="gtfs_url",
        default=None,
        help=(
            "URL of the GTFS feed zip file. Overrides GTFS_FEED_URL environment "
            "variable and the script's internal default."
        ),
    )
    parser.add_argument(
        "--log-level",
        dest="log_level_str",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level (default: INFO).",
    )
    parser.add_argument(
        "--log-file",
        dest="log_file_path",
        default=LOG_FILE,
        help=f"Path to the log file (default: {LOG_FILE}).",
    )
    parser.add_argument(
        "--no-console-log",
        action="store_false",
        dest="log_to_console",
        help="Disable logging to console (stdout).",
    )
    args = parser.parse_args()

    setup_update_gtfs_logging(
        log_level_str=args.log_level_str,
        log_file_path=args.log_file_path,
        log_to_console=args.log_to_console,
    )

    feed_url_for_logging = args.gtfs_url or DEFAULT_GTFS_URL

    module_logger.info(
        f"Attempting to process GTFS Feed URL: {feed_url_for_logging}"
    )
    module_logger.info(
        f"Target Database: dbname='{DB_PARAMS.get('dbname')}', "
        f"user='{DB_PARAMS.get('user')}', host='{DB_PARAMS.get('host')}'"
    )

    try:
        success = run_gtfs_etl_via_core_pipeline(
            feed_url_override=args.gtfs_url
        )
        sys.exit(0 if success else 1)
    except Exception as e:
        module_logger.critical(
            f"An unhandled error occurred during the GTFS update process via CLI: {e}",
            exc_info=True,
        )
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main_cli()
