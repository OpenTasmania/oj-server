#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
General utility functions, potentially for GTFS processing or wider application use.

This module currently provides:
- A flexible logging setup function.
- A function to establish PostgreSQL database connections.
- A utility to clean up contents of a directory.

Note: The name 'validate.py' might be misleading given its current contents.
It appears to serve as a general utilities module.
"""

import logging
import os
import sys
import shutil # For cleanup_directory if full recursive delete is needed
from pathlib import Path
from typing import Dict, Any, Optional, Union

import psycopg2
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import DictCursor

# Default DB parameters. These can be overridden by environment variables
# or by passing a dictionary to `get_db_connection`.
# Ensure these align with the main application's configuration strategy.
DEFAULT_DB_PARAMS: Dict[str, str] = {
    "dbname": os.environ.get("PG_GIS_DB", "gis"),
    "user": os.environ.get("PG_OSM_USER", "osmuser"),
    "password": os.environ.get(
        "PG_OSM_PASSWORD", "yourStrongPasswordHere_utils_default"
    ), # CRITICAL: Change this default or ensure env var is securely set.
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": os.environ.get("PG_PORT", "5432"),
}

module_logger = logging.getLogger(__name__)


def setup_logging(
    log_level: int = logging.INFO,
    log_file: Optional[Union[str, Path]] = None,
    log_to_console: bool = True,
    log_format: str = (
        "%(asctime)s - %(levelname)s - %(name)s - "
        "%(module)s.%(funcName)s:%(lineno)d - %(message)s"
    ),
    date_format: str = "%Y-%m-%d %H:%M:%S",
) -> None:
    """
    Configure root logging for the application.

    This function sets up handlers for console and/or file logging,
    applies a specified format, and sets the logging level. It clears
    existing handlers on the root logger to prevent duplicate messages if
    called multiple times.

    Args:
        log_level: The logging level (e.g., `logging.INFO`, `logging.DEBUG`).
        log_file: Optional path to a file where logs should be written.
                  The directory for the log file will be created if it
                  doesn't exist.
        log_to_console: If True, logs will also be output to standard output.
        log_format: The format string for log messages.
        date_format: The format string for timestamps in log messages.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers on the root logger to avoid duplicate messages.
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    formatter = logging.Formatter(log_format, datefmt=date_format)
    handlers_added = False

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        handlers_added = True

    if log_file:
        try:
            log_file_path = Path(log_file)
            # Ensure log directory exists.
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file_path, mode="a") # Append mode
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            handlers_added = True
        except Exception as e:
            # Fallback to console if file logging setup fails.
            # Using print as logger might not be fully functional here.
            print(
                f"ERROR: Failed to configure file logging to '{log_file}': {e}. "
                "Logging to console if enabled, or with basic config.",
                file=sys.stderr
            )
            # If console logging was also off, ensure there's at least one handler.
            if not log_to_console:
                console_fallback = logging.StreamHandler(sys.stdout)
                console_fallback.setFormatter(formatter)
                root_logger.addHandler(console_fallback)
                handlers_added = True

    if not handlers_added:
        # Ensure at least one handler if both console and file are false
        # (though current logic makes this unlikely unless error during file log setup)
        basic_console_handler = logging.StreamHandler(sys.stdout)
        basic_console_handler.setFormatter(formatter)
        root_logger.addHandler(basic_console_handler)
        module_logger.debug("Default console handler added as no other handlers were configured.")

    module_logger.debug(
        f"Root logger setup complete. Level: {logging.getLevelName(log_level)}"
    )


def get_db_connection(
    db_params: Optional[Dict[str, Any]] = None
) -> Optional[PgConnection]:
    """
    Establish and return a PostgreSQL database connection.

    Uses provided `db_params` dictionary or falls back to `DEFAULT_DB_PARAMS`
    defined in this module. The connection uses `DictCursor` for dictionary-like
    row access.

    Args:
        db_params: Optional dictionary with database connection parameters
                   (e.g., dbname, user, password, host, port).

    Returns:
        A psycopg2 connection object (`psycopg2.extensions.connection`) if
        successful, None otherwise.
    """
    current_params = DEFAULT_DB_PARAMS.copy()
    if db_params:
        current_params.update(db_params)

    # Critical check for placeholder password.
    # This checks against the specific default string in this module.
    placeholder_pw = "yourStrongPasswordHere_utils_default"
    if (current_params.get("password") == placeholder_pw and
            os.environ.get("PG_OSM_PASSWORD") == placeholder_pw):
        module_logger.critical(
            "CRITICAL: Default placeholder password is being used for database "
            "connection in utils.py (validate.py content)."
        )
        module_logger.critical(
            "Please configure a strong password in DB_PARAMS or via "
            "PG_OSM_PASSWORD environment variable."
        )
        # Depending on security policy, you might want to raise an exception here
        # or prevent connection. For now, it logs critically and proceeds.

    try:
        module_logger.debug(
            f"Attempting to connect to database: "
            f"dbname='{current_params.get('dbname')}', "
            f"user='{current_params.get('user')}', "
            f"host='{current_params.get('host')}', "
            f"port='{current_params.get('port')}'"
        )
        conn = psycopg2.connect(**current_params, cursor_factory=DictCursor)
        module_logger.info("Database connection established successfully.")
        return conn
    except psycopg2.OperationalError as e:
        module_logger.error(f"Database connection failed: {e}", exc_info=True)
    except Exception as e:
        module_logger.error(
            f"An unexpected error occurred while connecting to the database: {e}",
            exc_info=True,
        )
    return None


def cleanup_directory(
    dir_path: Union[str, Path], ensure_dir_exists_after: bool = False
) -> None:
    """
    Remove all files and subdirectories within a given directory.

    Optionally recreates the directory after cleaning if `ensure_dir_exists_after`
    is True.

    Args:
        dir_path: Path (string or Path object) to the directory to clean.
        ensure_dir_exists_after: If True, creates the directory if it doesn't
                                 exist after cleaning attempts.
    """
    dir_to_clean = Path(dir_path)
    module_logger.debug(f"Attempting to clean directory: {dir_to_clean}")

    if dir_to_clean.exists():
        if dir_to_clean.is_dir():
            try:
                # shutil.rmtree recursively removes a directory and its contents.
                shutil.rmtree(dir_to_clean)
                module_logger.info(
                    f"Successfully removed directory and its contents: {dir_to_clean}"
                )
            except Exception as e:
                module_logger.error(
                    f"Error removing directory {dir_to_clean} using "
                    f"shutil.rmtree: {e}", exc_info=True
                )
                # Fallback: try to delete items individually if rmtree failed
                # (e.g. permission issues with specific files)
                # This is a simplified fallback, more robust handling might be needed.
                # For now, if rmtree fails, we log and proceed to ensure_dir_exists_after.
        else:
            module_logger.warning(
                f"Path {dir_to_clean} exists but is not a directory. "
                "Cannot clean as a directory."
            )
    else:
        module_logger.info(
            f"Directory {dir_to_clean} does not exist. No cleanup needed there."
        )

    if ensure_dir_exists_after:
        try:
            dir_to_clean.mkdir(parents=True, exist_ok=True)
            module_logger.debug(f"Ensured directory exists: {dir_to_clean}")
        except Exception as e:
            module_logger.error(
                f"Error creating directory {dir_to_clean} after cleanup: {e}",
                exc_info=True
            )


# Example Usage (for testing this module directly)
if __name__ == "__main__":
    # --- Test logging setup ---
    print("--- Testing utils.py (was validate.py) Logging ---")
    # Test default logging (INFO to console)
    setup_logging(log_level=logging.DEBUG) # Set to DEBUG to see all messages
    module_logger.debug("This is a debug message from utils.py direct test.")
    module_logger.info("This is an info message from utils.py direct test.")
    module_logger.warning("This is a warning message.")
    module_logger.error("This is an error message.")
    module_logger.critical("This is a critical message.")

    # Test logging to a file
    TEST_LOG_FILE = Path("/tmp/utils_module_test.log") # Unique name
    setup_logging(
        log_level=logging.INFO, log_file=TEST_LOG_FILE, log_to_console=False
    )
    module_logger.info(
        f"This message should go to the test log file: {TEST_LOG_FILE}"
    )
    if TEST_LOG_FILE.exists():
        print(f"Test log file created at {TEST_LOG_FILE}. Check its contents.")
        # Clean up test log file after check.
        # TEST_LOG_FILE.unlink(missing_ok=True)
    else:
        print(f"ERROR: Test log file {TEST_LOG_FILE} was not created.")

    # Restore console logging for further tests
    setup_logging(log_level=logging.INFO)

    # --- Test DB Connection ---
    # NOTE: This test will attempt to connect to your PostgreSQL database
    # using DEFAULT_DB_PARAMS. Ensure your DB is running and parameters are
    # correctly configured (or env vars like PG_OSM_PASSWORD set) for success.
    print("\n--- Testing utils.py (was validate.py) DB Connection ---")
    # Check if password is still the placeholder defined in this module.
    if (DEFAULT_DB_PARAMS["password"] == "yourStrongPasswordHere_utils_default" and
            os.environ.get("PG_OSM_PASSWORD") == "yourStrongPasswordHere_utils_default"):
        module_logger.warning(
            "Skipping database connection test as password is the default "
            "placeholder for 'validate.py' content."
        )
        module_logger.warning(
            "To test DB connection, set PG_OSM_PASSWORD env var or update "
            "DEFAULT_DB_PARAMS in this script."
        )
    else:
        test_conn = get_db_connection()
        if test_conn:
            module_logger.info("Test DB connection successful.")
            try:
                with test_conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    pg_version_row = cur.fetchone()
                    if pg_version_row:
                        module_logger.info(
                            f"PostgreSQL version: {pg_version_row['version']}"
                        )
            except Exception as e_query:
                module_logger.error(f"Error executing test query: {e_query}")
            finally:
                test_conn.close()
                module_logger.info("Test DB connection closed.")
        else:
            module_logger.error("Test DB connection FAILED.")

    # --- Test Directory Cleanup ---
    print("\n--- Testing utils.py (was validate.py) Directory Cleanup ---")
    TEST_CLEANUP_DIR = Path("/tmp/test_cleanup_dir_validate_content")

    # Test 1: Cleanup a directory that doesn't exist, ensure it's created.
    if TEST_CLEANUP_DIR.exists(): # Cleanup from previous test if any
        shutil.rmtree(TEST_CLEANUP_DIR, ignore_errors=True)
    module_logger.info(f"Testing cleanup of non-existent directory, ensuring creation: {TEST_CLEANUP_DIR}")
    cleanup_directory(TEST_CLEANUP_DIR, ensure_dir_exists_after=True)
    if TEST_CLEANUP_DIR.exists() and TEST_CLEANUP_DIR.is_dir():
        module_logger.info(f"Test 1 successful. Directory {TEST_CLEANUP_DIR} exists.")
    else:
        module_logger.error(f"Test 1 FAILED. Directory {TEST_CLEANUP_DIR} does not exist.")

    # Test 2: Create directory with content, clean it, ensure it's recreated empty.
    TEST_CLEANUP_DIR.mkdir(parents=True, exist_ok=True) # Ensure it exists for this test
    (TEST_CLEANUP_DIR / "file1.txt").touch()
    (TEST_CLEANUP_DIR / "subdir").mkdir(exist_ok=True)
    (TEST_CLEANUP_DIR / "subdir" / "file3.txt").touch()

    module_logger.info(
        f"Directory contents before cleanup for Test 2: "
        f"{[str(p.relative_to(TEST_CLEANUP_DIR)) for p in TEST_CLEANUP_DIR.rglob('*')]}"
    )
    cleanup_directory(TEST_CLEANUP_DIR, ensure_dir_exists_after=True)
    remaining_items = [
        str(p.relative_to(TEST_CLEANUP_DIR))
        for p in TEST_CLEANUP_DIR.rglob("*")
    ]
    if TEST_CLEANUP_DIR.exists() and TEST_CLEANUP_DIR.is_dir() and not remaining_items:
        module_logger.info(
            f"Test 2 successful. Directory {TEST_CLEANUP_DIR} exists and is empty."
        )
    else:
        module_logger.error(
            f"Test 2 FAILED. Directory {TEST_CLEANUP_DIR} state incorrect. "
            f"Remaining items: {remaining_items}"
        )

    # Final cleanup of the test directory.
    if TEST_CLEANUP_DIR.exists():
        shutil.rmtree(TEST_CLEANUP_DIR, ignore_errors=True)

    module_logger.info("--- utils.py (was validate.py) test finished ---")