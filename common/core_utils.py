#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core utility functions for the project.

This module provides helper functions for:
- Logging setup.
- Establishing database connections (PostgreSQL using Psycopg 3).
- Cleaning up directories.
"""

import logging
import os
from pathlib import Path
from sys import stderr, stdout
from typing import Dict, List, Optional

module_logger = logging.getLogger(__name__)

DEFAULT_DB_PARAMS: Dict[str, str] = {
    "dbname": os.environ.get("PG_OSM_DATABASE", "gis"),
    "user": os.environ.get("PG_OSM_USER", "osmuser"),
    "password": os.environ.get("PG_OSM_PASSWORD", "yourStrongPasswordHere"),
    "host": os.environ.get("PG_OSM_HOST", "localhost"),
    "port": os.environ.get("PG_OSM_PORT", "5432"),
}


def setup_logging(
        log_level: int = logging.INFO,
        log_file: Optional[str] = None,
        log_to_console: bool = True,
) -> None:
    """
    Set up basic logging configuration for the application.

    Configures handlers for file and/or console logging with a standard format.

    Args:
        log_level: The minimum logging level.
        log_file: Optional path to a file where logs should be written.
        log_to_console: If True, logs will also be output to the console.
    """
    handlers: List[logging.Handler] = []
    if log_file:
        try:
            log_file_path = Path(log_file)
            log_file_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
            file_handler = logging.FileHandler(log_file_path, mode="a")
            handlers.append(file_handler)
        except Exception as e:
            print(
                f"Warning: Could not create file handler for log file {log_file}: {e}",
                file=stderr,
            )
    if log_to_console:
        console_handler = logging.StreamHandler(stdout)
        handlers.append(console_handler)

    if not handlers:  # Ensure at least one handler if none specified
        console_handler = logging.StreamHandler(stdout)
        handlers.append(console_handler)
        if log_level > logging.INFO:
            log_level = logging.INFO

    logging.basicConfig(
        level=log_level,
        format=(
            "%(asctime)s - %(levelname)s - %(name)s - "
            "%(module)s.%(funcName)s:%(lineno)d - %(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True  # Add force=True to override any existing root logger configuration
    )
    # Ensure the root logger's level is also set, especially if other libraries use logging.
    logging.getLogger().setLevel(log_level)

    # Get a logger for this module and log the configuration.
    # This ensures that if this setup_logging is called multiple times,
    # this specific message uses the just-configured settings.
    logger_for_this_message = logging.getLogger(__name__)
    logger_for_this_message.info(f"Logging configured at level {logging.getLevelName(log_level)}.")


def cleanup_directory(
        directory_path: Path, ensure_dir_exists_after: bool = False
) -> None:
    """
    Remove all files and subdirectories within a given directory.
    Optionally recreates the directory after cleaning.

    Args:
        directory_path: Path object representing the directory to clean up.
        ensure_dir_exists_after: If True, creates the directory if it doesn't
                                 exist after cleaning attempts.
    """
    import shutil
    dir_to_clean = Path(directory_path)
    module_logger.debug(f"Attempting to clean directory: {dir_to_clean}")

    if dir_to_clean.exists():
        if dir_to_clean.is_dir():
            try:
                shutil.rmtree(dir_to_clean)
                module_logger.info(f"Successfully removed directory and its contents: {dir_to_clean}")
            except Exception as e:
                module_logger.error(f"Error removing directory {dir_to_clean} using shutil.rmtree: {e}", exc_info=True)
        else:
            module_logger.warning(f"Path {dir_to_clean} exists but is not a directory. Cannot clean as a directory.")
    else:
        module_logger.info(f"Directory {dir_to_clean} does not exist. No cleanup needed there.")

    if ensure_dir_exists_after:
        try:
            dir_to_clean.mkdir(parents=True, exist_ok=True)
            module_logger.debug(f"Ensured directory exists: {dir_to_clean}")
        except Exception as e:
            module_logger.error(f"Error creating directory {dir_to_clean} after cleanup: {e}", exc_info=True)