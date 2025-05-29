#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GTFS Update Module for Standalone Execution using Psycopg 3.

This module provides functionality for running a full GTFS ETL (Extract,
Transform, Load) pipeline. It downloads a GTFS feed, processes it according
to predefined schema definitions, and loads the data into a PostgreSQL database
using Psycopg 3. It is designed to be usable as a standalone script.
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
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import psycopg  # Psycopg 3: Replaces psycopg2
import requests
from psycopg import sql  # Psycopg 3: Replaces psycopg2.sql
from psycopg import Connection as PgConnection  # Psycopg 3: Type hint

# Attempt to import from the main GTFS processing package.
try:
    from processors.gtfs import main_pipeline
except (ImportError, ValueError):
    main_pipeline = None

DB_PARAMS: Dict[str, str] = {
    "dbname": os.environ.get("PG_GIS_DB", "gis"),
    "user": os.environ.get("PG_OSM_USER", "osmuser"),
    "password": os.environ.get("PG_OSM_PASSWORD", "yourStrongPasswordHere"),
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": os.environ.get("PG_PORT", "5432"),
}

DOWNLOAD_PATH = "/tmp/gtfs_download.zip"
EXTRACT_PATH = "/tmp/gtfs_extracted/"
LOG_FILE = "/var/log/update_gtfs.log"
DEFAULT_GTFS_URL = os.environ.get(
    "GTFS_FEED_URL", "https://example.com/path/to/your/gtfs-feed.zip"
)

module_logger = logging.getLogger(__name__)

GTFS_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "agency.txt": {
        "table_name": "gtfs_agency",
        "columns": [
            ("agency_id", "TEXT", "PRIMARY KEY",),
            ("agency_name", "TEXT", "NOT NULL"),
            ("agency_url", "TEXT", "NOT NULL"),
            ("agency_timezone", "TEXT", "NOT NULL"),
            ("agency_lang", "TEXT", ""),
            ("agency_phone", "TEXT", ""),
            ("agency_fare_url", "TEXT", ""),
            ("agency_email", "TEXT", ""),
        ],
        "required_fields_in_file": ["agency_name", "agency_url", "agency_timezone", ],
    },
    "stops.txt": {
        "table_name": "gtfs_stops",
        "columns": [
            ("stop_id", "TEXT", "PRIMARY KEY"),
            ("stop_code", "TEXT", ""),
            ("stop_name", "TEXT", ""),
            ("stop_desc", "TEXT", ""),
            ("stop_lat", "DOUBLE PRECISION", "",),
            ("stop_lon", "DOUBLE PRECISION", "",),
            ("zone_id", "TEXT", ""),
            ("stop_url", "TEXT", ""),
            ("location_type", "INTEGER", ""),
            ("parent_station", "TEXT", ""),
            ("stop_timezone", "TEXT", ""),
            ("wheelchair_boarding", "INTEGER", ""),
            ("geom", "GEOMETRY(Point, 4326)", "",),
        ],
        "required_fields_in_file": ["stop_id"],
    },
    "routes.txt": {
        "table_name": "gtfs_routes",
        "columns": [
            ("route_id", "TEXT", "PRIMARY KEY"),
            ("agency_id", "TEXT", "",),
            ("route_short_name", "TEXT", "DEFAULT ''"),
            ("route_long_name", "TEXT", "DEFAULT ''",),
            ("route_desc", "TEXT", ""),
            ("route_type", "INTEGER", "NOT NULL"),
            ("route_url", "TEXT", ""),
            ("route_color", "TEXT", ""),
            ("route_text_color", "TEXT", ""),
            ("route_sort_order", "INTEGER", ""),
        ],
        "required_fields_in_file": ["route_id", "route_type"],
    },
    "trips.txt": {
        "table_name": "gtfs_trips",
        "columns": [
            ("route_id", "TEXT", "NOT NULL"),
            ("service_id", "TEXT", "NOT NULL",),
            ("trip_id", "TEXT", "PRIMARY KEY"),
            ("trip_headsign", "TEXT", ""),
            ("trip_short_name", "TEXT", ""),
            ("direction_id", "INTEGER", ""),
            ("block_id", "TEXT", ""),
            ("shape_id", "TEXT", "",),
            ("wheelchair_accessible", "INTEGER", ""),
            ("bikes_allowed", "INTEGER", ""),
        ],
        "required_fields_in_file": ["route_id", "service_id", "trip_id"],
    },
    "stop_times.txt": {
        "table_name": "gtfs_stop_times",
        "columns": [
            ("trip_id", "TEXT", "NOT NULL"),
            ("arrival_time", "TEXT", ""),
            ("departure_time", "TEXT", ""),
            ("stop_id", "TEXT", "NOT NULL"),
            ("stop_sequence", "INTEGER", "NOT NULL",),
            ("stop_headsign", "TEXT", ""),
            ("pickup_type", "INTEGER", ""),
            ("drop_off_type", "INTEGER", ""),
            ("shape_dist_traveled", "DOUBLE PRECISION", ""),
            ("timepoint", "INTEGER", ""),
        ],
        "composite_pk": ["trip_id", "stop_sequence"],
        "required_fields_in_file": ["trip_id", "stop_id", "stop_sequence"],
    },
    "calendar.txt": {
        "table_name": "gtfs_calendar",
        "columns": [
            ("service_id", "TEXT", "PRIMARY KEY"),
            ("monday", "INTEGER", "NOT NULL"),
            ("tuesday", "INTEGER", "NOT NULL"),
            ("wednesday", "INTEGER", "NOT NULL"),
            ("thursday", "INTEGER", "NOT NULL"),
            ("friday", "INTEGER", "NOT NULL"),
            ("saturday", "INTEGER", "NOT NULL"),
            ("sunday", "INTEGER", "NOT NULL"),
            ("start_date", "TEXT", "NOT NULL"),
            ("end_date", "TEXT", "NOT NULL"),
        ],
        "required_fields_in_file": [
            "service_id", "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday", "start_date", "end_date",
        ],
    },
    "calendar_dates.txt": {
        "table_name": "gtfs_calendar_dates",
        "columns": [
            ("service_id", "TEXT", "NOT NULL"),
            ("date", "TEXT", "NOT NULL"),
            ("exception_type", "INTEGER", "NOT NULL"),
        ],
        "composite_pk": ["service_id", "date"],
        "required_fields_in_file": ["service_id", "date", "exception_type"],
    },
    "shapes.txt": {
        "table_name": "gtfs_shapes_points",
        "columns": [
            ("shape_id", "TEXT", "NOT NULL"),
            ("shape_pt_lat", "DOUBLE PRECISION", "NOT NULL"),
            ("shape_pt_lon", "DOUBLE PRECISION", "NOT NULL"),
            ("shape_pt_sequence", "INTEGER", "NOT NULL",),
            ("shape_dist_traveled", "DOUBLE PRECISION", ""),
        ],
        "composite_pk": ["shape_id", "shape_pt_sequence"],
        "required_fields_in_file": [
            "shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence",
        ],
    },
}

GTFS_LOAD_ORDER: List[str] = [
    "agency.txt", "stops.txt", "routes.txt", "calendar.txt",
    "calendar_dates.txt", "shapes.txt", "trips.txt", "stop_times.txt",
]

GTFS_FOREIGN_KEYS: List[Tuple[str, List[str], str, List[str], str]] = [
    ("gtfs_routes", ["agency_id"], "gtfs_agency", ["agency_id"], "fk_routes_agency_id"),
    ("gtfs_trips", ["route_id"], "gtfs_routes", ["route_id"], "fk_trips_route_id"),
    ("gtfs_trips", ["shape_id"], "gtfs_shapes_lines", ["shape_id"], "fk_trips_shape_id_lines"),
    ("gtfs_stop_times", ["trip_id"], "gtfs_trips", ["trip_id"], "fk_stop_times_trip_id"),
    ("gtfs_stop_times", ["stop_id"], "gtfs_stops", ["stop_id"], "fk_stop_times_stop_id"),
    ("gtfs_stops", ["parent_station"], "gtfs_stops", ["stop_id"], "fk_stops_parent_station"),
]


def sanitize_identifier(name: str) -> str:
    """Sanitize SQL identifiers (table/column names) by quoting them."""
    return '"' + name.replace('"', '""').strip() + '"'


def create_tables_from_schema(conn: PgConnection) -> None:
    """
    Create database tables based on GTFS_DEFINITIONS if they don't exist using Psycopg 3.

    Args:
        conn: Active Psycopg 3 database connection.
    """
    module_logger.info(
        "Setting up database schema based on GTFS_DEFINITIONS..."
    )
    # Psycopg 3: SQL object usage from psycopg.sql
    with conn.cursor() as cursor:
        for filename in GTFS_LOAD_ORDER:
            if filename not in GTFS_DEFINITIONS:
                module_logger.debug(
                    f"No definition for '{filename}', skipping table creation."
                )
                continue

            details = GTFS_DEFINITIONS[filename]
            table_name = details["table_name"]
            cols_defs_str_list: List[str] = []
            for col_name, col_type, col_constraints in details["columns"]:
                cols_defs_str_list.append(
                    f"{sanitize_identifier(col_name)} {col_type} {col_constraints}"
                )

            cols_sql_segment = sql.SQL(", ").join(
                map(sql.SQL, cols_defs_str_list)
            )
            pk_def_sql_segment = sql.SQL("")

            if "composite_pk" in details and details["composite_pk"]:
                quoted_pks = [
                    sql.Identifier(pk_col)
                    for pk_col in details["composite_pk"]
                ]
                pk_def_sql_segment = sql.SQL(", PRIMARY KEY ({})").format(
                    sql.SQL(", ").join(quoted_pks)
                )

            create_sql = sql.SQL(
                "CREATE TABLE IF NOT EXISTS {} ({}{});"
            ).format(
                sql.Identifier(table_name),
                cols_sql_segment,
                pk_def_sql_segment,
            )
            try:
                module_logger.debug(
                    f"Executing SQL for table {table_name}: {create_sql.as_string(conn)}"
                )
                cursor.execute(create_sql)
            except psycopg.Error as e:  # Psycopg 3: Error class
                module_logger.error(f"Error creating table {table_name}: {e}")
                raise

        try:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS gtfs_shapes_lines
                (
                    shape_id
                    TEXT
                    PRIMARY
                    KEY,
                    geom
                    GEOMETRY
                (
                    LineString,
                    4326
                )
                    );
                """
            )
            module_logger.info("Table 'gtfs_shapes_lines' ensured.")
        except psycopg.Error as e:  # Psycopg 3: Error class
            module_logger.error(
                f"Error creating table gtfs_shapes_lines: {e}"
            )
            raise

        try:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS gtfs_dlq
                (
                    id
                    SERIAL
                    PRIMARY
                    KEY,
                    gtfs_filename
                    TEXT,
                    original_row_data
                    TEXT,
                    error_timestamp
                    TIMESTAMP
                    WITH
                    TIME
                    ZONE
                    DEFAULT
                    CURRENT_TIMESTAMP,
                    error_reason
                    TEXT,
                    notes
                    TEXT
                );
                """
            )
            module_logger.info("DLQ table 'gtfs_dlq' ensured.")
        except psycopg.Error as e:  # Psycopg 3: Error class
            module_logger.error(f"Error creating DLQ table gtfs_dlq: {e}")
    module_logger.info("Database schema setup/verification complete.")


def drop_all_gtfs_foreign_keys(conn: PgConnection) -> None:
    """
    Drop all defined GTFS foreign keys using Psycopg 3.

    Args:
        conn: Active Psycopg 3 database connection.
    """
    module_logger.info(
        "Dropping existing GTFS foreign keys before data load..."
    )
    with conn.cursor() as cursor:
        for from_table, _, _, _, fk_name in reversed(GTFS_FOREIGN_KEYS):
            cursor.execute(
                "SELECT to_regclass(%s);", (f"public.{from_table}",)
            )
            if not cursor.fetchone()[0]:
                module_logger.debug(
                    f"Table {from_table} for FK {fk_name} does not exist. "
                    "Skipping FK drop."
                )
                continue

            cursor.execute(
                """
                SELECT 1
                FROM information_schema.table_constraints
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
                    # Psycopg 3: Using psycopg.sql
                    cursor.execute(
                        sql.SQL(
                            "ALTER TABLE {} DROP CONSTRAINT IF EXISTS {};"
                        ).format(
                            sql.Identifier(from_table),
                            sql.Identifier(fk_name),
                        )
                    )
                except psycopg.Error as e:  # Psycopg 3: Error class
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
    Add foreign keys based on GTFS_FOREIGN_KEYS definitions using Psycopg 3.

    Args:
        conn: Active Psycopg 3 database connection.
    """
    module_logger.info("Attempting to add foreign keys post-data load...")
    with conn.cursor() as cursor:
        for (
                from_table,
                from_cols_list,
                to_table,
                to_cols_list,
                fk_name,
        ) in GTFS_FOREIGN_KEYS:
            cursor.execute(
                "SELECT to_regclass(%s);", (f"public.{from_table}",)
            )
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

            # Psycopg 3: Using psycopg.sql
            from_cols_sql = sql.SQL(", ").join(map(sql.Identifier, from_cols_list))
            to_cols_sql = sql.SQL(", ").join(map(sql.Identifier, to_cols_list))

            alter_sql = sql.SQL(
                "ALTER TABLE {} ADD CONSTRAINT {} FOREIGN KEY ({}) "
                "REFERENCES {} ({}) DEFERRABLE INITIALLY DEFERRED;"
            ).format(
                sql.Identifier(from_table),
                sql.Identifier(fk_name),
                from_cols_sql,
                sql.Identifier(to_table),
                to_cols_sql,
            )
            try:
                module_logger.info(
                    f"Adding FK {fk_name} on {from_table}({', '.join(from_cols_list)})"
                    f" -> {to_table}({', '.join(to_cols_list)})"
                )
                cursor.execute(alter_sql)
            except psycopg.Error as e:  # Psycopg 3: Error class
                module_logger.error(
                    f"Could not add foreign key {fk_name}: {e}", exc_info=True
                )
                try:
                    with conn.cursor() as dlq_cursor:
                        dlq_cursor.execute(
                            "INSERT INTO gtfs_dlq (gtfs_filename, error_reason, notes) "
                            "VALUES (%s, %s, %s);",
                            (
                                "SCHEMA_FK_ERROR",
                                str(e)[:1000],
                                f"Failed to add FK: {fk_name}",
                            ),
                        )
                except Exception as dlq_e:
                    module_logger.error(
                        f"Failed to log FK error to DLQ: {dlq_e}"
                    )
    module_logger.info("Foreign key application process finished.")


def download_and_extract_gtfs(feed_url: str) -> bool:
    """
    Download a GTFS feed from a URL and extract its contents.

    Args:
        feed_url: The URL of the GTFS feed zip file.

    Returns:
        True if download and extraction were successful, False otherwise.
    """
    module_logger.info(f"Starting GTFS download from {feed_url}")
    if feed_url == "https://example.com/path/to/your/gtfs-feed.zip":
        module_logger.critical(
            "GTFS_URL is a placeholder. Please set it via environment "
            "variable GTFS_FEED_URL or CLI argument."
        )
        raise ValueError("GTFS_URL not configured.")

    try:
        response = requests.get(feed_url, timeout=120)
        response.raise_for_status()

        Path(DOWNLOAD_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(DOWNLOAD_PATH, "wb") as f:
            f.write(response.content)
        module_logger.info(f"GTFS feed downloaded to {DOWNLOAD_PATH}")

        module_logger.info(f"Unzipping {DOWNLOAD_PATH} to {EXTRACT_PATH}")
        if os.path.exists(EXTRACT_PATH):
            shutil.rmtree(EXTRACT_PATH)
        os.makedirs(EXTRACT_PATH, exist_ok=True)

        with zipfile.ZipFile(DOWNLOAD_PATH, "r") as zip_ref:
            zip_ref.extractall(EXTRACT_PATH)
        module_logger.info("GTFS feed unzipped successfully.")
        return True
    except requests.exceptions.RequestException as re:
        module_logger.error(f"Download Error: {re}", exc_info=True)
    except zipfile.BadZipFile as bze:
        module_logger.error(
            f"Unzip Error: Bad Zip File from {DOWNLOAD_PATH}. {bze}",
            exc_info=True,
        )
    except Exception as e:
        module_logger.error(
            f"Unexpected error in download/extract: {e}", exc_info=True
        )
    return False


def load_data_to_db_with_dlq(conn: PgConnection) -> None:
    """
    Load data from GTFS files into database tables using Psycopg 3's COPY.

    Args:
        conn: Active Psycopg 3 database connection.
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
            for f_in_dir in os.listdir(EXTRACT_PATH):
                if (
                        f_in_dir.lower() == gtfs_filename_key.lower()
                        and f_in_dir.endswith(".txt")
                ):
                    actual_file_to_load = f_in_dir
                    break

            if not actual_file_to_load:
                if (gtfs_filename_key in GTFS_DEFINITIONS):
                    module_logger.warning(
                        f"Expected GTFS file '{gtfs_filename_key}' not found in "
                        "archive. Skipping."
                    )
                continue

            schema_info = GTFS_DEFINITIONS[gtfs_filename_key]
            table_name = schema_info["table_name"]
            filepath = os.path.join(EXTRACT_PATH, actual_file_to_load)

            module_logger.info(
                f"--- Processing {actual_file_to_load} for table {table_name} ---"
            )
            actual_load_cols: List[str] = []

            try:
                df = pd.read_csv(
                    filepath, dtype=str, keep_default_na=False,
                    na_filter=False, encoding="utf-8-sig",
                )

                if df.empty:
                    module_logger.info(
                        f"File {actual_file_to_load} is empty. "
                        f"Skipping table {table_name}."
                    )
                    continue

                df_for_copy = pd.DataFrame()
                csv_header_stripped = [col.strip() for col in df.columns]
                df.columns = csv_header_stripped

                table_db_columns_from_schema = [
                    col_def[0] for col_def in schema_info["columns"]
                    if col_def[0] != "geom"
                ]

                for db_col_name in table_db_columns_from_schema:
                    if db_col_name in csv_header_stripped:
                        df_for_copy[db_col_name] = df[db_col_name]
                        actual_load_cols.append(db_col_name)
                    else:
                        is_required_by_spec = db_col_name in schema_info.get(
                            "required_fields_in_file", []
                        )
                        is_not_null_in_db = any(
                            c[0] == db_col_name
                            and "NOT NULL" in c[2].upper()
                            and "DEFAULT" not in c[2].upper()
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
                                 "Whole file load skipped due to missing required column.",),
                            )
                            raise ValueError(err_msg)
                        else:
                            df_for_copy[db_col_name] = pd.Series(
                                [None] * len(df), dtype=object
                            )
                            actual_load_cols.append(db_col_name)

                if not actual_load_cols:
                    module_logger.warning(
                        f"No columns to load for {table_name} from "
                        f"{actual_file_to_load} after schema mapping. Skipping."
                    )
                    continue

                cursor.execute(
                    sql.SQL("TRUNCATE TABLE {} CASCADE;").format(  # Psycopg 3: Using psycopg.sql
                        sql.Identifier(table_name)
                    )
                )
                module_logger.info(f"Table {table_name} truncated.")

                sio = io.StringIO()
                df_for_copy[actual_load_cols].to_csv(
                    sio, index=False, header=True, sep=",",
                    quotechar='"', escapechar="\\", na_rep="",
                )
                sio.seek(0)

                # Psycopg 3: Using psycopg.sql
                db_cols_sql_identifiers = sql.SQL(", ").join(map(sql.Identifier, actual_load_cols))
                copy_sql_stmt = sql.SQL(
                    "COPY {} ({}) FROM STDIN WITH CSV HEADER DELIMITER ',' "
                    "QUOTE '\"' ESCAPE '\\' NULL AS '';"
                ).format(sql.Identifier(table_name), db_cols_sql_identifiers)

                # Psycopg 3: Get query string for cursor.copy()
                copy_query_string = copy_sql_stmt.as_string(conn)

                module_logger.debug(
                    f"Executing COPY for {table_name} with {len(df_for_copy)} "
                    f"records. Columns: {actual_load_cols}"
                )
                # Psycopg 3: Use cursor.copy() instead of copy_expert()
                with cursor.copy(copy_query_string) as copy_operation:
                    copy_operation.write(sio.read())

                loaded_count = (
                    cursor.rowcount if cursor.rowcount != -1 else len(df_for_copy)
                # Psycopg 3: cursor.rowcount for COPY
                )
                module_logger.info(
                    f"{loaded_count} records loaded into {table_name}."
                )

                if table_name == "gtfs_stops":
                    lat_col, lon_col, geom_col = ("stop_lat", "stop_lon", "geom",)
                    if (lat_col in actual_load_cols and lon_col in actual_load_cols):
                        # Psycopg 3: Using psycopg.sql
                        update_geom_sql = sql.SQL(
                            "UPDATE {} SET {} = ST_SetSRID(ST_MakePoint("
                            "   CAST(NULLIF(TRIM(CAST({} AS TEXT)), '') AS DOUBLE PRECISION), "
                            "   CAST(NULLIF(TRIM(CAST({} AS TEXT)), '') AS DOUBLE PRECISION) "
                            "), 4326) "
                            "WHERE "
                            "   NULLIF(TRIM(CAST({} AS TEXT)), '') IS NOT NULL AND "
                            "   NULLIF(TRIM(CAST({} AS TEXT)), '') IS NOT NULL;"
                        ).format(
                            sql.Identifier(table_name), sql.Identifier(geom_col),
                            sql.Identifier(lon_col), sql.Identifier(lat_col),
                            sql.Identifier(lon_col), sql.Identifier(lat_col),
                        )
                        try:
                            cursor.execute(update_geom_sql)
                            module_logger.info(
                                f"Geometry updated for {table_name} "
                                f"({cursor.rowcount} rows affected)."
                            )
                        except psycopg.Error as geom_e:  # Psycopg 3: Error class
                            module_logger.error(
                                f"Error updating geometry for {table_name}: {geom_e}",
                                exc_info=True,
                            )
                            raise geom_e
                    else:
                        module_logger.warning(
                            f"Could not update geometry for {table_name}: "
                            f"'{lat_col}' or '{lon_col}' not in processed columns: "
                            f"{actual_load_cols}"
                        )
            except ValueError as ve:
                module_logger.error(
                    f"ValueError processing {actual_file_to_load} for "
                    f"{table_name}: {ve}. File processing aborted for this file."
                )
                raise
            except psycopg.Error as db_err:  # Psycopg 3: Error class
                module_logger.error(
                    f"Database error processing {actual_file_to_load} for "
                    f"{table_name}: {db_err}",
                    exc_info=True,
                )
                with conn.cursor() as dlq_cursor_err:
                    dlq_cursor_err.execute(
                        "INSERT INTO gtfs_dlq (gtfs_filename, error_reason, notes) "
                        "VALUES (%s, %s, %s);",
                        (actual_file_to_load, str(db_err)[:1000],
                         f"DB error during COPY/TRUNCATE/GEOM_UPDATE for table {table_name}",),
                    )
                raise
            except Exception as e:
                module_logger.error(
                    f"Unexpected error processing file {actual_file_to_load} "
                    f"for table {table_name}: {e}",
                    exc_info=True,
                )
                with conn.cursor() as dlq_cursor_unexp:
                    dlq_cursor_unexp.execute(
                        "INSERT INTO gtfs_dlq (gtfs_filename, error_reason, notes) "
                        "VALUES (%s, %s, %s);",
                        (actual_file_to_load, str(e)[:1000],
                         f"Unexpected error for table {table_name}",),
                    )
                raise

        if ("shapes.txt" in GTFS_DEFINITIONS and "shapes.txt".lower() in available_files_in_feed):
            try:
                module_logger.info(
                    "Aggregating shape points into linestrings (gtfs_shapes_lines)..."
                )
                cursor.execute("TRUNCATE TABLE gtfs_shapes_lines CASCADE;")
                cursor.execute(
                    """
                    INSERT INTO gtfs_shapes_lines (shape_id, geom)
                    SELECT shape_id,
                           ST_MakeLine(
                                   ST_SetSRID(ST_MakePoint(
                                                      CAST(NULLIF(TRIM(CAST(shape_pt_lon AS TEXT)), '') AS DOUBLE PRECISION),
                                                      CAST(NULLIF(TRIM(CAST(shape_pt_lat AS TEXT)), '') AS DOUBLE PRECISION)
                                              ),
                                              4326) ORDER BY CAST(NULLIF(TRIM(CAST(shape_pt_sequence AS TEXT)), '') AS INTEGER)
                           ) AS line_geom
                    FROM gtfs_shapes_points
                    WHERE NULLIF(TRIM(CAST(shape_pt_lon AS TEXT)), '') IS NOT NULL
                      AND NULLIF(TRIM(CAST(shape_pt_lat AS TEXT)), '') IS NOT NULL
                      AND NULLIF(TRIM(CAST(shape_pt_sequence AS TEXT)), '') IS NOT NULL
                    GROUP BY shape_id
                    HAVING count(*) > 1;
                    """
                )
                module_logger.info(
                    f"Shape linestrings aggregated ({cursor.rowcount} shapes)."
                )
            except Exception as e_shape:
                module_logger.error(
                    f"Error aggregating shape linestrings: {e_shape}",
                    exc_info=True,
                )
                with conn.cursor() as dlq_cursor_shape:
                    dlq_cursor_shape.execute(
                        "INSERT INTO gtfs_dlq (gtfs_filename, error_reason, notes) "
                        "VALUES (%s, %s, %s);",
                        ("shapes.txt", f"Aggregation to lines failed: {str(e_shape)[:1000]}",
                         "gtfs_shapes_lines might be incomplete",),
                    )
                raise
    module_logger.info("Data loading process completed.")


def run_full_gtfs_etl_pipeline(
        feed_url_override: Optional[str] = None,
) -> bool:
    """
    Orchestrate the full GTFS ETL pipeline using Psycopg 3.

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
        if (effective_feed_url == "https://example.com/path/to/your/gtfs-feed.zip"):
            msg = ("CRITICAL: GTFS_URL is a placeholder. Set GTFS_FEED_URL "
                   "environment variable or use --gtfs-url CLI argument.")
            module_logger.critical(msg)
            raise ValueError(msg)

        if (DB_PARAMS["password"] == "yourStrongPasswordHere" and
                not os.environ.get("PG_OSM_PASSWORD")):
            msg = ("CRITICAL: Database password is the default placeholder and "
                   "PG_OSM_PASSWORD env var is not set. Update DB_PARAMS or set env var.")
            module_logger.critical(msg)
            raise ValueError(msg)

        if not download_and_extract_gtfs(effective_feed_url):
            raise Exception("GTFS feed download or extraction failed.")

        conn_kwargs_filtered = {k: v for k, v in DB_PARAMS.items() if v is not None}
        # Psycopg 3: Use psycopg.connect
        conn = psycopg.connect(**conn_kwargs_filtered)
        # Psycopg 3: Default is autocommit=True. Explicit transactions are used below.
        module_logger.info(
            "Database connection successful. Psycopg 3 using default autocommit."
        )

        # Psycopg 3: Use 'with conn.transaction():' for atomic operations.
        # Each major step (schema, FK drop, data load + FK add) gets its own transaction.
        with conn.transaction():
            create_tables_from_schema(conn)
        module_logger.info("Schema creation transaction complete.")

        with conn.transaction():
            drop_all_gtfs_foreign_keys(conn)
        module_logger.info("Foreign key drop transaction complete.")

        with conn.transaction():  # Main data load and FK creation in a single transaction
            load_data_to_db_with_dlq(conn)
            add_foreign_keys_from_schema(conn)
        module_logger.info("Data load and foreign key add transaction complete.")

        success = True
        module_logger.info(
            "All GTFS processing steps completed and committed successfully."
        )

    except ValueError as ve:
        module_logger.critical(f"Configuration/Validation Error: {ve}")
        # Psycopg 3: Rollback is automatic if 'with conn.transaction()' exits with an exception.
    except Exception as e:
        module_logger.critical(
            f"A critical error occurred during the GTFS update process: {e}",
            exc_info=True,
        )
    finally:
        if conn and not conn.closed:
            conn.close()  # Psycopg 3: Explicitly close connection
            module_logger.info("Database connection closed.")

        if os.path.exists(DOWNLOAD_PATH):
            try:
                os.remove(DOWNLOAD_PATH)
                module_logger.info(f"Cleaned up download file: {DOWNLOAD_PATH}")
            except OSError as e_clean_dl:
                module_logger.error(f"Error removing download file '{DOWNLOAD_PATH}': {e_clean_dl}")
        if os.path.exists(EXTRACT_PATH):
            try:
                shutil.rmtree(EXTRACT_PATH)
                module_logger.info(f"Cleaned up extract directory: {EXTRACT_PATH}")
            except OSError as e_clean_ext:
                module_logger.error(f"Error removing extract directory '{EXTRACT_PATH}': {e_clean_ext}")
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
        log_level_str: str = "INFO",
        log_file_path: Optional[str] = LOG_FILE,
        log_to_console: bool = True,
) -> None:
    """
    Set up logging configuration for the script.
    """
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    if not isinstance(log_level, int):
        print(f"Warning: Invalid log level string '{log_level_str}'. Defaulting to INFO.", file=sys.stderr, )
        log_level = logging.INFO

    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    handlers: List[logging.Handler] = []
    if log_file_path:
        try:
            Path(log_file_path).parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file_path, mode="a")
            handlers.append(file_handler)
        except Exception as e_fh:
            print(f"Error setting up file logger for {log_file_path}: {e_fh}", file=sys.stderr, )

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        handlers.append(console_handler)

    if not handlers:
        handlers.append(logging.StreamHandler(sys.stdout))
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
    module_logger.info(f"Logging configured at level {logging.getLevelName(log_level)}.")


def main_cli() -> None:
    """
    Main command-line interface entry point for the script.
    """
    parser = argparse.ArgumentParser(
        description="Run the GTFS ETL pipeline to download, process, and "
                    "load GTFS data into a PostgreSQL database."
    )
    parser.add_argument(
        "--gtfs-url", dest="gtfs_url", default=None,
        help=("URL of the GTFS feed zip file. Overrides GTFS_FEED_URL "
              "environment variable and the script's internal default."),
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

    setup_logging(
        log_level_str=args.log_level_str,
        log_file_path=args.log_file_path,
        log_to_console=args.log_to_console,
    )

    feed_url_to_use = (args.gtfs_url or os.environ.get("GTFS_FEED_URL") or DEFAULT_GTFS_URL)

    module_logger.info(f"GTFS Feed URL to be processed: {feed_url_to_use}")
    module_logger.info(
        f"Target Database: dbname='{DB_PARAMS.get('dbname')}', "
        f"user='{DB_PARAMS.get('user')}', host='{DB_PARAMS.get('host')}'"
    )

    try:
        os.environ["GTFS_FEED_URL"] = feed_url_to_use
        if main_pipeline:
            module_logger.info("Using main_pipeline from processors.gtfs package.")
            success = main_pipeline.run_full_gtfs_etl_pipeline()
        else:
            module_logger.info(
                "main_pipeline not available. Using standalone ETL logic "
                "from update_gtfs.py."
            )
            success = run_full_gtfs_etl_pipeline(feed_url_override=feed_url_to_use)
        sys.exit(0 if success else 1)
    except Exception as e:
        module_logger.critical(
            f"An unhandled error occurred during the GTFS update process: {e}",
            exc_info=True,
        )
        sys.exit(1)


if __name__ == "__main__":
    main_cli()