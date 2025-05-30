#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main orchestrator for the GTFS (General Transit Feed Specification) ETL pipeline.

This module coordinates the entire Extract, Transform, Load (ETL) process for
GTFS data using Psycopg 3 for database interactions and gtfs-kit for
reading and validating GTFS feeds. It handles:
1.  Downloading and extracting the GTFS feed.
2.  Reading the GTFS feed using gtfs-kit.
3.  Validating the feed using gtfs-kit.
4.  Setting up the database schema.
5.  Transforming and loading data from each relevant GTFS table into the
    corresponding database table.
6.  Applying foreign key constraints after data loading.
7.  Logging progress and errors.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import psycopg
import gtfs_kit

from . import download, load, utils, transform
from . import schema_definitions as schemas
from .update_gtfs import (
    GTFS_LOAD_ORDER,
    add_foreign_keys_from_schema,
    create_tables_from_schema,
)

try:
    from setup.config import GTFS_FEED_URL
except ImportError:
    if "GTFS_FEED_URL" not in os.environ:
        print(
            "CRITICAL: GTFS_FEED_URL environment variable not set and "
            "setup.config.GTFS_FEED_URL could not be imported. Pipeline cannot run.",
            file=sys.stderr,
        )
    GTFS_FEED_URL = os.environ.get(
        "GTFS_FEED_URL",
        "https://example.com/default_gtfs_feed.zip",
    )

module_logger = logging.getLogger(__name__)

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


def run_full_gtfs_etl_pipeline() -> bool:
    """
    Orchestrate the full GTFS ETL pipeline using gtfs-kit and Psycopg 3.

    Steps:
    1.  Download and extract the GTFS feed.
    2.  Read the feed using gtfs-kit.
    3.  Validate the feed using gtfs-kit.
    4.  Connect to PostgreSQL and ensure the schema exists.
    5.  Process each GTFS table: Transform data and load to the database.
    6.  Add foreign key constraints.
    7.  Clean up temporary files.

    Returns:
        True if the pipeline completed successfully, False otherwise.
    """
    start_time = datetime.now()
    module_logger.info(
        f"===== GTFS ETL Pipeline (gtfs-kit) Started at {start_time.isoformat()} ====="
    )

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
        if not download.download_gtfs_feed(GTFS_FEED_URL, TEMP_DOWNLOAD_PATH):
            module_logger.critical("Failed to download GTFS feed. Pipeline aborted.")
            return False
        if not download.extract_gtfs_feed(TEMP_DOWNLOAD_PATH, TEMP_EXTRACT_PATH):
            module_logger.critical("Failed to extract GTFS feed. Pipeline aborted.")
            return False
        module_logger.info("GTFS feed downloaded and extracted successfully.")

        module_logger.info("--- Step 2: Reading Feed with gtfs-kit ---")
        feed = gtfs_kit.read_feed(str(TEMP_EXTRACT_PATH), dist_units='km')
        module_logger.info(f"Feed loaded. Detected tables: {feed.list_tables()}")

        module_logger.info("--- Step 3: Validating Feed with gtfs-kit ---")
        validation_issues_df = feed.validate()
        critical_errors_found = False
        if not validation_issues_df.empty:
            for index, issue in validation_issues_df.iterrows():
                log_level = logging.ERROR if issue['type'] == 'error' else logging.WARNING
                module_logger.log(
                    log_level,
                    f"GTFS Validation: [{issue['type']}] {issue['message']} "
                    f"(Table: {issue['table']}, Column: {issue['column']}, Rows: {issue['rows']})"
                )
                if issue['type'] == 'error':
                    critical_errors_found = True

        if critical_errors_found:
            module_logger.warning(
                "Critical GTFS validation errors found during feed validation. Proceeding with load, but data quality may be affected.")
            # To abort on critical errors, uncomment below:
            # module_logger.critical("Critical GTFS validation errors found. Pipeline aborted.")
            # return False
        module_logger.info("Feed validation complete.")

        conn = utils.get_db_connection(DB_PARAMS)
        if not conn:
            module_logger.critical("Failed to connect to the database. Pipeline aborted.")
            return False

        module_logger.info("--- Step 4: Ensuring database schema exists ---")
        with conn.transaction():
            create_tables_from_schema(conn)
        module_logger.info("Database schema transaction complete.")

        total_records_processed = 0
        total_records_loaded_successfully = 0
        total_records_sent_to_dlq = 0

        module_logger.info("--- Step 5: Transforming and Loading GTFS Data ---")

        with conn.transaction():
            for gtfs_filename_key in GTFS_LOAD_ORDER:
                table_base_name = gtfs_filename_key.replace('.txt', '')

                df_original: Optional[pd.DataFrame] = None
                if hasattr(feed, table_base_name):
                    df_original = getattr(feed, table_base_name)

                if df_original is None or df_original.empty:
                    module_logger.info(
                        f"Table '{table_base_name}' (from {gtfs_filename_key}) not found in feed or is empty. Skipping.")
                    continue

                df_for_processing = df_original.copy()
                module_logger.info(f"Processing table: {table_base_name} with {len(df_for_processing)} records.")
                total_records_processed += len(df_for_processing)

                file_schema_definition = schemas.GTFS_FILE_SCHEMAS.get(gtfs_filename_key)
                if not file_schema_definition:
                    module_logger.warning(f"No DB schema definition for '{gtfs_filename_key}'. Skipping.")
                    continue

                df_transformed: pd.DataFrame
                if table_base_name == 'stops':
                    feed_with_stop_geom = feed.compute_stop_geometry()  # This re-reads feed.stops and adds geometry
                    df_transformed = feed_with_stop_geom.stops.copy() if feed_with_stop_geom.stops is not None else df_for_processing
                elif table_base_name == 'shapes':
                    if feed.shapes is not None and not feed.shapes.empty:
                        shapes_geom_df = feed.compute_shape_geometry().shapes_geometry  # This produces a specific shapes_geometry DataFrame
                        if shapes_geom_df is not None and not shapes_geom_df.empty:
                            module_logger.info(
                                f"Processing {len(shapes_geom_df)} shape geometries into 'gtfs_shapes_lines'.")
                            temp_shapes_df = shapes_geom_df.copy()

                            shapes_lines_db_schema = schemas.GTFS_FILE_SCHEMAS.get("gtfs_shapes_lines.txt")
                            if not shapes_lines_db_schema:
                                shapes_lines_db_schema = {
                                    "db_table_name": "gtfs_shapes_lines",
                                    "columns": {"shape_id": {"type": "TEXT"}, "geom": {"type": "GEOMETRY"}},
                                    "pk_cols": ["shape_id"],
                                    "geom_config": {"geom_col": "geom", "srid": 4326}  # Added for transform_dataframe
                                }

                            final_shapes_lines_df = transform.transform_dataframe(temp_shapes_df,
                                                                                  shapes_lines_db_schema)

                            loaded_sl, dlq_sl = load.load_dataframe_to_db(
                                conn,
                                final_shapes_lines_df,
                                shapes_lines_db_schema["db_table_name"],
                                shapes_lines_db_schema,
                                dlq_table_name=f"dlq_{shapes_lines_db_schema['db_table_name']}",
                            )
                            total_records_loaded_successfully += loaded_sl
                            total_records_sent_to_dlq += dlq_sl
                        else:
                            module_logger.info("No shapes data to process for lines.")
                    continue
                else:
                    df_transformed = df_for_processing.copy()

                final_df_for_loading = transform.transform_dataframe(df_transformed, file_schema_definition)

                loaded_count, dlq_count_from_load = load.load_dataframe_to_db(
                    conn,
                    final_df_for_loading,
                    file_schema_definition["db_table_name"],
                    file_schema_definition,
                    dlq_table_name=f"dlq_{file_schema_definition['db_table_name']}",
                )
                total_records_loaded_successfully += loaded_count
                total_records_sent_to_dlq += dlq_count_from_load

            module_logger.info("--- Step 6: Adding Foreign Keys ---")
            add_foreign_keys_from_schema(conn)

        module_logger.info("--- GTFS Data Load and FK Transaction Complete ---")
        module_logger.info(f"Total records processed (sum of rows in feed tables used): {total_records_processed}")
        module_logger.info(f"Total records loaded successfully to DB: {total_records_loaded_successfully}")
        module_logger.info(f"Total records sent to DLQ: {total_records_sent_to_dlq}")
        return True

    except ValueError as ve:
        module_logger.critical(f"Configuration Error in pipeline: {ve}", exc_info=True)
    except psycopg.Error as db_err:
        module_logger.critical(f"A Psycopg 3 database error occurred: {db_err}", exc_info=True)
    except Exception as e:
        module_logger.critical(f"A critical error occurred: {e}", exc_info=True)
    finally:
        if conn and not conn.closed:
            conn.close()
            module_logger.info("Database connection closed.")
        download.cleanup_temp_file(TEMP_DOWNLOAD_PATH)
        if TEMP_EXTRACT_PATH.exists():
            utils.cleanup_directory(TEMP_EXTRACT_PATH)
        end_time = datetime.now()
        duration = end_time - start_time
        module_logger.info(
            f"===== GTFS ETL Pipeline Finished at {end_time.isoformat()}. Duration: {duration} ====="
        )
    return False


if __name__ == "__main__":
    utils.setup_logging(log_level=logging.INFO)

    if (
            GTFS_FEED_URL == "https://example.com/default_gtfs_feed.zip"
            and os.environ.get("GTFS_FEED_URL", "").strip() == ""
    ):
        module_logger.warning(
            "CRITICAL: GTFS_FEED_URL is a placeholder or not set. "
            "Pipeline might fail at download."
        )
        module_logger.warning(
            "Set it like: export GTFS_FEED_URL='your_actual_url'"
        )

    if DB_PARAMS[
        "password"
    ] == "yourStrongPasswordHere" and not os.environ.get("PG_OSM_PASSWORD"):
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
    else:
        module_logger.error(
            "Main pipeline execution failed (from __main__ call)."
        )