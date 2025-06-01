# installer/carto_installer.py
# -*- coding: utf-8 -*-
"""
Handles installation of CartoCSS compiler (carto) and setup of the
OpenStreetMap-Carto stylesheet repository.
"""
import getpass
import grp
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

from common.command_utils import (
    command_exists,
    log_map_server,
    run_command,
    run_elevated_command,
)
# Import AppSettings for type hinting
from setup.config_models import AppSettings
# Import static_config for OSM_PROJECT_ROOT and other true constants
from setup import config as static_config

module_logger = logging.getLogger(__name__)

# OSM_CARTO_BASE_DIR is a static path, keep as module constant or from static_config
OSM_CARTO_BASE_DIR = "/opt/openstreetmap-carto"

def install_carto_cli(app_settings: AppSettings, current_logger: Optional[logging.Logger] = None) -> None:
    """Installs the CartoCSS compiler (carto) globally via npm."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(f"{symbols.get('step','➡️')} Installing CartoCSS compiler (carto CLI)...", "info", logger_to_use, app_settings)

    if not command_exists("npm"):
        log_map_server(
            f"{symbols.get('error','❌')} NPM (Node Package Manager) not found. "
            "Node.js needs to be installed first. Skipping carto CLI install.",
            "error", logger_to_use, app_settings
        )
        raise EnvironmentError("NPM not found, cannot install carto CLI.")

    try:
        run_elevated_command(["npm", "install", "-g", "carto"], app_settings, current_logger=logger_to_use)
        carto_version_result = run_command(
            ["carto", "-v"], app_settings, capture_output=True, check=False, current_logger=logger_to_use
        )
        carto_version = (
            carto_version_result.stdout.strip()
            if carto_version_result.returncode == 0 and carto_version_result.stdout
            else "Not found or error determining version"
        )
        log_map_server(
            f"{symbols.get('success','✅')} CartoCSS compiler 'carto' installed/updated. Version: {carto_version}",
            "success", logger_to_use, app_settings
        )
    except Exception as e:
        log_map_server(
            f"{symbols.get('error','❌')} Failed to install 'carto' via npm: {e}. Check npm/Node.js.",
            "error", logger_to_use, app_settings
        )
        raise

def setup_osm_carto_repository(app_settings: AppSettings, current_logger: Optional[logging.Logger] = None) -> None:
    """Clones or confirms existence of the OpenStreetMap-Carto git repository."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(f"{symbols.get('step','➡️')} Setting up OpenStreetMap-Carto repository at {OSM_CARTO_BASE_DIR}...", "info", logger_to_use, app_settings)

    dir_exists_check = run_elevated_command(
        ["test", "-d", OSM_CARTO_BASE_DIR], app_settings,
        check=False, capture_output=True, current_logger=logger_to_use
    )
    if dir_exists_check.returncode != 0:
        log_map_server(f"{symbols.get('info','ℹ️')} Cloning OpenStreetMap-Carto repository...", "info", logger_to_use, app_settings)
        run_elevated_command(
            ["git", "clone", "--depth", "1", "https://github.com/gravitystorm/openstreetmap-carto.git", OSM_CARTO_BASE_DIR],
            app_settings, current_logger=logger_to_use
        )
        log_map_server(f"{symbols.get('success','✅')} Cloned OpenStreetMap-Carto to {OSM_CARTO_BASE_DIR}.", "success", logger_to_use, app_settings)
    else:
        log_map_server(
            f"{symbols.get('info','ℹ️')} Directory {OSM_CARTO_BASE_DIR} already exists. To update, please do so manually.",
            "info", logger_to_use, app_settings
        )

def prepare_carto_directory_for_processing(app_settings: AppSettings, current_logger: Optional[logging.Logger] = None) -> None:
    """Temporarily changes ownership of the Carto directory to the current user for script execution."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    current_user = getpass.getuser()
    try:
        current_group_info = grp.getgrgid(os.getgid())
        current_group_name = current_group_info.gr_name
    except KeyError: # Fallback if group name can't be found
        current_group_name = str(os.getgid())

    log_map_server(
        f"{symbols.get('info','ℹ️')} Temporarily changing ownership of {OSM_CARTO_BASE_DIR} "
        f"to {current_user}:{current_group_name} for script execution.", "info", logger_to_use, app_settings
    )
    run_elevated_command(
        ["chown", "-R", f"{current_user}:{current_group_name}", OSM_CARTO_BASE_DIR],
        app_settings, current_logger=logger_to_use
    )

def fetch_carto_external_data(app_settings: AppSettings, current_logger: Optional[logging.Logger] = None) -> None:
    """Fetches external data (shapefiles, etc.) for the OpenStreetMap-Carto style."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(f"{symbols.get('step','➡️')} Fetching external data for OpenStreetMap-Carto style...", "info", logger_to_use, app_settings)

    original_cwd = os.getcwd()
    python_exe_path = sys.executable

    # OSM_PROJECT_ROOT comes from static_config
    custom_script_path = static_config.OSM_PROJECT_ROOT / "external/openstreetmap-carto/scripts/get-external-data.py"
    script_to_run_cmd: List[str] = []

    if custom_script_path.is_file():
        log_map_server(f"{symbols.get('info','ℹ️')} Using custom get-external-data.py: {custom_script_path}", "info", logger_to_use, app_settings)
        script_to_run_cmd = [python_exe_path, str(custom_script_path)]
    else:
        log_map_server(f"{symbols.get('warning','!')} Custom get-external-data.py: {custom_script_path} not found", "warning", logger_to_use, app_settings)
        default_script_path = Path(OSM_CARTO_BASE_DIR) / "scripts/get-external-data.py"
        if default_script_path.is_file():
            log_map_server(f"{symbols.get('info','ℹ️')} Using default get-external-data.py from Carto repo: {default_script_path}", "info", logger_to_use, app_settings)
            script_to_run_cmd = [python_exe_path, str(default_script_path)]
        else:
            log_map_server(f"{symbols.get('critical','🔥')} No get-external-data.py script found. Shapefiles might be missing.", "critical", logger_to_use, app_settings)
            # This is a significant issue, so re-raise to halt the Carto setup for this step.
            raise FileNotFoundError("get-external-data.py script not found at custom or default paths.")

    try:
        os.chdir(OSM_CARTO_BASE_DIR)
        if script_to_run_cmd:
            # Run command as current user (who now owns the directory)
            # run_command expects app_settings
            run_command(script_to_run_cmd, app_settings, current_logger=logger_to_use, check=True)
            log_map_server(f"{symbols.get('success','✅')} External data fetching process completed.", "success", logger_to_use, app_settings)
        # else case handled by prior raise if script_to_run_cmd is empty
    except Exception as e:
        log_map_server(f"{symbols.get('error','❌')} Error during external data fetching for Carto: {e}", "error", logger_to_use, app_settings)
        raise # Re-raise to signal failure
    finally:
        os.chdir(original_cwd)
        # Ownership reversion will be handled by a finalize step in carto_configurator.py