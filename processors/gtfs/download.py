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
import zipfile
from pathlib import Path
from typing import Optional, Union

import requests

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
    download_path = Path(download_to_path)
    module_logger.info(f"Attempting to download GTFS feed from: {feed_url}")
    response: Optional[requests.Response] = None

    try:
        download_path.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(feed_url, stream=True, timeout=120)
        response.raise_for_status()

        with open(download_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        module_logger.info(f"GTFS feed successfully downloaded to: {download_path}")
        return True
    except requests.exceptions.HTTPError as http_err:
        status_code = response.status_code if response else "Unknown"
        module_logger.error(f"HTTP error occurred: {http_err} - Status code: {status_code}")
    except requests.exceptions.ConnectionError as conn_err:
        module_logger.error(f"Connection error occurred: {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        module_logger.error(f"Timeout error occurred: {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        module_logger.error(f"An unexpected error occurred during download: {req_err}")
    except IOError as io_err:
        module_logger.error(f"File I/O error when saving download: {io_err}")
    except Exception as e:
        module_logger.error(f"A general error occurred in download_gtfs_feed: {e}", exc_info=True)
    return False


def extract_gtfs_feed(
    zip_file_path: Union[str, Path], extract_to_dir: Union[str, Path]
) -> bool:
    """
    Extract a GTFS zip file to a specified directory.

    It will clear existing files from the target directory before extraction.

    Args:
        zip_file_path: The path to the GTFS zip file.
        extract_to_dir: The directory to extract files into.

    Returns:
        True if extraction was successful, False otherwise.
    """
    zip_path = Path(zip_file_path)
    extract_path = Path(extract_to_dir)

    module_logger.info(f"Attempting to extract GTFS feed '{zip_path}' to '{extract_path}'")

    if not zip_path.is_file():
        module_logger.error(f"Zip file not found or is not a file: {zip_path}")
        return False

    try:
        if extract_path.exists():
            module_logger.info(f"Clearing existing files from extraction directory: {extract_path}")
            for item in extract_path.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    module_logger.warning(f"Subdirectory found in extract path: {item}. Not removed by this basic cleanup.")
        else:
            extract_path.mkdir(parents=True, exist_ok=True)
            module_logger.info(f"Created extraction directory: {extract_path}")

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            common_gtfs_files = {"stops.txt", "routes.txt", "trips.txt"}
            archive_files = {name.lower() for name in zip_ref.namelist()}
            if not common_gtfs_files.intersection(archive_files):
                module_logger.warning(
                    f"Archive '{zip_path}' may not contain common GTFS files. Proceeding."
                )
            zip_ref.extractall(extract_path)

        extracted_files = [item.name for item in extract_path.iterdir() if item.is_file()]
        module_logger.info(f"GTFS feed successfully extracted to: {extract_path}. Files found: {len(extracted_files)}.")
        module_logger.debug(f"Extracted files list: {extracted_files}")
        return True
    except zipfile.BadZipFile:
        module_logger.error(f"Error: '{zip_path}' is not a valid zip file or is corrupted.")
    except IOError as io_err:
        module_logger.error(f"File I/O error during extraction: {io_err}")
    except Exception as e:
        module_logger.error(f"A general error occurred in extract_gtfs_feed: {e}", exc_info=True)
    return False


def cleanup_temp_file(file_path: Union[str, Path]) -> None:
    """
    Remove a temporary file if it exists.

    Args:
        file_path: Path to the file to remove.
    """
    path_to_remove = Path(file_path)
    try:
        if path_to_remove.is_file():
            path_to_remove.unlink()
            module_logger.info(f"Cleaned up temporary file: {path_to_remove}")
        elif path_to_remove.exists():
            module_logger.warning(f"Path '{path_to_remove}' exists but is not a file. Not removed.")
    except Exception as e:
        module_logger.error(f"Error cleaning up file '{path_to_remove}': {e}", exc_info=True)