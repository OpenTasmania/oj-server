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

from common import core_utils
# Relative import for the main pipeline function
from . import main_pipeline as core_gtfs_pipeline

module_logger = logging.getLogger(__name__)

DB_PARAMS: Dict[str, str] = {
    "dbname": os.environ.get("PG_GIS_DB", "gis"),
    "user": os.environ.get("PG_OSM_USER", "osmuser"),
    "password": os.environ.get("PG_OSM_PASSWORD", "yourStrongPasswordHere"),
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": os.environ.get("PG_PORT", "5432"),
}

LOG_FILE = "/var/log/update_gtfs_cli.log"
try:
    # Attempt to get the default URL from a central config, fallback if not found
    from setup.config import GTFS_FEED_URL as DEFAULT_GTFS_URL_CONFIG
except ImportError:
    DEFAULT_GTFS_URL_CONFIG = "https://example.com/default_gtfs_feed.zip"

# Effective default URL considering environment override first, then config, then hardcoded.
DEFAULT_GTFS_URL = os.environ.get("GTFS_FEED_URL", DEFAULT_GTFS_URL_CONFIG)


def run_gtfs_etl_via_core_pipeline(feed_url_override: Optional[str] = None) -> bool:
    """
    Sets GTFS_FEED_URL and DB environment variables then runs the main ETL pipeline.

    Args:
        feed_url_override: Optional URL to override the default GTFS feed URL.
    Returns:
        True if the pipeline completed successfully, False otherwise.
    """
    # Determine the feed URL to use for this run
    effective_feed_url = feed_url_override or DEFAULT_GTFS_URL

    os.environ["GTFS_FEED_URL"] = effective_feed_url
    module_logger.info(f"GTFS_FEED_URL set for core pipeline: {effective_feed_url}")

    # Ensure DB_PARAMS are reflected in environment variables for the core pipeline
    os.environ["PG_GIS_DB"] = DB_PARAMS["dbname"]
    os.environ["PG_OSM_USER"] = DB_PARAMS["user"]
    os.environ["PG_OSM_PASSWORD"] = DB_PARAMS["password"]
    os.environ["PG_HOST"] = DB_PARAMS["host"]
    os.environ["PG_PORT"] = DB_PARAMS["port"]

    # If the core_gtfs_pipeline module directly uses a global GTFS_FEED_URL variable from setup.config,
    # and that module was already imported, its GTFS_FEED_URL might not reflect the override.
    # The most robust way is for the pipeline itself to read from os.environ['GTFS_FEED_URL']
    # or be passed the URL directly.
    # Here, we assume core_gtfs_pipeline.run_full_gtfs_etl_pipeline() will pick up the
    # environment variable or has its own mechanism to get the feed URL.
    # If direct patching of an imported global is needed (less ideal):
    if hasattr(core_gtfs_pipeline, 'GTFS_FEED_URL_MODULE_LEVEL_VAR'):  # Example if it had such a var
        core_gtfs_pipeline.GTFS_FEED_URL_MODULE_LEVEL_VAR = effective_feed_url

    return core_gtfs_pipeline.run_full_gtfs_etl_pipeline()


def setup_update_gtfs_logging(
        log_level_str: str = "INFO",
        log_file_path: Optional[str] = LOG_FILE,
        log_to_console: bool = True,
) -> None:
    """Set up logging configuration for the update_gtfs CLI script."""
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    # Uses a shared logging setup utility
    core_utils.setup_logging(
        log_level=log_level,
        log_file=log_file_path,
        log_to_console=log_to_console
    )
    module_logger.info(f"update_gtfs.py CLI logging configured at level {logging.getLevelName(log_level)}.")


def main_cli() -> None:
    """Main command-line interface entry point for this script."""
    parser = argparse.ArgumentParser(
        description="Run the GTFS ETL pipeline using the core processing module."
    )
    parser.add_argument(
        "--gtfs-url", dest="gtfs_url", default=None,
        help=(
            "URL of the GTFS feed zip file. Overrides GTFS_FEED_URL environment "
            "variable and the script's internal default."),
    )
    parser.add_argument(
        "--log-level", dest="log_level_str",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default="INFO",
        help="Set the logging level (default: INFO).",
    )
    parser.add_argument(
        "--log-file", dest="log_file_path", default=LOG_FILE,
        help=f"Path to the log file (default: {LOG_FILE}).",
    )
    parser.add_argument(
        "--no-console-log", action="store_false", dest="log_to_console",
        help="Disable logging to console (stdout).",
    )
    args = parser.parse_args()

    setup_update_gtfs_logging(
        log_level_str=args.log_level_str,
        log_file_path=args.log_file_path,
        log_to_console=args.log_to_console,
    )

    # The feed URL to be used is determined within run_gtfs_etl_via_core_pipeline
    # based on CLI args and defaults.
    feed_url_for_logging = args.gtfs_url or DEFAULT_GTFS_URL

    module_logger.info(f"Attempting to process GTFS Feed URL: {feed_url_for_logging}")
    module_logger.info(
        f"Target Database: dbname='{DB_PARAMS.get('dbname')}', "
        f"user='{DB_PARAMS.get('user')}', host='{DB_PARAMS.get('host')}'"
    )

    try:
        success = run_gtfs_etl_via_core_pipeline(feed_url_override=args.gtfs_url)
        sys.exit(0 if success else 1)
    except Exception as e:
        module_logger.critical(
            f"An unhandled error occurred during the GTFS update process via CLI: {e}",
            exc_info=True,
        )
        sys.exit(1)


if __name__ == "__main__":
    main_cli()