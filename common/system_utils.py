# common/system_utils.py
# -*- coding: utf-8 -*-
"""
System-level utility functions for the map server setup script.

This module includes functions for system operations like reloading systemd,
determining the Debian codename, and calculating a project hash.
"""

import hashlib
import logging
import subprocess
from pathlib import Path
from typing import List, Optional

# Import static_config for OSM_PROJECT_ROOT, as it's a fixed project path
# Import AppSettings for type hinting
from setup.config_models import AppSettings
# Import command utilities that now also expect app_settings
from .command_utils import log_map_server, run_command, run_elevated_command

module_logger = logging.getLogger(__name__)

# --- Script Hashing (moved from state_manager) ---
# Global variable to cache the calculated script hash.
CACHED_SCRIPT_HASH: Optional[str] = None


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
        project_root_dir: Path,  # Expected to be static_config.OSM_PROJECT_ROOT
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


# --- Other System Utilities ---


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
        # run_elevated_command now takes app_settings
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
        # Consider if this should raise an error or just log, depending on criticality of systemd reload


def get_debian_codename(
        app_settings: Optional[AppSettings], current_logger: Optional[logging.Logger] = None
) -> Optional[str]:
    """
    Get the Debian codename (e.g., 'bookworm', 'bullseye').
    Uses app_settings for logging symbols.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    try:
        # run_command now takes app_settings
        result = run_command(
            ["lsb_release", "-cs"],
            app_settings,
            capture_output=True,
            check=True,
            current_logger=logger_to_use,
        )
        return result.stdout.strip()
    except FileNotFoundError:  # lsb_release not found
        log_map_server(
            f"{symbols.get('warning', '!')} lsb_release command not found. Cannot determine Debian codename.",
            "warning",
            logger_to_use,
            app_settings,
        )
        return None
    except subprocess.CalledProcessError:  # Command failed
        # Error is already logged by run_command if check=True
        return None
    except Exception as e:  # Other errors
        log_map_server(
            f"{symbols.get('warning', '!')} Unexpected error getting Debian codename: {e}",
            "warning",
            logger_to_use,
            app_settings,
        )
        return None
