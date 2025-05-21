#!/usr/bin/env python3
"""
GTFS Update Module

This module provides functionality for running the GTFS ETL pipeline.
It downloads, processes, and loads GTFS data into a PostgreSQL database.
It can be used as a module or as a standalone script.
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

import pandas as pd
import psycopg2
import requests
from psycopg2 import sql
from psycopg2.extras import execute_values, DictCursor

# Import from the gtfs_processor package if available
try:
    from . import main_pipeline, utils
except (ImportError, ValueError):
    # When run as a standalone script, these imports might fail
    # We'll handle this case in the main function
    pass

# Default values
GTFS_URL = os.environ.get("GTFS_FEED_URL", "https://example.com/path/to/your/gtfs-feed.zip")
DB_PARAMS = {
    "dbname": os.environ.get("PG_GIS_DB", "gis"),
    "user": os.environ.get("PG_OSM_USER", "osmuser"),
    "password": os.environ.get("PG_OSM_PASSWORD", "yourStrongPasswordHere"),
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": os.environ.get("PG_PORT", "5432")
}
DOWNLOAD_PATH = "/tmp/gtfs_download.zip"
EXTRACT_PATH = "/tmp/gtfs_extracted/"
LOG_FILE = "/var/log/update_gtfs.log"

# Configure logging
logger = logging.getLogger(__name__)

GTFS_DEFINITIONS = {
    "agency.txt": {
        "table_name": "gtfs_agency",
        "columns": [
            ("agency_id", "TEXT", "PRIMARY KEY"), ("agency_name", "TEXT", "NOT NULL"),
            ("agency_url", "TEXT", "NOT NULL"), ("agency_timezone", "TEXT", "NOT NULL"),
            ("agency_lang", "TEXT", ""), ("agency_phone", "TEXT", ""),
            ("agency_fare_url", "TEXT", ""), ("agency_email", "TEXT", "")
        ],
        "required_fields_in_file": ["agency_name", "agency_url", "agency_timezone"]
    },
    "stops.txt": {
        "table_name": "gtfs_stops",
        "columns": [
            ("stop_id", "TEXT", "PRIMARY KEY"), ("stop_code", "TEXT", ""),
            ("stop_name", "TEXT", ""), ("stop_desc", "TEXT", ""),
            ("stop_lat", "DOUBLE PRECISION", ""), ("stop_lon", "DOUBLE PRECISION", ""),
            ("zone_id", "TEXT", ""), ("stop_url", "TEXT", ""),
            ("location_type", "INTEGER", ""), ("parent_station", "TEXT", ""),
            ("stop_timezone", "TEXT", ""), ("wheelchair_boarding", "INTEGER", ""),
            ("geom", "GEOMETRY(Point, 4326)", "")
        ],
        "required_fields_in_file": ["stop_id"]
    },
    "routes.txt": {
        "table_name": "gtfs_routes",
        "columns": [
            ("route_id", "TEXT", "PRIMARY KEY"), ("agency_id", "TEXT", ""),
            ("route_short_name", "TEXT", "DEFAULT ''"), ("route_long_name", "TEXT", "DEFAULT ''"),
            ("route_desc", "TEXT", ""), ("route_type", "INTEGER", "NOT NULL"),
            ("route_url", "TEXT", ""), ("route_color", "TEXT", ""),
            ("route_text_color", "TEXT", ""), ("route_sort_order", "INTEGER", "")
        ],
        "required_fields_in_file": ["route_id", "route_type"]
    },
    "trips.txt": {
        "table_name": "gtfs_trips",
        "columns": [
            ("route_id", "TEXT", "NOT NULL"), ("service_id", "TEXT", "NOT NULL"),
            ("trip_id", "TEXT", "PRIMARY KEY"), ("trip_headsign", "TEXT", ""),
            ("trip_short_name", "TEXT", ""), ("direction_id", "INTEGER", ""),
            ("block_id", "TEXT", ""), ("shape_id", "TEXT", ""),
            ("wheelchair_accessible", "INTEGER", ""), ("bikes_allowed", "INTEGER", "")
        ],
        "required_fields_in_file": ["route_id", "service_id", "trip_id"]
    },
    "stop_times.txt": {
        "table_name": "gtfs_stop_times",
        "columns": [
            ("trip_id", "TEXT", "NOT NULL"), ("arrival_time", "TEXT", ""),
            ("departure_time", "TEXT", ""), ("stop_id", "TEXT", "NOT NULL"),
            ("stop_sequence", "INTEGER", "NOT NULL"), ("stop_headsign", "TEXT", ""),
            ("pickup_type", "INTEGER", ""), ("drop_off_type", "INTEGER", ""),
            ("shape_dist_traveled", "DOUBLE PRECISION", ""), ("timepoint", "INTEGER", "")
        ],
        "composite_pk": ["trip_id", "stop_sequence"],
        "required_fields_in_file": ["trip_id", "stop_id", "stop_sequence"]
    },
    "calendar.txt": {
        "table_name": "gtfs_calendar",
        "columns": [
            ("service_id", "TEXT", "PRIMARY KEY"),
            ("monday", "INTEGER", "NOT NULL"), ("tuesday", "INTEGER", "NOT NULL"),
            ("wednesday", "INTEGER", "NOT NULL"), ("thursday", "INTEGER", "NOT NULL"),
            ("friday", "INTEGER", "NOT NULL"), ("saturday", "INTEGER", "NOT NULL"),
            ("sunday", "INTEGER", "NOT NULL"),
            ("start_date", "TEXT", "NOT NULL"), ("end_date", "TEXT", "NOT NULL")
        ],
        "required_fields_in_file": ["service_id", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
                                    "sunday", "start_date", "end_date"]
    },
    "calendar_dates.txt": {
        "table_name": "gtfs_calendar_dates",
        "columns": [
            ("service_id", "TEXT", "NOT NULL"), ("date", "TEXT", "NOT NULL"),
            ("exception_type", "INTEGER", "NOT NULL")
        ],
        "composite_pk": ["service_id", "date"],
        "required_fields_in_file": ["service_id", "date", "exception_type"]
    },
    "shapes.txt": {
        "table_name": "gtfs_shapes_points",
        "columns": [
            ("shape_id", "TEXT", "NOT NULL"),
            ("shape_pt_lat", "DOUBLE PRECISION", ""),
            ("shape_pt_lon", "DOUBLE PRECISION", ""),
            ("shape_pt_sequence", "INTEGER", "NOT NULL"),
            ("shape_dist_traveled", "DOUBLE PRECISION", "")
        ],
        "composite_pk": ["shape_id", "shape_pt_sequence"],
        "required_fields_in_file": ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"]
    }
}
GTFS_LOAD_ORDER = [
    "agency.txt", "stops.txt", "routes.txt", "calendar.txt", "calendar_dates.txt",
    "shapes.txt", "trips.txt", "stop_times.txt"
]
GTFS_FOREIGN_KEYS = [
    ("gtfs_routes", ["agency_id"], "gtfs_agency", ["agency_id"], "fk_routes_agency_id"),
    ("gtfs_trips", ["route_id"], "gtfs_routes", ["route_id"], "fk_trips_route_id"),
    ("gtfs_trips", ["shape_id"], "gtfs_shapes_lines", ["shape_id"], "fk_trips_shape_id_lines"),
    ("gtfs_stop_times", ["trip_id"], "gtfs_trips", ["trip_id"], "fk_stop_times_trip_id"),
    ("gtfs_stop_times", ["stop_id"], "gtfs_stops", ["stop_id"], "fk_stop_times_stop_id"),
    ("gtfs_stops", ["parent_station"], "gtfs_stops", ["stop_id"], "fk_stops_parent_station"),
]


def sanitize_identifier(name):
    return '"' + name.replace('"', '""').strip() + '"'


def create_tables_from_schema(conn):
    cursor = conn.cursor()
    logger.info("Setting up database schema based on GTFS_DEFINITIONS...")
    for filename in GTFS_LOAD_ORDER:
        if filename not in GTFS_DEFINITIONS: continue
        details = GTFS_DEFINITIONS[filename]
        table_name = details["table_name"]

        cols_defs_str_list = []
        for col_name, col_type, col_constraints in details["columns"]:
            cols_defs_str_list.append(f"{sanitize_identifier(col_name)} {col_type} {col_constraints}")

        cols_sql_segment = sql.SQL(", ").join(map(sql.SQL, cols_defs_str_list))

        pk_def_sql_segment = sql.SQL("")
        if details.get("composite_pk"):
            quoted_pks = [sql.Identifier(pk_col) for pk_col in details["composite_pk"]]
            pk_def_sql_segment = sql.SQL(", PRIMARY KEY ({})").format(sql.SQL(", ").join(quoted_pks))

        create_sql = sql.SQL("CREATE TABLE IF NOT EXISTS {} ({}{});").format(
            sql.Identifier(table_name),
            cols_sql_segment,
            pk_def_sql_segment
        )
        try:
            logger.debug(f"Executing SQL for table {table_name}: {create_sql.as_string(conn)}")
            cursor.execute(create_sql)
        except psycopg2.Error as e:
            logger.error(f"Error creating table {table_name}: {e}")
            raise

    try:
        cursor.execute("""
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
    except psycopg2.Error as e:
        logger.error(f"Error creating table gtfs_shapes_lines: {e}")
        raise

    try:
        cursor.execute("""
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
                       """)
        logger.info("DLQ table gtfs_dlq ensured.")
    except psycopg2.Error as e:
        logger.error(f"Error creating DLQ table gtfs_dlq: {e}")
    cursor.close()
    logger.info("Database schema setup/verification queries prepared.")


def drop_all_gtfs_foreign_keys(conn):
    cursor = conn.cursor()
    logger.info("Dropping existing GTFS foreign keys before data load...")
    for from_table, _, _, _, fk_name in reversed(GTFS_FOREIGN_KEYS):
        cursor.execute("SELECT to_regclass(%s);", (f'public.{from_table}',))
        if not cursor.fetchone()[0]:
            logger.debug(f"Table {from_table} for FK {fk_name} does not exist. Skipping drop.")
            continue

        cursor.execute("""
                       SELECT 1
                       FROM information_schema.table_constraints
                       WHERE constraint_type = 'FOREIGN KEY'
                         AND constraint_name = %s
                         AND table_name = %s;
                       """, (fk_name, from_table))

        if cursor.fetchone():
            try:
                logger.info(f"Dropping foreign key {fk_name} from {from_table}.")
                cursor.execute(sql.SQL("ALTER TABLE {} DROP CONSTRAINT IF EXISTS {};").format(
                    sql.Identifier(from_table), sql.Identifier(fk_name)))
            except psycopg2.Error as e:
                logger.warning(f"Could not drop foreign key {fk_name} from {from_table}: {e}")
        else:
            logger.debug(f"Foreign key {fk_name} on {from_table} does not exist. Skipping drop.")
    cursor.close()
    logger.info("Finished attempting to drop GTFS foreign keys.")


def add_foreign_keys_from_schema(conn):
    cursor = conn.cursor()
    logger.info("Attempting to add foreign keys post-data load...")
    for from_table, from_cols_list, to_table, to_cols_list, fk_name in GTFS_FOREIGN_KEYS:
        cursor.execute("SELECT to_regclass(%s);", (f'public.{from_table}',))
        if not cursor.fetchone()[0]:
            logger.warning(f"Source Table {from_table} for FK {fk_name} does not exist. Skipping.")
            continue
        cursor.execute("SELECT to_regclass(%s);", (f'public.{to_table}',))
        if not cursor.fetchone()[0]:
            logger.warning(f"Target Table {to_table} for FK {fk_name} does not exist. Skipping.")
            continue

        from_cols_sql = sql.SQL(', ').join(map(sql.Identifier, from_cols_list))
        to_cols_sql = sql.SQL(', ').join(map(sql.Identifier, to_cols_list))

        alter_sql = sql.SQL(
            "ALTER TABLE {} ADD CONSTRAINT {} FOREIGN KEY ({}) REFERENCES {} ({}) DEFERRABLE INITIALLY DEFERRED;").format(
            sql.Identifier(from_table), sql.Identifier(fk_name), from_cols_sql,
            sql.Identifier(to_table), to_cols_sql
        )
        try:
            logger.info(
                f"Adding FK {fk_name} on {from_table}({', '.join(from_cols_list)}) -> {to_table}({', '.join(to_cols_list)})")
            cursor.execute(alter_sql)
        except psycopg2.Error as e:
            logger.error(f"Could not add foreign key {fk_name}: {e}", exc_info=True)
            try:
                dlq_cursor = conn.cursor()  # Use a separate cursor for DLQ if main one is in error state from alter
                dlq_cursor.execute(
                    "INSERT INTO gtfs_dlq (gtfs_filename, error_reason, notes) VALUES (%s, %s, %s);",
                    ("SCHEMA_FK_ERROR", str(e)[:1000], f"Failed to add FK: {fk_name}")
                )
                dlq_cursor.close()
                # conn.commit() # Commit DLQ log separately - careful with main transaction
            except Exception as dlq_e:
                logger.error(f"Failed to log FK error to DLQ: {dlq_e}")
    cursor.close()
    logger.info("Foreign key application process finished.")


def download_and_extract_gtfs():
    logger.info(f"Starting GTFS download from {GTFS_URL}")
    if GTFS_URL == "https://example.com/path/to/your/gtfs-feed.zip":
        logger.critical("GTFS_URL is a placeholder. Please set it.")
        raise ValueError("GTFS_URL not configured.")
    try:
        response = requests.get(GTFS_URL, timeout=120)
        response.raise_for_status()
        Path(DOWNLOAD_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(DOWNLOAD_PATH, 'wb') as f:
            f.write(response.content)
        logger.info(f"GTFS feed downloaded to {DOWNLOAD_PATH}")

        logger.info(f"Unzipping {DOWNLOAD_PATH} to {EXTRACT_PATH}")
        if os.path.exists(EXTRACT_PATH):
            shutil.rmtree(EXTRACT_PATH)
        os.makedirs(EXTRACT_PATH, exist_ok=True)

        with zipfile.ZipFile(DOWNLOAD_PATH, 'r') as zip_ref:
            zip_ref.extractall(EXTRACT_PATH)
        logger.info("GTFS feed unzipped successfully.")
        return True
    except requests.exceptions.RequestException as re:
        logger.error(f"Download Error: {re}", exc_info=True)
    except zipfile.BadZipFile as bze:
        logger.error(f"Unzip Error: {bze}", exc_info=True)
    except Exception as e:
        logger.error(f"Error in download/extract: {e}", exc_info=True)
    return False


def load_data_to_db_with_dlq(conn):
    cursor = conn.cursor()
    available_files_in_feed = {f.lower() for f in os.listdir(EXTRACT_PATH) if f.endswith('.txt')}
    logger.info(f"Files found in GTFS feed for loading: {available_files_in_feed}")

    for gtfs_filename_key in GTFS_LOAD_ORDER:
        actual_file_to_load = None
        for f_in_dir in os.listdir(EXTRACT_PATH):
            if f_in_dir.lower() == gtfs_filename_key.lower() and f_in_dir.endswith('.txt'):
                actual_file_to_load = f_in_dir
                break

        if not actual_file_to_load:
            if gtfs_filename_key in GTFS_DEFINITIONS:
                logging.warning(f"Expected GTFS file '{gtfs_filename_key}' not found in archive. Skipping.")
            continue

        schema_info = GTFS_DEFINITIONS[gtfs_filename_key]
        table_name = schema_info["table_name"]
        filepath = os.path.join(EXTRACT_PATH, actual_file_to_load)

        logging.info(f"--- Processing {actual_file_to_load} for table {table_name} ---")
        actual_load_cols = []

        try:
            df = pd.read_csv(filepath, dtype=str, keep_default_na=False, na_filter=False, encoding='utf-8-sig')

            if df.empty:
                logging.info(f"File {actual_file_to_load} is empty. Skipping table {table_name}.")
                continue

            table_db_columns_from_schema = [col_def[0] for col_def in schema_info["columns"] if col_def[0] != "geom"]
            df_for_copy = pd.DataFrame()

            csv_header_stripped = [col.strip() for col in df.columns]
            df.columns = csv_header_stripped

            for db_col_name in table_db_columns_from_schema:
                if db_col_name in csv_header_stripped:
                    df_for_copy[db_col_name] = df[db_col_name]
                    actual_load_cols.append(db_col_name)
                else:
                    is_required_by_spec = db_col_name in schema_info.get("required_fields_in_file", [])
                    is_not_null_in_db = any(
                        c[0] == db_col_name and "NOT NULL" in c[2].upper() and "DEFAULT" not in c[2].upper() for c in
                        schema_info["columns"])
                    if is_required_by_spec or is_not_null_in_db:
                        err_msg = f"Required/NOT NULL column '{db_col_name}' for table '{table_name}' missing in '{actual_file_to_load}'."
                        logging.error(err_msg)
                        cursor.execute(
                            "INSERT INTO gtfs_dlq (gtfs_filename, error_reason, notes) VALUES (%s, %s, %s);",
                            (actual_file_to_load, err_msg,
                             "Whole file load skipped due to missing required/NOT NULL column.")
                        )
                        raise ValueError(err_msg)
                    else:
                        df_for_copy[db_col_name] = pd.Series([None] * len(df), dtype=object)
                        actual_load_cols.append(db_col_name)

            if not actual_load_cols:
                logging.warning(f"No columns to load for {table_name} from {actual_file_to_load}. Skipping.")
                continue

            cursor.execute(sql.SQL("TRUNCATE TABLE {} CASCADE;").format(sql.Identifier(table_name)))
            logging.info(f"Table {table_name} truncated.")

            sio = io.StringIO()
            df_for_copy[actual_load_cols].to_csv(sio, index=False, header=True, sep=',', quotechar='"', escapechar='\\',
                                                 na_rep='')
            sio.seek(0)

            db_cols_sql_identifiers = sql.SQL(', ').join(map(sql.Identifier, actual_load_cols))
            copy_sql_stmt = sql.SQL(
                "COPY {} ({}) FROM STDIN WITH CSV HEADER DELIMITER ',' QUOTE '\"' ESCAPE '\\' NULL AS '';").format(
                sql.Identifier(table_name),
                db_cols_sql_identifiers
            )

            logging.debug(
                f"Executing COPY for {table_name} with {len(df_for_copy)} records. Columns: {actual_load_cols}")
            cursor.copy_expert(copy_sql_stmt, sio)
            loaded_count = cursor.rowcount if cursor.rowcount is not None else len(df_for_copy)
            logging.info(f"{loaded_count} records loaded into {table_name}.")

            if table_name == "gtfs_stops":
                lat_col, lon_col, geom_col = "stop_lat", "stop_lon", "geom"
                if lat_col in actual_load_cols and lon_col in actual_load_cols:
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
                        sql.Identifier(lon_col), sql.Identifier(lat_col)
                    )
                    try:
                        cursor.execute(update_geom_sql)
                        logging.info(f"Geometry updated for {table_name} ({cursor.rowcount} rows affected).")
                    except psycopg2.Error as geom_e:
                        logging.error(f"Error updating geometry for {table_name}: {geom_e}", exc_info=True)
                        raise geom_e
                else:
                    logging.warning(
                        f"Could not update geometry for {table_name}: '{lat_col}' or '{lon_col}' not in processed columns: {actual_load_cols}")

        except ValueError as ve:
            logging.error(
                f"ValueError processing {actual_file_to_load} for {table_name}: {ve}. File processing aborted for this file.")
            raise
        except psycopg2.Error as db_err:
            logging.error(f"Database error processing {actual_file_to_load} for {table_name}: {db_err}", exc_info=True)
            try:
                dlq_cursor = conn.cursor()  # New cursor for DLQ
                dlq_cursor.execute(
                    "INSERT INTO gtfs_dlq (gtfs_filename, error_reason, notes) VALUES (%s, %s, %s);",
                    (actual_file_to_load, str(db_err)[:1000],
                     f"DB error during COPY/TRUNCATE/GEOM_UPDATE for table {table_name}")
                )
                dlq_cursor.close()
                # conn.commit() # Commit DLQ entry separately. Risky inside main transaction. Better to log and let main tx fail.
            except Exception as e_dlq:
                logging.error(f"Failed to write to DLQ for {actual_file_to_load} after DB error: {e_dlq}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error processing file {actual_file_to_load} for table {table_name}: {e}",
                          exc_info=True)
            try:
                dlq_cursor = conn.cursor()
                dlq_cursor.execute(
                    "INSERT INTO gtfs_dlq (gtfs_filename, error_reason, notes) VALUES (%s, %s, %s);",
                    (actual_file_to_load, str(e)[:1000], f"Unexpected error for table {table_name}")
                )
                dlq_cursor.close()
            except Exception as e_dlq:
                logging.error(f"Failed to write to DLQ for {actual_file_to_load} after unexpected error: {e_dlq}")
            raise

    if "shapes.txt" in GTFS_DEFINITIONS and "shapes.txt".lower() in available_files_in_feed:
        try:
            logging.info("Aggregating shape points into linestrings (gtfs_shapes_lines)...")
            cursor.execute("TRUNCATE TABLE gtfs_shapes_lines CASCADE;")
            cursor.execute("""
                           INSERT INTO gtfs_shapes_lines (shape_id, geom)
                           SELECT shape_id,
                                  ST_MakeLine(
                                          ST_SetSRID(ST_MakePoint(
                                                             CAST(NULLIF(TRIM(CAST(shape_pt_lon AS TEXT)), '') AS DOUBLE PRECISION),
                                                             CAST(NULLIF(TRIM(CAST(shape_pt_lat AS TEXT)), '') AS DOUBLE PRECISION)
                                                     ),
                                                     4326) ORDER BY CAST(NULLIF(TRIM(CAST(shape_pt_sequence AS TEXT)), '') AS INTEGER)
                                  )
                           FROM gtfs_shapes_points
                           WHERE NULLIF(TRIM(CAST(shape_pt_lon AS TEXT)), '') IS NOT NULL
                             AND NULLIF(TRIM(CAST(shape_pt_lat AS TEXT)), '') IS NOT NULL
                             AND NULLIF(TRIM(CAST(shape_pt_sequence AS TEXT)), '') IS NOT NULL
                           GROUP BY shape_id
                           HAVING count(*) > 1;
                           """)
            logging.info(f"Shape linestrings aggregated ({cursor.rowcount} shapes).")
        except Exception as e:
            logging.error(f"Error aggregating shape linestrings: {e}", exc_info=True)
            try:
                dlq_cursor = conn.cursor()
                dlq_cursor.execute(
                    "INSERT INTO gtfs_dlq (gtfs_filename, error_reason, notes) VALUES (%s, %s, %s);",
                    ("shapes.txt", f"Aggregation to lines failed: {e}", "gtfs_shapes_lines might be incomplete")
                )
                dlq_cursor.close()
            except Exception as e_dlq:
                logging.error(f"Failed to write to DLQ for shape aggregation error: {e_dlq}")
            raise  # Let main transaction fail if shape aggregation is critical
    cursor.close()


def run_full_gtfs_etl_pipeline():
    """
    Orchestrates the full GTFS ETL (Extract, Transform, Load) pipeline.

    This function is similar to the main_pipeline.run_full_gtfs_etl_pipeline function,
    but it's implemented directly in this module for standalone use.

    Returns:
        bool: True if the pipeline completed successfully, False otherwise.
    """
    start_time = datetime.now()
    logger.info(f"=== Starting GTFS Full Update Process at {start_time.isoformat()} ===")
    conn = None
    success = False

    try:
        if GTFS_URL == "https://example.com/path/to/your/gtfs-feed.zip" and "GTFS_FEED_URL" not in os.environ:
            msg = "CRITICAL: GTFS_URL is a placeholder. Set GTFS_FEED_URL environment variable or update script."
            logger.critical(msg)
            raise ValueError(msg)

        if DB_PARAMS["password"] == "yourStrongPasswordHere":
            msg = "CRITICAL: Database password is a placeholder. Update DB_PARAMS in the script."
            logger.critical(msg)
            raise ValueError(msg)

        if not download_and_extract_gtfs():
            raise Exception("GTFS feed download or extraction failed. See logs for details.")

        conn = psycopg2.connect(**DB_PARAMS)
        conn.autocommit = False
        logger.info("Database connection successful. Transaction started.")

        create_tables_from_schema(conn)
        conn.commit()  # Commit schema changes separately and first

        drop_all_gtfs_foreign_keys(conn)
        conn.commit()  # Commit FK drops

        # New transaction for data loading and FK re-creation
        load_data_to_db_with_dlq(conn)
        add_foreign_keys_from_schema(conn)

        conn.commit()
        success = True
        logger.info("All GTFS processing steps completed and committed successfully.")

    except ValueError as ve:
        logger.critical(f"Configuration/Validation Error: {ve}")
        if conn and not conn.closed: conn.rollback()
    except Exception as e:
        logger.critical(f"A critical error occurred during the GTFS update process: {e}", exc_info=True)
        if conn and not conn.closed: conn.rollback()
    finally:
        if conn and not conn.closed:
            conn.close()
            logger.info("Database connection closed.")

        if os.path.exists(DOWNLOAD_PATH):
            try:
                os.remove(DOWNLOAD_PATH)
            except OSError as e:
                logger.error(f"Error removing download file '{DOWNLOAD_PATH}': {e}")
        if os.path.exists(EXTRACT_PATH):
            try:
                shutil.rmtree(EXTRACT_PATH)
            except OSError as e:
                logger.error(f"Error removing extract directory '{EXTRACT_PATH}': {e}")
        logger.info("Cleanup of temporary files attempted.")

        end_time = datetime.now()
        duration = end_time - start_time
        if success:
            logger.info(
                f"GTFS Full Update Process completed successfully at {end_time.isoformat()}. Duration: {duration}")
        else:
            logger.error(f"GTFS Full Update Process FAILED at {end_time.isoformat()}. Duration: {duration}")
        logger.info("=== GTFS Full Update Process Finished ===")

    return success


def setup_logging(log_level=logging.INFO, log_file=LOG_FILE, log_to_console=True):
    """
    Set up logging configuration.

    Args:
        log_level: The logging level to use
        log_file: Path to the log file
        log_to_console: Whether to log to console
    """
    # Clear existing handlers
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Create handlers
    handlers = []
    if log_file:
        file_handler = logging.FileHandler(log_file, mode='a')
        handlers.append(file_handler)

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        handlers.append(console_handler)

    # Configure logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(name)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=handlers
    )

    logger.info("Logging configured.")


def main():
    """
    Main entry point for the script.

    Parses command-line arguments, sets up logging, and runs the GTFS ETL pipeline.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Run the GTFS ETL pipeline to download, process, and load GTFS data."
    )
    parser.add_argument(
        "--gtfs-url",
        dest="gtfs_url",
        default=os.environ.get("GTFS_FEED_URL", "https://example.com/path/to/your/gtfs-feed.zip"),
        help="URL of the GTFS feed to download and process."
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level."
    )
    parser.add_argument(
        "--log-file",
        dest="log_file",
        default=LOG_FILE,
        help="Path to the log file."
    )
    args = parser.parse_args()

    # Set up logging
    log_level = getattr(logging, args.log_level)
    setup_logging(
        log_level=log_level,
        log_file=args.log_file,
        log_to_console=True
    )

    # Get GTFS feed URL from command-line argument or environment variable
    gtfs_url_to_check = args.gtfs_url
    if gtfs_url_to_check == "https://example.com/path/to/your/gtfs-feed.zip" and "GTFS_FEED_URL" in os.environ:
        gtfs_url_to_check = os.environ["GTFS_FEED_URL"]

    # Log configuration
    logger.info(f"GTFS Feed URL to be processed: {gtfs_url_to_check}")
    logger.info(
        f"Target Database: dbname='{DB_PARAMS.get('dbname')}', user='{DB_PARAMS.get('user')}', host='{DB_PARAMS.get('host')}'")

    try:
        # Set the GTFS_FEED_URL environment variable for the pipeline
        os.environ["GTFS_FEED_URL"] = gtfs_url_to_check

        # Try to use the main_pipeline module if available
        try:
            # If we're running as part of the gtfs_processor package
            success = main_pipeline.run_full_gtfs_etl_pipeline()
        except (NameError, AttributeError):
            # If we're running as a standalone script
            success = run_full_gtfs_etl_pipeline()

        # Exit with appropriate status code
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.critical(f"An error occurred during the GTFS update process: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
