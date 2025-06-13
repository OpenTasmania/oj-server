#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main orchestrator for the GTFS (General Transit Feed Specification) ETL pipeline.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import gtfs_kit  # type: ignore[import-untyped]
import pandas as pd
import psycopg

from common.core_utils import setup_logging as common_setup_logging
from common.db_utils import get_db_connection
from common.file_utils import (
    cleanup_directory,  # Updated cleanup_directory is used here
)
from processors.plugins.importers.transit.gtfs import (
    download,
    load,
    transform,
)
from processors.plugins.importers.transit.gtfs import (
    schema_definitions as schemas,
)

from .db_setup import (
    add_foreign_keys_from_schema,
    create_tables_from_schema,
)
from .pipeline_definitions import GTFS_LOAD_ORDER

module_logger = logging.getLogger(__name__)

DEFAULT_GTFS_FEED_URL_CONFIG = "https://example.com/default_gtfs_feed.zip"

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
    Runs the complete GTFS ETL (Extract, Transform, Load) pipeline using the GTFS kit. This
    function handles downloading, extracting, validating, transforming, and loading GTFS
    data into a database.

    In the first step, the latest GTFS feed is downloaded from the specified URL and
    extracted. The second step loads the GTFS feed into memory using the gtfs-kit library,
    while assuming the input GTFS data has already been validated. The function then
    ensures that the required database schema (tables and primary keys) exists.

    Next, it iterates through the predefined GTFS file load order to transform and load
    each table into a database. Table-specific transformation logic is applied (e.g.,
    geometrizing stops or shapes using gtfs-kit). Optionally processed geometry data is
    also handled for specific tables such as `shapes`. Any failures to download data,
    extract files, validate schema, connect to the database, or process data result in the
    pipeline halting.

    Finally, the function records statistics on the pipeline's execution, such as the
    total number of records processed, loaded successfully, and sent to a dead-letter
    queue (DLQ). Temporary directories created for file downloads and extraction are
    cleaned up during this operation.

    Arguments:
        None

    Returns:
        bool: True if the pipeline succeeded, otherwise False.
    """
    start_time = datetime.now()
    module_logger.info(
        f"===== GTFS ETL Pipeline (gtfs-kit) Started at {start_time.isoformat()} ====="
    )

    current_gtfs_feed_url = os.environ.get(
        "GTFS_FEED_URL", DEFAULT_GTFS_FEED_URL_CONFIG
    )
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
        module_logger.info(
            "--- Step 1: Downloading and Extracting GTFS Feed ---"
        )
        if not download.download_gtfs_feed(
            current_gtfs_feed_url, TEMP_DOWNLOAD_PATH
        ):
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

        module_logger.info("--- Step 2: Reading Feed with gtfs-kit ---")
        feed: gtfs_kit.Feed = gtfs_kit.read_feed(
            str(TEMP_EXTRACT_PATH), dist_units="km"
        )  # type: ignore[assignment]
        module_logger.info(
            f"Feed loaded. Detected tables: {list(feed.list_fields().keys())}"  # type: ignore[attr-defined]
        )
        module_logger.warning(
            "--- Feed Validation Responsibility --- This pipeline assumes input GTFS data has been validated. Proceeding."
        )

        conn = get_db_connection(DB_PARAMS)
        if not conn:
            module_logger.critical(
                "Failed to connect to the database. Pipeline aborted."
            )
            return False

        with conn.transaction():
            module_logger.info(
                "--- Step 3: Ensuring database schema exists (tables & PKs) ---"
            )
            create_tables_from_schema(conn)
            module_logger.info(
                "Database schema transaction component complete."
            )

            total_records_processed = 0
            total_records_loaded_successfully = 0
            total_records_sent_to_dlq = 0

            module_logger.info(
                "--- Step 4: Transforming and Loading GTFS Data ---"
            )
            for gtfs_filename_key in GTFS_LOAD_ORDER:
                table_base_name = gtfs_filename_key.replace(".txt", "")
                df_original: Optional[pd.DataFrame] = getattr(
                    feed, table_base_name, None
                )

                if df_original is None or df_original.empty:
                    if (
                        table_base_name == "shapes"
                        and gtfs_filename_key == "shapes.txt"
                    ):
                        module_logger.info(
                            "Table 'shapes' (points data from shapes.txt) not found or empty. If lines are derived, this might be fine."
                        )
                    elif (
                        table_base_name == "gtfs_shapes_lines"
                        and gtfs_filename_key == "gtfs_shapes_lines.txt"
                    ):
                        module_logger.info(
                            "Conceptual table 'gtfs_shapes_lines' - actual data processing happens under 'shapes.txt' key."
                        )
                        continue
                    elif table_base_name not in [
                        "frequencies",
                        "feed_info",
                        "transfers",
                        "pathways",
                        "levels",
                        "attributions",
                        "translations",
                    ]:
                        module_logger.warning(
                            f"Table '{table_base_name}' (from {gtfs_filename_key}) not found in feed or is empty. Skipping."
                        )
                    else:
                        module_logger.info(
                            f"Optional table '{table_base_name}' not found or empty. Skipping."
                        )
                    continue

                df_for_processing = df_original.copy()
                module_logger.info(
                    f"Processing table: {table_base_name} with {len(df_for_processing)} records."
                )
                total_records_processed += len(df_for_processing)

                file_schema_definition = schemas.GTFS_FILE_SCHEMAS.get(
                    gtfs_filename_key
                )
                if not file_schema_definition:
                    module_logger.warning(
                        f"No DB schema definition for '{gtfs_filename_key}'. Skipping."
                    )
                    continue

                df_transformed: pd.DataFrame
                if table_base_name == "stops":
                    if feed.stops is not None and not feed.stops.empty:  # type: ignore[attr-defined]
                        stops_gdf = gtfs_kit.geometrize_stops(feed.stops)  # type: ignore[attr-defined]
                        df_transformed = (
                            stops_gdf.copy()
                            if stops_gdf is not None
                            else df_for_processing.copy()
                        )
                    else:
                        module_logger.warning(
                            "feed.stops is missing or empty. Cannot compute stop geometries."
                        )
                        df_transformed = df_for_processing.copy()
                elif (
                    table_base_name == "shapes"
                    and gtfs_filename_key == "shapes.txt"
                ):
                    if feed.shapes is not None and not feed.shapes.empty:  # type: ignore[attr-defined]
                        shapes_lines_gdf = gtfs_kit.geometrize_shapes(
                            feed.shapes  # type: ignore[attr-defined]
                        )
                        if (
                            shapes_lines_gdf is not None
                            and not shapes_lines_gdf.empty
                        ):
                            module_logger.info(
                                f"Processing {len(shapes_lines_gdf)} shape geometries into 'gtfs_shapes_lines'."
                            )
                            temp_shapes_df = shapes_lines_gdf.copy()
                            shapes_lines_db_schema = (
                                schemas.GTFS_FILE_SCHEMAS.get(
                                    "gtfs_shapes_lines.txt"
                                )
                            )
                            if not shapes_lines_db_schema:
                                module_logger.error(
                                    "Schema for 'gtfs_shapes_lines.txt' not found. Cannot load shape lines."
                                )
                                df_transformed = df_for_processing.copy()
                            else:
                                final_shapes_lines_df = (
                                    transform.transform_dataframe(
                                        temp_shapes_df, shapes_lines_db_schema
                                    )
                                )
                                loaded_sl, dlq_sl = load.load_dataframe_to_db(
                                    conn,
                                    final_shapes_lines_df,
                                    shapes_lines_db_schema["db_table_name"],
                                    shapes_lines_db_schema,
                                    dlq_table_name=f"dlq_{shapes_lines_db_schema['db_table_name']}",
                                )
                                total_records_loaded_successfully += loaded_sl
                                total_records_sent_to_dlq += dlq_sl
                                df_transformed = df_for_processing.copy()
                        else:
                            module_logger.info(
                                "No shape geometries computed or result is empty for 'gtfs_shapes_lines'."
                            )
                            df_transformed = df_for_processing.copy()
                    else:
                        module_logger.info(
                            "No shapes data in feed. Skipping line geometrization. Original shapes.txt points will be processed if they exist."
                        )
                        df_transformed = df_for_processing.copy()
                else:
                    df_transformed = df_for_processing.copy()

                if (
                    df_transformed.empty
                    and table_base_name == "shapes"
                    and gtfs_filename_key == "shapes.txt"
                ):
                    module_logger.info(
                        f"Skipping loading for original points in '{table_base_name}' (from shapes.txt) as its DataFrame is empty after (optional) line processing."
                    )
                    continue

                final_df_for_loading = transform.transform_dataframe(
                    df_transformed, file_schema_definition
                )
                if final_df_for_loading.empty:
                    module_logger.info(
                        f"DataFrame for {table_base_name} is empty after transformation. Skipping load."
                    )
                    continue

                loaded_count, dlq_count_from_load = load.load_dataframe_to_db(
                    conn,
                    final_df_for_loading,
                    file_schema_definition["db_table_name"],
                    file_schema_definition,
                    dlq_table_name=f"dlq_{file_schema_definition['db_table_name']}",
                )
                total_records_loaded_successfully += loaded_count
                total_records_sent_to_dlq += dlq_count_from_load

            module_logger.info(
                "--- Step 5: Adding Foreign Keys (within transaction) ---"
            )
            add_foreign_keys_from_schema(conn)

        module_logger.info(
            "--- Main Transaction (Schema, Data Load, FKs) Complete ---"
        )
        module_logger.info(
            f"Total records processed from feed files: {total_records_processed}"
        )
        module_logger.info(
            f"Total records loaded successfully to DB: {total_records_loaded_successfully}"
        )
        module_logger.info(
            f"Total records sent to DLQ: {total_records_sent_to_dlq}"
        )
        return True
    except ValueError as ve:
        module_logger.critical(
            f"Configuration Error in pipeline: {ve}", exc_info=True
        )
    except psycopg.Error as db_err:
        module_logger.critical(
            f"A Psycopg 3 database error occurred: {db_err.diag.message_primary if db_err.diag else str(db_err)}",
            exc_info=True,
        )
    except Exception as e:
        module_logger.critical(
            f"A critical error occurred during GTFS ETL: {e}", exc_info=True
        )
    finally:
        if conn and not conn.closed:
            conn.close()
            module_logger.info("Database connection closed.")
        download.cleanup_temp_file(TEMP_DOWNLOAD_PATH)
        if TEMP_EXTRACT_PATH.exists():
            cleanup_directory(
                TEMP_EXTRACT_PATH,
                app_settings=None,
                ensure_dir_exists_after=True,
                current_logger=module_logger,
            )
        end_time = datetime.now()
        duration = end_time - start_time
        module_logger.info(
            f"===== GTFS ETL Pipeline Finished at {end_time.isoformat()}. Duration: {duration} ====="
        )
    return False


if __name__ == "__main__":
    if not logging.getLogger().handlers:
        common_setup_logging(
            log_level=logging.INFO,
            log_to_console=True,
            log_prefix="[GTFS-PIPELINE-DIRECT]",
        )

    _feed_url_check = os.environ.get(
        "GTFS_FEED_URL", DEFAULT_GTFS_FEED_URL_CONFIG
    )
    if _feed_url_check == "https://example.com/default_gtfs_feed.zip":
        module_logger.warning(
            "CRITICAL: GTFS_FEED_URL is a placeholder. Pipeline might fail."
        )
        module_logger.warning(
            "Set it like: export GTFS_FEED_URL='your_actual_url'"
        )

    if DB_PARAMS.get(
        "password"
    ) == "yourStrongPasswordHere" and not os.environ.get("PG_OSM_PASSWORD"):
        module_logger.warning(
            "CRITICAL: PostgreSQL password is a placeholder. Set PG_OSM_PASSWORD or update DB_PARAMS."
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
