#!/usr/bin/env python3
import logging
import os
from typing import Tuple, List, Dict, Any, Optional, Type

import pandas as pd
from pydantic import ValidationError, BaseModel

# Import schema definitions
from . import schema_definitions as schemas  # To access GTFS_FILE_SCHEMAS and Pydantic models

logger = logging.getLogger(__name__)

# Default database parameters
DEFAULT_DB_PARAMS = {
    "dbname": os.environ.get("PG_OSM_DATABASE", "gis"),
    "user": os.environ.get("PG_OSM_USER", "osmuser"),
    "password": os.environ.get("PG_OSM_PASSWORD", "yourStrongPasswordHere"),
    "host": os.environ.get("PG_OSM_HOST", "localhost"),
    "port": os.environ.get("PG_OSM_PORT", "5432")
}


def setup_logging(log_level: int = logging.INFO, log_file: Optional[str] = None, log_to_console: bool = True) -> None:
    """
    Set up logging configuration.

    Args:
        log_level: The logging level to use
        log_file: Path to the log file (if None, no file logging is set up)
        log_to_console: Whether to log to console
    """
    handlers = []

    # Add file handler if log_file is provided
    if log_file:
        file_handler = logging.FileHandler(log_file)
        handlers.append(file_handler)

    # Add console handler if log_to_console is True
    if log_to_console:
        console_handler = logging.StreamHandler()
        handlers.append(console_handler)

    # Configure logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(name)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=handlers
    )

    logger.info("Logging configured.")


def get_db_connection(db_params: Dict[str, str] = None) -> Any:
    """
    Get a database connection using the provided parameters or DEFAULT_DB_PARAMS.

    Args:
        db_params: Database connection parameters (if None, DEFAULT_DB_PARAMS is used)

    Returns:
        A database connection object
    """
    import psycopg2

    # Use provided db_params or DEFAULT_DB_PARAMS
    params = db_params or DEFAULT_DB_PARAMS

    try:
        conn = psycopg2.connect(**params)
        logger.info(f"Connected to database {params.get('dbname')} on {params.get('host')}:{params.get('port')}")
        return conn
    except psycopg2.Error as e:
        logger.error(f"Failed to connect to database: {e}")
        return None


def cleanup_directory(directory_path: Path) -> None:
    """
    Clean up a directory by removing all files and subdirectories.

    Args:
        directory_path: Path to the directory to clean up
    """
    import shutil

    try:
        shutil.rmtree(directory_path)
        logger.info(f"Cleaned up directory: {directory_path}")
    except Exception as e:
        logger.error(f"Failed to clean up directory {directory_path}: {e}")


def validate_dataframe_with_pydantic(
        df: pd.DataFrame,
        pydantic_model: Type[BaseModel],
        gtfs_filename: str  # For logging/DLQ context
) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    Validates each row of a Pandas DataFrame against a given Pydantic model.

    Args:
        df: The input Pandas DataFrame with raw data.
        pydantic_model: The Pydantic model to validate against.
        gtfs_filename: The name of the GTFS file being processed (for context in DLQ).

    Returns:
        A tuple containing:
            - pd.DataFrame: DataFrame with only the valid records (as dictionaries).
            - List[Dict[str, Any]]: A list of dictionaries, where each dictionary
              represents a failed record along with its validation errors.
              Each dict will have 'original_record' and 'errors'.
    """
    if df.empty:
        logger.info(f"DataFrame for validating with {pydantic_model.__name__} is empty.")
        return pd.DataFrame(columns=df.columns), []

    valid_records_list = []
    invalid_records_info_list = []  # Stores original record and error details

    logger.info(
        f"Validating {len(df)} records from '{gtfs_filename}' using Pydantic model '{pydantic_model.__name__}'...")

    for index, row in df.iterrows():
        try:
            # Convert row to dict. Handle potential NaN/NaT by converting to None for Pydantic.
            # Pydantic models should handle Optional fields gracefully.
            # Raw data read with dtype=str and keep_default_na=False, na_values=[''] helps.
            # Then replace empty strings with None before passing to Pydantic if model fields are Optional.

            record_dict = {}
            for col, val in row.items():
                # Pydantic expects None for missing optional fields, not empty strings if type is not str.
                # If a field is defined as Optional[int], an empty string "" will fail.
                # This preprocessing depends heavily on how Pydantic models are defined (e.g., if default_factory is used).
                # For now, assume Pydantic models will try to coerce types.
                # Stripping whitespace is handled by GTFSBaseModel's anystr_strip_whitespace.
                record_dict[col] = val if pd.notna(val) and str(val).strip() != "" else None

            # Attempt to parse and validate the record using the Pydantic model
            validated_model_instance = pydantic_model(**record_dict)

            # If successful, add the model's dictionary representation (cleaned data)
            valid_records_list.append(
                validated_model_instance.model_dump(exclude_none=False))  # exclude_none=False to keep explicit None

        except ValidationError as e:
            # Record failed validation
            invalid_record_info = {
                "original_record": row.to_dict(),  # Keep the original row data
                "errors": e.errors(),  # Pydantic provides detailed errors
                "source_filename": gtfs_filename,
                "original_index": index
            }
            invalid_records_info_list.append(invalid_record_info)
            logger.debug(f"Validation failed for record at index {index} from {gtfs_filename}: {e.errors()}")
        except Exception as ex:
            # Catch other unexpected errors during model instantiation
            invalid_record_info = {
                "original_record": row.to_dict(),
                "errors": [{"loc": ["unknown"], "msg": str(ex), "type": "unexpected_error"}],
                "source_filename": gtfs_filename,
                "original_index": index
            }
            invalid_records_info_list.append(invalid_record_info)
            logger.error(f"Unexpected error validating record at index {index} from {gtfs_filename}: {ex}",
                         exc_info=True)

    # Create DataFrames from the lists
    if valid_records_list:
        # Preserve original column order as much as possible, but ensure model fields are primary.
        # Pydantic model_dump() gives a dict; columns from the first valid record can define order.
        valid_df_columns = list(valid_records_list[0].keys()) if valid_records_list else []
        valid_df = pd.DataFrame(valid_records_list, columns=valid_df_columns)
    else:
        # If all records failed, create an empty DataFrame with columns from the Pydantic model
        # to maintain schema consistency for the next step (transform.py)
        # This gets fields from the model, including aliases if used.
        valid_df = pd.DataFrame(columns=[field_name for field_name in pydantic_model.model_fields.keys()])

    logger.info(f"Validation for '{gtfs_filename}' complete. "
                f"Valid records: {len(valid_df)}. Invalid records: {len(invalid_records_info_list)}.")

    return valid_df, invalid_records_info_list


# Example Usage (for testing this module directly)
if __name__ == "__main__":
    # Setup basic logging for direct script execution test
    # In a real pipeline, main_pipeline.py or run_gtfs_update.py would set up logging.
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
    logger.info("--- Testing validate.py ---")

    # --- Test with Stop Model ---
    # Get the Stop Pydantic model from schema_definitions
    stop_pydantic_model = schemas.GTFS_FILE_SCHEMAS["stops.txt"]["model"]

    # Sample raw DataFrame for stops.txt (as if read by pandas with dtype=str)
    raw_stop_data = {
        'stop_id': ['s1', 's2', 's3', 's4', 's5', 's6'],
        'stop_code': ['c1', '', None, 'c4', 'c5', 'c6'],  # Test empty string and None
        'stop_name': [' Stop One ', 'Stop Two (Good LatLon)', '  ', 'Stop Four (Bad Lat)', 'Stop Five (Missing Lon)',
                      'Stop Six (Good)'],  # Test stripping, empty after strip
        'stop_desc': ['Desc 1', None, 'Desc 3', 'Desc 4', 'Desc 5', 'Desc 6'],
        'stop_lat': ['40.7128 ', '40.7321', '40.777', '95.0', '40.123', '34.0522'],  # Test stripping, bad value
        'stop_lon': [' -74.0060', '-74.0001', '-74.111', '-74.0020', '', '-118.2437'],  # Test stripping, empty string
        'zone_id': ['z1', 'z2', 'z1', None, 'z3', 'z4'],
        'location_type': ['0', '1', '', '0', '2', None],
        # Test empty string, None (Pydantic should use default or validate)
        'parent_station': [None, None, 's2', 's1', None, ''],
        'extra_column_not_in_model': ['ex1', 'ex2', 'ex3', 'ex4', 'ex5', 'ex6']
    }
    raw_stops_df = pd.DataFrame(raw_stop_data)
    logger.info(f"\nRaw stops DataFrame for validation:\n{raw_stops_df}")

    valid_stops_df, invalid_stops_info = validate_dataframe_with_pydantic(raw_stops_df, stop_pydantic_model,
                                                                          "stops.txt")

    logger.info(f"\nValidated Stops DataFrame ({len(valid_stops_df)} records):\n{valid_stops_df.head().to_string()}")
    if valid_stops_df.empty and not invalid_stops_info:  # Check if something unexpected happened
        logger.warning(
            "Validation returned empty valid DataFrame and no invalid records - check logic if input was not empty.")

    logger.info(f"\nInvalid Stops Records/Info ({len(invalid_stops_info)} records):")
    for invalid_info in invalid_stops_info:
        logger.info(f"  Original: {invalid_info['original_record']}")
        logger.info(f"  Errors: {invalid_info['errors']}")
        # In a real pipeline, these invalid_stops_info would be passed to load.log_to_dlq()

    # --- Test with Agency Model ---
    agency_pydantic_model = schemas.GTFS_FILE_SCHEMAS["agency.txt"]["model"]
    raw_agency_data = {
        "agency_id": ["AG1", "AG2", None, "AG4"],  # Test None for optional
        "agency_name": ["Agency One", "Agency Two", "Agency Three No ID", "Agency Four Bad URL"],
        "agency_url": ["http://agency1.com", "https://agency2.org", "http://agency3.net", "badurl.com"],
        "agency_timezone": ["America/New_York", "Europe/London", "Australia/Sydney", "Invalid/Timezone"],
        # Pydantic doesn't validate TZ names by default
        "agency_lang": ["en", "fr", None, "toolong"]
    }
    raw_agency_df = pd.DataFrame(raw_agency_data)
    logger.info(f"\nRaw agency DataFrame for validation:\n{raw_agency_df}")

    valid_agency_df, invalid_agency_info = validate_dataframe_with_pydantic(raw_agency_df, agency_pydantic_model,
                                                                            "agency.txt")
    logger.info(f"\nValidated Agency DataFrame ({len(valid_agency_df)} records):\n{valid_agency_df.head().to_string()}")
    logger.info(f"\nInvalid Agency Records/Info ({len(invalid_agency_info)} records):")
    for invalid_info in invalid_agency_info:
        logger.info(f"  Original: {invalid_info['original_record']}")
        logger.info(f"  Errors: {invalid_info['errors']}")

    logger.info("--- validate.py test finished ---")
