# common/system_utils.py
# -*- coding: utf-8 -*-
"""
System-level utility functions for the map server setup script.

This module includes functions for system operations like reloading systemd,
determining the Debian codename, and calculating a project hash.
"""

import hashlib
import logging
import socket
import subprocess
from os import cpu_count
from pathlib import Path
from typing import List, Optional

from common.command_utils import (
    log_map_server,
    run_command,
    run_elevated_command,
)
from setup.config_models import (
    SYMBOLS_DEFAULT,
    AppSettings,
)

module_logger = logging.getLogger(__name__)

CACHED_SCRIPT_HASH: Optional[str] = None


def get_primary_ip_address(
    app_settings: Optional[AppSettings] = None,
    current_logger: Optional[logging.Logger] = None,
) -> Optional[str]:
    """
    Get the primary IP address of the machine.

    This function attempts to determine the primary IP address by creating a socket
    connection to an external host (doesn't actually connect).

    Args:
        app_settings: Optional application settings for logging symbols.
        current_logger: Optional logger instance.

    Returns:
        The primary IP address as a string, or None if it cannot be determined.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols_to_use = SYMBOLS_DEFAULT
    if (
        app_settings
        and hasattr(app_settings, "symbols")
        and app_settings.symbols
    ):
        symbols_to_use = app_settings.symbols

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_address = s.getsockname()[0]
        s.close()
        return str(ip_address)
    except Exception as e:
        log_map_server(
            f"{symbols_to_use.get('warning', '!')} Could not determine primary IP address: {e}",
            "warning",
            logger_to_use,
            app_settings,
        )
        return None


def calculate_project_hash(
    project_root_dir: Path,
    app_settings: AppSettings,
    current_logger: Optional[logging.Logger] = None,
) -> Optional[str]:
    """
    Calculate a SHA256 hash of all .py files within the project directory.

    The hash includes both file content and relative file paths (normalized to
    POSIX style) to detect additions, deletions, renames, and content changes.

    Args:
        project_root_dir: The root directory of the project (Path object).
        app_settings: The application settings object for accessing symbols.
        current_logger: Optional logger instance.

    Returns:
        The hex digest of the SHA256 hash as a string, or None if an error
        occurs.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    hasher = hashlib.sha256()
    py_files_found: List[Path] = []

    try:
        project_root = Path(project_root_dir)  # Ensure it's a Path object
        if not project_root.is_dir():
            log_map_server(
                f"{symbols.get('error', '❌')} Project root directory '{project_root}' not found for hashing.",
                "error",
                logger_to_use,
                app_settings,
            )
            return None

        # Iterate over .py files for hashing
        for path_object in project_root.rglob("*.py"):
            if path_object.is_file():
                py_files_found.append(path_object)

        if not py_files_found:  # Handle case with no Python files
            log_map_server(
                f"{symbols.get('warning', '!')} No .py files found under '{project_root}' for hashing. Hash will be of an empty set.",
                "warning",
                logger_to_use,
                app_settings,
            )
            return hasher.hexdigest()  # Returns hash of empty string

        # Sort files by relative path for consistent hashing
        sorted_files = sorted(
            py_files_found,
            key=lambda p: p.relative_to(project_root).as_posix(),
        )

        for file_path in sorted_files:
            try:
                # Include relative path in hash to account for file moves/renames
                relative_path_str = file_path.relative_to(
                    project_root
                ).as_posix()
                hasher.update(relative_path_str.encode("utf-8"))
                # Include file content in hash
                file_content = file_path.read_bytes()
                hasher.update(file_content)
            except (
                Exception
            ) as e_file:  # Handle errors reading individual files
                log_map_server(
                    f"{symbols.get('error', '❌')} Error reading file {file_path} for hashing: {e_file}",
                    "error",
                    logger_to_use,
                    app_settings,
                )
                return None  # Invalidate hash on any file read error

        final_hash = hasher.hexdigest()
        log_map_server(
            f"{symbols.get('debug', '🐛')} Calculated SCRIPT_HASH: {final_hash} from {len(sorted_files)} .py files in {project_root}.",
            "debug",
            logger_to_use,
            app_settings,
        )
        return final_hash
    except (
        Exception
    ) as e_hash:  # Catch-all for other errors during hashing process
        log_map_server(
            f"{symbols.get('error', '❌')} Critical error during project hashing: {e_hash}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        return None


def get_current_script_hash(
    project_root_dir: Path,
    app_settings: AppSettings,
    logger_instance: Optional[logging.Logger] = None,  # Renamed for clarity
) -> Optional[str]:
    """
    Get the current script hash, calculating it if not already cached.
    Uses app_settings for logging symbols via calculate_project_hash.
    """
    global CACHED_SCRIPT_HASH
    if CACHED_SCRIPT_HASH is None:
        CACHED_SCRIPT_HASH = calculate_project_hash(
            project_root_dir, app_settings, current_logger=logger_instance
        )
    return CACHED_SCRIPT_HASH


def systemd_reload(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Reload the systemd daemon.
    Uses app_settings for logging symbols.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('gear', '⚙️')} Reloading systemd daemon...",
        "info",
        logger_to_use,
        app_settings,
    )
    try:
        run_elevated_command(
            ["systemctl", "daemon-reload"],
            app_settings,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Systemd daemon reloaded.",
            "success",
            logger_to_use,
            app_settings,
        )
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to reload systemd: {e}",
            "error",
            logger_to_use,
            app_settings,
        )


def get_debian_codename(
    app_settings: Optional[AppSettings],
    current_logger: Optional[logging.Logger] = None,
) -> Optional[str]:
    """
    Get the Debian codename (e.g., 'bookworm', 'bullseye').
    Uses app_settings for logging symbols.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols_to_use = SYMBOLS_DEFAULT
    if (
        app_settings
        and hasattr(app_settings, "symbols")
        and app_settings.symbols
    ):
        symbols_to_use = app_settings.symbols

    try:
        result: subprocess.CompletedProcess = run_command(
            ["lsb_release", "-cs"],
            app_settings,
            capture_output=True,
            check=True,
            current_logger=logger_to_use,
        )
        stdout_val: Optional[str] = result.stdout
        if stdout_val is not None:
            return stdout_val.strip()
        return None
    except FileNotFoundError:
        log_map_server(
            f"{symbols_to_use.get('warning', '!')} lsb_release command not found. Cannot determine Debian codename.",
            "warning",
            logger_to_use,
            app_settings,
        )
        return None
    except subprocess.CalledProcessError:  # Command failed
        # Error is already logged by run_command if check=True and it raises
        # If check=False, or if run_command itself handles and logs, then this might be redundant or not hit.
        # Assuming run_command with check=True re-raises CalledProcessError
        # and its logging within run_command is sufficient.
        return None
    except Exception as e:  # Other errors
        log_map_server(
            f"{symbols_to_use.get('warning', '!')} Unexpected error getting Debian codename: {e}",
            "warning",
            logger_to_use,
            app_settings,
        )
        return None


def calculate_threads(
    app_settings: Optional[AppSettings],
    current_logger: Optional[logging.Logger] = None,
) -> Optional[str]:
    logger_to_use = current_logger if current_logger else module_logger
    symbols_to_use = SYMBOLS_DEFAULT
    num_threads_str = "0"
    # Ensure app_settings and renderd are accessible
    if (
        app_settings
        and hasattr(app_settings, "symbols")
        and app_settings.symbols
    ):
        symbols_to_use = app_settings.symbols

    if (
        not app_settings
        or not hasattr(app_settings, "renderd")
        or not app_settings.renderd
    ):
        log_map_server(
            f"{symbols_to_use.get('error', '❌')} App settings or renderd configuration not found. Cannot calculate threads.",
            "error",
            logger_to_use,
            app_settings,
        )
        return None

    renderd_cfg = app_settings.renderd

    try:
        result: subprocess.CompletedProcess = run_command(
            ["lscpu", "-p=Core,Socket"],
            app_settings,
            capture_output=True,
            check=True,
            current_logger=logger_to_use,
        )
        stdout_val: Optional[str] = result.stdout

        if stdout_val is not None:
            if float(renderd_cfg.num_threads_multiplier) > 0:
                physical_core_count = None
                try:
                    # Use stdout_val from the run_command call
                    physical_cores = {
                        line
                        for line in stdout_val.strip().split("\n")
                        if not line.startswith("#")
                    }
                    if physical_cores:
                        physical_core_count = len(physical_cores)
                except Exception as e:
                    log_map_server(
                        f"{symbols_to_use.get('warning', '!')} Error parsing lscpu output for physical cores: {e}",
                        "warning",
                        logger_to_use,
                        app_settings,
                    )
                    physical_core_count = None

                cpu_c: Optional[int] = cpu_count()
                cpu_count_to_use = physical_core_count or cpu_c

                calculated_threads = int(
                    (cpu_count_to_use or 1)
                    * float(renderd_cfg.num_threads_multiplier)
                )
                num_threads_str = str(max(1, calculated_threads))
            return num_threads_str
        return None  # If stdout_val is None after run_command
    except FileNotFoundError:
        log_map_server(
            f"{symbols_to_use.get('warning', '!')} lscpu command not found. Cannot determine cpu count.",
            "warning",
            logger_to_use,
            app_settings,
        )
        return None
    except subprocess.CalledProcessError:
        # run_command with check=True already logs the error, just return None
        return None
    except Exception as e:  # Other errors
        log_map_server(
            f"{symbols_to_use.get('warning', '!')} Unexpected error calculating threads: {e}",
            "warning",
            logger_to_use,
            app_settings,
        )
        return None
