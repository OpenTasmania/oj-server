# setup/carto_installer.py
# -*- coding: utf-8 -*-
"""
Handles installation of CartoCSS compiler (carto) and setup of the
OpenStreetMap-Carto stylesheet repository.
"""
import getpass  # For user/group info
import grp
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from common.command_utils import (
    command_exists,
    log_map_server,
    run_command,
    run_elevated_command,
)
from setup import config

module_logger = logging.getLogger(__name__)

OSM_CARTO_BASE_DIR = "/opt/openstreetmap-carto"

def install_carto_cli(current_logger: Optional[logging.Logger] = None) -> None:
    """Installs the CartoCSS compiler (carto) globally via npm."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Installing CartoCSS compiler (carto CLI)...", "info", logger_to_use)

    if not command_exists("npm"):
        log_map_server(
            f"{config.SYMBOLS['error']} NPM (Node Package Manager) not found. "
            "Node.js needs to be installed first (e.g., via core prerequisites). Skipping carto CLI install.",
            "error", logger_to_use
        )
        raise EnvironmentError("NPM not found, cannot install carto CLI.")

    try:
        run_elevated_command(["npm", "install", "-g", "carto"], current_logger=logger_to_use)
        carto_version_result = run_command(
            ["carto", "-v"], capture_output=True, check=False, current_logger=logger_to_use
        )
        carto_version = (
            carto_version_result.stdout.strip()
            if carto_version_result.returncode == 0 and carto_version_result.stdout
            else "Not found or error determining version"
        )
        log_map_server(
            f"{config.SYMBOLS['success']} CartoCSS compiler 'carto' installed/updated. Version: {carto_version}",
            "success", logger_to_use
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to install 'carto' via npm: {e}. "
            "Check npm and Node.js installation.", "error", logger_to_use
        )
        raise

def setup_osm_carto_repository(current_logger: Optional[logging.Logger] = None) -> None:
    """Clones or confirms existence of the OpenStreetMap-Carto git repository."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Setting up OpenStreetMap-Carto repository at {OSM_CARTO_BASE_DIR}...", "info", logger_to_use)

    dir_exists_check = run_elevated_command(
        ["test", "-d", OSM_CARTO_BASE_DIR], check=False, capture_output=True, current_logger=logger_to_use
    )
    if dir_exists_check.returncode != 0:
        log_map_server(f"{config.SYMBOLS['info']} Cloning OpenStreetMap-Carto repository...", "info", logger_to_use)
        run_elevated_command(
            ["git", "clone", "--depth", "1", "https://github.com/gravitystorm/openstreetmap-carto.git", OSM_CARTO_BASE_DIR],
            current_logger=logger_to_use
        )
        log_map_server(f"{config.SYMBOLS['success']} Cloned OpenStreetMap-Carto to {OSM_CARTO_BASE_DIR}.", "success", logger_to_use)
    else:
        log_map_server(
            f"{config.SYMBOLS['info']} Directory {OSM_CARTO_BASE_DIR} already exists. "
            "To update, please do it manually (e.g., cd {OSM_CARTO_BASE_DIR} && sudo git pull).",
            "info", logger_to_use
        )

def prepare_carto_directory_for_processing(current_logger: Optional[logging.Logger] = None) -> None:
    """Temporarily changes ownership of the Carto directory to the current user for script execution."""
    logger_to_use = current_logger if current_logger else module_logger
    current_user = getpass.getuser()
    try:
        current_group_info = grp.getgrgid(os.getgid())
        current_group_name = current_group_info.gr_name
    except KeyError:
        current_group_name = str(os.getgid())

    log_map_server(
        f"{config.SYMBOLS['info']} Temporarily changing ownership of {OSM_CARTO_BASE_DIR} "
        f"to {current_user}:{current_group_name} for script execution.", "info", logger_to_use
    )
    run_elevated_command(
        ["chown", "-R", f"{current_user}:{current_group_name}", OSM_CARTO_BASE_DIR],
        current_logger=logger_to_use
    )

def fetch_carto_external_data(current_logger: Optional[logging.Logger] = None) -> None:
    """Fetches external data (shapefiles, etc.) for the OpenStreetMap-Carto style."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Fetching external data for OpenStreetMap-Carto style...", "info", logger_to_use)

    original_cwd = os.getcwd()
    python_exe_path = sys.executable # Assumes main_installer is run from the project's venv

    # Determine path to the custom get-external-data.py or the one in OSM_CARTO_BASE_DIR
    custom_script_path = config.OSM_PROJECT_ROOT / "external/openstreetmap-carto/scripts/get-external-data.py"
    script_to_run = []

    if custom_script_path.is_file():
        log_map_server(f"{config.SYMBOLS['info']} Using custom get-external-data.py: {custom_script_path}", "info", logger_to_use)
        script_to_run = [python_exe_path, str(custom_script_path)]
    else:
        log_map_server(f"{config.SYMBOLS['warning']} Custom get-external-data.py: {custom_script_path} not found", "warning",
                       logger_to_use)
        default_script_path = Path(OSM_CARTO_BASE_DIR) / "scripts/get-external-data.py"
        if default_script_path.is_file():
            log_map_server(f"{config.SYMBOLS['info']} Using default get-external-data.py from Carto repo: {default_script_path}", "info", logger_to_use)
            script_to_run = [python_exe_path, str(default_script_path)]
        else:
            log_map_server(f"{config.SYMBOLS['fatal']} No get-external-data.py script found at custom or default paths. Shapefiles might be missing.",
                           "fatal", logger_to_use)
            # Optionally, revert ownership here if this is considered a fatal error for this step
            raise # Or raise an error

    try:
        os.chdir(OSM_CARTO_BASE_DIR) # Scripts expect to be run from here
        if script_to_run:
            # Run command as current user (who now owns the directory)
            run_command(script_to_run, current_logger=logger_to_use, check=True) # check=True to catch errors
            log_map_server(f"{config.SYMBOLS['success']} External data fetching process completed.", "success", logger_to_use)
        else:
            log_map_server(f"{config.SYMBOLS['warning']} Skipped running get-external-data.py as it was not found.", "warning", logger_to_use)

    except Exception as e:
        log_map_server(f"{config.SYMBOLS['error']} Error during external data fetching for Carto: {e}", "error", logger_to_use)
        raise
    finally:
        os.chdir(original_cwd)
        # Ownership reversion will be handled by a finalize step
