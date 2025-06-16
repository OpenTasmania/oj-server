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

from setup.config_models import SYMBOLS_DEFAULT

module_logger = logging.getLogger(__name__)

DEFAULT_DB_PARAMS: Dict[str, str] = {
    "dbname": os.environ.get("PG_OSM_DATABASE", "gis"),
    "user": os.environ.get("PG_OSM_USER", "osmuser"),
    "password": os.environ.get("PG_OSM_PASSWORD", "yourStrongPasswordHere"),
    "host": os.environ.get("PG_OSM_HOST", "localhost"),
    "port": os.environ.get("PG_OSM_PORT", "5432"),
}

DETAILED_LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s"
SIMPLE_LOG_FORMAT_WITH_PREFIX_PLACEHOLDER = "{log_prefix}%(asctime)s - %(levelname)s - %(symbol)s %(name)s - %(message)s"
SIMPLE_LOG_FORMAT_NO_PREFIX = (
    "%(asctime)s - %(levelname)s - %(symbol)s %(name)s - %(message)s"
)


class SymbolFormatter(logging.Formatter):
    """
    A custom formatter that adds symbols to log messages based on the log level.
    """

    def __init__(
        self, fmt=None, datefmt=None, style="%", validate=True, symbols=None
    ):
        super().__init__(fmt, datefmt, style, validate)
        self.symbols = symbols or SYMBOLS_DEFAULT

    def format(self, record):
        if record.levelno == logging.DEBUG:
            record.symbol = self.symbols.get("debug", "🐛")
        elif record.levelno == logging.INFO:
            record.symbol = self.symbols.get("info", "ℹ️")
        elif record.levelno == logging.WARNING:
            record.symbol = self.symbols.get("warning", "⚠️")
        elif record.levelno == logging.ERROR:
            record.symbol = self.symbols.get("error", "❌")
        elif record.levelno == logging.CRITICAL:
            record.symbol = self.symbols.get("critical", "🔥")
        else:
            record.symbol = ""

        return super().format(record)


def setup_logging(
    log_level: int = logging.INFO,
    log_file: Optional[str] = None,
    log_to_console: bool = True,
    log_format_str: Optional[str] = None,
    log_prefix: Optional[str] = None,
) -> None:
    """
    Configures logging for an application.

    This function sets up a flexible logging configuration, allowing logging information to be directed to a file, the console,
    or both. It also supports customization of the log format and optional prefixing of log messages. The function ensures that
    logging is always configured properly, even when no handlers are explicitly defined. Additionally, it provides safeguards
    against invalid configurations and will fallback to defaults as necessary.

    Parameters:
    log_level: int
        The logging level to configure. Defaults to logging.INFO.
    log_file: Optional[str]
        The file path for the log file. If specified, logs will be written to this file. Defaults to None.
    log_to_console: bool
        Whether to log to the console (stdout). Defaults to True.
    log_format_str: Optional[str]
        A custom log format string. If specified, it will be used for formatting log messages. If left None, a default format
        will be applied. Defaults to None.
    log_prefix: Optional[str]
        An optional string to prefix log messages with. If specified, the prefix is added to the log messages. Defaults to None.

    Raises:
    Exception
        If an error occurs while attempting to create a file log handler, a warning is printed to stderr.

    Returns:
    None
    """
    handlers: List[logging.Handler] = []
    if log_file:
        try:
            log_file_path = Path(log_file)
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file_path, mode="a")
            handlers.append(file_handler)
        except Exception as e:
            print(
                f"Warning: Could not create file handler for log file {log_file}: {e}",
                file=sys.stderr,
            )

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        handlers.append(console_handler)

    if not handlers:  # pragma: no cover
        handlers.append(logging.StreamHandler(sys.stdout))
        if log_level > logging.INFO:
            log_level = logging.INFO

    final_format_str: str
    actual_prefix = (
        (log_prefix.strip() + " ")
        if log_prefix and log_prefix.strip()
        else ""
    )

    if log_format_str:
        if "{log_prefix}" in log_format_str:
            final_format_str = log_format_str.format(log_prefix=actual_prefix)
        else:
            final_format_str = actual_prefix + log_format_str
    else:
        if actual_prefix:
            final_format_str = (
                SIMPLE_LOG_FORMAT_WITH_PREFIX_PLACEHOLDER.format(
                    log_prefix=actual_prefix
                )
            )
        else:
            final_format_str = SIMPLE_LOG_FORMAT_NO_PREFIX

    formatter = SymbolFormatter(
        fmt=final_format_str,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    for handler in handlers:
        handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    for handler in handlers:
        root_logger.addHandler(handler)

    logger_for_this_message = logging.getLogger(__name__)
    if not logger_for_this_message.isEnabledFor(
        logging.INFO
    ):  # pragma: no cover
        logger_for_this_message.setLevel(logging.INFO)

    logger_for_this_message.info(
        f"Logging configured. Level: {logging.getLevelName(log_level)}. Format: '{final_format_str}'"
    )
