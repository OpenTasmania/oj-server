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

# Assuming config.py is accessible from the project root or PYTHONPATH is set up
# If config.py moves to root, this would be: from config import SYMBOLS, OSM_PROJECT_ROOT
from setup import config
# Assuming command_utils is now in the common package
from .command_utils import log_map_server, run_command, run_elevated_command

module_logger = logging.getLogger(__name__)


def systemd_reload(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Reload the systemd daemon.

    Args:
        current_logger: Optional logger instance to use.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['gear']} Reloading systemd daemon...",
        "info",
        logger_to_use,
    )
    try:
        run_elevated_command(
            ["systemctl", "daemon-reload"], current_logger=logger_to_use
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Systemd daemon reloaded.",
            "success",
            logger_to_use,
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to reload systemd: {e}",
            "error",
            logger_to_use,
        )
        # Depending on script's overall error handling,
        # you might want to raise e here.


def get_debian_codename(
    current_logger: Optional[logging.Logger] = None,
) -> Optional[str]:
    """
    Get the Debian codename (e.g., 'bookworm', 'bullseye').

    Args:
        current_logger: Optional logger instance.

    Returns:
        The Debian codename as a string if successful, None otherwise.
    """
    logger_to_use = current_logger if current_logger else module_logger
    try:
        result = run_command(
            ["lsb_release", "-cs"],
            capture_output=True,
            check=True,
            current_logger=logger_to_use,
        )
        return result.stdout.strip()
    except FileNotFoundError:
        log_map_server(
            f"{config.SYMBOLS['warning']} lsb_release command not found. "
            "Cannot determine Debian codename.",
            "warning",
            logger_to_use,
        )
        return None
    except subprocess.CalledProcessError:
        return None # Error already logged by run_command
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['warning']} Unexpected error getting Debian "
            f"codename: {e}",
            "warning",
            logger_to_use,
        )
        return None


def calculate_project_hash(
    project_root_dir: Path, current_logger: Optional[logging.Logger] = None
) -> Optional[str]:
    """
    Calculate a SHA256 hash of all .py files within the project directory.

    The hash includes both file content and relative file paths (normalized to
    POSIX style) to detect additions, deletions, renames, and content changes.

    Args:
        project_root_dir: The root directory of the project (Path object).
        current_logger: Optional logger instance.

    Returns:
        The hex digest of the SHA256 hash as a string, or None if an error
        occurs.
    """
    logger_to_use = current_logger if current_logger else module_logger
    hasher = hashlib.sha256()
    py_files_found: List[Path] = []

    try:
        project_root = Path(project_root_dir)
        if not project_root.is_dir():
            log_map_server(
                f"{config.SYMBOLS['error']} Project root directory "
                f"'{project_root}' not found for hashing.",
                "error",
                logger_to_use,
            )
            return None

        for path_object in project_root.rglob("*.py"):
            if path_object.is_file():
                py_files_found.append(path_object)

        if not py_files_found:
            log_map_server(
                f"{config.SYMBOLS['warning']} No .py files found under "
                f"'{project_root}' for hashing.",
                "warning",
                logger_to_use,
            )
            return hasher.hexdigest() # Return hash of empty set

        sorted_files = sorted(
            py_files_found,
            key=lambda p: p.relative_to(project_root).as_posix(),
        )

        for file_path in sorted_files:
            try:
                relative_path_str = file_path.relative_to(
                    project_root
                ).as_posix()
                hasher.update(relative_path_str.encode("utf-8"))
                file_content = file_path.read_bytes()
                hasher.update(file_content)
            except Exception as e_file:
                log_map_server(
                    f"{config.SYMBOLS['error']} Error reading file "
                    f"{file_path} for hashing: {e_file}",
                    "error",
                    logger_to_use,
                )
                return None

        final_hash = hasher.hexdigest()
        log_map_server(
            f"{config.SYMBOLS['debug']} Calculated SCRIPT_HASH: {final_hash} "
            f"from {len(sorted_files)} .py files in {project_root}.",
            "debug",
            logger_to_use,
        )
        return final_hash

    except Exception as e_hash:
        log_map_server(
            f"{config.SYMBOLS['error']} Critical error during project "
            f"hashing: {e_hash}",
            "error",
            logger_to_use,
        )
        return None