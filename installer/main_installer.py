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
import sys # Keep sys import for sys.exit
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

import gtfs_kit
import pandas as pd
import psycopg
from psycopg import Connection as PgConnection
from psycopg import sql

# Import the new common_setup_logging
from common.core_utils import setup_logging as common_setup_logging
from common.core_utils import cleanup_directory # Already imported via common.core_utils in original
from common.db_utils import get_db_connection
from processors.gtfs import download, load, transform
from processors.gtfs import schema_definitions as schemas

module_logger = logging.getLogger(__name__)

try:
    from setup.config import GTFS_FEED_URL as CONFIG_GTFS_FEED_URL
except ImportError: # pragma: no cover
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

GTFS_LOAD_ORDER: List[str] = [
    "agency.txt", "stops.txt", "routes.txt", "calendar.txt",
    "calendar_dates.txt", "shapes.txt",
    "trips.txt", "stop_times.txt",
    "frequencies.txt", "transfers.txt", "feed_info.txt",
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


def sanitize_identifier(name: str) -> str:
    """Sanitize SQL identifiers (table/column names) by quoting them."""
    # This function will be refactored later as discussed.
    # For now, keeping it to focus on logging changes.
    return '"' + name.replace('"', '""').strip() + '"'


def create_tables_from_schema(conn: PgConnection) -> None:
    module_logger.info("Setting up database schema based on schema_definitions.GTFS_FILE_SCHEMAS...")
    with conn.cursor() as cursor:
        for filename_key in GTFS_LOAD_ORDER:
            details = schemas.GTFS_FILE_SCHEMAS.get(filename_key)
            if not details:
                if filename_key not in ["gtfs_shapes_lines.txt"]: # pragma: no cover
                    module_logger.debug(
                        f"No schema definition for '{filename_key}', skipping table creation in this loop.")
                continue

            table_name = details["db_table_name"]
            cols_defs_str_list: List[str] = []

            db_columns_def = details.get("columns", {})
            if not isinstance(db_columns_def, dict): # pragma: no cover
                module_logger.error(f"Columns definition for {table_name} is not a dictionary. Skipping.")
                continue

            for col_name, col_props in db_columns_def.items():
                col_type = col_props.get("type", "TEXT")
                col_constraints = "" # Assuming simple for now
                # sanitize_identifier usage will be refactored separately.
                cols_defs_str_list.append(
                    f"{sanitize_identifier(col_name)} {col_type} {col_constraints}".strip()
                )

            if not cols_defs_str_list: # pragma: no cover
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
            except psycopg.Error as e: # pragma: no cover
                module_logger.error(
                    f"Error creating table {table_name}: {e.diag.message_primary if e.diag else str(e)}")
                raise

            pk_column_names = details.get("pk_cols")
            if pk_column_names and isinstance(pk_column_names, list) and len(pk_column_names) > 0:
                sanitized_pk_cols = [sql.Identifier(col) for col in pk_column_names]
                pk_cols_sql_segment = sql.SQL(", ").join(sanitized_pk_cols)
                constraint_name_str = f"pk_{table_name.replace('gtfs_', '')}"
                if len(constraint_name_str) > 63: # pragma: no cover
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
                except psycopg.Error as e_pk: # pragma: no cover
                    # Error might occur if PK already exists or columns don't exist/not suitable
                    # For a "CREATE IF NOT EXISTS" style, this might indicate prior setup or an issue.
                    # The original code re-raised, which is appropriate for a transactional block.
                    module_logger.error(
                        f"Failed to add PRIMARY KEY to {table_name}: {e_pk.diag.message_primary if e_pk.diag else str(e_pk)}")
                    raise e_pk
        try:
            cursor.execute(
                sql.SQL("""
                        CREATE TABLE IF NOT EXISTS gtfs_shapes_lines
                        (shape_id TEXT PRIMARY KEY, geom GEOMETRY(LineString, 4326));
                        """)
            )
            module_logger.info("Table 'gtfs_shapes_lines' ensured.")
        except psycopg.Error as e: # pragma: no cover
            module_logger.error(
                f"Error creating table gtfs_shapes_lines: {e.diag.message_primary if e.diag else str(e)}")
            raise
        try:
            cursor.execute(sql.SQL("""
                                   CREATE TABLE IF NOT EXISTS gtfs_dlq
                                   (id SERIAL PRIMARY KEY, gtfs_filename TEXT, original_row_data TEXT,
                                    error_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                                    error_reason TEXT, notes TEXT);
                                   """))
            module_logger.info("Generic DLQ table 'gtfs_dlq' ensured.")
        except psycopg.Error as e: # pragma: no cover
            module_logger.error(
                f"Error creating generic DLQ table gtfs_dlq: {e.diag.message_primary if e.diag else str(e)}")
    module_logger.info("Database schema setup/verification complete.")


def add_foreign_keys_from_schema(conn: PgConnection) -> None: # pragma: no cover
    module_logger.info("Attempting to add foreign keys post-data load...")
    with conn.cursor() as cursor:
        for (from_table, from_cols_list, to_table, to_cols_list, fk_name) in GTFS_FOREIGN_KEYS:
            try:
                # Check if tables exist before attempting to add FK
                cursor.execute("SELECT to_regclass(%s);", (f"public.{from_table}",)) # Assuming public schema
                if not cursor.fetchone()[0]:
                    module_logger.warning(f"Source Table {from_table} for FK {fk_name} does not exist. Skipping FK creation.")
                    continue
                cursor.execute("SELECT to_regclass(%s);", (f"public.{to_table}",))
                if not cursor.fetchone()[0]:
                    module_logger.warning(f"Target Table {to_table} for FK {fk_name} does not exist. Skipping FK creation.")
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
                module_logger.info(
                    f"Preparing to add FK {fk_name} on {from_table}({', '.join(from_cols_list)})"
                    f" -> {to_table}({', '.join(to_cols_list)})")
                cursor.execute(alter_sql)
                module_logger.info(f"Successfully prepared FK {fk_name} for commit.")
            except psycopg.Error as e:
                module_logger.error(
                    f"Could not prepare foreign key {fk_name} for commit: {e.diag.message_primary if e.diag else str(e)}")
                raise
            except Exception as ex:
                module_logger.error(f"Unexpected error preparing foreign key {fk_name}: {ex}", exc_info=True)
                raise
    module_logger.info("Foreign key application process finished (pending commit of parent transaction).")


def drop_all_gtfs_foreign_keys(conn: PgConnection) -> None: # pragma: no cover
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
    start_time = datetime.now()
    module_logger.info(
        f"===== GTFS ETL Pipeline (gtfs-kit) Started at {start_time.isoformat()} ====="
    )
    current_gtfs_feed_url = os.environ.get("GTFS_FEED_URL", CONFIG_GTFS_FEED_URL)
    module_logger.info(f"Using GTFS_FEED_URL: {current_gtfs_feed_url}")

    try:
        TEMP_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        TEMP_EXTRACT_PATH.mkdir(parents=True, exist_ok=True)
    except OSError as e: # pragma: no cover
        module_logger.critical(f"Failed to create temporary directories: {e}. Pipeline aborted.")
        return False

    conn: Optional[psycopg.Connection] = None
    try:
        module_logger.info("--- Step 1: Downloading and Extracting GTFS Feed ---")
        if not download.download_gtfs_feed(current_gtfs_feed_url, TEMP_DOWNLOAD_PATH): # pragma: no cover
            module_logger.critical("Failed to download GTFS feed. Pipeline aborted.")
            return False
        if not download.extract_gtfs_feed(TEMP_DOWNLOAD_PATH, TEMP_EXTRACT_PATH): # pragma: no cover
            module_logger.critical("Failed to extract GTFS feed. Pipeline aborted.")
            return False
        module_logger.info("GTFS feed downloaded and extracted successfully.")

        module_logger.info("--- Step 2: Reading Feed with gtfs-kit ---")
        feed = gtfs_kit.read_feed(str(TEMP_EXTRACT_PATH), dist_units='km')
        module_logger.info(f"Feed loaded. Detected tables: {list(feed.list_fields().keys())}")
        module_logger.warning("--- Feed Validation Responsibility --- This pipeline assumes input GTFS data has been validated. Proceeding.")

        conn = get_db_connection(DB_PARAMS)
        if not conn: # pragma: no cover
            module_logger.critical("Failed to connect to the database. Pipeline aborted.")
            return False

        with conn.transaction():
            module_logger.info("--- Step 3: Ensuring database schema exists (tables & PKs) ---")
            create_tables_from_schema(conn)
            module_logger.info("Database schema transaction component complete.")

            total_records_processed = 0
            total_records_loaded_successfully = 0
            total_records_sent_to_dlq = 0

            module_logger.info("--- Step 4: Transforming and Loading GTFS Data ---")
            for gtfs_filename_key in GTFS_LOAD_ORDER:
                table_base_name = gtfs_filename_key.replace('.txt', '')
                df_original: Optional[pd.DataFrame] = getattr(feed, table_base_name, None)

                if df_original is None or df_original.empty: # pragma: no cover
                    if table_base_name == 'shapes' and gtfs_filename_key == "shapes.txt":
                        module_logger.info("Table 'shapes' (points data from shapes.txt) not found or empty. If lines are derived, this might be fine.")
                    elif table_base_name == 'gtfs_shapes_lines' and gtfs_filename_key == "gtfs_shapes_lines.txt":
                        module_logger.info("Conceptual table 'gtfs_shapes_lines' - actual data processing happens under 'shapes.txt' key.")
                        continue
                    elif table_base_name not in ['frequencies', 'feed_info', 'transfers', 'pathways', 'levels', 'attributions', 'translations']:
                        module_logger.warning(f"Table '{table_base_name}' (from {gtfs_filename_key}) not found in feed or is empty. Skipping.")
                    else:
                        module_logger.info(f"Optional table '{table_base_name}' not found or empty. Skipping.")
                    continue

                df_for_processing = df_original.copy()
                module_logger.info(f"Processing table: {table_base_name} with {len(df_for_processing)} records.")
                total_records_processed += len(df_for_processing)

                file_schema_definition = schemas.GTFS_FILE_SCHEMAS.get(gtfs_filename_key)
                if not file_schema_definition: # pragma: no cover
                    module_logger.warning(f"No DB schema definition for '{gtfs_filename_key}'. Skipping.")
                    continue

                df_transformed: pd.DataFrame
                if table_base_name == 'stops':
                    if feed.stops is not None and not feed.stops.empty:
                        stops_gdf = gtfs_kit.geometrize_stops(feed.stops)
                        df_transformed = stops_gdf.copy() if stops_gdf is not None else df_for_processing.copy()
                    else: # pragma: no cover
                        module_logger.warning("feed.stops is missing or empty. Cannot compute stop geometries.")
                        df_transformed = df_for_processing.copy()
                elif table_base_name == 'shapes' and gtfs_filename_key == "shapes.txt":
                    if feed.shapes is not None and not feed.shapes.empty:
                        shapes_lines_gdf = gtfs_kit.geometrize_shapes(feed.shapes)
                        if shapes_lines_gdf is not None and not shapes_lines_gdf.empty:
                            module_logger.info(f"Processing {len(shapes_lines_gdf)} shape geometries into 'gtfs_shapes_lines'.")
                            temp_shapes_df = shapes_lines_gdf.copy()
                            shapes_lines_db_schema = schemas.GTFS_FILE_SCHEMAS.get("gtfs_shapes_lines.txt")
                            if not shapes_lines_db_schema: # pragma: no cover
                                module_logger.error("Schema for 'gtfs_shapes_lines.txt' not found. Cannot load shape lines.")
                                df_transformed = df_for_processing.copy()
                            else:
                                final_shapes_lines_df = transform.transform_dataframe(temp_shapes_df, shapes_lines_db_schema)
                                loaded_sl, dlq_sl = load.load_dataframe_to_db(
                                    conn, final_shapes_lines_df,
                                    shapes_lines_db_schema["db_table_name"],
                                    shapes_lines_db_schema,
                                    dlq_table_name=f"dlq_{shapes_lines_db_schema['db_table_name']}",
                                )
                                total_records_loaded_successfully += loaded_sl
                                total_records_sent_to_dlq += dlq_sl
                                df_transformed = df_for_processing.copy() # For original points
                        else: # pragma: no cover
                            module_logger.info("No shape geometries computed or result is empty.")
                            df_transformed = df_for_processing.copy()
                    else: # pragma: no cover
                        module_logger.info("No shapes data in feed. Skipping line geometrization and point loading for shapes.txt.")
                        df_transformed = pd.DataFrame()
                else:
                    df_transformed = df_for_processing.copy()

                if df_transformed.empty and table_base_name == 'shapes' and gtfs_filename_key == "shapes.txt": # pragma: no cover
                    module_logger.info(f"Skipping loading for '{table_base_name}' as df_transformed is empty.")
                    continue

                final_df_for_loading = transform.transform_dataframe(df_transformed, file_schema_definition)
                if final_df_for_loading.empty: # pragma: no cover
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
            add_foreign_keys_from_schema(conn)

        module_logger.info("--- Main Transaction (Schema, Data Load, FKs) Complete ---")
        module_logger.info(f"Total records processed: {total_records_processed}")
        module_logger.info(f"Total records loaded successfully: {total_records_loaded_successfully}")
        module_logger.info(f"Total records sent to DLQ: {total_records_sent_to_dlq}")
        return True
    except ValueError as ve: # pragma: no cover
        module_logger.critical(f"Configuration Error in pipeline: {ve}", exc_info=True)
    except psycopg.Error as db_err: # pragma: no cover
        module_logger.critical(
            f"A Psycopg 3 database error occurred: {db_err.diag.message_primary if db_err.diag else str(db_err)}",
            exc_info=True)
    except Exception as e: # pragma: no cover
        module_logger.critical(f"A critical error occurred during GTFS ETL: {e}", exc_info=True)
    finally:
        if conn and not conn.closed:
            conn.close()
            module_logger.info("Database connection closed.")
        download.cleanup_temp_file(TEMP_DOWNLOAD_PATH)
        if TEMP_EXTRACT_PATH.exists():
            cleanup_directory(TEMP_EXTRACT_PATH, ensure_dir_exists_after=True) # Use common cleanup
        end_time = datetime.now()
        duration = end_time - start_time
        module_logger.info(
            f"===== GTFS ETL Pipeline Finished at {end_time.isoformat()}. Duration: {duration} ====="
        )
    return False


if __name__ == "__main__": # pragma: no cover
    # Ensure logging is configured if running standalone
    # This check is simple: if root logger has no handlers, configure.
    if not logging.getLogger().handlers:
        # Call the new common_setup_logging
        common_setup_logging(
            log_level=logging.INFO,
            log_to_console=True,
            log_prefix="[GTFS-PIPELINE-DIRECT]" # Example prefix for direct execution
        )

    _feed_url_check = os.environ.get("GTFS_FEED_URL", CONFIG_GTFS_FEED_URL)
    if _feed_url_check == "https://example.com/default_gtfs_feed.zip":
        module_logger.warning("CRITICAL: GTFS_FEED_URL is a placeholder. Pipeline might fail.")
        module_logger.warning("Set it like: export GTFS_FEED_URL='your_actual_url'")

    if DB_PARAMS.get("password") == "yourStrongPasswordHere" and not os.environ.get("PG_OSM_PASSWORD"):
        module_logger.warning("CRITICAL: PostgreSQL password is a placeholder. Set PG_OSM_PASSWORD or update DB_PARAMS.")

    pipeline_succeeded = run_full_gtfs_etl_pipeline()
    if pipeline_succeeded:
        module_logger.info("Main pipeline execution completed successfully (from __main__ call).")
        sys.exit(0)
    else:
        module_logger.error("Main pipeline execution failed (from __main__ call).")
        sys.exit(1)