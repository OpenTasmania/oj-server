# common/file_utils.py
# -*- coding: utf-8 -*-
"""
File system utility functions, such as backing up files and cleaning directories.
"""

import datetime
import logging
import shutil
import subprocess # Keep for CalledProcessError if run_elevated_command raises it directly
from pathlib import Path
from typing import Optional

from setup.config_models import SYMBOLS_DEFAULT, AppSettings # Import SYMBOLS_DEFAULT
from .command_utils import log_map_server, run_elevated_command

module_logger = logging.getLogger(__name__)


def backup_file(
        file_path: str,
        app_settings: Optional[AppSettings], # Changed to Optional
        current_logger: Optional[logging.Logger] = None,
) -> bool:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols if app_settings and app_settings.symbols else SYMBOLS_DEFAULT # Handle None

    try:
        # run_elevated_command handles Optional[AppSettings]
        run_elevated_command(
            ["test", "-f", file_path],
            app_settings,
            check=True,
            capture_output=True,
            current_logger=logger_to_use,
        )
    except (
            subprocess.CalledProcessError
    ):
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} File {file_path} does not exist or is not a regular file. No backup needed.",
            "info",
            logger_to_use,
            app_settings,
        )
        return True
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Error pre-checking file existence for backup of {file_path}: {e}",
            "error",
            logger_to_use,
            app_settings,
        )
        return False

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = f"{file_path}.bak.{timestamp}"
    try:
        # run_elevated_command handles Optional[AppSettings]
        run_elevated_command(
            ["cp", "-a", file_path, backup_path],
            app_settings,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Backed up {file_path} to {backup_path}",
            "success",
            logger_to_use,
            app_settings,
        )
        return True
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to backup {file_path} to {backup_path}: {e}",
            "error",
            logger_to_use,
            app_settings,
        )
        return False


def cleanup_directory(
        directory_path: Path,
        app_settings: Optional[AppSettings], # Changed to Optional
        ensure_dir_exists_after: bool = False,
        current_logger: Optional[logging.Logger] = None,
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols if app_settings and app_settings.symbols else SYMBOLS_DEFAULT # Handle None

    log_map_server(
        f"Attempting to clean directory: {directory_path}", # Keep symbols out of direct string for this call
        "debug",
        logger_to_use,
        app_settings, # Pass app_settings
    )

    if directory_path.exists():
        if directory_path.is_dir():
            try:
                shutil.rmtree(directory_path)
                log_map_server(
                    f"{symbols.get('success', '✅')} Successfully removed directory and its contents: {directory_path}",
                    "info",
                    logger_to_use,
                    app_settings, # Pass app_settings
                )
            except Exception as e:
                log_map_server(
                    f"{symbols.get('error', '❌')} Error removing directory {directory_path} using shutil.rmtree: {e}",
                    "error",
                    logger_to_use,
                    app_settings, # Pass app_settings
                    exc_info=True,
                )
        else:
            log_map_server(
                f"{symbols.get('warning', '!')} Path {directory_path} exists but is not a directory.",
                "warning",
                logger_to_use,
                app_settings, # Pass app_settings
            )
    else:
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Directory {directory_path} does not exist. No cleanup needed.",
            "info",
            logger_to_use,
            app_settings, # Pass app_settings
        )

    if ensure_dir_exists_after:
        try:
            directory_path.mkdir(parents=True, exist_ok=True)
            log_map_server(
                f"Ensured directory exists: {directory_path}",
                "debug",
                logger_to_use,
                app_settings, # Pass app_settings
            )
        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '❌')} Error creating directory {directory_path} after cleanup: {e}",
                "error",
                logger_to_use,
                app_settings, # Pass app_settings
                exc_info=True,
            )