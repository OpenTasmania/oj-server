#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilities for the GTFS (General Transit Feed Specification) processing package.

This module provides helper functions for:
- Logging setup.
- Establishing database connections (PostgreSQL using Psycopg 3).
- Cleaning up directories.
- Validating Pandas DataFrames against Pydantic models.

It relies on schema definitions from `schema_definitions.py` within the same
package for Pydantic model validation.
"""

import logging
import os
from pathlib import Path
from sys import stderr, stdout
from typing import Any, Dict, List, Optional, Tuple, Type

import pandas as pd
import psycopg # Psycopg 3: Replaces psycopg2
from pydantic import BaseModel, ValidationError

# Import schema definitions from the local package.
from . import schema_definitions as schemas

module_logger = logging.getLogger(__name__)

# Default database parameters, primarily for get_db_connection.
# These can be overridden by environment variables.
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
        log_level: The minimum logging level (e.g., logging.INFO,
                   logging.DEBUG).
        log_file: Optional path to a file where logs should be written.
                  If None, no file logging is set up.
        log_to_console: If True, logs will also be output to the console
                        (stdout).
    """
    handlers: List[logging.Handler] = []

    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, mode="a")
            handlers.append(file_handler)
        except Exception as e:
            # Fallback or log an error if file handler can't be created.
            # Using print here as logger itself might not be fully set up.
            print(
                f"Warning: Could not create file handler for log file "
                f"{log_file}: {e}",
                file=stderr,
            )

    if log_to_console:
        console_handler = logging.StreamHandler(stdout)
        handlers.append(console_handler)

    if not handlers:  # Ensure there's at least one handler if none specified
        console_handler = logging.StreamHandler(stdout)
        handlers.append(console_handler)
        if (
            log_level > logging.INFO
        ):  # If default level too high, ensure some output
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
    # Get the root logger and ensure its level is also set.
    # This can be important if other libraries also use logging.
    logging.getLogger().setLevel(log_level)

    module_logger.info("Logging configured.")


def get_db_connection(
    db_params: Optional[Dict[str, str]] = None,
) -> Optional[psycopg.Connection]: # Psycopg 3: Type hint changed from psycopg2.extensions.connection
    """
    Establish and return a PostgreSQL database connection using Psycopg 3.

    Uses provided `db_params` or falls back to `DEFAULT_DB_PARAMS`.

    Args:
        db_params: Optional dictionary with database connection parameters
                   (dbname, user, password, host, port).

    Returns:
        A psycopg.Connection object if successful, None otherwise.
    """
    params_to_use = DEFAULT_DB_PARAMS.copy()
    if db_params:
        params_to_use.update(db_params)

    # Password security check
    if (
        params_to_use.get("password") == "yourStrongPasswordHere"
        and os.environ.get("PG_OSM_PASSWORD") == "yourStrongPasswordHere"
    ):
        module_logger.critical(
            "CRITICAL: Default placeholder password is being used for database "
            "connection. Please configure a strong password in DB_PARAMS or "
            "via PG_OSM_PASSWORD environment variable."
        )
        # Depending on policy, might raise an exception or allow connection for dev.

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
        # Psycopg 3: Use psycopg.connect instead of psycopg2.connect
        conn = psycopg.connect(**conn_kwargs_filtered)
        module_logger.info(
            f"Connected to database {conn_kwargs_filtered.get('dbname')} on "
            f"{conn_kwargs_filtered.get('host')}:{conn_kwargs_filtered.get('port')} using Psycopg 3."
        )
        return conn
    except psycopg.Error as e: # Psycopg 3: Error base class changed from psycopg2.Error
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
                f"Path {directory_path} exists but is not a directory. "
                "Cannot clean."
            )
    else:
        module_logger.info(
            f"Directory {directory_path} does not exist. No cleanup needed."
        )


def validate_dataframe_with_pydantic(
    df: pd.DataFrame,
    pydantic_model: Type[BaseModel],
    gtfs_filename: str,
) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    Validate each row of a Pandas DataFrame against a given Pydantic model.

    Args:
        df: The input Pandas DataFrame with raw data.
        pydantic_model: The Pydantic model class to validate against.
        gtfs_filename: The name of the GTFS file being processed (for context
                       in logging and DLQ).

    Returns:
        A tuple containing:
            - pd.DataFrame: DataFrame with only the valid records. The records
                            are dictionaries dumped from Pydantic model
                            instances (i.e., cleaned and typed data).
            - List[Dict[str, Any]]: A list of dictionaries, where each
                                    dictionary represents a failed record
                                    along with its validation errors. Each dict
                                    will have 'original_record', 'errors',
                                    'source_filename', and 'original_index'.
    """
    if df.empty:
        module_logger.info(
            f"DataFrame for validating with {pydantic_model.__name__} is empty."
        )
        model_field_names = list(pydantic_model.model_fields.keys())
        return pd.DataFrame(columns=model_field_names), []

    valid_records_list: List[Dict[str, Any]] = []
    invalid_records_info_list: List[Dict[str, Any]] = []

    module_logger.info(
        f"Validating {len(df)} records from '{gtfs_filename}' using "
        f"Pydantic model '{pydantic_model.__name__}'..."
    )

    for index, row in df.iterrows():
        try:
            record_dict_for_pydantic: Dict[str, Any] = {}
            for col, val in row.items():
                if pd.isna(val) or (isinstance(val, str) and not val.strip()):
                    record_dict_for_pydantic[col] = None
                else:
                    record_dict_for_pydantic[col] = val

            validated_model_instance = pydantic_model(
                **record_dict_for_pydantic
            )
            valid_records_list.append(
                validated_model_instance.model_dump(exclude_none=False)
            )

        except ValidationError as e_val:
            invalid_record_info = {
                "original_record": row.to_dict(),
                "errors": e_val.errors(),
                "source_filename": gtfs_filename,
                "original_index": index,
            }
            invalid_records_info_list.append(invalid_record_info)
            module_logger.debug(
                f"Validation failed for record at index {index} from "
                f"{gtfs_filename}: {e_val.errors()}"
            )
        except Exception as ex_other:
            invalid_record_info = {
                "original_record": row.to_dict(),
                "errors": [
                    {
                        "loc": ["unknown"],
                        "msg": str(ex_other),
                        "type": "unexpected_error",
                    }
                ],
                "source_filename": gtfs_filename,
                "original_index": index,
            }
            invalid_records_info_list.append(invalid_record_info)
            module_logger.error(
                f"Unexpected error validating record at index {index} from "
                f"{gtfs_filename}: {ex_other}",
                exc_info=True,
            )

    valid_df: pd.DataFrame
    if valid_records_list:
        valid_df_columns = list(pydantic_model.model_fields.keys())
        valid_df = pd.DataFrame(valid_records_list, columns=valid_df_columns)
    else:
        valid_df = pd.DataFrame(
            columns=list(pydantic_model.model_fields.keys())
        )

    module_logger.info(
        f"Validation for '{gtfs_filename}' complete. "
        f"Valid records: {len(valid_df)}. "
        f"Invalid records: {len(invalid_records_info_list)}."
    )

    return valid_df, invalid_records_info_list


if __name__ == "__main__":
    setup_logging(log_level=logging.DEBUG)
    module_logger.info("--- Testing osm.processors.gtfs.utils.py ---")

    stop_model_definition = schemas.GTFS_FILE_SCHEMAS.get("stops.txt")
    if not stop_model_definition or "model" not in stop_model_definition:
        module_logger.error(
            "Stop model not found in schema_definitions. Skipping test."
        )
    else:
        stop_pydantic_model_class = stop_model_definition["model"]
        raw_stop_data = {
            "stop_id": ["s1", "s2", "s3", "s4", "s5", "s6"],
            "stop_code": ["c1", "", None, "c4", "c5", "c6"],
            "stop_name": [
                " Stop One ", "Stop Two (Good LatLon)", "  ",
                "Stop Four (Bad Lat)", "Stop Five (Missing Lon)", "Stop Six (Good)",
            ],
            "stop_desc": ["Desc 1", None, "Desc 3", "Desc 4", "Desc 5", "Desc 6"],
            "stop_lat": ["40.7128 ", "40.7321", "40.777", "95.0", "40.123", "34.0522"],
            "stop_lon": [" -74.0060", "-74.0001", "-74.111", "-74.0020", "", "-118.2437"],
            "zone_id": ["z1", "z2", "z1", None, "z3", "z4"],
            "location_type": ["0", "1", "", "0", "2", None],
            "parent_station": [None, None, "s2", "s1", None, ""],
            "extra_column_not_in_model": ["ex1", "ex2", "ex3", "ex4", "ex5", "ex6"],
        }
        raw_stops_df = pd.DataFrame(raw_stop_data)
        module_logger.info(
            f"\nRaw stops DataFrame for validation:\n{raw_stops_df}"
        )
        valid_stops_df, invalid_stops_info = validate_dataframe_with_pydantic(
            raw_stops_df, stop_pydantic_model_class, "stops.txt"
        )
        module_logger.info(
            f"\nValidated Stops DataFrame ({len(valid_stops_df)} records):\n"
            f"{valid_stops_df.head().to_string()}"
        )
        if (
            valid_stops_df.empty
            and not invalid_stops_info
            and not raw_stops_df.empty
        ):
            module_logger.warning(
                "Validation returned empty valid DataFrame and no invalid "
                "records - check logic if input was not empty."
            )
        module_logger.info(
            f"\nInvalid Stops Records/Info ({len(invalid_stops_info)} records):"
        )
        for invalid_info in invalid_stops_info:
            module_logger.info(
                f"  Original: {invalid_info['original_record']}"
            )
            module_logger.info(f"  Errors: {invalid_info['errors']}")

    if (
        DEFAULT_DB_PARAMS["password"] == "yourStrongPasswordHere"
        and os.environ.get("PG_OSM_PASSWORD") == "yourStrongPasswordHere"
    ):
        module_logger.warning(
            "Skipping database connection test as password is the placeholder "
            "and PG_OSM_PASSWORD env var is not set differently."
        )
    else:
        module_logger.info("\n--- Testing Database Connection ---")
        test_conn = get_db_connection()
        if test_conn:
            module_logger.info("Test DB connection successful (Psycopg 3).")
            try:
                with test_conn.cursor() as cur: # Psycopg 3: Cursor from connection
                    cur.execute("SELECT version();")
                    pg_version = cur.fetchone()
                    if pg_version:
                        module_logger.info(
                            f"PostgreSQL version: {pg_version[0]}"
                        )
            except Exception as e_db_test:
                module_logger.error(
                    f"Error executing test query with Psycopg 3: {e_db_test}"
                )
            finally:
                # Psycopg 3: Connection should be explicitly closed if not using a 'with psycopg.connect(...)' block.
                if test_conn and not test_conn.closed:
                     test_conn.close()
            module_logger.info("Test DB connection closed (Psycopg 3).")
        else:
            module_logger.error("Test DB connection FAILED (Psycopg 3).")

    module_logger.info("--- osm.processors.gtfs.utils.py test finished ---")