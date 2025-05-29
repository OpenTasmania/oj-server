#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main orchestrator for the GTFS (General Transit Feed Specification) ETL pipeline.

This module coordinates the entire Extract, Transform, Load (ETL) process for
GTFS data using Psycopg 3 for database interactions. It handles:
1.  Downloading and extracting the GTFS feed.
2.  Setting up the database schema (tables for GTFS data and DLQ).
3.  Iterating through GTFS files in a defined order.
4.  Reading, (conceptually) validating, transforming, and loading data from
    each file into the corresponding database table.
5.  Applying foreign key constraints after data loading.
6.  Logging progress and errors throughout the pipeline.

The pipeline is designed to be idempotent where possible (e.g., creating tables
if they don't exist) and aims for robustness by attempting to process each
GTFS file individually. Transactions are managed for database operations.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import psycopg  # Psycopg 3: Replaces psycopg2

# Import from other modules in the GTFS processor package
from . import (
    download,
    load,
    utils,
)
from . import schema_definitions as schemas

# Import specific items needed for this pipeline's orchestration
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
    Orchestrate the full GTFS ETL (Extract, Transform, Load) pipeline using Psycopg 3.

    Steps:
    1.  Download the GTFS feed from `GTFS_FEED_URL`.
    2.  Extract the GTFS feed to a temporary directory.
    3.  Connect to the PostgreSQL database (Psycopg 3).
    4.  Ensure the database schema (tables) exists (within a transaction).
    5.  Process each GTFS file: Read, Validate, Transform, Load (main data operations within a transaction).
    6.  Add foreign key constraints (within the main data transaction).
    7.  Commit transactions (handled by `with conn.transaction():`) and clean up.

    Returns:
        True if the pipeline completed successfully, False otherwise.
    """
    start_time = datetime.now()
    module_logger.info(
        f"===== GTFS ETL Pipeline Started at {start_time.isoformat()} ====="
    )

    try:
        TEMP_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        TEMP_EXTRACT_PATH.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        module_logger.critical(
            f"Failed to create temporary directories: {e}. Pipeline aborted."
        )
        return False

    conn: Optional[psycopg.Connection] = None  # Psycopg 3: Type hint for connection
    try:
        module_logger.info(
            "--- Step 1: Downloading and Extracting GTFS Feed ---"
        )
        if not download.download_gtfs_feed(GTFS_FEED_URL, TEMP_DOWNLOAD_PATH):
            module_logger.critical(
                "Failed to download GTFS feed. Pipeline aborted."
            )
            return False

        if not download.extract_gtfs_feed(
                TEMP_DOWNLOAD_PATH, TEMP_EXTRACT_PATH
        ):
            module_logger.critical(
                "Failed to extract GTFS feed. Pipeline aborted."
            )
            return False
        module_logger.info("GTFS feed downloaded and extracted successfully.")

        conn = utils.get_db_connection(DB_PARAMS)  # utils.get_db_connection now returns a Psycopg 3 connection
        if not conn:
            module_logger.critical(
                "Failed to connect to the database. Pipeline aborted."
            )
            return False
        # Psycopg 3: Connections are autocommit by default. Explicit 'conn.autocommit = False' is removed.

        module_logger.info("--- Ensuring database schema exists ---")
        # Psycopg 3: Use 'with conn.transaction()' to manage atomic operations.
        with conn.transaction():
            create_tables_from_schema(conn)
        module_logger.info("Database schema transaction complete (committed or rolled back on error).")

        module_logger.info(
            "--- Step 2 & 3: Validating, Transforming, and Loading GTFS Data ---"
        )
        total_records_processed = 0
        total_records_loaded_successfully = 0
        total_records_sent_to_dlq = 0

        # Psycopg 3: Main data loading and FK addition in a single transaction.
        with conn.transaction():
            for gtfs_filename in GTFS_LOAD_ORDER:
                file_schema_definition = schemas.GTFS_FILE_SCHEMAS.get(gtfs_filename)
                if not file_schema_definition:
                    module_logger.warning(
                        f"No schema definition found for '{gtfs_filename}' in "
                        "schema_definitions.py. Skipping."
                    )
                    continue

                file_path_on_disk = TEMP_EXTRACT_PATH / gtfs_filename
                if not file_path_on_disk.exists():
                    module_logger.warning(
                        f"GTFS file '{gtfs_filename}' not found in extracted feed "
                        f"at '{file_path_on_disk}'. Skipping."
                    )
                    continue

                module_logger.info(f"--- Processing file: {gtfs_filename} ---")

                try:
                    # Pandas 2+: Use dtype_backend for nullable dtypes and pd.NA.
                    raw_df = pd.read_csv(
                        file_path_on_disk,
                        dtype_backend="numpy_nullable",
                        keep_default_na=False,
                        na_values=[""],
                    )
                    module_logger.info(
                        f"Read {len(raw_df)} raw records from {gtfs_filename} "
                        f"using Pandas 2 nullable dtypes."
                    )
                    total_records_processed += len(raw_df)
                except pd.errors.EmptyDataError:
                    module_logger.info(f"File {gtfs_filename} is empty. Skipping.")
                    continue
                except Exception as e_read:
                    module_logger.error(
                        f"Failed to read {gtfs_filename} into DataFrame: {e_read}. "
                        "Skipping file.",
                        exc_info=True,
                    )
                    continue

                # Conceptual validation/transformation (placeholders from original file)
                # pydantic_model = file_schema_definition.get('model')
                # if pydantic_model:
                #    validated_df, rejected_records = utils.validate_dataframe_with_pydantic(...)
                #    df_for_loading = transform.transform_dataframe(validated_df, ...)
                # else:
                #    df_for_loading = raw_df
                df_for_loading = raw_df  # Current placeholder logic

                schema_cols = list(file_schema_definition.get("columns", {}).keys())
                df_cols_to_load = [col for col in schema_cols if col in df_for_loading.columns]
                if not df_cols_to_load:
                    module_logger.warning(
                        f"No schema columns found in DataFrame for {gtfs_filename}. Skipping load."
                    )
                    continue
                final_df_for_loading = df_for_loading[df_cols_to_load].copy()

                geom_config = file_schema_definition.get("geom_config")
                if geom_config:
                    geom_col_name = geom_config.get("geom_col")
                    if (geom_col_name and geom_col_name not in final_df_for_loading.columns):
                        final_df_for_loading[geom_col_name] = None

                module_logger.info(
                    f"Preparing to load data for table "
                    f"'{file_schema_definition['db_table_name']}'..."
                )
                loaded_count, dlq_count_from_load = load.load_dataframe_to_db(
                    conn,
                    final_df_for_loading,
                    file_schema_definition["db_table_name"],
                    file_schema_definition,
                    dlq_table_name=f"dlq_{file_schema_definition['db_table_name']}",
                )
                total_records_loaded_successfully += loaded_count
                total_records_sent_to_dlq += dlq_count_from_load

            module_logger.info("--- Adding Foreign Keys ---")
            add_foreign_keys_from_schema(conn)
        # Psycopg 3: Transaction for data load & FKs is committed here if 'with' block succeeded.
        module_logger.info("--- GTFS Data Load and FK Transaction Complete ---")

        module_logger.info(
            f"Total records encountered in files: {total_records_processed}"
        )
        module_logger.info(
            f"Total records loaded successfully: {total_records_loaded_successfully}"
        )
        module_logger.info(
            f"Total records sent to DLQ (basic count): {total_records_sent_to_dlq}"
        )
        return True

    except ValueError as ve:
        module_logger.critical(f"Configuration Error in pipeline: {ve}")
        # Psycopg 3: Rollback handled by 'with conn.transaction()' if error originated there.
    except psycopg.Error as db_err:  # Psycopg 3: Specific catch for database errors
        module_logger.critical(
            f"A Psycopg 3 database error occurred in the GTFS ETL pipeline: {db_err}",
            exc_info=True,
        )
    except Exception as e:
        module_logger.critical(
            f"A critical error occurred in the GTFS ETL pipeline: {e}",
            exc_info=True,
        )
        # Psycopg 3: Rollback handled by 'with conn.transaction()' if error originated there.
    finally:
        if conn and not conn.closed:
            conn.close()  # Psycopg 3: Explicitly close connection
            module_logger.info("Database connection closed.")

        download.cleanup_temp_file(TEMP_DOWNLOAD_PATH)
        if TEMP_EXTRACT_PATH.exists():
            utils.cleanup_directory(TEMP_EXTRACT_PATH)
            module_logger.info(
                f"Cleaned up extraction directory: {TEMP_EXTRACT_PATH}"
            )

        end_time = datetime.now()
        duration = end_time - start_time
        module_logger.info(
            f"===== GTFS ETL Pipeline Finished at {end_time.isoformat()}. "
            f"Duration: {duration} ====="
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