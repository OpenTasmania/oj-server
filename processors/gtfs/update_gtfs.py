#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GTFS Update Module for Standalone Execution.

This module provides a command-line interface for running the main GTFS ETL
pipeline. It retains database schema creation and foreign key management logic
that might be used by the main pipeline.
"""

import argparse
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import psycopg
from psycopg import sql
from psycopg import Connection as PgConnection

from . import main_pipeline as core_gtfs_pipeline  # For calling the refactored pipeline
from . import utils as gtfs_utils  # For this script's own logging setup

module_logger = logging.getLogger(__name__)

DB_PARAMS: Dict[str, str] = {
    "dbname": os.environ.get("PG_GIS_DB", "gis"),
    "user": os.environ.get("PG_OSM_USER", "osmuser"),
    "password": os.environ.get("PG_OSM_PASSWORD", "yourStrongPasswordHere"),
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": os.environ.get("PG_PORT", "5432"),
}

# Constants related to paths and GTFS feed URL might be centralized
# or overridden by main_pipeline's environment settings.
# These are kept here if this script needs to pass them or for context.
LOG_FILE = "/var/log/update_gtfs_cli.log"
DEFAULT_GTFS_URL = os.environ.get(
    "GTFS_FEED_URL", "https://example.com/path/to/your/gtfs-feed.zip"
)

# --- Schema Definitions and Load Order ---
# These are kept because main_pipeline.py currently imports them from this file.
# Ideally, these would move to schema_definitions.py or a dedicated db_schema.py.

# GTFS_DEFINITIONS from the original update_gtfs.py was for its own CSV loading.
# The main_pipeline uses schema_definitions.GTFS_FILE_SCHEMAS.
# If create_tables_from_schema is to be generic, it should use a passed-in schema
# or rely on schema_definitions.GTFS_FILE_SCHEMAS.
# For now, we keep the structure that main_pipeline.py expects to import.

GTFS_LOAD_ORDER: List[str] = [
    "agency.txt", "stops.txt", "routes.txt", "calendar.txt",
    "calendar_dates.txt", "shapes.txt", "trips.txt", "stop_times.txt",
    "frequencies.txt", "transfers.txt", "feed_info.txt",
    # Added for clarity, though shapes.txt processing results in gtfs_shapes_lines
    "gtfs_shapes_lines.txt"
]

GTFS_FOREIGN_KEYS: List[Tuple[str, List[str], str, List[str], str]] = [
    ("gtfs_routes", ["agency_id"], "gtfs_agency", ["agency_id"], "fk_routes_agency_id"),
    ("gtfs_trips", ["route_id"], "gtfs_routes", ["route_id"], "fk_trips_route_id"),
    ("gtfs_trips", ["shape_id"], "gtfs_shapes_lines", ["shape_id"], "fk_trips_shape_id_lines"),
    ("gtfs_stop_times", ["trip_id"], "gtfs_trips", ["trip_id"], "fk_stop_times_trip_id"),
    ("gtfs_stop_times", ["stop_id"], "gtfs_stops", ["stop_id"], "fk_stop_times_stop_id"),
    ("gtfs_stops", ["parent_station"], "gtfs_stops", ["stop_id"], "fk_stops_parent_station"),
]


# --- End Schema Definitions for Import by main_pipeline.py ---


def sanitize_identifier(name: str) -> str:
    """Sanitize SQL identifiers (table/column names) by quoting them."""
    return '"' + name.replace('"', '""').strip() + '"'


def create_tables_from_schema(conn: PgConnection) -> None:
    """
    Create database tables based on schema_definitions.GTFS_FILE_SCHEMAS.
    This function is imported and used by main_pipeline.py.
    """
    from . import schema_definitions  # Import here to use the centralized schema

    module_logger.info("Setting up database schema based on schema_definitions.GTFS_FILE_SCHEMAS...")
    with conn.cursor() as cursor:
        for filename_key in GTFS_LOAD_ORDER:  # Iterate GTFS_LOAD_ORDER
            details = schema_definitions.GTFS_FILE_SCHEMAS.get(filename_key)
            if not details:
                if filename_key not in ["shapes.txt",
                                        "gtfs_shapes_lines.txt"]:  # shapes.txt itself might not have a direct table if only lines are stored
                    module_logger.debug(f"No schema definition for '{filename_key}', skipping table creation.")
                continue

            table_name = details["db_table_name"]
            cols_defs_str_list: List[str] = []

            db_columns_def = details.get("columns", {})
            if not isinstance(db_columns_def, dict):  # Ensure it's a dictionary
                module_logger.error(f"Columns definition for {table_name} is not a dictionary. Skipping.")
                continue

            for col_name, col_props in db_columns_def.items():
                col_type = col_props.get("type", "TEXT")  # Default to TEXT if type not specified
                col_constraints = ""  # Add logic for pk, not null from col_props if needed
                if col_props.get("pk"):
                    col_constraints += " PRIMARY KEY"  # Simplified
                cols_defs_str_list.append(
                    f"{sanitize_identifier(col_name)} {col_type} {col_constraints}".strip()
                )

            if not cols_defs_str_list:
                module_logger.warning(f"No columns to define for table {table_name}. Skipping.")
                continue

            cols_sql_segment = sql.SQL(", ").join(map(sql.SQL, cols_defs_str_list))
            pk_def_sql_segment = sql.SQL("")  # Primary keys handled in column def for simplicity here

            # Handle composite PKs if defined separately in schema_definitions (not current structure)
            # For example, if details['pk_cols'] exists and has multiple items for composite.
            # This simplified version assumes PK is part of column constraint string.

            create_sql = sql.SQL("CREATE TABLE IF NOT EXISTS {} ({});").format(
                sql.Identifier(table_name),
                cols_sql_segment,
            )
            try:
                module_logger.debug(f"Executing SQL for table {table_name}: {create_sql.as_string(conn)}")
                cursor.execute(create_sql)
            except psycopg.Error as e:
                module_logger.error(f"Error creating table {table_name}: {e}")
                raise

        # Ensure gtfs_shapes_lines and gtfs_dlq tables from the original update_gtfs.py
        try:
            cursor.execute(
                sql.SQL("""
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
                        """)
            )
            module_logger.info("Table 'gtfs_shapes_lines' ensured.")
        except psycopg.Error as e:
            module_logger.error(f"Error creating table gtfs_shapes_lines: {e}")
            raise

        # Create a generic DLQ table for the pipeline
        # main_pipeline.py refers to dlq_table_name=f"dlq_{file_schema_definition['db_table_name']}"
        # This implies per-table DLQs. The code below creates one generic one.
        # This part needs reconciliation with how main_pipeline.py names DLQ tables.
        # For now, we keep the generic one from original update_gtfs.py
        try:
            cursor.execute(sql.SQL("""
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
                                   """))
            module_logger.info("Generic DLQ table 'gtfs_dlq' ensured.")
        except psycopg.Error as e:
            module_logger.error(f"Error creating generic DLQ table gtfs_dlq: {e}")
            # Not raising, as per-table DLQs might be the primary mechanism

    module_logger.info("Database schema setup/verification based on schema_definitions.py complete.")


def add_foreign_keys_from_schema(conn: PgConnection) -> None:
    """
    Add foreign keys based on GTFS_FOREIGN_KEYS definitions.
    This function is imported and used by main_pipeline.py.
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
            try:
                cursor.execute("SELECT to_regclass(%s);", (f"public.{from_table}",))
                if not cursor.fetchone()[0]:
                    module_logger.warning(
                        f"Source Table {from_table} for FK {fk_name} does not exist. Skipping FK creation.")
                    continue
                cursor.execute("SELECT to_regclass(%s);", (f"public.{to_table}",))
                if not cursor.fetchone()[0]:
                    module_logger.warning(
                        f"Target Table {to_table} for FK {fk_name} does not exist. Skipping FK creation.")
                    continue

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

                module_logger.info(
                    f"Adding FK {fk_name} on {from_table}({', '.join(from_cols_list)})"
                    f" -> {to_table}({', '.join(to_cols_list)})"
                )
                cursor.execute(alter_sql)
            except psycopg.Error as e:
                module_logger.error(f"Could not add foreign key {fk_name}: {e}", exc_info=True)
                # Log to DLQ or handle error
            except Exception as ex:
                module_logger.error(f"Unexpected error adding foreign key {fk_name}: {ex}", exc_info=True)
    module_logger.info("Foreign key application process finished.")


def drop_all_gtfs_foreign_keys(conn: PgConnection) -> None:
    """
    Drop all defined GTFS foreign keys using Psycopg 3.
    This function is currently NOT imported by main_pipeline.py.
    It's kept here if direct use from update_gtfs.py is ever needed for its own ETL.
    """
    module_logger.info("Dropping existing GTFS foreign keys...")
    with conn.cursor() as cursor:
        for from_table, _, _, _, fk_name in reversed(GTFS_FOREIGN_KEYS):
            try:
                cursor.execute("SELECT to_regclass(%s);", (f"public.{from_table}",))
                if not cursor.fetchone()[0]:
                    module_logger.debug(f"Table {from_table} for FK {fk_name} does not exist. Skipping FK drop.")
                    continue

                cursor.execute(
                    sql.SQL("ALTER TABLE {} DROP CONSTRAINT IF EXISTS {};").format(
                        sql.Identifier(from_table), sql.Identifier(fk_name)
                    )
                )
                module_logger.info(f"Dropped foreign key {fk_name} from {from_table} (if existed).")
            except psycopg.Error as e:
                module_logger.warning(f"Could not drop foreign key {fk_name} from {from_table}: {e}.")
    module_logger.info("Finished attempting to drop GTFS foreign keys.")


def run_gtfs_etl_via_core_pipeline(feed_url_override: Optional[str] = None) -> bool:
    """
    Sets the GTFS_FEED_URL environment variable if overridden and runs the main ETL pipeline.
    This is the primary ETL execution function for this CLI.

    Args:
        feed_url_override: Optional URL to override the default GTFS feed URL.
                           The main_pipeline will pick this up from the environment.
    Returns:
        True if the pipeline completed successfully, False otherwise.
    """
    if feed_url_override:
        os.environ["GTFS_FEED_URL"] = feed_url_override
        module_logger.info(f"GTFS_FEED_URL overridden for core pipeline by CLI: {feed_url_override}")

    # Ensure other necessary env vars for core_gtfs_pipeline are set (DB params)
    # These are typically set when the script starts, based on DB_PARAMS
    os.environ["PG_GIS_DB"] = DB_PARAMS["dbname"]
    os.environ["PG_OSM_USER"] = DB_PARAMS["user"]
    os.environ["PG_OSM_PASSWORD"] = DB_PARAMS["password"]
    os.environ["PG_HOST"] = DB_PARAMS["host"]
    os.environ["PG_PORT"] = DB_PARAMS["port"]

    return core_gtfs_pipeline.run_full_gtfs_etl_pipeline()


def setup_update_gtfs_logging(
        log_level_str: str = "INFO",
        log_file_path: Optional[str] = LOG_FILE,
        log_to_console: bool = True,
) -> None:
    """Set up logging configuration for the update_gtfs CLI script."""
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    gtfs_utils.setup_logging(  # Call the general logging setup from utils
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
            "URL of the GTFS feed zip file. Overrides GTFS_FEED_URL environment variable and the script's internal default."),
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

    # feed_url_to_use will be set as an environment variable by run_gtfs_etl_via_core_pipeline
    effective_feed_url = args.gtfs_url or os.environ.get("GTFS_FEED_URL") or DEFAULT_GTFS_URL

    module_logger.info(f"GTFS Feed URL to be processed by core pipeline: {effective_feed_url}")
    module_logger.info(
        f"Target Database: dbname='{DB_PARAMS.get('dbname')}', user='{DB_PARAMS.get('user')}', host='{DB_PARAMS.get('host')}'"
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