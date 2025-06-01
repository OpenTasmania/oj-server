# common/file_utils.py
# -*- coding: utf-8 -*-
"""
File system utility functions, such as backing up files and cleaning directories.
"""

import datetime
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from setup.config_models import AppSettings # For type hinting
# from setup import config as static_config # Keep for SYMBOLS if not from app_settings
from .command_utils import log_map_server, run_elevated_command # log_map_server now takes app_settings

module_logger = logging.getLogger(__name__)


def backup_file(
    file_path: str,
    app_settings: AppSettings, # Added app_settings
    current_logger: Optional[logging.Logger] = None,
) -> bool:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols

    try:
        run_elevated_command(
            ["test", "-f", file_path], app_settings, # Pass app_settings
            check=True, capture_output=True, current_logger=logger_to_use,
        )
    except subprocess.CalledProcessError:
        log_map_server(
            f"{symbols.get('info','')} File {file_path} does not exist or is not a regular file. No backup needed.",
            "info", logger_to_use, app_settings)
        return True
    except Exception as e:
        log_map_server(
            f"{symbols.get('error','')} Error pre-checking file existence for backup of {file_path}: {e}",
            "error", logger_to_use, app_settings)
        return False

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = f"{file_path}.bak.{timestamp}"
    try:
        run_elevated_command(["cp", "-a", file_path, backup_path], app_settings, current_logger=logger_to_use) # Pass app_settings
        log_map_server(
            f"{symbols.get('success','')} Backed up {file_path} to {backup_path}",
            "success", logger_to_use, app_settings)
        return True
    except Exception as e:
        log_map_server(
            f"{symbols.get('error','')} Failed to backup {file_path} to {backup_path}: {e}",
            "error", logger_to_use, app_settings)
        return False


def cleanup_directory(
        directory_path: Path,
        app_settings: AppSettings, # Added app_settings
        ensure_dir_exists_after: bool = False,
        current_logger: Optional[logging.Logger] = None,
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    dir_to_clean = Path(directory_path)
    # Use log_map_server for consistency if symbols are desired here
    log_map_server(f"Attempting to clean directory: {dir_to_clean}", "debug", logger_to_use, app_settings)

    if dir_to_clean.exists():
        if dir_to_clean.is_dir():
            try:
                shutil.rmtree(dir_to_clean)
                log_map_server(f"{symbols.get('success','')} Successfully removed directory and its contents: {dir_to_clean}", "info", logger_to_use, app_settings)
            except Exception as e:
                log_map_server(f"{symbols.get('error','')} Error removing directory {dir_to_clean} using shutil.rmtree: {e}", "error", logger_to_use, app_settings, exc_info=True)
        else:
            log_map_server(f"{symbols.get('warning','')} Path {dir_to_clean} exists but is not a directory.", "warning", logger_to_use, app_settings)
    else:
        log_map_server(f"{symbols.get('info','')} Directory {dir_to_clean} does not exist. No cleanup needed.", "info", logger_to_use, app_settings)

    if ensure_dir_exists_after:
        try:
            dir_to_clean.mkdir(parents=True, exist_ok=True)
            log_map_server(f"Ensured directory exists: {dir_to_clean}", "debug", logger_to_use, app_settings)
        except Exception as e:
            log_map_server(f"{symbols.get('error','')} Error creating directory {dir_to_clean} after cleanup: {e}", "error", logger_to_use, app_settings, exc_info=True)