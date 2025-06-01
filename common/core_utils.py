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
import sys  # For sys.stdout, sys.stderr
from pathlib import Path
from typing import Dict, List, Optional  # Ensure sys, Path, List, Optional are imported

module_logger = logging.getLogger(__name__)

DEFAULT_DB_PARAMS: Dict[str, str] = {
    "dbname": os.environ.get("PG_OSM_DATABASE", "gis"),
    "user": os.environ.get("PG_OSM_USER", "osmuser"),
    "password": os.environ.get("PG_OSM_PASSWORD", "yourStrongPasswordHere"),
    "host": os.environ.get("PG_OSM_HOST", "localhost"),
    "port": os.environ.get("PG_OSM_PORT", "5432"),
}

# Define standard formats (these could also live in setup/config.py if preferred)
DETAILED_LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s"
# New format string that can accept a prefix.
# Using {log_prefix} which will be formatted by f-string logic before Formatter uses it.
SIMPLE_LOG_FORMAT_WITH_PREFIX_PLACEHOLDER = "{log_prefix}%(asctime)s - %(levelname)s - %(name)s - %(message)s"
SIMPLE_LOG_FORMAT_NO_PREFIX = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"


def setup_logging(
        log_level: int = logging.INFO,
        log_file: Optional[str] = None,
        log_to_console: bool = True,
        log_format_str: Optional[str] = None,
        log_prefix: Optional[str] = None
) -> None:
    """
    Set up basic logging configuration for the application.

    Configures handlers for file and/or console logging with a standard format.
    This function will configure the root logger.

    Args:
        log_level: The minimum logging level.
        log_file: Optional path to a file where logs should be written.
        log_to_console: If True, logs will also be output to the console.
        log_format_str: Optional custom log format string.
        log_prefix: Optional prefix for log messages (used if log_format_str
                    supports a '{log_prefix}' placeholder or is None).
    """
    handlers: List[logging.Handler] = []
    if log_file:
        try:
            log_file_path = Path(log_file)
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file_path, mode="a")
            handlers.append(file_handler)
        except Exception as e:
            # Use print for this initial setup error as logger might not be working yet
            print(f"Warning: Could not create file handler for log file {log_file}: {e}", file=sys.stderr)

    if log_to_console:
        # Log to sys.stdout by default. Specific error-level formatting
        # would be a more advanced handler feature if needed.
        console_handler = logging.StreamHandler(sys.stdout)
        handlers.append(console_handler)

    if not handlers:  # pragma: no cover
        # Fallback if neither file nor console specified, log to console
        handlers.append(logging.StreamHandler(sys.stdout))
        if log_level > logging.INFO:  # Ensure some output for fallback
            log_level = logging.INFO

    # Determine final format string
    final_format_str: str
    actual_prefix = (log_prefix.strip() + " ") if log_prefix and log_prefix.strip() else ""

    if log_format_str:
        if "{log_prefix}" in log_format_str:  # Check if placeholder exists
            final_format_str = log_format_str.format(log_prefix=actual_prefix)
        else:  # log_format_str provided but doesn't have a placeholder; use it as is, prepend prefix if any
            final_format_str = actual_prefix + log_format_str
    else:  # No specific format_str given, use default based on prefix
        if actual_prefix:  # Check if actual_prefix has content after stripping
            # Use the placeholder version, which becomes the actual prefix due to .format()
            final_format_str = SIMPLE_LOG_FORMAT_WITH_PREFIX_PLACEHOLDER.format(log_prefix=actual_prefix)
        else:
            final_format_str = SIMPLE_LOG_FORMAT_NO_PREFIX

    logging.basicConfig(
        level=log_level,
        format=final_format_str,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True  # Override any existing root logger configuration
    )
    # Ensure root logger's level is also set, especially if other libraries use logging.
    logging.getLogger().setLevel(log_level)

    # Log the configuration using a logger obtained *after* basicConfig
    # This logger will be common.core_utils
    logger_for_this_message = logging.getLogger(__name__)  # common.core_utils
    # Check if this logger itself is disabled or has a higher level
    if not logger_for_this_message.isEnabledFor(logging.INFO):  # pragma: no cover
        logger_for_this_message.setLevel(logging.INFO)  # Temporarily ensure it can log this

    logger_for_this_message.info(
        f"Logging configured. Level: {logging.getLevelName(log_level)}. Format: '{final_format_str}'"
    )


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
