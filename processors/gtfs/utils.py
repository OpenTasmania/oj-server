#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilities for the GTFS (General Transit Feed Specification) processing package.

This module provides helper functions for:
- Logging setup.
- Establishing database connections (PostgreSQL using Psycopg 3).
- Cleaning up directories.
"""

import logging
import os
from pathlib import Path
from sys import stderr, stdout
from typing import Any, Dict, List, Optional

import pandas as pd
import psycopg

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
            file_handler = logging.FileHandler(log_file, mode="a")
            handlers.append(file_handler)
        except Exception as e:
            print(
                f"Warning: Could not create file handler for log file {log_file}: {e}",
                file=stderr,
            )
    if log_to_console:
        console_handler = logging.StreamHandler(stdout)
        handlers.append(console_handler)
    if not handlers:
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
    )
    logging.getLogger().setLevel(log_level)
    module_logger.info("Logging configured.")


def get_db_connection(
    db_params: Optional[Dict[str, str]] = None,
) -> Optional[psycopg.Connection]:
    """
    Establish and return a PostgreSQL database connection using Psycopg 3.

    Args:
        db_params: Optional dictionary with database connection parameters.

    Returns:
        A psycopg.Connection object if successful, None otherwise.
    """
    params_to_use = DEFAULT_DB_PARAMS.copy()
    if db_params:
        params_to_use.update(db_params)

    if (
        params_to_use.get("password") == "yourStrongPasswordHere"
        and os.environ.get("PG_OSM_PASSWORD") == "yourStrongPasswordHere"
    ):
        module_logger.critical(
            "CRITICAL: Default placeholder password is being used for database "
            "connection. Please configure a strong password."
        )

    conn_kwargs = {
        "dbname": params_to_use.get("dbname"),
        "user": params_to_use.get("user"),
        "password": params_to_use.get("password"),
        "host": params_to_use.get("host"),
        "port": params_to_use.get("port"),
    }
    conn_kwargs_filtered = {k: v for k, v in conn_kwargs.items() if v is not None}

    try:
        module_logger.debug(
            f"Attempting to connect to database using Psycopg 3: "
            f"dbname='{conn_kwargs_filtered.get('dbname')}', "
            f"user='{conn_kwargs_filtered.get('user')}', "
            f"host='{conn_kwargs_filtered.get('host')}', "
            f"port='{conn_kwargs_filtered.get('port')}'"
        )
        conn = psycopg.connect(**conn_kwargs_filtered)
        module_logger.info(
            f"Connected to database {conn_kwargs_filtered.get('dbname')} on "
            f"{conn_kwargs_filtered.get('host')}:{conn_kwargs_filtered.get('port')} using Psycopg 3."
        )
        return conn
    except psycopg.Error as e:
        module_logger.error(f"Psycopg 3 database connection failed: {e}", exc_info=True)
    except Exception as e:
        module_logger.error(
            f"An unexpected error occurred while connecting to the database using Psycopg 3: {e}",
            exc_info=True,
        )
    return None


def cleanup_directory(directory_path: Path) -> None:
    """
    Remove all files and subdirectories within a given directory.

    Args:
        directory_path: Path object representing the directory to clean up.
    """
    import shutil
    if directory_path.exists():
        if directory_path.is_dir():
            try:
                shutil.rmtree(directory_path)
                module_logger.info(f"Cleaned up directory: {directory_path}")
            except Exception as e:
                module_logger.error(
                    f"Failed to clean up directory {directory_path}: {e}",
                    exc_info=True,
                )
        else:
            module_logger.warning(
                f"Path {directory_path} exists but is not a directory. Cannot clean."
            )
    else:
        module_logger.info(
            f"Directory {directory_path} does not exist. No cleanup needed."
        )