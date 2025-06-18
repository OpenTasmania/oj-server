# common/file_utils.py
# -*- coding: utf-8 -*-
"""
File system utility functions, such as backing up files and cleaning directories.
"""

import datetime
import logging
import shutil
import subprocess
from os import getgid, getuid
from pathlib import Path
from typing import Optional

from installer.config_models import (
    SYMBOLS_DEFAULT,
    AppSettings,
)

from .command_utils import log_map_server, run_elevated_command

module_logger = logging.getLogger(__name__)


def backup_file(
    file_path: str,
    app_settings: Optional[AppSettings],
    current_logger: Optional[logging.Logger] = None,
) -> bool:
    """
    Backup a specified file to a timestamped backup file.

    This function attempts to create a backup of a given file by copying it to a
    new location with a timestamp suffix. It ensures that the source file exists
    and is a regular file before proceeding with the backup. If the operation
    fails at any point, appropriate logging is handled based on the provided
    logger or default logger. Symbols for log messages can be customized through
    the application settings.

    Parameters:
        file_path (str): The path of the file to be backed up.
        app_settings (Optional[AppSettings]): Application-specific settings, which
            may include customized symbols for log messages.
        current_logger (Optional[logging.Logger]): Logger instance to use for
            logging messages. If not provided, a module-level logger will be used.

    Returns:
        bool: True if the backup operation was successful or if no backup was
            needed (e.g., file does not exist). False if an error occurred
            during the backup process.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = (
        app_settings.symbols
        if app_settings and app_settings.symbols
        else SYMBOLS_DEFAULT
    )  # Handle None

    try:
        run_elevated_command(
            ["test", "-f", file_path],
            app_settings,
            check=True,
            capture_output=True,
            current_logger=logger_to_use,
        )
    except subprocess.CalledProcessError:
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
    app_settings: Optional[AppSettings],
    ensure_dir_exists_after: bool = False,
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Cleans up the specified directory by removing its contents and optionally ensures the directory's existence
    afterwards. Logs the process and handles potential errors.

    Parameters:
        directory_path (Path): The path to the directory to be cleaned up. It can represent a directory
            or a non-directory entity.
        app_settings (Optional[AppSettings]): Application settings that may include logging configuration and
            symbol customization. Can be None.
        ensure_dir_exists_after (bool): Specifies whether to recreate the directory after cleanup. Defaults to False.
        current_logger (Optional[logging.Logger]): The logger instance to use for logging messages. If not provided,
            a module-level logger is used.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = (
        app_settings.symbols
        if app_settings and app_settings.symbols
        else SYMBOLS_DEFAULT
    )  # Handle None

    log_map_server(
        f"Attempting to clean directory: {directory_path}",
        "debug",
        logger_to_use,
        app_settings,
    )
    if directory_path.exists():
        if directory_path.is_dir():
            try:
                shutil.rmtree(directory_path)
                log_map_server(
                    f"{symbols.get('success', '✅')} Successfully removed directory and its contents: {directory_path}",
                    "info",
                    logger_to_use,
                    app_settings,
                )
            except Exception as e:
                log_map_server(
                    f"{symbols.get('error', '❌')} Error removing directory {directory_path} using shutil.rmtree: {e}",
                    "error",
                    logger_to_use,
                    app_settings,
                    exc_info=True,
                )
        else:
            log_map_server(
                f"{symbols.get('warning', '!')} Path {directory_path} exists but is not a directory.",
                "warning",
                logger_to_use,
                app_settings,
            )
    else:
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Directory {directory_path} does not exist. No cleanup needed.",
            "info",
            logger_to_use,
            app_settings,
        )

    if ensure_dir_exists_after:
        try:
            directory_path.mkdir(parents=True, exist_ok=True)
            log_map_server(
                f"Ensured directory exists: {directory_path}",
                "debug",
                logger_to_use,
                app_settings,
            )
        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '❌')} Error creating directory {directory_path} after cleanup: {e}",
                "error",
                logger_to_use,
                app_settings,
                exc_info=True,
            )


def ensure_directory_owned_by_current_user(
    dir_path: Path,
    make_directory: bool,
    world_access: bool,
    app_settings: AppSettings,
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Ensures that a specified directory exists, is owned by the current user, and has the
    desired permissions. If the directory does not exist, it can optionally create the
    directory. The permissions assigned can optionally include world access.

    Parameters:
    dir_path: Path
        The path to the directory that needs to be verified or created.
    make_directory: bool
        Indicates whether to create the directory if it does not exist.
    world_access: bool
        Flags whether the directory should be world-accessible.
    app_settings: AppSettings
        Application settings object containing configuration and other utility
        information.
    current_logger: Optional[logging.Logger], default = None
        A logger instance to log actions and events. If not provided, a default logger
        is used.

    Returns:
    None
    """
    logger_to_use = current_logger or logging.getLogger(__name__)
    symbols = app_settings.symbols

    current_uid_str = str(getuid())
    current_gid_str = str(getgid())

    if not dir_path.exists():
        log_map_server(
            f"Directory not found: {dir_path}. Creating it with elevated privileges.",
            "info",
            logger_to_use,
            app_settings,
        )
        if not make_directory:
            log_map_server(
                f"{dir_path} not found",
                "error",
                logger_to_use,
                app_settings,
                exc_info=True,
            )
        run_elevated_command(
            ["mkdir", "-p", str(dir_path)],
            app_settings,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Created directory: {dir_path}",
            "info",
            logger_to_use,
            app_settings,
        )

    log_map_server(
        f"Ensuring ownership ({current_uid_str}:{current_gid_str}) for {dir_path}",
        "debug",
        logger_to_use,
        app_settings,
    )
    run_elevated_command(
        ["chown", f"{current_uid_str}:{current_gid_str}", str(dir_path)],
        app_settings,
        current_logger=logger_to_use,
    )
    if world_access:
        run_elevated_command(
            ["chmod", "u+rwx,g+rx,o+rx", str(dir_path)],
            app_settings,
            current_logger=logger_to_use,
        )
    else:
        run_elevated_command(
            ["chmod", "u+rwx,g+rx,o-wrx", str(dir_path)],
            app_settings,
            current_logger=logger_to_use,
        )
