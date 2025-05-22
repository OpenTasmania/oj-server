#!/usr/bin/env python3
import logging
import os  # For environment variables if used for DB params
import sys
from pathlib import Path
from typing import Dict, Any, Optional

import psycopg2
from psycopg2.extras import DictCursor

# Default DB parameters (can be overridden by environment variables or a config file mechanism)
# These should match the ones defined or prompted for in the main execution context.
DEFAULT_DB_PARAMS = {
    "dbname": os.environ.get("PG_GIS_DB", "gis"),
    "user": os.environ.get("PG_OSM_USER", "osmuser"),
    "password": os.environ.get("PG_OSM_PASSWORD", "yourStrongPasswordHere_utils_default"),
    # CRITICAL: Change this default or ensure env var is set
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": os.environ.get("PG_PORT", "5432")
}


def setup_logging(
        log_level: int = logging.INFO,
        log_file: Optional[Union[str, Path]] = None,
        log_to_console: bool = True,
        log_format: str = '%(asctime)s - %(levelname)s - %(name)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s',
        date_format: str = '%Y-%m-%d %H:%M:%S'
) -> None:
    """
    Configures root logging for the application.

    Args:
        log_level: The logging level (e.g., logging.INFO, logging.DEBUG).
        log_file: Optional path to a file where logs should be written.
        log_to_console: If True, logs will also be output to the console.
        log_format: The format string for log messages.
        date_format: The format string for timestamps in log messages.
    """
    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers on the root logger to avoid duplicate messages if called multiple times
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    formatter = logging.Formatter(log_format, datefmt=date_format)

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        # print(f"Console logging configured at level: {logging.getLevelName(log_level)}") # Debug print

    if log_file:
        try:
            log_file_path = Path(log_file)
            log_file_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure log directory exists
            file_handler = logging.FileHandler(log_file_path, mode='a')  # Append mode
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            # print(f"File logging configured at level: {logging.getLevelName(log_level)} to {log_file_path}") # Debug print
        except Exception as e:
            # Fallback to console if file logging setup fails
            logging.error(f"Failed to configure file logging to '{log_file}': {e}. Logging to console only.",
                          exc_info=True)
            if not log_to_console:  # Ensure there's at least console logging if file fails and console was off
                console_handler_fallback = logging.StreamHandler(sys.stdout)
                console_handler_fallback.setFormatter(formatter)
                root_logger.addHandler(console_handler_fallback)

    # Test message to confirm logger is working (will only show if level is DEBUG for this message)
    # logging.debug("Root logger setup complete.")


def get_db_connection(db_params: Optional[Dict[str, Any]] = None) -> Optional[psycopg2.extensions.connection]:
    """
    Establishes and returns a PostgreSQL database connection.
    Uses provided db_params or falls back to DEFAULT_DB_PARAMS.

    Args:
        db_params: Optional dictionary with database connection parameters
                   (dbname, user, password, host, port).

    Returns:
        A psycopg2 connection object if successful, None otherwise.
    """
    current_params = DEFAULT_DB_PARAMS.copy()
    if db_params:
        current_params.update(db_params)

    # Check for placeholder password
    if current_params.get("password") == "yourStrongPasswordHere_utils_default" and \
            os.environ.get("PG_OSM_PASSWORD") == "yourStrongPasswordHere_utils_default":  # Check env var too
        logging.critical("CRITICAL: Default placeholder password is being used for database connection.")
        logging.critical("Please configure a strong password in DB_PARAMS or via PG_OSM_PASSWORD environment variable.")
        # Depending on policy, you might want to raise an exception here or allow connection for dev.
        # For now, we'll log critically and proceed, but in production this should fail hard.

    try:
        logging.debug(f"Attempting to connect to database: "
                      f"dbname='{current_params.get('dbname')}', "
                      f"user='{current_params.get('user')}', "
                      f"host='{current_params.get('host')}', "
                      f"port='{current_params.get('port')}'")
        conn = psycopg2.connect(**current_params, cursor_factory=DictCursor)
        logging.info("Database connection established successfully.")
        return conn
    except psycopg2.OperationalError as e:
        logging.error(f"Database connection failed: {e}", exc_info=True)
    except Exception as e:
        logging.error(f"An unexpected error occurred while connecting to the database: {e}", exc_info=True)
    return None


def cleanup_directory(dir_path: Union[str, Path], ensure_dir_exists: bool = False) -> None:
    """
    Removes all files and subdirectories within a given directory.
    Optionally creates the directory if it doesn't exist.

    Args:
        dir_path: Path to the directory to clean.
        ensure_dir_exists: If True, creates the directory if it doesn't exist after cleaning attempts.
    """
    dir_path = Path(dir_path)
    logger.debug(f"Attempting to clean directory: {dir_path}")
    if dir_path.exists():
        if dir_path.is_dir():
            for item in dir_path.iterdir():
                try:
                    if item.is_dir():
                        # shutil.rmtree(item) # For recursive delete of subdirectories
                        # For now, only delete files, warn about subdirs as GTFS extract is usually flat
                        logger.warning(
                            f"Subdirectory found in cleanup path: {item}. Not deleting subdirectories in this basic cleanup.")
                    else:
                        item.unlink()
                except Exception as e:
                    logger.error(f"Error deleting item {item} in {dir_path}: {e}")
            logger.info(f"Cleaned contents of directory: {dir_path}")
        else:
            logger.warning(f"Path {dir_path} exists but is not a directory. Cannot clean.")
    else:
        logger.info(f"Directory {dir_path} does not exist. No cleanup needed there.")

    if ensure_dir_exists:
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {dir_path}")
        except Exception as e:
            logger.error(f"Error creating directory {dir_path}: {e}")


# Example Usage (for testing this module directly)
if __name__ == "__main__":
    # --- Test logging setup ---
    print("--- Testing utils.py Logging ---")
    # Test default logging (INFO to console)
    setup_logging(log_level=logging.DEBUG)  # Set to DEBUG to see all test messages
    logging.debug("This is a debug message from utils.py direct test.")
    logging.info("This is an info message from utils.py direct test.")
    logging.warning("This is a warning message.")
    logging.error("This is an error message.")
    logging.critical("This is a critical message.")

    # Test logging to a file
    TEST_LOG_FILE = Path("/tmp/utils_test.log")
    setup_logging(log_level=logging.INFO, log_file=TEST_LOG_FILE, log_to_console=False)
    logging.info(f"This message should go to the test log file: {TEST_LOG_FILE}")
    if TEST_LOG_FILE.exists():
        print(f"Test log file created at {TEST_LOG_FILE}. Check its contents.")
        # TEST_LOG_FILE.unlink() # Clean up test log file
    else:
        print(f"ERROR: Test log file {TEST_LOG_FILE} was not created.")

    # Restore console logging for further tests
    setup_logging(log_level=logging.INFO)

    # --- Test DB Connection ---
    # NOTE: This test will attempt to connect to your PostgreSQL database
    # using DB_PARAMS (which includes a placeholder password by default).
    # Ensure your DB is running and DB_PARAMS is correctly configured (or env vars set)
    # if you want this test to succeed.
    print("\n--- Testing utils.py DB Connection ---")
    # For this test to work without changing the script, you'd need to set PG_OSM_PASSWORD env var
    # or update DEFAULT_DB_PARAMS above if running this file directly.
    # Example: export PG_OSM_PASSWORD='your_actual_password'

    # Check if password is still placeholder
    if DEFAULT_DB_PARAMS["password"] == "yourStrongPasswordHere_utils_default" and \
            os.environ.get("PG_OSM_PASSWORD") == "yourStrongPasswordHere_utils_default":
        logging.warning("Skipping database connection test as password is still the placeholder.")
        logging.warning("To test DB connection, set PG_OSM_PASSWORD env var or update DEFAULT_DB_PARAMS.")
    else:
        test_conn = get_db_connection()
        if test_conn:
            logging.info("Test DB connection successful.")
            try:
                with test_conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    pg_version = cur.fetchone()
                    logging.info(f"PostgreSQL version: {pg_version['version']}")
            except Exception as e:
                logging.error(f"Error executing test query: {e}")
            finally:
                test_conn.close()
                logging.info("Test DB connection closed.")
        else:
            logging.error("Test DB connection FAILED.")

    # --- Test Directory Cleanup ---
    print("\n--- Testing utils.py Directory Cleanup ---")
    TEST_CLEANUP_DIR = Path("/tmp/test_cleanup_dir_utils")
    TEST_CLEANUP_DIR.mkdir(parents=True, exist_ok=True)
    (TEST_CLEANUP_DIR / "file1.txt").touch()
    (TEST_CLEANUP_DIR / "file2.txt").touch()
    (TEST_CLEANUP_DIR / "subdir").mkdir(exist_ok=True)
    (TEST_CLEANUP_DIR / "subdir" / "file3.txt").touch()

    logging.info(
        f"Directory contents before cleanup: {[str(p.relative_to(TEST_CLEANUP_DIR)) for p in TEST_CLEANUP_DIR.rglob('*')]}")
    cleanup_directory(TEST_CLEANUP_DIR,
                      ensure_dir_exists=False)  # Clean contents, don't ensure it exists after (it will be empty)
    remaining_items = [str(p.relative_to(TEST_CLEANUP_DIR)) for p in TEST_CLEANUP_DIR.rglob('*')]
    logging.info(
        f"Directory contents after cleanup (files removed, subdir might remain): {remaining_items if remaining_items else 'Empty'}")
    if not any(item.startswith("file") for item in remaining_items):  # Check if files are gone
        logging.info("File cleanup part successful.")
    else:
        logging.error("File cleanup part FAILED.")

    # Test cleanup and ensure_dir_exists
    if TEST_CLEANUP_DIR.exists():
        import shutil

        shutil.rmtree(TEST_CLEANUP_DIR)  # Fully remove for next test

    cleanup_directory(TEST_CLEANUP_DIR, ensure_dir_exists=True)
    if TEST_CLEANUP_DIR.exists() and TEST_CLEANUP_DIR.is_dir():
        logging.info(f"Cleanup with ensure_dir_exists=True successful. Directory {TEST_CLEANUP_DIR} exists.")
    else:
        logging.error(f"Cleanup with ensure_dir_exists=True FAILED. Directory {TEST_CLEANUP_DIR} does not exist.")

    # Final cleanup of test dir
    if TEST_CLEANUP_DIR.exists():
        import shutil

        shutil.rmtree(TEST_CLEANUP_DIR)

    logging.info("--- utils.py test finished ---")
