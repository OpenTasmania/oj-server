#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GTFS Update Module for Standalone Execution.

This module provides functionality for running a full GTFS ETL (Extract,
Transform, Load) pipeline. It downloads a GTFS feed, processes it according
to predefined schema definitions, and loads the data into a PostgreSQL database.
It is designed to be usable as a standalone script, potentially for cron jobs
or direct execution, and includes its own schema definitions and ETL orchestration.

It can also attempt to use `processors.gtfs.main_pipeline` if available,
allowing it to act as a wrapper or entry point.
"""

import argparse
import io
import logging
import os
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

import pandas as pd
import psycopg2
import requests
from psycopg2 import sql
from psycopg2.extensions import connection as PgConnection

# Attempt to import from the main GTFS processing package.
# This allows the script to leverage a more structured pipeline if available.
try:
    from processors.gtfs import main_pipeline
except (ImportError, ValueError):
    # If running as a standalone script or if the package is not in PYTHONPATH,
    # these imports might fail. The script will then use its own pipeline logic.
    main_pipeline = None
    # Indicate that the main_pipeline module is not available.
    # The script's own `run_full_gtfs_etl_pipeline` will be used as a fallback.

# Configuration: Default values for database connection, paths, and feed URL.
# These can be overridden by environment variables or command-line arguments.

# Default database connection parameters.
# Environment variables (e.g., PG_GIS_DB, PG_OSM_USER) take precedence.
DB_PARAMS: Dict[str, str] = {
    "dbname": os.environ.get("PG_GIS_DB", "gis"),
    "user": os.environ.get("PG_OSM_USER", "osmuser"),
    "password": os.environ.get("PG_OSM_PASSWORD", "yourStrongPasswordHere"),
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": os.environ.get("PG_PORT", "5432"),
}

# Default paths for downloaded and extracted GTFS feed data.
DOWNLOAD_PATH = "/tmp/gtfs_download.zip"
EXTRACT_PATH = "/tmp/gtfs_extracted/"

# Default log file path.
LOG_FILE = "/var/log/update_gtfs.log"

# Default GTFS Feed URL -  IMPORTANT: This should be overridden via environment
# variable `GTFS_FEED_URL` or a command-line argument for actual use.
# The `setup.config` import is commented out as this script aims for standalone
# capability first, relying on its own config or env vars.
# from setup.config import GTFS_FEED_URL as DEFAULT_GTFS_URL_FROM_CONFIG
DEFAULT_GTFS_URL = os.environ.get(
    "GTFS_FEED_URL", "https://example.com/path/to/your/gtfs-feed.zip"
)


# Configure module-level logger.
# The `setup_logging` function in this script will further configure handlers.
module_logger = logging.getLogger(__name__)


# --- GTFS Schema Definitions (Embedded for Standalone Use) ---
# These definitions specify table names, column types, constraints,
# and required fields for each GTFS file.
# Note: This is a duplication if `schema_definitions.py` is also used.
# For a fully standalone script, these are necessary here.

GTFS_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "agency.txt": {
        "table_name": "gtfs_agency",
        "columns": [
            ("agency_id", "TEXT", "PRIMARY KEY"), # Conditionally optional in spec
            ("agency_name", "TEXT", "NOT NULL"),
            ("agency_url", "TEXT", "NOT NULL"),
            ("agency_timezone", "TEXT", "NOT NULL"),
            ("agency_lang", "TEXT", ""),
            ("agency_phone", "TEXT", ""),
            ("agency_fare_url", "TEXT", ""),
            ("agency_email", "TEXT", ""),
        ],
        "required_fields_in_file": [ # Fields that must be present in the CSV header
            "agency_name", "agency_url", "agency_timezone",
        ],
    },
    "stops.txt": {
        "table_name": "gtfs_stops",
        "columns": [
            ("stop_id", "TEXT", "PRIMARY KEY"),
            ("stop_code", "TEXT", ""),
            ("stop_name", "TEXT", ""), # Conditionally required by spec
            ("stop_desc", "TEXT", ""),
            ("stop_lat", "DOUBLE PRECISION", ""), # Required if location_type is 0 or 1
            ("stop_lon", "DOUBLE PRECISION", ""), # Required if location_type is 0 or 1
            ("zone_id", "TEXT", ""),
            ("stop_url", "TEXT", ""),
            ("location_type", "INTEGER", ""), # 0-4
            ("parent_station", "TEXT", ""), # FK to stops.stop_id
            ("stop_timezone", "TEXT", ""),
            ("wheelchair_boarding", "INTEGER", ""), # 0, 1, or 2
            ("geom", "GEOMETRY(Point, 4326)", ""), # Derived from stop_lat, stop_lon
        ],
        "required_fields_in_file": ["stop_id"], # stop_lat, stop_lon are also key
    },
    "routes.txt": {
        "table_name": "gtfs_routes",
        "columns": [
            ("route_id", "TEXT", "PRIMARY KEY"),
            ("agency_id", "TEXT", ""), # FK to agency.agency_id, cond. required
            ("route_short_name", "TEXT", "DEFAULT ''"),
            ("route_long_name", "TEXT", "DEFAULT ''"), # One of short/long must be provided
            ("route_desc", "TEXT", ""),
            ("route_type", "INTEGER", "NOT NULL"), # Defined set of integers
            ("route_url", "TEXT", ""),
            ("route_color", "TEXT", ""), # Hex color
            ("route_text_color", "TEXT", ""), # Hex color
            ("route_sort_order", "INTEGER", ""), # Non-negative
        ],
        "required_fields_in_file": ["route_id", "route_type"],
    },
    "trips.txt": {
        "table_name": "gtfs_trips",
        "columns": [
            ("route_id", "TEXT", "NOT NULL"), # FK to routes.route_id
            ("service_id", "TEXT", "NOT NULL"), # FK to calendar.service_id or calendar_dates.service_id
            ("trip_id", "TEXT", "PRIMARY KEY"),
            ("trip_headsign", "TEXT", ""),
            ("trip_short_name", "TEXT", ""),
            ("direction_id", "INTEGER", ""), # 0 or 1
            ("block_id", "TEXT", ""),
            ("shape_id", "TEXT", ""), # FK to shapes.shape_id (from shapes.txt)
            ("wheelchair_accessible", "INTEGER", ""), # 0, 1, or 2
            ("bikes_allowed", "INTEGER", ""), # 0, 1, or 2
        ],
        "required_fields_in_file": ["route_id", "service_id", "trip_id"],
    },
    "stop_times.txt": {
        "table_name": "gtfs_stop_times",
        "columns": [
            ("trip_id", "TEXT", "NOT NULL"), # FK to trips.trip_id
            ("arrival_time", "TEXT", ""), # HH:MM:SS format
            ("departure_time", "TEXT", ""), # HH:MM:SS format
            ("stop_id", "TEXT", "NOT NULL"), # FK to stops.stop_id
            ("stop_sequence", "INTEGER", "NOT NULL"), # Non-negative, increasing
            ("stop_headsign", "TEXT", ""),
            ("pickup_type", "INTEGER", ""), # 0-3
            ("drop_off_type", "INTEGER", ""), # 0-3
            ("shape_dist_traveled", "DOUBLE PRECISION", ""), # Non-negative
            ("timepoint", "INTEGER", ""), # 0 or 1
        ],
        "composite_pk": ["trip_id", "stop_sequence"],
        "required_fields_in_file": ["trip_id", "stop_id", "stop_sequence"],
        # arrival_time and departure_time are conditionally required.
    },
    "calendar.txt": { # Conditionally required file
        "table_name": "gtfs_calendar",
        "columns": [
            ("service_id", "TEXT", "PRIMARY KEY"),
            ("monday", "INTEGER", "NOT NULL"), # 0 or 1
            ("tuesday", "INTEGER", "NOT NULL"),
            ("wednesday", "INTEGER", "NOT NULL"),
            ("thursday", "INTEGER", "NOT NULL"),
            ("friday", "INTEGER", "NOT NULL"),
            ("saturday", "INTEGER", "NOT NULL"),
            ("sunday", "INTEGER", "NOT NULL"),
            ("start_date", "TEXT", "NOT NULL"), # YYYYMMDD
            ("end_date", "TEXT", "NOT NULL"), # YYYYMMDD
        ],
        "required_fields_in_file": [
            "service_id", "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday", "start_date", "end_date",
        ],
    },
    "calendar_dates.txt": { # Conditionally required file
        "table_name": "gtfs_calendar_dates",
        "columns": [
            ("service_id", "TEXT", "NOT NULL"), # FK to calendar.service_id
            ("date", "TEXT", "NOT NULL"), # YYYYMMDD
            ("exception_type", "INTEGER", "NOT NULL"), # 1 or 2
        ],
        "composite_pk": ["service_id", "date"],
        "required_fields_in_file": ["service_id", "date", "exception_type"],
    },
    "shapes.txt": { # Optional file
        "table_name": "gtfs_shapes_points", # Staging table for points
        "columns": [
            ("shape_id", "TEXT", "NOT NULL"),
            ("shape_pt_lat", "DOUBLE PRECISION", "NOT NULL"),
            ("shape_pt_lon", "DOUBLE PRECISION", "NOT NULL"),
            ("shape_pt_sequence", "INTEGER", "NOT NULL"), # Non-negative, increasing
            ("shape_dist_traveled", "DOUBLE PRECISION", ""), # Non-negative
        ],
        "composite_pk": ["shape_id", "shape_pt_sequence"],
        "required_fields_in_file": [
            "shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence",
        ],
    },
    # Other optional files like fare_attributes.txt, fare_rules.txt,
    # frequencies.txt, transfers.txt, feed_info.txt could be added here.
}

# Defines the order in which GTFS files should be processed and loaded
# to respect dependencies (e.g., load agencies and routes before trips).
GTFS_LOAD_ORDER: List[str] = [
    "agency.txt",
    "stops.txt",
    "routes.txt",
    "calendar.txt",       # Must be loaded before trips if trips reference its service_ids
    "calendar_dates.txt", # Must be loaded before trips for same reason
    "shapes.txt",         # For shape points, lines aggregated later
    "trips.txt",
    "stop_times.txt",
    # Add other files like frequencies.txt, transfers.txt here if supported.
]

# Defines foreign key relationships between GTFS tables.
# Format: (from_table, [from_columns], to_table, [to_columns], fk_name)
GTFS_FOREIGN_KEYS: List[Tuple[str, List[str], str, List[str], str]] = [
    ("gtfs_routes", ["agency_id"], "gtfs_agency", ["agency_id"], "fk_routes_agency_id"),
    ("gtfs_trips", ["route_id"], "gtfs_routes", ["route_id"], "fk_trips_route_id"),
    # Assuming gtfs_shapes_lines table is created from gtfs_shapes_points
    ("gtfs_trips", ["shape_id"], "gtfs_shapes_lines", ["shape_id"], "fk_trips_shape_id_lines"),
    ("gtfs_stop_times", ["trip_id"], "gtfs_trips", ["trip_id"], "fk_stop_times_trip_id"),
    ("gtfs_stop_times", ["stop_id"], "gtfs_stops", ["stop_id"], "fk_stop_times_stop_id"),
    ("gtfs_stops", ["parent_station"], "gtfs_stops", ["stop_id"], "fk_stops_parent_station"),
    # calendar_dates.service_id could FK to calendar.service_id, but GTFS allows
    # service_ids to exist only in calendar_dates.txt.
]


def sanitize_identifier(name: str) -> str:
    """Sanitize SQL identifiers (table/column names) by quoting them."""
    return '"' + name.replace('"', '""').strip() + '"'


def create_tables_from_schema(conn: PgConnection) -> None:
    """
    Create database tables based on GTFS_DEFINITIONS if they don't exist.

    Also creates `gtfs_shapes_lines` for aggregated shape geometries and
    a `gtfs_dlq` (Dead-Letter Queue) table for logging problematic data.

    Args:
        conn: Active psycopg2 database connection.
    """
    module_logger.info("Setting up database schema based on GTFS_DEFINITIONS...")
    with conn.cursor() as cursor:
        for filename in GTFS_LOAD_ORDER:
            if filename not in GTFS_DEFINITIONS:
                module_logger.debug(f"No definition for '{filename}', skipping table creation.")
                continue

            details = GTFS_DEFINITIONS[filename]
            table_name = details["table_name"]
            cols_defs_str_list: List[str] = []
            for col_name, col_type, col_constraints in details["columns"]:
                cols_defs_str_list.append(
                    f"{sanitize_identifier(col_name)} {col_type} {col_constraints}"
                )

            cols_sql_segment = sql.SQL(", ").join(map(sql.SQL, cols_defs_str_list))
            pk_def_sql_segment = sql.SQL("")

            if "composite_pk" in details and details["composite_pk"]:
                quoted_pks = [sql.Identifier(pk_col) for pk_col in details["composite_pk"]]
                pk_def_sql_segment = sql.SQL(", PRIMARY KEY ({})").format(
                    sql.SQL(", ").join(quoted_pks)
                )

            create_sql = sql.SQL("CREATE TABLE IF NOT EXISTS {} ({}{});").format(
                sql.Identifier(table_name), cols_sql_segment, pk_def_sql_segment
            )
            try:
                module_logger.debug(
                    f"Executing SQL for table {table_name}: {create_sql.as_string(conn)}"
                )
                cursor.execute(create_sql)
            except psycopg2.Error as e:
                module_logger.error(f"Error creating table {table_name}: {e}")
                raise # Propagate error to stop execution if table creation fails.

        # Create gtfs_shapes_lines table for aggregated shape geometries.
        try:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS gtfs_shapes_lines (
                    shape_id TEXT PRIMARY KEY,
                    geom GEOMETRY(LineString, 4326)
                );
                """
            )
            module_logger.info("Table 'gtfs_shapes_lines' ensured.")
        except psycopg2.Error as e:
            module_logger.error(f"Error creating table gtfs_shapes_lines: {e}")
            raise

        # Create Dead-Letter Queue (DLQ) table for logging problematic data.
        try:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS gtfs_dlq (
                    id SERIAL PRIMARY KEY,
                    gtfs_filename TEXT,
                    original_row_data TEXT, -- Could be JSONB for structured data
                    error_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    error_reason TEXT,
                    notes TEXT
                );
                """
            )
            module_logger.info("DLQ table 'gtfs_dlq' ensured.")
        except psycopg2.Error as e:
            module_logger.error(f"Error creating DLQ table gtfs_dlq: {e}")
            # Non-critical, log and continue if DLQ table creation fails.
    module_logger.info("Database schema setup/verification complete.")


def drop_all_gtfs_foreign_keys(conn: PgConnection) -> None:
    """
    Drop all defined GTFS foreign keys.

    This is typically done before a full data reload to avoid FK constraint
    violations during loading of individual tables. Keys are dropped in
    reverse order of definition.

    Args:
        conn: Active psycopg2 database connection.
    """
    module_logger.info("Dropping existing GTFS foreign keys before data load...")
    with conn.cursor() as cursor:
        # Iterate in reverse to handle dependencies.
        for from_table, _, _, _, fk_name in reversed(GTFS_FOREIGN_KEYS):
            # Check if the 'from_table' exists before trying to alter it.
            cursor.execute("SELECT to_regclass(%s);", (f"public.{from_table}",))
            if not cursor.fetchone()[0]:
                module_logger.debug(
                    f"Table {from_table} for FK {fk_name} does not exist. "
                    "Skipping FK drop."
                )
                continue

            # Check if the constraint exists.
            cursor.execute(
                """
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_type = 'FOREIGN KEY'
                  AND constraint_name = %s
                  AND table_name = %s;
                """,
                (fk_name, from_table),
            )
            if cursor.fetchone():
                try:
                    module_logger.info(
                        f"Dropping foreign key {fk_name} from {from_table}."
                    )
                    cursor.execute(
                        sql.SQL("ALTER TABLE {} DROP CONSTRAINT IF EXISTS {};").format(
                            sql.Identifier(from_table), sql.Identifier(fk_name)
                        )
                    )
                except psycopg2.Error as e:
                    module_logger.warning(
                        f"Could not drop foreign key {fk_name} from "
                        f"{from_table}: {e}. This might be acceptable if "
                        "the table was just created or FK was already dropped."
                    )
            else:
                module_logger.debug(
                    f"Foreign key {fk_name} on {from_table} does not exist. "
                    "Skipping drop."
                )
    module_logger.info("Finished attempting to drop GTFS foreign keys.")


def add_foreign_keys_from_schema(conn: PgConnection) -> None:
    """
    Add foreign keys based on GTFS_FOREIGN_KEYS definitions.

    This is typically done after all data has been loaded. Foreign keys are
    created as DEFERRABLE INITIALLY DEFERRED to handle potential out-of-order
    references that resolve by the end of the transaction.

    Args:
        conn: Active psycopg2 database connection.
    """
    module_logger.info("Attempting to add foreign keys post-data load...")
    with conn.cursor() as cursor:
        for from_table, from_cols_list, to_table, to_cols_list, fk_name \
                in GTFS_FOREIGN_KEYS:
            # Check if source and target tables exist.
            cursor.execute("SELECT to_regclass(%s);", (f"public.{from_table}",))
            if not cursor.fetchone()[0]:
                module_logger.warning(
                    f"Source Table {from_table} for FK {fk_name} does not exist. "
                    "Skipping FK creation."
                )
                continue
            cursor.execute("SELECT to_regclass(%s);", (f"public.{to_table}",))
            if not cursor.fetchone()[0]:
                module_logger.warning(
                    f"Target Table {to_table} for FK {fk_name} does not exist. "
                    "Skipping FK creation."
                )
                continue

            from_cols_sql = sql.SQL(", ").join(map(sql.Identifier, from_cols_list))
            to_cols_sql = sql.SQL(", ").join(map(sql.Identifier, to_cols_list))

            alter_sql = sql.SQL(
                "ALTER TABLE {} ADD CONSTRAINT {} FOREIGN KEY ({}) "
                "REFERENCES {} ({}) DEFERRABLE INITIALLY DEFERRED;"
            ).format(
                sql.Identifier(from_table), sql.Identifier(fk_name),
                from_cols_sql, sql.Identifier(to_table), to_cols_sql,
            )
            try:
                module_logger.info(
                    f"Adding FK {fk_name} on {from_table}({', '.join(from_cols_list)})"
                    f" -> {to_table}({', '.join(to_cols_list)})"
                )
                cursor.execute(alter_sql)
            except psycopg2.Error as e:
                module_logger.error(
                    f"Could not add foreign key {fk_name}: {e}", exc_info=True
                )
                # Log failure to DLQ for investigation.
                try:
                    # Use a separate cursor for DLQ if main one is in error state.
                    with conn.cursor() as dlq_cursor: # New cursor context
                        dlq_cursor.execute(
                            "INSERT INTO gtfs_dlq (gtfs_filename, error_reason, notes) "
                            "VALUES (%s, %s, %s);",
                            ("SCHEMA_FK_ERROR", str(e)[:1000], # Truncate error if too long
                             f"Failed to add FK: {fk_name}")
                        )
                    # Committing DLQ log separately can be risky if main transaction
                    # needs to rollback. Consider if this commit is appropriate.
                    # conn.commit()
                except Exception as dlq_e:
                    module_logger.error(f"Failed to log FK error to DLQ: {dlq_e}")
    module_logger.info("Foreign key application process finished.")


def download_and_extract_gtfs(feed_url: str) -> bool:
    """
    Download a GTFS feed from a URL and extract its contents.

    Uses DOWNLOAD_PATH and EXTRACT_PATH constants for file locations.

    Args:
        feed_url: The URL of the GTFS feed zip file.

    Returns:
        True if download and extraction were successful, False otherwise.

    Raises:
        ValueError: If the `feed_url` is a placeholder.
    """
    module_logger.info(f"Starting GTFS download from {feed_url}")
    if feed_url == "https://example.com/path/to/your/gtfs-feed.zip":
        module_logger.critical(
            "GTFS_URL is a placeholder. Please set it via environment "
            "variable GTFS_FEED_URL or CLI argument."
        )
        raise ValueError("GTFS_URL not configured.")

    try:
        response = requests.get(feed_url, timeout=120) # 2-minute timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        Path(DOWNLOAD_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(DOWNLOAD_PATH, "wb") as f:
            f.write(response.content)
        module_logger.info(f"GTFS feed downloaded to {DOWNLOAD_PATH}")

        module_logger.info(f"Unzipping {DOWNLOAD_PATH} to {EXTRACT_PATH}")
        if os.path.exists(EXTRACT_PATH):
            shutil.rmtree(EXTRACT_PATH) # Clear existing extraction directory
        os.makedirs(EXTRACT_PATH, exist_ok=True)

        with zipfile.ZipFile(DOWNLOAD_PATH, "r") as zip_ref:
            zip_ref.extractall(EXTRACT_PATH)
        module_logger.info("GTFS feed unzipped successfully.")
        return True
    except requests.exceptions.RequestException as re:
        module_logger.error(f"Download Error: {re}", exc_info=True)
    except zipfile.BadZipFile as bze:
        module_logger.error(f"Unzip Error: Bad Zip File from {DOWNLOAD_PATH}. {bze}", exc_info=True)
    except Exception as e:
        module_logger.error(f"Unexpected error in download/extract: {e}", exc_info=True)
    return False


def load_data_to_db_with_dlq(conn: PgConnection) -> None:
    """
    Load data from extracted GTFS files into database tables with DLQ support.

    Iterates through GTFS files in GTFS_LOAD_ORDER, reads them into Pandas
    DataFrames, performs basic column mapping, and uses PostgreSQL's COPY
    command for efficient loading. Handles geometry updates for `gtfs_stops`
    and aggregation for `gtfs_shapes_lines`. Failures are logged to `gtfs_dlq`.

    Args:
        conn: Active psycopg2 database connection.

    Raises:
        ValueError: If a required column is missing in a GTFS file.
        psycopg2.Error: For database errors during TRUNCATE, COPY, or geometry updates.
        Exception: For other unexpected errors during file processing.
    """
    module_logger.info("Starting data loading process into database tables.")
    available_files_in_feed = {
        f.lower() for f in os.listdir(EXTRACT_PATH) if f.endswith(".txt")
    }
    module_logger.info(
        f"Files found in GTFS feed for loading: {available_files_in_feed}"
    )

    with conn.cursor() as cursor:
        for gtfs_filename_key in GTFS_LOAD_ORDER:
            actual_file_to_load = None
            # Find the actual filename in the directory (case-insensitive match)
            for f_in_dir in os.listdir(EXTRACT_PATH):
                if (f_in_dir.lower() == gtfs_filename_key.lower() and
                        f_in_dir.endswith(".txt")):
                    actual_file_to_load = f_in_dir
                    break

            if not actual_file_to_load:
                if gtfs_filename_key in GTFS_DEFINITIONS: # Check if it's a defined file
                    module_logger.warning(
                        f"Expected GTFS file '{gtfs_filename_key}' not found in "
                        "archive. Skipping."
                    )
                # If not in GTFS_DEFINITIONS, it's fine if it's missing (e.g. optional files)
                continue

            schema_info = GTFS_DEFINITIONS[gtfs_filename_key]
            table_name = schema_info["table_name"]
            filepath = os.path.join(EXTRACT_PATH, actual_file_to_load)

            module_logger.info(
                f"--- Processing {actual_file_to_load} for table {table_name} ---"
            )
            actual_load_cols: List[str] = [] # Columns that will be in the COPY statement

            try:
                df = pd.read_csv(
                    filepath,
                    dtype=str, # Read all as string initially
                    keep_default_na=False, # Keep empty strings as is
                    na_filter=False, # Don't interpret "NA", "NULL" as NaN
                    encoding="utf-8-sig", # Handle potential BOM
                )

                if df.empty:
                    module_logger.info(
                        f"File {actual_file_to_load} is empty. "
                        f"Skipping table {table_name}."
                    )
                    continue

                # Prepare DataFrame for COPY: select and rename columns as per schema.
                # This section ensures DataFrame columns match DB table columns.
                df_for_copy = pd.DataFrame()
                csv_header_stripped = [col.strip() for col in df.columns]
                df.columns = csv_header_stripped # Use stripped headers

                # Get DB column names from schema, excluding 'geom' if it's derived.
                table_db_columns_from_schema = [
                    col_def[0] for col_def in schema_info["columns"]
                    if col_def[0] != "geom" # 'geom' is handled separately if derived
                ]

                for db_col_name in table_db_columns_from_schema:
                    if db_col_name in csv_header_stripped:
                        df_for_copy[db_col_name] = df[db_col_name]
                        actual_load_cols.append(db_col_name)
                    else:
                        # Check if missing column is required by spec or DB schema.
                        is_required_by_spec = db_col_name in schema_info.get(
                            "required_fields_in_file", []
                        )
                        is_not_null_in_db = any(
                            c[0] == db_col_name and
                            "NOT NULL" in c[2].upper() and
                            "DEFAULT" not in c[2].upper() # Consider DEFAULT if present
                            for c in schema_info["columns"]
                        )
                        if is_required_by_spec or is_not_null_in_db:
                            err_msg = (
                                f"Required/NOT NULL column '{db_col_name}' for "
                                f"table '{table_name}' missing in CSV file "
                                f"'{actual_file_to_load}'."
                            )
                            module_logger.error(err_msg)
                            cursor.execute(
                                "INSERT INTO gtfs_dlq (gtfs_filename, error_reason, notes) "
                                "VALUES (%s, %s, %s);",
                                (actual_file_to_load, err_msg,
                                 "Whole file load skipped due to missing required column.")
                            )
                            raise ValueError(err_msg) # Fail fast for this file
                        else:
                            # Optional column missing in CSV, add as series of Nones.
                            df_for_copy[db_col_name] = pd.Series([None] * len(df), dtype=object)
                            actual_load_cols.append(db_col_name)

                if not actual_load_cols:
                    module_logger.warning(
                        f"No columns to load for {table_name} from "
                        f"{actual_file_to_load} after schema mapping. Skipping."
                    )
                    continue

                # Truncate table before loading.
                cursor.execute(
                    sql.SQL("TRUNCATE TABLE {} CASCADE;").format(
                        sql.Identifier(table_name)
                    )
                )
                module_logger.info(f"Table {table_name} truncated.")

                # Use StringIO to pass DataFrame to COPY command.
                sio = io.StringIO()
                # Select only 'actual_load_cols' for to_csv and ensure order.
                df_for_copy[actual_load_cols].to_csv(
                    sio, index=False, header=True, sep=",",
                    quotechar='"', escapechar="\\", na_rep="" # Empty string for NULLs in COPY
                )
                sio.seek(0)

                # Construct COPY statement.
                db_cols_sql_identifiers = sql.SQL(", ").join(
                    map(sql.Identifier, actual_load_cols)
                )
                copy_sql_stmt = sql.SQL(
                    "COPY {} ({}) FROM STDIN WITH CSV HEADER DELIMITER ',' "
                    "QUOTE '\"' ESCAPE '\\' NULL AS '';"
                ).format(sql.Identifier(table_name), db_cols_sql_identifiers)

                module_logger.debug(
                    f"Executing COPY for {table_name} with {len(df_for_copy)} "
                    f"records. Columns: {actual_load_cols}"
                )
                cursor.copy_expert(copy_sql_stmt, sio)
                loaded_count = cursor.rowcount if cursor.rowcount is not None else len(df_for_copy)
                module_logger.info(f"{loaded_count} records loaded into {table_name}.")

                # Post-load processing: Geometry update for gtfs_stops.
                if table_name == "gtfs_stops":
                    lat_col, lon_col, geom_col = "stop_lat", "stop_lon", "geom"
                    # Ensure lat/lon columns were actually loaded.
                    if lat_col in actual_load_cols and lon_col in actual_load_cols:
                        # SQL to update geometry from lat/lon columns.
                        # Handles empty strings or non-numeric values gracefully using NULLIF and CAST.
                        update_geom_sql = sql.SQL(
                            "UPDATE {} SET {} = ST_SetSRID(ST_MakePoint("
                            "   CAST(NULLIF(TRIM(CAST({} AS TEXT)), '') AS DOUBLE PRECISION), "
                            "   CAST(NULLIF(TRIM(CAST({} AS TEXT)), '') AS DOUBLE PRECISION) "
                            "), 4326) "
                            "WHERE " # Only update rows with valid lat/lon text
                            "   NULLIF(TRIM(CAST({} AS TEXT)), '') IS NOT NULL AND "
                            "   NULLIF(TRIM(CAST({} AS TEXT)), '') IS NOT NULL;"
                        ).format(
                            sql.Identifier(table_name), sql.Identifier(geom_col),
                            sql.Identifier(lon_col), sql.Identifier(lat_col), # Lon, Lat order for ST_MakePoint
                            sql.Identifier(lon_col), sql.Identifier(lat_col),
                        )
                        try:
                            cursor.execute(update_geom_sql)
                            module_logger.info(
                                f"Geometry updated for {table_name} "
                                f"({cursor.rowcount} rows affected)."
                            )
                        except psycopg2.Error as geom_e:
                            module_logger.error(
                                f"Error updating geometry for {table_name}: {geom_e}",
                                exc_info=True,
                            )
                            raise geom_e # Re-raise to fail the transaction
                    else:
                        module_logger.warning(
                            f"Could not update geometry for {table_name}: "
                            f"'{lat_col}' or '{lon_col}' not in processed columns: "
                            f"{actual_load_cols}"
                        )
            except ValueError as ve: # Raised if required column is missing
                module_logger.error(
                    f"ValueError processing {actual_file_to_load} for "
                    f"{table_name}: {ve}. File processing aborted for this file."
                )
                raise # Propagate to rollback transaction for this file's load
            except psycopg2.Error as db_err: # Catch DB errors from TRUNCATE, COPY, GEOM_UPDATE
                module_logger.error(
                    f"Database error processing {actual_file_to_load} for "
                    f"{table_name}: {db_err}", exc_info=True
                )
                # Log to DLQ
                with conn.cursor() as dlq_cursor_err: # Use a new cursor for DLQ logging
                    dlq_cursor_err.execute(
                        "INSERT INTO gtfs_dlq (gtfs_filename, error_reason, notes) "
                        "VALUES (%s, %s, %s);",
                        (actual_file_to_load, str(db_err)[:1000],
                         f"DB error during COPY/TRUNCATE/GEOM_UPDATE for table {table_name}")
                    )
                # conn.commit() # Consider if DLQ entries should be committed independently
                raise # Propagate to rollback main transaction
            except Exception as e: # Catch any other unexpected errors
                module_logger.error(
                    f"Unexpected error processing file {actual_file_to_load} "
                    f"for table {table_name}: {e}", exc_info=True
                )
                with conn.cursor() as dlq_cursor_unexp:
                    dlq_cursor_unexp.execute(
                        "INSERT INTO gtfs_dlq (gtfs_filename, error_reason, notes) "
                        "VALUES (%s, %s, %s);",
                        (actual_file_to_load, str(e)[:1000],
                         f"Unexpected error for table {table_name}")
                    )
                raise

        # Post-load processing: Aggregate shapes.txt points into linestrings.
        if ("shapes.txt" in GTFS_DEFINITIONS and
                "shapes.txt".lower() in available_files_in_feed):
            try:
                module_logger.info(
                    "Aggregating shape points into linestrings (gtfs_shapes_lines)..."
                )
                cursor.execute("TRUNCATE TABLE gtfs_shapes_lines CASCADE;")
                # SQL to aggregate points into linestrings, ordered by sequence.
                # Ensures points are valid numbers and more than one point exists per shape.
                cursor.execute(
                    """
                    INSERT INTO gtfs_shapes_lines (shape_id, geom)
                    SELECT
                        shape_id,
                        ST_MakeLine(
                            ST_SetSRID(ST_MakePoint(
                                CAST(NULLIF(TRIM(CAST(shape_pt_lon AS TEXT)), '') AS DOUBLE PRECISION),
                                CAST(NULLIF(TRIM(CAST(shape_pt_lat AS TEXT)), '') AS DOUBLE PRECISION)
                            ), 4326)
                            ORDER BY CAST(NULLIF(TRIM(CAST(shape_pt_sequence AS TEXT)), '') AS INTEGER)
                        ) AS line_geom
                    FROM gtfs_shapes_points
                    WHERE
                        NULLIF(TRIM(CAST(shape_pt_lon AS TEXT)), '') IS NOT NULL AND
                        NULLIF(TRIM(CAST(shape_pt_lat AS TEXT)), '') IS NOT NULL AND
                        NULLIF(TRIM(CAST(shape_pt_sequence AS TEXT)), '') IS NOT NULL
                    GROUP BY shape_id
                    HAVING count(*) > 1;
                    """
                )
                module_logger.info(
                    f"Shape linestrings aggregated ({cursor.rowcount} shapes)."
                )
            except Exception as e_shape:
                module_logger.error(
                    f"Error aggregating shape linestrings: {e_shape}", exc_info=True
                )
                with conn.cursor() as dlq_cursor_shape:
                    dlq_cursor_shape.execute(
                        "INSERT INTO gtfs_dlq (gtfs_filename, error_reason, notes) "
                        "VALUES (%s, %s, %s);",
                        ("shapes.txt", f"Aggregation to lines failed: {str(e_shape)[:1000]}",
                         "gtfs_shapes_lines might be incomplete")
                    )
                raise # Let main transaction fail if shape aggregation is critical.
    module_logger.info("Data loading process completed.")


def run_full_gtfs_etl_pipeline(feed_url_override: Optional[str] = None) -> bool:
    """
    Orchestrate the full GTFS ETL (Extract, Transform, Load) pipeline.

    This function is the main entry point for standalone execution of the
    GTFS update process. It handles downloading, schema setup, data loading,
    and foreign key creation.

    Args:
        feed_url_override: Optional URL to override the default GTFS feed URL.

    Returns:
        True if the pipeline completed successfully, False otherwise.
    """
    start_time = datetime.now()
    module_logger.info(
        f"=== Starting GTFS Full Update Process at {start_time.isoformat()} ==="
    )
    conn: Optional[PgConnection] = None
    success = False
    effective_feed_url = feed_url_override or DEFAULT_GTFS_URL

    try:
        # Validate configurations.
        if effective_feed_url == "https://example.com/path/to/your/gtfs-feed.zip":
            msg = ("CRITICAL: GTFS_URL is a placeholder. Set GTFS_FEED_URL "
                   "environment variable or use --gtfs-url CLI argument.")
            module_logger.critical(msg)
            raise ValueError(msg)

        if DB_PARAMS["password"] == "yourStrongPasswordHere" and \
           not os.environ.get("PG_OSM_PASSWORD"): # Check env var too
            msg = ("CRITICAL: Database password is the default placeholder and "
                   "PG_OSM_PASSWORD env var is not set. Update DB_PARAMS or set env var.")
            module_logger.critical(msg)
            raise ValueError(msg)

        # 1. Download and Extract GTFS feed.
        if not download_and_extract_gtfs(effective_feed_url):
            # Error already logged by download_and_extract_gtfs.
            raise Exception("GTFS feed download or extraction failed.")

        # 2. Connect to Database.
        conn = psycopg2.connect(**DB_PARAMS)
        conn.autocommit = False # Manage transactions explicitly.
        module_logger.info("Database connection successful. Transaction started.")

        # 3. Setup Database Schema (Create tables if not exist).
        create_tables_from_schema(conn)
        conn.commit()  # Commit schema changes separately and first.

        # 4. Prepare for Data Load: Drop existing foreign keys.
        drop_all_gtfs_foreign_keys(conn)
        conn.commit()  # Commit FK drops.

        # 5. Load Data into Tables.
        # This occurs in a new transaction block implicitly after commit.
        load_data_to_db_with_dlq(conn)

        # 6. Recreate Foreign Keys.
        add_foreign_keys_from_schema(conn)

        conn.commit() # Commit data load and FK creation.
        success = True
        module_logger.info(
            "All GTFS processing steps completed and committed successfully."
        )

    except ValueError as ve: # Configuration errors
        module_logger.critical(f"Configuration/Validation Error: {ve}")
        if conn and not conn.closed:
            conn.rollback()
    except Exception as e: # Catch all other exceptions during the pipeline
        module_logger.critical(
            f"A critical error occurred during the GTFS update process: {e}",
            exc_info=True,
        )
        if conn and not conn.closed:
            conn.rollback()
    finally:
        # 7. Cleanup
        if conn and not conn.closed:
            conn.close()
            module_logger.info("Database connection closed.")

        if os.path.exists(DOWNLOAD_PATH):
            try:
                os.remove(DOWNLOAD_PATH)
                module_logger.info(f"Cleaned up download file: {DOWNLOAD_PATH}")
            except OSError as e_clean_dl:
                module_logger.error(
                    f"Error removing download file '{DOWNLOAD_PATH}': {e_clean_dl}"
                )
        if os.path.exists(EXTRACT_PATH):
            try:
                shutil.rmtree(EXTRACT_PATH)
                module_logger.info(f"Cleaned up extract directory: {EXTRACT_PATH}")
            except OSError as e_clean_ext:
                module_logger.error(
                    f"Error removing extract directory '{EXTRACT_PATH}': {e_clean_ext}"
                )
        module_logger.info("Cleanup of temporary files attempted.")

        end_time = datetime.now()
        duration = end_time - start_time
        if success:
            module_logger.info(
                f"GTFS Full Update Process completed successfully at "
                f"{end_time.isoformat()}. Duration: {duration}"
            )
        else:
            module_logger.error(
                f"GTFS Full Update Process FAILED at {end_time.isoformat()}. "
                f"Duration: {duration}"
            )
        module_logger.info("=== GTFS Full Update Process Finished ===")
    return success


def setup_logging(
    log_level_str: str = "INFO", # Changed to string for argparse
    log_file_path: Optional[str] = LOG_FILE, # Use constant
    log_to_console: bool = True
) -> None:
    """
    Set up logging configuration for the script.

    Args:
        log_level_str: The logging level as a string (e.g., "INFO", "DEBUG").
        log_file_path: Path to the log file. Defaults to LOG_FILE constant.
        log_to_console: Whether to log to console (stdout).
    """
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    if not isinstance(log_level, int): # Fallback if string is invalid
        print(f"Warning: Invalid log level string '{log_level_str}'. Defaulting to INFO.", file=sys.stderr)
        log_level = logging.INFO


    # Clear existing handlers from the root logger to avoid duplicate logs
    # if this function is called multiple times or by different modules.
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    handlers: List[logging.Handler] = []
    if log_file_path:
        try:
            # Ensure log directory exists
            Path(log_file_path).parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file_path, mode="a") # Append mode
            handlers.append(file_handler)
        except Exception as e_fh:
            print(f"Error setting up file logger for {log_file_path}: {e_fh}", file=sys.stderr)


    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        handlers.append(console_handler)

    if not handlers: # Ensure at least console output if others fail or are off
        handlers.append(logging.StreamHandler(sys.stdout))
        if log_level > logging.INFO: # Ensure some output if level was too high
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
    # Ensure the root logger's level is also set.
    logging.getLogger().setLevel(log_level)

    module_logger.info(f"Logging configured at level {logging.getLevelName(log_level)}.")


def main_cli() -> None:
    """
    Main command-line interface entry point for the script.

    Parses arguments, sets up logging, and runs the GTFS ETL pipeline.
    This allows the script to be executed directly from the command line.
    """
    parser = argparse.ArgumentParser(
        description="Run the GTFS ETL pipeline to download, process, and "
                    "load GTFS data into a PostgreSQL database."
    )
    parser.add_argument(
        "--gtfs-url",
        dest="gtfs_url",
        default=None, # Default handled by run_full_gtfs_etl_pipeline
        help=(
            "URL of the GTFS feed zip file. Overrides GTFS_FEED_URL "
            "environment variable and the script's internal default."
        ),
    )
    parser.add_argument(
        "--log-level",
        dest="log_level_str", # Store as string
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level (default: INFO).",
    )
    parser.add_argument(
        "--log-file",
        dest="log_file_path", # Store path
        default=LOG_FILE, # Use default from constants
        help=f"Path to the log file (default: {LOG_FILE}).",
    )
    parser.add_argument(
        "--no-console-log",
        action="store_false",
        dest="log_to_console",
        help="Disable logging to console (stdout).",
    )
    args = parser.parse_args()

    # Set up logging based on parsed arguments.
    setup_logging(
        log_level_str=args.log_level_str,
        log_file_path=args.log_file_path,
        log_to_console=args.log_to_console
    )

    # Determine the GTFS feed URL to use.
    # Priority: CLI arg > Environment var GTFS_FEED_URL > Internal DEFAULT_GTFS_URL
    feed_url_to_use = args.gtfs_url or os.environ.get("GTFS_FEED_URL") or DEFAULT_GTFS_URL

    module_logger.info(f"GTFS Feed URL to be processed: {feed_url_to_use}")
    module_logger.info(
        f"Target Database: dbname='{DB_PARAMS.get('dbname')}', "
        f"user='{DB_PARAMS.get('user')}', host='{DB_PARAMS.get('host')}'"
    )

    try:
        # If main_pipeline (from the processors.gtfs package) is available,
        # it's preferred as it might contain more sophisticated logic.
        # The environment variable GTFS_FEED_URL needs to be set for it.
        os.environ["GTFS_FEED_URL"] = feed_url_to_use

        if main_pipeline:
            module_logger.info("Using main_pipeline from processors.gtfs package.")
            # This assumes main_pipeline.run_full_gtfs_etl_pipeline() uses
            # environment variables or a shared config for DB params etc.
            success = main_pipeline.run_full_gtfs_etl_pipeline()
        else:
            module_logger.info(
                "main_pipeline not available. Using standalone ETL logic "
                "from update_gtfs.py."
            )
            success = run_full_gtfs_etl_pipeline(feed_url_override=feed_url_to_use)

        sys.exit(0 if success else 1) # Exit with appropriate status code.

    except Exception as e:
        module_logger.critical(
            f"An unhandled error occurred during the GTFS update process: {e}",
            exc_info=True,
        )
        sys.exit(1) # Exit with error status.


if __name__ == "__main__":
    main_cli()