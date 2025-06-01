# common/system_utils.py
# -*- coding: utf-8 -*-
"""
System-level utility functions for the map server setup script.
"""

import hashlib
import logging
import subprocess
from pathlib import Path
from typing import List, Optional

from setup.config_models import AppSettings # For type hinting
# from setup import config as static_config # For OSM_PROJECT_ROOT (if not in AppSettings) and SYMBOLS
from .command_utils import log_map_server, run_command, run_elevated_command
# OSM_PROJECT_ROOT is now a static constant in static_config
from setup import config as static_config


module_logger = logging.getLogger(__name__)


def systemd_reload(app_settings: AppSettings, current_logger: Optional[logging.Logger] = None) -> None: # Added app_settings
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(f"{symbols.get('gear','')} Reloading systemd daemon...", "info", logger_to_use, app_settings)
    try:
        run_elevated_command(["systemctl", "daemon-reload"], app_settings, current_logger=logger_to_use) # Pass app_settings
        log_map_server(f"{symbols.get('success','')} Systemd daemon reloaded.", "success", logger_to_use, app_settings)
    except Exception as e:
        log_map_server(f"{symbols.get('error','')} Failed to reload systemd: {e}", "error", logger_to_use, app_settings)
        # raise # Decide if this should be fatal

def get_debian_codename(app_settings: AppSettings, current_logger: Optional[logging.Logger] = None) -> Optional[str]: # Added app_settings
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    try:
        result = run_command(["lsb_release", "-cs"], app_settings, capture_output=True, check=True, current_logger=logger_to_use) # Pass app_settings
        return result.stdout.strip()
    except FileNotFoundError:
        log_map_server(f"{symbols.get('warning','')} lsb_release command not found. Cannot determine Debian codename.", "warning", logger_to_use, app_settings)
        return None
    except subprocess.CalledProcessError: return None # Error already logged
    except Exception as e:
        log_map_server(f"{symbols.get('warning','')} Unexpected error getting Debian codename: {e}", "warning", logger_to_use, app_settings)
        return None


def calculate_project_hash(
    project_root_dir: Path, # project_root_dir is static, from static_config
    app_settings: AppSettings, # Added app_settings for symbols
    current_logger: Optional[logging.Logger] = None
) -> Optional[str]:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    hasher = hashlib.sha256()
    py_files_found: List[Path] = []

    try:
        project_root = Path(project_root_dir)
        if not project_root.is_dir():
            log_map_server(f"{symbols.get('error','')} Project root directory '{project_root}' not found for hashing.", "error", logger_to_use, app_settings)
            return None
        for path_object in project_root.rglob("*.py"):
            if path_object.is_file(): py_files_found.append(path_object)
        if not py_files_found:
            log_map_server(f"{symbols.get('warning','')} No .py files found under '{project_root}' for hashing.", "warning", logger_to_use, app_settings)
            return hasher.hexdigest()
        sorted_files = sorted(py_files_found, key=lambda p: p.relative_to(project_root).as_posix())
        for file_path in sorted_files:
            try:
                relative_path_str = file_path.relative_to(project_root).as_posix()
                hasher.update(relative_path_str.encode("utf-8"))
                file_content = file_path.read_bytes()
                hasher.update(file_content)
            except Exception as e_file:
                log_map_server(f"{symbols.get('error','')} Error reading file {file_path} for hashing: {e_file}", "error", logger_to_use, app_settings)
                return None
        final_hash = hasher.hexdigest()
        log_map_server(f"{symbols.get('debug','')} Calculated SCRIPT_HASH: {final_hash} from {len(sorted_files)} .py files in {project_root}.", "debug", logger_to_use, app_settings)
        return final_hash
    except Exception as e_hash:
        log_map_server(f"{symbols.get('error','')} Critical error during project hashing: {e_hash}", "error", logger_to_use, app_settings)
        return None