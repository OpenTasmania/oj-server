# common/file_utils.py
# -*- coding: utf-8 -*-
"""
File system utility functions, such as backing up files and cleaning directories.
"""

import datetime
import logging
import os
import shutil # For shutil.rmtree
import subprocess
from pathlib import Path
from typing import Optional

# Assuming config.py is accessible from the project root or PYTHONPATH is set up
# If config.py moves to root, this would be: from config import SYMBOLS
from setup import config
# Assuming command_utils is now in the common package
from .command_utils import log_map_server, run_elevated_command

module_logger = logging.getLogger(__name__)


def backup_file(
    file_path: str, current_logger: Optional[logging.Logger] = None
) -> bool:
    """
    Create a timestamped backup of a file using elevated privileges.

    Args:
        file_path: The absolute path to the file to back up.
        current_logger: Optional logger instance to use.

    Returns:
        True if the backup was successful or if the file does not exist
        (nothing to backup), False if a critical error occurs during backup.
    """
    logger_to_use = current_logger if current_logger else module_logger

    try:
        # Check file existence with elevated privileges first.
        # run_elevated_command will raise CalledProcessError if 'test -f' fails
        # which means file doesn't exist or isn't a regular file.
        run_elevated_command(
            ["test", "-f", file_path],
            check=True, # Raise error if file doesn't exist or isn't regular file
            capture_output=True,
            current_logger=logger_to_use,
        )
    except subprocess.CalledProcessError:
        # test -f returns 1 if file does not exist or is not a regular file.
        log_map_server(
            f"{config.SYMBOLS['info']} File {file_path} does not exist or "
            "is not a regular file. No backup needed.", # Changed from warning to info
            "info",
            logger_to_use,
        )
        return True # Indicate success as there's nothing to backup or it's not a file we manage this way
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Error pre-checking file existence "
            f"for backup of {file_path}: {e}",
            "error",
            logger_to_use,
        )
        return False # Indicate failure in pre-check

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = f"{file_path}.bak.{timestamp}"
    try:
        run_elevated_command(
            ["cp", "-a", file_path, backup_path], current_logger=logger_to_use
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Backed up {file_path} to "
            f"{backup_path}",
            "success",
            logger_to_use,
        )
        return True
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to backup {file_path} to "
            f"{backup_path}: {e}",
            "error",
            logger_to_use,
        )
        return False


def cleanup_directory(
        directory_path: Path, ensure_dir_exists_after: bool = False,
        current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Remove all files and subdirectories within a given directory.
    Optionally recreates the directory after cleaning.

    Args:
        directory_path: Path object representing the directory to clean up.
        ensure_dir_exists_after: If True, creates the directory if it doesn't
                                 exist after cleaning attempts.
        current_logger: Optional logger instance.
    """
    logger_to_use = current_logger if current_logger else module_logger
    dir_to_clean = Path(directory_path)
    logger_to_use.debug(f"Attempting to clean directory: {dir_to_clean}")

    if dir_to_clean.exists():
        if dir_to_clean.is_dir():
            try:
                # shutil.rmtree does not require elevated privileges if the current user
                # has permissions to delete the directory and its contents.
                # If it might contain files owned by root, this could fail.
                # For consistency with other operations that might create root-owned files
                # in temp dirs, using an elevated remove might be safer in some contexts,
                # but generally, user-initiated cleanup should work with standard perms
                # if the user owns the directory.
                # For now, using shutil.rmtree directly. If issues arise, consider
                # an elevated 'rm -rf'.
                shutil.rmtree(dir_to_clean)
                logger_to_use.info(f"Successfully removed directory and its contents: {dir_to_clean}")
            except Exception as e:
                logger_to_use.error(f"Error removing directory {dir_to_clean} using shutil.rmtree: {e}", exc_info=True)
        else:
            logger_to_use.warning(f"Path {dir_to_clean} exists but is not a directory. Cannot clean as a directory.")
    else:
        logger_to_use.info(f"Directory {dir_to_clean} does not exist. No cleanup needed there.")

    if ensure_dir_exists_after:
        try:
            dir_to_clean.mkdir(parents=True, exist_ok=True)
            logger_to_use.debug(f"Ensured directory exists: {dir_to_clean}")
        except Exception as e:
            logger_to_use.error(f"Error creating directory {dir_to_clean} after cleanup: {e}", exc_info=True)
