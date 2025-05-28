#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main orchestrator for the GTFS (General Transit Feed Specification) ETL pipeline.

This module coordinates the entire Extract, Transform, Load (ETL) process for
GTFS data. It handles:
1.  Downloading and extracting the GTFS feed.
2.  Setting up the database schema (tables for GTFS data and DLQ).
3.  Iterating through GTFS files in a defined order.
4.  Reading, (conceptually) validating, transforming, and loading data from
    each file into the corresponding database table.
5.  Applying foreign key constraints after data loading.
6.  Logging progress and errors throughout the pipeline.

The pipeline is designed to be idempotent where possible (e.g., creating tables
if they don't exist) and aims for robustness by attempting to process each
GTFS file individually.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional  # For PgConnection type hint

import pandas as pd
import psycopg2  # For PgConnection type hint, actual connection in utils

# Import from other modules in the GTFS processor package
from . import (
    download,
    load,
    utils,  # For setup_logging, get_db_connection, cleanup_directory
)
from . import schema_definitions as schemas

# Import specific items needed for this pipeline's orchestration
from .update_gtfs import (
    GTFS_LOAD_ORDER,  # Relies on GTFS_LOAD_ORDER from update_gtfs or a shared config
    add_foreign_keys_from_schema,
    create_tables_from_schema,  # Assumes this is from a shared/adapted update_gtfs
)

# Import GTFS feed URL from a central configuration.
# This assumes `setup.config` is part of the accessible Python path when this
# module is run, or that `GTFS_FEED_URL` is set as an environment variable
# that `setup.config` might read.
try:
    from setup.config import GTFS_FEED_URL
except ImportError:
    # Fallback if setup.config is not available (e.g., running processor standalone)
    # In this case, ensure GTFS_FEED_URL environment variable is set.
    if "GTFS_FEED_URL" not in os.environ:
        print(
            "CRITICAL: GTFS_FEED_URL environment variable not set and "
            "setup.config.GTFS_FEED_URL could not be imported. Pipeline cannot run.",
            file=sys.stderr
        )
        # Exit or raise an error to prevent running without a URL
        # For now, let it try to proceed and fail in download if URL is bad.
    GTFS_FEED_URL = os.environ.get(
        "GTFS_FEED_URL",
        "https://example.com/default_gtfs_feed.zip"  # Placeholder default
    )


module_logger = logging.getLogger(__name__)

# --- Configuration ---
# Database connection parameters.
# These should ideally be sourced from environment variables or a secure config.
# The `utils.get_db_connection` function will use its defaults if these are
# not explicitly passed or if environment variables it checks are not set.
DB_PARAMS: dict[str, str] = {
    "dbname": os.environ.get("PG_GIS_DB", "gis"),  # Consistent with update_gtfs.py
    "user": os.environ.get("PG_OSM_USER", "osmuser"),
    "password": os.environ.get("PG_OSM_PASSWORD", "yourStrongPasswordHere"),
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": os.environ.get("PG_PORT", "5432"),
}

# Temporary directories for pipeline operation.
TEMP_DOWNLOAD_DIR = Path(
    os.environ.get("GTFS_TEMP_DOWNLOAD_DIR", "/tmp/gtfs_pipeline_downloads")
)
TEMP_ZIP_FILENAME = "gtfs_feed.zip"  # Name for the downloaded zip file.
TEMP_EXTRACT_DIR_NAME = "gtfs_extracted_feed"  # Subdirectory for extracted files.

# Full paths for download and extraction.
TEMP_DOWNLOAD_PATH = TEMP_DOWNLOAD_DIR / TEMP_ZIP_FILENAME
TEMP_EXTRACT_PATH = TEMP_DOWNLOAD_DIR / TEMP_EXTRACT_DIR_NAME


def run_full_gtfs_etl_pipeline() -> bool:
    """
    Orchestrate the full GTFS ETL (Extract, Transform, Load) pipeline.

    Steps:
    1.  Download the GTFS feed from `GTFS_FEED_URL`.
    2.  Extract the GTFS feed to a temporary directory.
    3.  Connect to the PostgreSQL database.
    4.  Ensure the database schema (tables) exists using definitions from
        `schema_definitions.py` and potentially `update_gtfs.py`.
    5.  Process each GTFS file in the `GTFS_LOAD_ORDER`:
        a.  Read the raw data (e.g., using Pandas).
        b.  (Conceptual) Validate data against Pydantic models from `schemas`.
        c.  (Conceptual) Transform data (cleaning, type casting, geometry creation).
        d.  Load the processed data into the corresponding database table.
            Records failing validation/transformation should be routed to a DLQ.
    6.  Add foreign key constraints to the database tables.
    7.  Commit the transaction and clean up temporary files.

    Returns:
        True if the pipeline completed successfully, False otherwise.
    """
    start_time = datetime.now()
    module_logger.info(
        f"===== GTFS ETL Pipeline Started at {start_time.isoformat()} ====="
    )

    # Ensure temporary directories exist.
    try:
        TEMP_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        # `extract_gtfs_feed` also creates extract_path, but good to ensure.
        TEMP_EXTRACT_PATH.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        module_logger.critical(
            f"Failed to create temporary directories: {e}. Pipeline aborted."
        )
        return False

    conn: Optional[psycopg2.extensions.connection] = None
    try:
        # --- 1. EXTRACT: Download and Unzip GTFS Feed ---
        module_logger.info("--- Step 1: Downloading and Extracting GTFS Feed ---")
        if not download.download_gtfs_feed(GTFS_FEED_URL, TEMP_DOWNLOAD_PATH):
            module_logger.critical("Failed to download GTFS feed. Pipeline aborted.")
            return False

        if not download.extract_gtfs_feed(TEMP_DOWNLOAD_PATH, TEMP_EXTRACT_PATH):
            module_logger.critical("Failed to extract GTFS feed. Pipeline aborted.")
            return False
        module_logger.info("GTFS feed downloaded and extracted successfully.")

        # --- Get Database Connection ---
        # `utils.get_db_connection` uses DB_PARAMS or its own defaults.
        conn = utils.get_db_connection(DB_PARAMS)
        if not conn:
            module_logger.critical("Failed to connect to the database. Pipeline aborted.")
            return False
        conn.autocommit = False  # Ensure transactions are managed.

        # --- Setup Schema (Idempotent: CREATE TABLE IF NOT EXISTS) ---
        module_logger.info("--- Ensuring database schema exists ---")
        # `create_tables_from_schema` (from update_gtfs or similar)
        # should handle main GTFS tables and potentially a DLQ table.
        create_tables_from_schema(conn)
        # TODO: Explicitly create DLQ tables per entity if not handled by above.
        # e.g., utils.setup_dlq_tables(conn, schemas.GTFS_DLQ_SCHEMA_DEFINITIONS)
        module_logger.info("Database schema verified/created.")
        conn.commit()  # Commit schema changes before data loading.

        # --- 2. TRANSFORM & VALIDATE & 3. LOAD (File by File) ---
        module_logger.info(
            "--- Step 2 & 3: Validating, Transforming, and Loading GTFS Data ---"
        )

        total_records_processed = 0
        total_records_loaded_successfully = 0
        total_records_sent_to_dlq = 0  # Requires full validate/transform integration

        # Iterate through GTFS files in a defined load order (from update_gtfs).
        for gtfs_filename in GTFS_LOAD_ORDER:
            file_schema_definition = schemas.GTFS_FILE_SCHEMAS.get(gtfs_filename)
            if not file_schema_definition:
                module_logger.warning(
                    f"No schema definition found for '{gtfs_filename}' in "
                    "schema_definitions.py. Skipping."
                )
                continue

            # Construct path to the individual GTFS text file.
            file_path_on_disk = TEMP_EXTRACT_PATH / gtfs_filename
            if not file_path_on_disk.exists():
                # Log warning if an expected file (key in GTFS_FILE_SCHEMAS) is missing.
                module_logger.warning(
                    f"GTFS file '{gtfs_filename}' not found in extracted feed "
                    f"at '{file_path_on_disk}'. Skipping."
                )
                continue

            module_logger.info(f"--- Processing file: {gtfs_filename} ---")

            # Read raw data (e.g., using pandas).
            try:
                # Read all as string initially to preserve original values for validation.
                raw_df = pd.read_csv(
                    file_path_on_disk,
                    dtype='str',
                    keep_default_na=False,  # Keep empty strings as is
                    na_values=[""],  # Treat empty strings as NA for some ops if needed later
                )
                module_logger.info(
                    f"Read {len(raw_df)} raw records from {gtfs_filename}."
                )
                total_records_processed += len(raw_df)
            except pd.errors.EmptyDataError:
                module_logger.info(f"File {gtfs_filename} is empty. Skipping.")
                continue
            except Exception as e_read:
                module_logger.error(
                    f"Failed to read {gtfs_filename} into DataFrame: {e_read}. "
                    "Skipping file.", exc_info=True
                )
                # Optionally, log this file itself to a "failed files" log/table.
                continue

            # --- Conceptual Validation and Transformation Steps ---
            # These steps would use functions from `validate.py` and `transform.py`.
            #
            # 1. Validate `raw_df` against Pydantic model from `file_schema_definition`.
            #    pydantic_model = file_schema_definition.get('model')
            #    if pydantic_model:
            #        validated_df, rejected_records = utils.validate_dataframe_with_pydantic(
            #            raw_df, pydantic_model, gtfs_filename
            #        )
            #        for rejected_info in rejected_records:
            #            load.log_to_dlq( # Assuming log_to_dlq is adapted
            #                conn,
            #                f"dlq_{file_schema_definition['db_table_name']}",
            #                rejected_info['original_record'],
            #                str(rejected_info['errors']), # Convert Pydantic errors to str
            #                gtfs_filename
            #            )
            #            total_records_sent_to_dlq += 1
            #    else:
            #        module_logger.warning(f"No Pydantic model for {gtfs_filename}, skipping Pydantic validation.")
            #        validated_df = raw_df # Or handle as error
            #
            # 2. Transform `validated_df`.
            #    transformed_df = transform.transform_dataframe(
            #        validated_df, file_schema_definition
            #    )
            #    df_for_loading = transformed_df
            # --- End Conceptual Steps ---

            # For this simplified pipeline structure, we'll do basic column selection
            # and pass to load.py, assuming more complex V&T is done by a dedicated processor.
            # This placeholder logic prepares the DataFrame for the current `load.py`.
            df_for_loading = raw_df  # Placeholder: should be output of transform.py

            # Prepare DataFrame columns based on schema for loading.
            # This logic might be better inside transform.py or load.py.
            schema_cols = list(file_schema_definition.get("columns", {}).keys())
            df_cols_to_load = [
                col for col in schema_cols if col in df_for_loading.columns
            ]
            if not df_cols_to_load:
                module_logger.warning(
                    f"No schema columns found in DataFrame for {gtfs_filename}. Skipping load."
                )
                continue
            final_df_for_loading = df_for_loading[df_cols_to_load].copy()

            # Add geom column placeholder if needed (transform.py should create WKT).
            geom_config = file_schema_definition.get("geom_config")
            if geom_config:
                geom_col_name = geom_config.get("geom_col")
                if geom_col_name and geom_col_name not in final_df_for_loading.columns:
                    # This implies transform.py would create this column with WKT strings.
                    final_df_for_loading[geom_col_name] = None

            module_logger.info(
                f"Preparing to load data for table "
                f"'{file_schema_definition['db_table_name']}'..."
            )
            # `load_dataframe_to_db` expects the DataFrame to have columns
            # matching the schema definition.
            loaded_count, dlq_count_from_load = load.load_dataframe_to_db(
                conn,
                final_df_for_loading,
                file_schema_definition["db_table_name"],
                file_schema_definition,  # Pass full schema info for column mapping and geom handling
                dlq_table_name=f"dlq_{file_schema_definition['db_table_name']}",
            )
            total_records_loaded_successfully += loaded_count
            total_records_sent_to_dlq += dlq_count_from_load  # Basic DLQ from load.py

        # After all tables are loaded, attempt to create foreign keys.
        module_logger.info("--- Adding Foreign Keys ---")
        add_foreign_keys_from_schema(conn)  # From update_gtfs or similar.

        conn.commit()  # Final commit for the entire data load and FK process.
        module_logger.info("--- GTFS Data Load Phase Complete ---")
        module_logger.info(
            f"Total records encountered in files: {total_records_processed}"
        )
        module_logger.info(
            f"Total records loaded successfully: {total_records_loaded_successfully}"
        )
        module_logger.info(
            f"Total records sent to DLQ (basic count): {total_records_sent_to_dlq}"
            # More accurate DLQ count requires full V&T integration.
        )
        return True

    except ValueError as ve:  # E.g., config error from download_and_extract_gtfs
        module_logger.critical(f"Configuration Error in pipeline: {ve}")
        if conn:
            conn.rollback()
    except Exception as e:
        module_logger.critical(
            f"A critical error occurred in the GTFS ETL pipeline: {e}",
            exc_info=True,
        )
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            module_logger.info("Database connection closed.")

        # Cleanup temporary files and directories.
        download.cleanup_temp_file(TEMP_DOWNLOAD_PATH)
        if TEMP_EXTRACT_PATH.exists():
            # `utils.cleanup_directory` should handle recursive deletion.
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
    # This block allows direct execution of the pipeline, useful for testing.
    # It assumes necessary environment variables (DB_PARAMS, GTFS_FEED_URL) are set,
    # or it relies on the defaults defined in this script or in `utils.py`.

    # Setup basic logging if run directly for testing.
    # The `utils.setup_logging` function should be robust.
    utils.setup_logging(log_level=logging.INFO)

    # Check critical environment variables for direct execution.
    if (GTFS_FEED_URL == "https://example.com/default_gtfs_feed.zip" and
            os.environ.get("GTFS_FEED_URL", "").strip() == ""):
        module_logger.warning(
            "CRITICAL: GTFS_FEED_URL is a placeholder or not set. "
            "Pipeline might fail at download."
        )
        module_logger.warning("Set it like: export GTFS_FEED_URL='your_actual_url'")

    if (DB_PARAMS["password"] == "yourStrongPasswordHere" and
            not os.environ.get("PG_OSM_PASSWORD")):
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
        module_logger.info("Main pipeline execution completed successfully (from __main__ call).")
    else:
        module_logger.error("Main pipeline execution failed (from __main__ call).")