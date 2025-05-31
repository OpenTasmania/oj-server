#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main orchestrator for the GTFS (General Transit Feed Specification) ETL pipeline.

This module coordinates the entire Extract, Transform, Load (ETL) process for
GTFS data using Psycopg 3 for database interactions and gtfs-kit for
reading GTFS feeds. It assumes input GTFS data has been pre-validated.
It handles:
1.  Downloading and extracting the GTFS feed.
2.  Reading the GTFS feed using gtfs-kit.
3.  Setting up the database schema (tables and primary keys).
4.  Transforming and loading data from each relevant GTFS table into the
    corresponding database table.
5.  Applying foreign key constraints after data loading.
6.  Logging progress and errors.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

import gtfs_kit
import pandas as pd
import psycopg
from psycopg import Connection as PgConnection
from psycopg import sql

from common import core_utils
from common.db_utils import get_db_connection
from processors.gtfs import download, load, transform  # Relative imports for siblings
from processors.gtfs import schema_definitions as schemas  # Relative import

module_logger = logging.getLogger(__name__)

# GTFS_FEED_URL will be primarily sourced from the environment variable
# set by the calling script (e.g., update_gtfs.py or main_installer.py)
# A fallback is provided here if the environment variable is somehow not set.
try:
    from setup.config import GTFS_FEED_URL as CONFIG_GTFS_FEED_URL
except ImportError:
    CONFIG_GTFS_FEED_URL = "https://example.com/default_gtfs_feed.zip"

GTFS_FEED_URL_MODULE_LEVEL_VAR = os.environ.get("GTFS_FEED_URL", CONFIG_GTFS_FEED_URL)

DB_PARAMS: dict[str, str] = {
    "dbname": os.environ.get("PG_GIS_DB", "gis"),
    "user": os.environ.get("PG_OSM_USER", "osmuser"),
    "password": os.environ.get("PG_OSM_PASSWORD", "yourStrongPasswordHere"),
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": os.environ.get("PG_PORT", "5432"),
}

TEMP_DOWNLOAD_DIR = Path(
    os.environ.get("GTFS_TEMP_DOWNLOAD_DIR", "/tmp/gtfs_pipeline_downloads")
)
TEMP_ZIP_FILENAME = "gtfs_feed.zip"
TEMP_EXTRACT_DIR_NAME = "gtfs_extracted_feed"
TEMP_DOWNLOAD_PATH = TEMP_DOWNLOAD_DIR / TEMP_ZIP_FILENAME
TEMP_EXTRACT_PATH = TEMP_DOWNLOAD_DIR / TEMP_EXTRACT_DIR_NAME

# Moved from update_gtfs.py
GTFS_LOAD_ORDER: List[str] = [
    "agency.txt", "stops.txt", "routes.txt", "calendar.txt",
    "calendar_dates.txt", "shapes.txt",
    "trips.txt", "stop_times.txt",
    "frequencies.txt", "transfers.txt", "feed_info.txt",
    "gtfs_shapes_lines.txt"  # Conceptual entry for processing shape lines
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
    Create database tables based on schema_definitions.GTFS_FILE_SCHEMAS.
    Primary keys are added using ALTER TABLE based on 'pk_cols' in the schema.
    """
    module_logger.info("Setting up database schema based on schema_definitions.GTFS_FILE_SCHEMAS...")
    with conn.cursor() as cursor:
        for filename_key in GTFS_LOAD_ORDER:
            details = schemas.GTFS_FILE_SCHEMAS.get(filename_key)
            if not details:
                if filename_key not in ["gtfs_shapes_lines.txt"]:
                    module_logger.debug(
                        f"No schema definition for '{filename_key}', skipping table creation in this loop.")
                continue

            table_name = details["db_table_name"]
            cols_defs_str_list: List[str] = []

            db_columns_def = details.get("columns", {})
            if not isinstance(db_columns_def, dict):
                module_logger.error(f"Columns definition for {table_name} is not a dictionary. Skipping.")
                continue

            for col_name, col_props in db_columns_def.items():
                col_type = col_props.get("type", "TEXT")
                col_constraints = ""
                cols_defs_str_list.append(
                    f"{sanitize_identifier(col_name)} {col_type} {col_constraints}".strip()
                )

            if not cols_defs_str_list:
                module_logger.warning(f"No columns to define for table {table_name}. Skipping creation.")
                continue

            cols_sql_segment = sql.SQL(", ").join(map(sql.SQL, cols_defs_str_list))

            create_sql = sql.SQL("CREATE TABLE IF NOT EXISTS {} ({});").format(
                sql.Identifier(table_name),
                cols_sql_segment,
            )
            try:
                module_logger.debug(f"Executing SQL for table {table_name}: {create_sql.as_string(conn)}")
                cursor.execute(create_sql)
            except psycopg.Error as e:
                module_logger.error(
                    f"Error creating table {table_name}: {e.diag.message_primary if e.diag else str(e)}")
                raise  # Re-raise to be caught by the transaction block

            pk_column_names = details.get("pk_cols")
            if pk_column_names and isinstance(pk_column_names, list) and len(pk_column_names) > 0:
                sanitized_pk_cols = [sql.Identifier(col) for col in pk_column_names]
                pk_cols_sql_segment = sql.SQL(", ").join(sanitized_pk_cols)
                constraint_name_str = f"pk_{table_name.replace('gtfs_', '')}"
                if len(constraint_name_str) > 63:
                    constraint_name_str = constraint_name_str[:63]
                pk_constraint_name = sql.Identifier(constraint_name_str)

                alter_pk_sql = sql.SQL("ALTER TABLE {} ADD CONSTRAINT {} PRIMARY KEY ({});").format(
                    sql.Identifier(table_name),
                    pk_constraint_name,
                    pk_cols_sql_segment
                )
                try:
                    module_logger.debug(
                        f"Attempting to add PRIMARY KEY to {table_name} on ({', '.join(pk_column_names)})")
                    cursor.execute(alter_pk_sql)
                    module_logger.info(f"Added PRIMARY KEY to {table_name} on ({', '.join(pk_column_names)}).")
                except psycopg.Error as e_pk:
                    module_logger.error(
                        f"Failed to add PRIMARY KEY to {table_name}: {e_pk.diag.message_primary if e_pk.diag else str(e_pk)}")
                    raise e_pk  # Re-raise

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
                        ));
                        """)
            )
            module_logger.info("Table 'gtfs_shapes_lines' ensured.")
        except psycopg.Error as e:
            module_logger.error(
                f"Error creating table gtfs_shapes_lines: {e.diag.message_primary if e.diag else str(e)}")
            raise

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
            module_logger.error(
                f"Error creating generic DLQ table gtfs_dlq: {e.diag.message_primary if e.diag else str(e)}")
            # Not raising, as DLQ might be non-critical to basic data load

    module_logger.info("Database schema setup/verification complete.")


def add_foreign_keys_from_schema(conn: PgConnection) -> None:
    """
    Add foreign keys based on GTFS_FOREIGN_KEYS definitions.
    This function expects to be run within an existing transaction.
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
                    f"Preparing to add FK {fk_name} on {from_table}({', '.join(from_cols_list)})"
                    f" -> {to_table}({', '.join(to_cols_list)})"
                )
                cursor.execute(alter_sql)
                module_logger.info(f"Successfully prepared FK {fk_name} for commit.")
            except psycopg.Error as e:
                module_logger.error(
                    f"Could not prepare foreign key {fk_name} for commit: {e.diag.message_primary if e.diag else str(e)}")
                raise  # Re-raise to ensure the transaction block catches it
            except Exception as ex:
                module_logger.error(f"Unexpected error preparing foreign key {fk_name}: {ex}", exc_info=True)
                raise
    module_logger.info("Foreign key application process finished (pending commit of parent transaction).")


def drop_all_gtfs_foreign_keys(conn: PgConnection) -> None:
    """Drop all defined GTFS foreign keys using Psycopg 3."""
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
                module_logger.warning(
                    f"Could not drop foreign key {fk_name} from {from_table}: {e.diag.message_primary if e.diag else str(e)}.")
    module_logger.info("Finished attempting to drop GTFS foreign keys.")


def run_full_gtfs_etl_pipeline() -> bool:
    """
    Orchestrate the full GTFS ETL pipeline using gtfs-kit and Psycopg 3.
    """
    start_time = datetime.now()
    module_logger.info(
        f"===== GTFS ETL Pipeline (gtfs-kit) Started at {start_time.isoformat()} ====="
    )

    # Get the effective GTFS_FEED_URL from the environment, falling back to a default
    # This variable is primarily set by the calling script (update_gtfs.py or other).
    current_gtfs_feed_url = os.environ.get("GTFS_FEED_URL", CONFIG_GTFS_FEED_URL)
    module_logger.info(f"Using GTFS_FEED_URL: {current_gtfs_feed_url}")

    try:
        TEMP_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        TEMP_EXTRACT_PATH.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        module_logger.critical(
            f"Failed to create temporary directories: {e}. Pipeline aborted."
        )
        return False

    conn: Optional[psycopg.Connection] = None
    try:
        module_logger.info("--- Step 1: Downloading and Extracting GTFS Feed ---")
        if not download.download_gtfs_feed(current_gtfs_feed_url, TEMP_DOWNLOAD_PATH):
            module_logger.critical("Failed to download GTFS feed. Pipeline aborted.")
            return False
        if not download.extract_gtfs_feed(TEMP_DOWNLOAD_PATH, TEMP_EXTRACT_PATH):
            module_logger.critical("Failed to extract GTFS feed. Pipeline aborted.")
            return False
        module_logger.info("GTFS feed downloaded and extracted successfully.")

        module_logger.info("--- Step 2: Reading Feed with gtfs-kit ---")
        feed = gtfs_kit.read_feed(str(TEMP_EXTRACT_PATH), dist_units='km')
        module_logger.info(f"Feed loaded. Detected tables: {list(feed.list_fields().keys())}")

        module_logger.warning(
            "--- Feed Validation Responsibility --- "
            "This pipeline assumes the input GTFS data has been validated beforehand. Proceeding."
        )

        conn = get_db_connection(DB_PARAMS)
        if not conn:
            module_logger.critical("Failed to connect to the database. Pipeline aborted.")
            return False

        # Entire schema setup, data load, and FK addition will be one transaction
        with conn.transaction():
            module_logger.info("--- Step 3: Ensuring database schema exists (tables & PKs) ---")
            create_tables_from_schema(conn)  # Now defines PKs via ALTER TABLE
            module_logger.info("Database schema transaction component complete.")

            total_records_processed = 0
            total_records_loaded_successfully = 0
            total_records_sent_to_dlq = 0

            module_logger.info("--- Step 4: Transforming and Loading GTFS Data ---")
            for gtfs_filename_key in GTFS_LOAD_ORDER:
                table_base_name = gtfs_filename_key.replace('.txt', '')
                df_original: Optional[pd.DataFrame] = getattr(feed, table_base_name, None)

                if df_original is None or df_original.empty:
                    # Special handling for shapes.txt (points) vs gtfs_shapes_lines.txt (lines derived from shapes)
                    if table_base_name == 'shapes' and gtfs_filename_key == "shapes.txt":
                        module_logger.info(
                            f"Table 'shapes' (points data from shapes.txt) not found or empty. If lines are derived, this might be fine.")
                    elif table_base_name == 'gtfs_shapes_lines' and gtfs_filename_key == "gtfs_shapes_lines.txt":
                        module_logger.info(
                            f"Conceptual table 'gtfs_shapes_lines' - actual data processing happens under 'shapes.txt' key for geometrization.")
                        continue  # This key is for ordering, actual processing for lines is in 'shapes.txt' block
                    elif table_base_name not in ['frequencies', 'feed_info', 'transfers', 'pathways', 'levels',
                                                 'attributions', 'translations']:
                        module_logger.warning(
                            f"Table '{table_base_name}' (from {gtfs_filename_key}) not found in feed or is empty. Skipping.")
                    else:
                        module_logger.info(f"Optional table '{table_base_name}' not found or empty. Skipping.")
                    continue

                df_for_processing = df_original.copy()
                module_logger.info(f"Processing table: {table_base_name} with {len(df_for_processing)} records.")
                total_records_processed += len(df_for_processing)

                file_schema_definition = schemas.GTFS_FILE_SCHEMAS.get(gtfs_filename_key)
                if not file_schema_definition:
                    module_logger.warning(f"No DB schema definition for '{gtfs_filename_key}'. Skipping.")
                    continue

                df_transformed: pd.DataFrame
                if table_base_name == 'stops':  # Handle stops geometry
                    if feed.stops is not None and not feed.stops.empty:
                        stops_gdf = gtfs_kit.geometrize_stops(feed.stops)
                        if stops_gdf is not None:
                            df_transformed = stops_gdf.copy()
                        else:
                            module_logger.warning("Failed to compute stop geometries. Using original stops data.")
                            df_transformed = df_for_processing.copy()
                    else:
                        module_logger.warning("feed.stops is missing or empty. Cannot compute stop geometries.")
                        df_transformed = df_for_processing.copy()

                elif table_base_name == 'shapes' and gtfs_filename_key == "shapes.txt":  # Handle shapes.txt for line geometrization
                    if feed.shapes is not None and not feed.shapes.empty:
                        shapes_lines_gdf = gtfs_kit.geometrize_shapes(feed.shapes)
                        if shapes_lines_gdf is not None and not shapes_lines_gdf.empty:
                            module_logger.info(
                                f"Processing {len(shapes_lines_gdf)} shape geometries into 'gtfs_shapes_lines'.")
                            temp_shapes_df = shapes_lines_gdf.copy()
                            shapes_lines_db_schema = schemas.GTFS_FILE_SCHEMAS.get(
                                "gtfs_shapes_lines.txt")  # Get schema for the target lines table
                            if not shapes_lines_db_schema:
                                module_logger.error(
                                    "Schema for 'gtfs_shapes_lines.txt' not found. Cannot load shape lines.")
                                df_transformed = df_for_processing.copy()  # Fallback to points if lines fail
                            else:
                                final_shapes_lines_df = transform.transform_dataframe(temp_shapes_df,
                                                                                      shapes_lines_db_schema)
                                loaded_sl, dlq_sl = load.load_dataframe_to_db(
                                    conn, final_shapes_lines_df,
                                    shapes_lines_db_schema["db_table_name"],
                                    shapes_lines_db_schema,
                                    dlq_table_name=f"dlq_{shapes_lines_db_schema['db_table_name']}",
                                )
                                total_records_loaded_successfully += loaded_sl
                                total_records_sent_to_dlq += dlq_sl
                                # Now, set df_transformed to the original points for standard loading of shapes.txt as points
                                df_transformed = df_for_processing.copy()
                        else:  # No lines geometrizied
                            module_logger.info(
                                "No shape geometries computed or result is empty from gtfs_kit.geometrize_shapes.")
                            df_transformed = df_for_processing.copy()  # Load original points
                    else:  # No feed.shapes
                        module_logger.info(
                            "No shapes data in feed (feed.shapes is None or empty). Skipping line geometrization and point loading for shapes.txt.")
                        df_transformed = pd.DataFrame()  # Empty dataframe so it skips loading later
                else:  # Default case for other tables
                    df_transformed = df_for_processing.copy()

                if df_transformed.empty and table_base_name == 'shapes' and gtfs_filename_key == "shapes.txt":
                    module_logger.info(
                        f"Skipping loading for '{table_base_name}' as df_transformed is empty (likely handled by line geometrization or no data).")
                    continue  # Avoid loading empty dataframe for shapes if it was only for lines

                final_df_for_loading = transform.transform_dataframe(df_transformed, file_schema_definition)
                if final_df_for_loading.empty:
                    module_logger.info(f"DataFrame for {table_base_name} is empty after transformation. Skipping load.")
                    continue

                loaded_count, dlq_count_from_load = load.load_dataframe_to_db(
                    conn, final_df_for_loading,
                    file_schema_definition["db_table_name"],
                    file_schema_definition,
                    dlq_table_name=f"dlq_{file_schema_definition['db_table_name']}",
                )
                total_records_loaded_successfully += loaded_count
                total_records_sent_to_dlq += dlq_count_from_load

            module_logger.info("--- Step 5: Adding Foreign Keys (within transaction) ---")
            add_foreign_keys_from_schema(conn)  # FKs added as part of the main transaction

        module_logger.info("--- Main Transaction (Schema, Data Load, FKs) Complete ---")
        module_logger.info(f"Total records processed (sum of rows in feed tables used): {total_records_processed}")
        module_logger.info(f"Total records loaded successfully to DB: {total_records_loaded_successfully}")
        module_logger.info(f"Total records sent to DLQ: {total_records_sent_to_dlq}")
        return True

    except ValueError as ve:  # Catch config errors etc.
        module_logger.critical(f"Configuration Error in pipeline: {ve}", exc_info=True)
    except psycopg.Error as db_err:  # Catch DB errors (which includes those re-raised by schema/FK functions)
        module_logger.critical(
            f"A Psycopg 3 database error occurred: {db_err.diag.message_primary if db_err.diag else str(db_err)}",
            exc_info=True)
    except Exception as e:  # Catch any other unexpected errors
        module_logger.critical(f"A critical error occurred during GTFS ETL: {e}", exc_info=True)
    finally:
        if conn and not conn.closed:
            conn.close()
            module_logger.info("Database connection closed.")
        download.cleanup_temp_file(TEMP_DOWNLOAD_PATH)
        if TEMP_EXTRACT_PATH.exists():
            core_utils.cleanup_directory(TEMP_EXTRACT_PATH, ensure_dir_exists_after=True)
        end_time = datetime.now()
        duration = end_time - start_time
        module_logger.info(
            f"===== GTFS ETL Pipeline Finished at {end_time.isoformat()}. Duration: {duration} ====="
        )
    return False


if __name__ == "__main__":
    # Ensure core_utils.setup_logging is called if running standalone
    # It's good practice for any executable script to configure its own logging.
    # update_gtfs.py (the CLI) already calls this. If running main_pipeline.py directly:
    if not logging.getLogger().hasHandlers():  # Basic check if logging is already configured
        core_utils.setup_logging(log_level=logging.INFO, log_to_console=True)

    # Check for placeholder GTFS_FEED_URL if running directly
    _feed_url_check = os.environ.get("GTFS_FEED_URL", CONFIG_GTFS_FEED_URL)
    if _feed_url_check == "https://example.com/default_gtfs_feed.zip":
        module_logger.warning(
            "CRITICAL: GTFS_FEED_URL is a placeholder or not set. "
            "Pipeline might fail at download."
        )
        module_logger.warning(
            "Set it like: export GTFS_FEED_URL='your_actual_url'"
        )

    # Check for placeholder password if running directly
    if DB_PARAMS.get("password") == "yourStrongPasswordHere" and not os.environ.get("PG_OSM_PASSWORD"):
        module_logger.warning(
            "CRITICAL: PostgreSQL password is a placeholder in DB_PARAMS and "
            "PG_OSM_PASSWORD env var is not set."
        )
        module_logger.warning(
            "Set PGPASSWORD (for psql tool) or PG_OSM_PASSWORD "
            "(for this script's DB_PARAMS), or update DB_PARAMS in script."
        )

    pipeline_succeeded = run_full_gtfs_etl_pipeline()
    if pipeline_succeeded:
        module_logger.info(
            "Main pipeline execution completed successfully (from __main__ call)."
        )
        sys.exit(0)
    else:
        module_logger.error(
            "Main pipeline execution failed (from __main__ call)."
        )
        sys.exit(1)