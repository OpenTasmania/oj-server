#!/usr/bin/env python3
import logging
import os
import zipfile
from pathlib import Path
from typing import Union

import requests

# Configure logging for this module
logger = logging.getLogger(__name__)  # Use module-specific logger


def download_gtfs_feed(
    feed_url: str, download_to_path: Union[str, Path]
) -> bool:
    """
    Downloads a GTFS feed from a given URL to a specified path.

    Args:
        feed_url (str): The URL of the GTFS zip file.
        download_to_path (Union[str, Path]): The file path to save the downloaded zip file.

    Returns:
        bool: True if download was successful, False otherwise.
    """
    download_to_path = Path(download_to_path)
    logger.info(f"Attempting to download GTFS feed from: {feed_url}")
    response = None
    try:
        # Ensure the directory for the download path exists
        download_to_path.parent.mkdir(parents=True, exist_ok=True)

        response = requests.get(
            feed_url, stream=True, timeout=120
        )  # stream=True for large files, 120s timeout
        response.raise_for_status()  # Raise an HTTPError for bad responses (4XX or 5XX)

        with open(download_to_path, "wb") as f:
            for chunk in response.iter_content(
                chunk_size=8192
            ):  # Download in chunks
                f.write(chunk)

        logger.info(
            f"GTFS feed successfully downloaded to: {download_to_path}"
        )
        return True
    except requests.exceptions.HTTPError as http_err:
        logger.error(
            f"HTTP error occurred during download: {http_err} - Status code: {response.status_code}"
        )
    except requests.exceptions.ConnectionError as conn_err:
        logger.error(f"Connection error occurred during download: {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        logger.error(f"Timeout error occurred during download: {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        logger.error(
            f"An unexpected error occurred during download: {req_err}"
        )
    except IOError as io_err:
        logger.error(f"File I/O error when saving download: {io_err}")
    except Exception as e:
        logger.error(
            f"A general error occurred in download_gtfs_feed: {e}",
            exc_info=True,
        )

    return False


def extract_gtfs_feed(
    zip_file_path: Union[str, Path], extract_to_dir: Union[str, Path]
) -> bool:
    """
    Extracts a GTFS zip file to a specified directory.
    It will clear the target directory before extraction if it exists.

    Args:
        zip_file_path (Union[str, Path]): The path to the GTFS zip file.
        extract_to_dir (Union[str, Path]): The directory to extract files into.

    Returns:
        bool: True if extraction was successful, False otherwise.
    """
    zip_file_path = Path(zip_file_path)
    extract_to_dir = Path(extract_to_dir)

    logger.info(
        f"Attempting to extract GTFS feed '{zip_file_path}' to '{extract_to_dir}'"
    )

    if not zip_file_path.exists() or not zip_file_path.is_file():
        logger.error(f"Zip file not found: {zip_file_path}")
        return False

    try:
        if extract_to_dir.exists():
            logger.info(
                f"Clearing existing contents from extraction directory: {extract_to_dir}"
            )
            for item in extract_to_dir.iterdir():
                if item.is_dir():
                    # shutil.rmtree(item) # For recursive delete if needed, but GTFS usually flat
                    logger.warning(
                        f"Subdirectory found in extract path: {item}. Manual cleanup might be needed if not expected."
                    )
                else:
                    item.unlink()  # Delete file
        else:
            extract_to_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created extraction directory: {extract_to_dir}")

        with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
            # Check for common GTFS files to validate it's likely a GTFS archive
            required_files_present = any(
                name.lower() in ["stops.txt", "routes.txt", "trips.txt"]
                for name in zip_ref.namelist()
            )
            if not required_files_present:
                logger.warning(
                    f"The archive '{zip_file_path}' does not seem to contain common GTFS files. Proceeding with extraction anyway."
                )

            zip_ref.extractall(extract_to_dir)

        extracted_files = [
            item.name for item in extract_to_dir.iterdir() if item.is_file()
        ]
        logger.info(
            f"GTFS feed successfully extracted to: {extract_to_dir}. Files: {extracted_files}"
        )
        return True
    except zipfile.BadZipFile:
        logger.error(
            f"Error: '{zip_file_path}' is not a valid zip file or is corrupted."
        )
    except IOError as io_err:
        logger.error(f"File I/O error during extraction: {io_err}")
    except Exception as e:
        logger.error(
            f"A general error occurred in extract_gtfs_feed: {e}",
            exc_info=True,
        )

    return False


def cleanup_temp_file(file_path: Union[str, Path]) -> None:
    """
    Removes a temporary file if it exists.

    Args:
        file_path (Union[str, Path]): Path to the file to remove.
    """
    file_path = Path(file_path)
    try:
        if file_path.exists() and file_path.is_file():
            file_path.unlink()
            logger.info(f"Cleaned up temporary file: {file_path}")
    except Exception as e:
        logger.error(f"Error cleaning up file '{file_path}': {e}")


# Example usage (for testing this module directly)
if __name__ == "__main__":
    # Configure basic logging for direct script execution test
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # --- TEST PARAMETERS (REPLACE WITH ACTUAL TEST VALUES) ---
    # Use a small, publicly available GTFS feed for testing if possible
    # Example: MBTA (Massachusetts Bay Transportation Authority) - check for their current feed URL
    # Or a test feed you have locally.
    # For this example, let's use a placeholder that will likely fail but demonstrates structure.
    # You would get the actual URL from the environment or a config file in the main pipeline.
    TEST_GTFS_URL = os.environ.get(
        "TEST_GTFS_URL", "https://cdn.mbta.com/archive/archived_feeds.txt"
    )  # This is a list of feeds, not a feed itself!
    # Replace with a direct link to a GTFS .zip for a real test
    TEST_DOWNLOAD_DIR = Path("/tmp/gtfs_test_download")
    TEST_ZIP_FILE = TEST_DOWNLOAD_DIR / "test_feed.zip"
    TEST_EXTRACT_DIR = TEST_DOWNLOAD_DIR / "extracted_feed"

    # Ensure test download directory exists
    TEST_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("--- Testing download.py ---")
    logger.info(
        f"Using Test GTFS URL: {TEST_GTFS_URL}"
    )  # This URL will likely fail as it's not a direct zip
    logger.info(f"Test Download Path: {TEST_ZIP_FILE}")
    logger.info(f"Test Extract Path: {TEST_EXTRACT_DIR}")

    # Create a dummy zip file for extraction test if download fails or URL is bad
    dummy_zip_created = False
    if not Path(
        "dummy_stops.txt"
    ).exists():  # Create dummy files only if they don't exist
        with open("dummy_stops.txt", "w") as f:
            f.write("stop_id,stop_name,stop_lat,stop_lon\n")
            f.write("1,Main St,40.7128,-74.0060\n")
        with open("dummy_routes.txt", "w") as f:
            f.write("route_id,route_short_name,route_long_name,route_type\n")
            f.write("R1,10,Main Street Express,3\n")

        with zipfile.ZipFile(TEST_ZIP_FILE, "w") as zf:
            zf.write("dummy_stops.txt")
            zf.write("dummy_routes.txt")
        dummy_zip_created = True
        logger.info(
            f"Created dummy test zip: {TEST_ZIP_FILE} because live URL might fail for example."
        )
        # Use this dummy zip for testing extraction
        source_zip_for_extraction = TEST_ZIP_FILE
    else:  # If dummy files exist, assume dummy zip also exists or was created previously
        if Path(TEST_ZIP_FILE).exists():
            source_zip_for_extraction = TEST_ZIP_FILE
            logger.info(f"Using existing dummy test zip: {TEST_ZIP_FILE}")
        else:  # Fallback if dummy zip is missing too, extraction test will likely fail
            source_zip_for_extraction = Path("non_existent_for_fail_test.zip")

    # Test download (this will likely fail with the example URL)
    # if download_gtfs_feed(TEST_GTFS_URL, TEST_ZIP_FILE):
    #     source_zip_for_extraction = TEST_ZIP_FILE # Use downloaded if successful
    #     if extract_gtfs_feed(source_zip_for_extraction, TEST_EXTRACT_DIR):
    #         logger.info("Extraction test successful.")
    #     else:
    #         logger.error("Extraction test failed.")
    # else:
    #     logger.error(f"Download test failed. Using dummy zip for extraction test if available.")
    #     if dummy_zip_created or Path(TEST_ZIP_FILE).exists():
    #          if extract_gtfs_feed(source_zip_for_extraction, TEST_EXTRACT_DIR):
    #             logger.info("Extraction test with dummy zip successful.")
    #          else:
    #             logger.error("Extraction test with dummy zip failed.")
    #     else:
    #         logger.error("No zip file to test extraction.")

    # More focused test for extraction using the dummy zip if it was created
    if dummy_zip_created or Path(TEST_ZIP_FILE).exists():
        logger.info(
            f"--- Testing extraction with: {source_zip_for_extraction} ---"
        )
        if extract_gtfs_feed(source_zip_for_extraction, TEST_EXTRACT_DIR):
            logger.info(
                f"Extraction test successful. Check contents in {TEST_EXTRACT_DIR}"
            )
        else:
            logger.error("Extraction test failed.")
    else:
        logger.warning(
            f"Could not find or create a dummy zip at {TEST_ZIP_FILE} for extraction test."
        )

    # Test cleanup
    # cleanup_temp_file(TEST_ZIP_FILE) # Only if download was real
    # If dummy was created for test, you might want to clean it up too
    if dummy_zip_created:
        try:
            Path("dummy_stops.txt").unlink()
            Path("dummy_routes.txt").unlink()
            # TEST_ZIP_FILE might have already been cleaned by cleanup_temp_file if called
            if TEST_ZIP_FILE.exists():
                TEST_ZIP_FILE.unlink()
            logger.info("Cleaned up dummy source files.")
        except OSError as e:
            logger.warning(f"Could not clean up all dummy source files: {e}")

    logger.info("--- download.py test finished ---")
