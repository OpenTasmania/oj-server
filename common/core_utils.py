#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core utility functions for the project.

This module provides helper functions for:
- Logging setup.
- Establishing database connections (PostgreSQL using Psycopg 3).
# REMOVED: - Cleaning up directories. (This function is now in common/file_utils.py)
"""

import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

module_logger = logging.getLogger(__name__)

DEFAULT_DB_PARAMS: Dict[str, str] = {
    "dbname": os.environ.get("PG_OSM_DATABASE", "gis"),
    "user": os.environ.get("PG_OSM_USER", "osmuser"),
    "password": os.environ.get("PG_OSM_PASSWORD", "yourStrongPasswordHere"),
    "host": os.environ.get("PG_OSM_HOST", "localhost"),
    "port": os.environ.get("PG_OSM_PORT", "5432"),
}

DETAILED_LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s"
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
    (Implementation as previously refactored)
    """
    handlers: List[logging.Handler] = []
    if log_file:
        try:
            log_file_path = Path(log_file)
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file_path, mode="a")
            handlers.append(file_handler)
        except Exception as e:
            print(f"Warning: Could not create file handler for log file {log_file}: {e}", file=sys.stderr)

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        handlers.append(console_handler)

    if not handlers:  # pragma: no cover
        handlers.append(logging.StreamHandler(sys.stdout))
        if log_level > logging.INFO:
            log_level = logging.INFO

    final_format_str: str
    actual_prefix = (log_prefix.strip() + " ") if log_prefix and log_prefix.strip() else ""

    if log_format_str:
        if "{log_prefix}" in log_format_str:
            final_format_str = log_format_str.format(log_prefix=actual_prefix)
        else:
            final_format_str = actual_prefix + log_format_str
    else:
        if actual_prefix:
            final_format_str = SIMPLE_LOG_FORMAT_WITH_PREFIX_PLACEHOLDER.format(log_prefix=actual_prefix)
        else:
            final_format_str = SIMPLE_LOG_FORMAT_NO_PREFIX

    logging.basicConfig(
        level=log_level,
        format=final_format_str,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True
    )
    logging.getLogger().setLevel(log_level)

    logger_for_this_message = logging.getLogger(__name__)
    if not logger_for_this_message.isEnabledFor(logging.INFO):  # pragma: no cover
        logger_for_this_message.setLevel(logging.INFO)

    logger_for_this_message.info(
        f"Logging configured. Level: {logging.getLevelName(log_level)}. Format: '{final_format_str}'"
    )

# REMOVE cleanup_directory function from here.
