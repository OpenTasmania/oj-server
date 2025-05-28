#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Handles downloading and extracting GTFS (General Transit Feed Specification)
zip files.

This module provides functions to download a GTFS feed from a URL, extract
its contents, and clean up temporary files. It includes basic error handling
for network issues, file I/O, and zip file processing.
"""

import logging
import os
import zipfile
from pathlib import Path
from typing import Optional, Union

import requests

# Configure logging for this module.
# It's recommended that the main application configures the root logger.
# This module-specific logger will inherit that configuration.
module_logger = logging.getLogger(__name__)


def download_gtfs_feed(
    feed_url: str, download_to_path: Union[str, Path]
) -> bool:
    """
    Download a GTFS feed from a given URL to a specified path.

    Args:
        feed_url: The URL of the GTFS zip file.
        download_to_path: The file path (string or Path object) where the
                          downloaded zip file will be saved.

    Returns:
        True if the download was successful, False otherwise.
    """
    download_path = Path(download_to_path)  # Ensure it's a Path object
    module_logger.info(f"Attempting to download GTFS feed from: {feed_url}")
    response: Optional[requests.Response] = None  # Initialize for status code access in except

    try:
        # Ensure the directory for the download path exists.
        download_path.parent.mkdir(parents=True, exist_ok=True)

        response = requests.get(
            feed_url,
            stream=True,  # Recommended for large files to avoid memory issues.
            timeout=120   # Timeout in seconds (e.g., 2 minutes).
        )
        # Raise an HTTPError for bad responses (4XX or 5XX client/server errors).
        response.raise_for_status()

        with open(download_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):  # Download in chunks
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)

        module_logger.info(
            f"GTFS feed successfully downloaded to: {download_path}"
        )
        return True
    except requests.exceptions.HTTPError as http_err:
        status_code = response.status_code if response else "Unknown"
        module_logger.error(
            f"HTTP error occurred during download: {http_err} - "
            f"Status code: {status_code}"
        )
    except requests.exceptions.ConnectionError as conn_err:
        module_logger.error(
            f"Connection error occurred during download: {conn_err}"
        )
    except requests.exceptions.Timeout as timeout_err:
        module_logger.error(
            f"Timeout error occurred during download: {timeout_err}"
        )
    except requests.exceptions.RequestException as req_err:
        # For other requests-related errors.
        module_logger.error(
            f"An unexpected error occurred during download: {req_err}"
        )
    except IOError as io_err:
        module_logger.error(f"File I/O error when saving download: {io_err}")
    except Exception as e:
        # Catch-all for any other unexpected errors.
        module_logger.error(
            f"A general error occurred in download_gtfs_feed: {e}",
            exc_info=True,  # Include traceback for general exceptions
        )
    return False


def extract_gtfs_feed(
    zip_file_path: Union[str, Path], extract_to_dir: Union[str, Path]
) -> bool:
    """
    Extract a GTFS zip file to a specified directory.

    It will clear the target directory of existing files (but not subdirectories
    not directly part of the zip) before extraction if it exists.

    Args:
        zip_file_path: The path to the GTFS zip file (string or Path object).
        extract_to_dir: The directory (string or Path object) to extract
                        files into.

    Returns:
        True if extraction was successful, False otherwise.
    """
    zip_path = Path(zip_file_path)
    extract_path = Path(extract_to_dir)

    module_logger.info(
        f"Attempting to extract GTFS feed '{zip_path}' to '{extract_path}'"
    )

    if not zip_path.is_file():  # More specific check than exists()
        module_logger.error(f"Zip file not found or is not a file: {zip_path}")
        return False

    try:
        if extract_path.exists():
            module_logger.info(
                f"Clearing existing files from extraction directory: {extract_path}"
            )
            # Iterate and remove files; be cautious with subdirectories.
            for item in extract_path.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    # Decide on policy for subdirs: remove or warn.
                    # For GTFS, usually flat, so warning might be enough.
                    # If recursive delete is needed: shutil.rmtree(item)
                    module_logger.warning(
                        f"Subdirectory found in extract path: {item}. "
                        "This basic cleanup only removes files, not subdirectories "
                        "unless they are part of the new zip extraction."
                    )
        else:
            extract_path.mkdir(parents=True, exist_ok=True)
            module_logger.info(f"Created extraction directory: {extract_path}")

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            # Optional: Check for common GTFS files to validate archive content.
            # This is a heuristic and not foolproof.
            common_gtfs_files = {"stops.txt", "routes.txt", "trips.txt"}
            archive_files = {name.lower() for name in zip_ref.namelist()}
            if not common_gtfs_files.intersection(archive_files):
                module_logger.warning(
                    f"The archive '{zip_path}' does not appear to contain "
                    "common GTFS files (stops.txt, routes.txt, trips.txt). "
                    "Proceeding with extraction anyway."
                )

            zip_ref.extractall(extract_path)

        extracted_files = [
            item.name for item in extract_path.iterdir() if item.is_file()
        ]
        module_logger.info(
            f"GTFS feed successfully extracted to: {extract_path}. "
            f"Files found: {len(extracted_files)}."
        )
        module_logger.debug(f"Extracted files list: {extracted_files}")
        return True

    except zipfile.BadZipFile:
        module_logger.error(
            f"Error: '{zip_path}' is not a valid zip file or is corrupted."
        )
    except IOError as io_err:
        module_logger.error(f"File I/O error during extraction: {io_err}")
    except Exception as e:
        module_logger.error(
            f"A general error occurred in extract_gtfs_feed: {e}",
            exc_info=True,  # Include traceback for general exceptions
        )
    return False


def cleanup_temp_file(file_path: Union[str, Path]) -> None:
    """
    Remove a temporary file if it exists.

    Args:
        file_path: Path (string or Path object) to the file to remove.
    """
    path_to_remove = Path(file_path)
    try:
        if path_to_remove.is_file():  # Check if it's a file before unlinking
            path_to_remove.unlink()
            module_logger.info(f"Cleaned up temporary file: {path_to_remove}")
        elif path_to_remove.exists():  # It exists but is not a file (e.g. directory)
            module_logger.warning(
                f"Path '{path_to_remove}' exists but is not a file. "
                "Not removed by this function."
            )
    except Exception as e:
        module_logger.error(
            f"Error cleaning up file '{path_to_remove}': {e}",
            exc_info=True
        )


# Example usage (for testing this module directly)
if __name__ == "__main__":
    # Configure basic logging for direct script execution test.
    # This setup is minimal and for testing purposes only.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()]  # Log to console
    )

    # --- TEST PARAMETERS (REPLACE WITH ACTUAL TEST VALUES IF NEEDED) ---
    # Example: A known small, publicly available GTFS feed for testing.
    # Using a placeholder URL that might list feeds, not a direct zip.
    # For a real test, replace with a direct link to a GTFS .zip file.
    TEST_GTFS_URL = os.environ.get(
        "TEST_GTFS_URL",
        "https://gtfscommunity.org/resources/transitfeeds-archives-direct-links"
        # This URL lists feeds, not a direct feed itself!
        # A better test URL would be a direct link to a small GTFS zip.
        # e.g. (check for validity and size):
        # TEST_GTFS_URL = "https://gitlab.com/LACMTA/gtfs_bus/-/raw/master/gtfs_bus.zip"
    )
    TEST_DOWNLOAD_DIR = Path("/tmp/gtfs_test_download_module")
    TEST_ZIP_FILE = TEST_DOWNLOAD_DIR / "test_feed.zip"
    TEST_EXTRACT_DIR = TEST_DOWNLOAD_DIR / "extracted_feed"

    # Ensure test download directory exists for the dummy zip creation.
    TEST_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    module_logger.info(f"--- Testing {__file__} ---")
    module_logger.info(f"Using Test GTFS URL: {TEST_GTFS_URL}")
    module_logger.info(f"Test Download Path: {TEST_ZIP_FILE}")
    module_logger.info(f"Test Extract Path: {TEST_EXTRACT_DIR}")

    # Attempt live download (this might fail with the example URL).
    download_success = download_gtfs_feed(TEST_GTFS_URL, TEST_ZIP_FILE)
    source_zip_for_extraction = TEST_ZIP_FILE if download_success else None

    if not download_success:
        module_logger.warning(
            f"Live download from {TEST_GTFS_URL} failed or was skipped. "
            "Attempting to create and use a dummy zip file for extraction test."
        )
        # Create a dummy zip file for extraction test.
        dummy_zip_created = False
        dummy_stops_path = TEST_DOWNLOAD_DIR / "dummy_stops.txt"
        dummy_routes_path = TEST_DOWNLOAD_DIR / "dummy_routes.txt"

        try:
            with open(dummy_stops_path, "w", encoding="utf-8") as f_stops:
                f_stops.write("stop_id,stop_name,stop_lat,stop_lon\n")
                f_stops.write("1,Main St,40.7128,-74.0060\n")
            with open(dummy_routes_path, "w", encoding="utf-8") as f_routes:
                f_routes.write("route_id,route_short_name,route_long_name,route_type\n")
                f_routes.write("R1,10,Main Street Express,3\n")

            with zipfile.ZipFile(TEST_ZIP_FILE, "w") as zf:
                zf.write(dummy_stops_path, arcname="stops.txt")  # Use standard names in zip
                zf.write(dummy_routes_path, arcname="routes.txt")
            dummy_zip_created = True
            source_zip_for_extraction = TEST_ZIP_FILE
            module_logger.info(f"Created dummy test zip: {TEST_ZIP_FILE}")
        except Exception as e_dummy:
            module_logger.error(f"Could not create dummy zip file: {e_dummy}")
            source_zip_for_extraction = None  # Ensure it's None if dummy creation fails
        finally:
            # Clean up individual dummy text files after zipping (or attempting to).
            if dummy_stops_path.exists():
                dummy_stops_path.unlink()
            if dummy_routes_path.exists():
                dummy_routes_path.unlink()

    # Test extraction if a source zip is available (either downloaded or dummy).
    if source_zip_for_extraction and source_zip_for_extraction.exists():
        module_logger.info(
            f"--- Testing extraction with: {source_zip_for_extraction} ---"
        )
        if extract_gtfs_feed(source_zip_for_extraction, TEST_EXTRACT_DIR):
            module_logger.info(
                f"Extraction test successful. Check contents in {TEST_EXTRACT_DIR}"
            )
            # Optionally, clean up the extract directory after test
            # shutil.rmtree(TEST_EXTRACT_DIR, ignore_errors=True)
        else:
            module_logger.error("Extraction test failed.")
    else:
        module_logger.error(
            "No zip file (live or dummy) available to test extraction."
        )

    # Test cleanup of the downloaded/dummy zip file.
    if TEST_ZIP_FILE.exists():
        cleanup_temp_file(TEST_ZIP_FILE)
    else:
        module_logger.info(f"Test zip file {TEST_ZIP_FILE} was not present for cleanup test.")

    # Clean up the main test directory if it's empty or desired
    # For safety, this is often done manually or with more checks.
    # if TEST_DOWNLOAD_DIR.exists():
    #     try:
    #         if not any(TEST_DOWNLOAD_DIR.iterdir()): # Check if empty
    #             TEST_DOWNLOAD_DIR.rmdir()
    #             module_logger.info(f"Cleaned up empty test directory: {TEST_DOWNLOAD_DIR}")
    #         else:
    #             module_logger.info(f"Test directory {TEST_DOWNLOAD_DIR} not empty, not removed.")
    #     except OSError as e_rmdir:
    #         module_logger.warning(f"Could not remove test directory {TEST_DOWNLOAD_DIR}: {e_rmdir}")

    module_logger.info(f"--- {__file__} test finished ---")