#!/usr/bin/env python3
import logging
import os
from datetime import datetime
from pathlib import Path

# Import from other modules in the package
from . import download
from . import load
from . import schema_definitions as schemas  # Assuming GTFS_SCHEMA and other defs are here
from . import utils  # For setup_logging and get_db_connection

# Configure logging for this module (or rely on root logger configured by run_gtfs_update.py)
logger = logging.getLogger(__name__)

# --- Configuration (These would ideally be loaded from a config file or environment) ---
# These paths and URLs should match what's defined in the main run_gtfs_update.py or passed in.
# For now, using placeholders or deriving from environment for flexibility.

# Fetched from environment, with defaults matching previous script discussions
GTFS_FEED_URL = os.environ.get("GTFS_FEED_URL", "https://example.com/path/to/your/gtfs-feed.zip")
DB_PARAMS = {  # These should ideally come from utils or a config manager
    "dbname": os.environ.get("PG_GIS_DB", "gis"),
    "user": os.environ.get("PG_OSM_USER", "osmuser"),
    "password": os.environ.get("PG_OSM_PASSWORD", "yourStrongPasswordHere"),  # Placeholder!
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": os.environ.get("PG_PORT", "5432")
}

TEMP_DOWNLOAD_DIR = Path(os.environ.get("GTFS_TEMP_DOWNLOAD_DIR", "/tmp/gtfs_pipeline_downloads"))
TEMP_ZIP_FILENAME = "gtfs_feed.zip"
TEMP_EXTRACT_DIR_NAME = "gtfs_extracted_feed"

# Ensure temporary directories exist
TEMP_DOWNLOAD_PATH = TEMP_DOWNLOAD_DIR / TEMP_ZIP_FILENAME
TEMP_EXTRACT_PATH = TEMP_DOWNLOAD_DIR / TEMP_EXTRACT_DIR_NAME


def run_full_gtfs_etl_pipeline():
    """
    Orchestrates the full GTFS ETL (Extract, Transform, Load) pipeline.
    """
    start_time = datetime.now()
    logger.info(f"===== GTFS ETL Pipeline Started at {start_time.isoformat()} =====")

    # Create temporary directories if they don't exist
    TEMP_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_EXTRACT_PATH.mkdir(parents=True, exist_ok=True)  # extract_gtfs_feed also creates it

    conn = None  # Initialize conn to None
    try:
        # --- 1. EXTRACT: Download and Unzip GTFS Feed ---
        logger.info("--- Step 1: Downloading and Extracting GTFS Feed ---")
        if not download.download_gtfs_feed(GTFS_FEED_URL, TEMP_DOWNLOAD_PATH):
            logger.critical("Failed to download GTFS feed. Pipeline aborted.")
            return False

        if not download.extract_gtfs_feed(TEMP_DOWNLOAD_PATH, TEMP_EXTRACT_PATH):
            logger.critical("Failed to extract GTFS feed. Pipeline aborted.")
            return False
        logger.info("GTFS feed downloaded and extracted successfully.")

        # --- Get Database Connection ---
        conn = utils.get_db_connection(DB_PARAMS)  # Assuming utils.py has this
        if not conn:
            logger.critical("Failed to connect to the database. Pipeline aborted.")
            return False

        # --- Setup Schema (Idempotent: CREATE TABLE IF NOT EXISTS) ---
        logger.info("--- Ensuring database schema exists ---")
        # Assuming schema_definitions.py contains GTFS_SCHEMA and GTFS_DLQ_SCHEMA structures
        # And utils.py might contain a function to create tables based on these.
        # For now, let's assume a setup_all_schemas function exists in utils or load.
        # Or, directly call the schema setup from load.py if that's where it's defined
        load.setup_gtfs_schema(conn)  # From load.py example, creates main tables
        # You would also need a similar function to create DLQ tables
        # e.g., utils.setup_dlq_schemas(conn, schemas.GTFS_DLQ_SCHEMA_DEFINITIONS)
        logger.info("Database schema verified/created.")

        # --- 2. TRANSFORM & VALIDATE & 3. LOAD (File by File) ---
        logger.info("--- Step 2 & 3: Validating, Transforming, and Loading GTFS Data ---")

        total_records_processed = 0
        total_records_loaded_successfully = 0
        total_records_sent_to_dlq = 0

        # Iterate through GTFS files in a defined load order
        for gtfs_filename in schemas.GTFS_LOAD_ORDER:
            file_schema_definition = schemas.GTFS_SCHEMA.get(gtfs_filename)
            if not file_schema_definition:
                logger.warning(f"No schema definition found for '{gtfs_filename}'. Skipping.")
                continue

            file_path_on_disk = TEMP_EXTRACT_PATH / gtfs_filename
            if not file_path_on_disk.exists():
                # Only log warning if the file is generally expected (not for purely optional ones if not present)
                # GTFS_SCHEMA keys are files we expect to define
                logger.warning(f"GTFS file '{gtfs_filename}' not found in extracted feed. Skipping.")
                continue

            logger.info(f"--- Processing file: {gtfs_filename} ---")

            # Read raw data (e.g., using pandas as an intermediary)
            # validate.py and transform.py will need access to this raw data.
            # This is a simplified flow; in reality, validate/transform might stream or chunk.
            try:
                raw_df = pd.read_csv(file_path_on_disk, dtype=str, keep_default_na=False, na_values=[''])
                logger.info(f"Read {len(raw_df)} raw records from {gtfs_filename}.")
                total_records_processed += len(raw_df)
            except pd.errors.EmptyDataError:
                logger.info(f"File {gtfs_filename} is empty. Skipping.")
                continue
            except Exception as e:
                logger.error(f"Failed to read {gtfs_filename} into DataFrame: {e}. Skipping file.")
                # Optionally, log this file itself to a "failed files" log/table
                continue

            # Validate records
            # validated_df, rejected_records_with_errors = validate.validate_dataframe(raw_df, file_schema_definition)
            # For each rejected_record in rejected_records_with_errors:
            #     load.log_to_dlq(conn, f"dlq_{file_schema_definition['table_name']}", rejected_record, error_reason, gtfs_filename)
            #     total_records_sent_to_dlq += 1
            # This assumes validate.py returns a clean DataFrame and a list of rejected records.
            # For simplicity now, let's assume validate.py is part of transform and returns a single df or raises errors.
            # A more robust pipeline would separate validation and DLQ logging before transformation.

            # Transform records (cleaning, type casting, geometry creation)
            # transformed_df = transform.transform_dataframe(validated_df, file_schema_definition)
            # If transform fails for some rows, those could also go to DLQ.
            # For now, let's assume transform.py prepares the DataFrame for load.py

            # This is a placeholder for a more sophisticated validate & transform pipeline per file.
            # The current load.py assumes the DataFrame passed to it is mostly ready.
            # Here, we'd integrate the more granular validation and transformation.
            # Let's assume for now transform.py takes raw_df and schema, returns clean_df and logs to DLQ itself.

            # Placeholder: For now, just pass raw_df assuming load.py will use schema
            # This needs to be replaced with calls to actual validate.py and transform.py
            df_for_loading = raw_df  # In a real pipeline, this would be the output of transform.py

            # Prepare DataFrame columns based on schema for loading
            # (This logic might be better inside transform.py or load.py)
            schema_cols = list(file_schema_definition.get("columns", {}).keys())
            df_cols_to_load = [col for col in schema_cols if col in df_for_loading.columns]
            final_df_for_loading = df_for_loading[df_cols_to_load].copy()

            # Add geom column placeholder if needed (transform.py should actually create WKT)
            geom_config = file_schema_definition.get("geom_config")
            if geom_config and geom_config.get("geom_col") not in final_df_for_loading.columns:
                final_df_for_loading[geom_config.get("geom_col")] = None  # transform.py populates this

            # --- This section needs real implementation of validate & transform ---
            # Example flow:
            # good_records_df, bad_records_info = validate.validate_records(raw_df, file_schema_definition, gtfs_filename)
            # for bad_rec, reason in bad_records_info:
            #    load.log_to_dlq(conn, f"dlq_{file_schema_definition['table_name']}", bad_rec, reason, gtfs_filename)
            #    total_records_sent_to_dlq +=1
            #
            # if not good_records_df.empty:
            #    transformed_df = transform.transform_records(good_records_df, file_schema_definition)
            #    loaded, _ = load.load_dataframe_to_db(conn, transformed_df, file_schema_definition['table_name'], file_schema_definition)
            #    total_records_loaded_successfully += loaded
            # else:
            #    logger.info(f"No valid records to load for {gtfs_filename} after validation.")
            # --- End placeholder ---

            # Current simplified load call (assumes df_for_loading is "good enough")
            # The DLQ name would be derived, e.g., f"dlq_{file_schema_definition['table_name']}"
            # The load_dataframe_to_db needs to be more aware of the schema for column ordering.
            # The provided load.py assumed the DataFrame passed was already ordered and cleaned.

            # We will use the load_dataframe_to_db function as defined in load.py
            # which now expects the dataframe to have columns matching the schema_definition.
            # The actual data cleaning and transformation would happen in transform.py
            # which is called before this. For this skeleton, we pass the 'final_df_for_loading'.

            # --- Conceptual call to transform (which would include validation and DLQ logging) ---
            # Assume transform.py has a function like:
            # transformed_df, newly_dlq_count = transform.process_file_data(
            #     conn, raw_df, file_schema_definition,
            #     f"dlq_{file_schema_definition['table_name']}", # Pass DLQ table name
            #     gtfs_filename
            # )
            # total_records_sent_to_dlq += newly_dlq_count
            # ----------------------------------------------------------------------------------
            # For now, we'll stick to the simpler path: load whatever pandas read.
            # This means the load_dataframe_to_db will do its best.
            # Granular DLQ logic needs to be built into validate.py and transform.py

            logger.info(f"Preparing to load data for {file_schema_definition['table_name']}...")
            loaded_count, dlq_count_from_load = load.load_dataframe_to_db(
                conn,
                final_df_for_loading,  # This DataFrame needs to be perfectly prepared by transform.py
                file_schema_definition['table_name'],
                file_schema_definition,
                dlq_table_name=f"dlq_{file_schema_definition['table_name']}"  # Pass DLQ table name
            )
            total_records_loaded_successfully += loaded_count
            # The dlq_count_from_load in current load.py is basic (for batch fails)
            # Real row-level DLQ would be reflected from validate/transform stages.

        # After all tables are loaded, attempt to create foreign keys
        logger.info("--- Adding Foreign Keys ---")
        load.add_foreign_keys(conn)  # From load.py

        logger.info("--- GTFS Data Load Phase Complete ---")
        logger.info(f"Total records encountered in files: {total_records_processed}")
        logger.info(f"Total records loaded successfully: {total_records_loaded_successfully}")
        logger.info(
            f"Total records sent to DLQ (needs full implementation): {total_records_sent_to_dlq}")  # This count needs to come from validate/transform

        conn.commit()  # Final commit for the entire process
        return True

    except ValueError as ve:  # Catch specific config error from download_and_extract_gtfs
        logger.critical(f"Configuration Error in pipeline: {ve}")
        if conn: conn.rollback()
    except Exception as e:
        logger.critical(f"A critical error occurred in the GTFS ETL pipeline: {e}", exc_info=True)
        if conn: conn.rollback()
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed.")
        download.cleanup_temp_file(TEMP_DOWNLOAD_PATH)
        # cleanup for TEMP_EXTRACT_PATH is handled in download.py or could be here
        if TEMP_EXTRACT_PATH.exists():
            utils.cleanup_directory(TEMP_EXTRACT_PATH)  # Assuming utils.py has this
            logger.info(f"Cleaned up extraction directory: {TEMP_EXTRACT_PATH}")

        end_time = datetime.now()
        duration = end_time - start_time
        logger.info(f"===== GTFS ETL Pipeline Finished at {end_time.isoformat()}. Duration: {duration} =====")

    return False


if __name__ == "__main__":
    # This is the entry point that would be called by scripts/run_gtfs_update.py
    # Setup basic logging if run directly for testing
    utils.setup_logging(log_level=logging.INFO)  # Assuming utils.py has setup_logging

    # Ensure critical environment variables are set for direct execution test
    if "GTFS_FEED_URL" not in os.environ or os.environ[
        "GTFS_FEED_URL"] == "https://example.com/path/to/your/gtfs-feed.zip":
        logger.warning("CRITICAL: GTFS_FEED_URL environment variable is not set or is a placeholder.")
        logger.warning("Set it like: export GTFS_FEED_URL='your_actual_url'")
        # For testing, you might provide a default or raise an error
        # For this example, we'll let it try the default and likely fail in download.

    if "PG_OSM_PASSWORD" not in os.environ and DB_PARAMS["password"] == "yourStrongPasswordHere":
        logger.warning("CRITICAL: PostgreSQL password is a placeholder.")
        logger.warning(
            "Set PGPASSWORD (for psql tool) or PG_OSM_PASSWORD (for this script's DB_PARAMS) environment variable, or update DB_PARAMS in script.")

    run_full_gtfs_etl_pipeline()
