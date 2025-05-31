# setup/osrm_installer.py
# -*- coding: utf-8 -*-
"""
Handles initial setup for OSRM: dependency checks, directory creation,
PBF download, and region boundary file preparation.
"""
import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from common.command_utils import (
    log_map_server,
    run_elevated_command,
    check_package_installed,
    command_exists,
    run_command
)
from setup import config

module_logger = logging.getLogger(__name__)

OSM_DATA_BASE_DIR = "/opt/osm_data"
OSM_DATA_REGIONS_DIR = os.path.join(OSM_DATA_BASE_DIR, "regions")
OSRM_BASE_PROCESSED_DIR = "/opt/osrm_processed_data"  # For OSRM outputs
AUSTRALIA_PBF_FILENAME = "australia-latest.osm.pbf"  # Example, from original script
GEOFABRIK_AUSTRALIA_PBF_URL = (  # Example
    f"https://download.geofabrik.de/australia-oceania/{AUSTRALIA_PBF_FILENAME}"
)


def ensure_osrm_dependencies(current_logger: Optional[logging.Logger] = None) -> None:
    """Ensures Docker and Osmium (via osmium-tool) are available."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['info']} Checking OSRM dependencies (Docker, osmium-tool)...", "info",
                   logger_to_use)

    if not command_exists("docker"):
        log_map_server(f"{config.SYMBOLS['error']} Docker is not installed. OSRM processing requires Docker.", "error",
                       logger_to_use)
        raise EnvironmentError("Docker is not installed. Please run Docker installation.")
    log_map_server(f"{config.SYMBOLS['success']} Docker is available.", "success", logger_to_use)

    if not check_package_installed("osmium-tool", current_logger=logger_to_use):
        log_map_server(
            f"{config.SYMBOLS['error']} 'osmium-tool' is not installed. This is required for PBF extraction.", "error",
            logger_to_use)
        raise EnvironmentError("'osmium-tool' not found. Please ensure mapping packages are installed.")
    log_map_server(f"{config.SYMBOLS['success']} 'osmium-tool' is available.", "success", logger_to_use)

    if not command_exists("wget"):  # For PBF download
        log_map_server(f"{config.SYMBOLS['error']} 'wget' is not installed. This is required for PBF download.",
                       "error", logger_to_use)
        raise EnvironmentError("'wget' not found.")
    log_map_server(f"{config.SYMBOLS['success']} 'wget' is available.", "success", logger_to_use)


def setup_osrm_data_directories(current_logger: Optional[logging.Logger] = None) -> None:
    """Creates base directories for OSRM source data and processed files."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Setting up OSRM data directories...", "info", logger_to_use)

    # These UIDs are for directory ownership, not Docker execution.
    # Docker execution UID/GID is passed per command.
    current_uid_str = str(os.getuid())
    current_gid_str = str(os.getgid())

    dirs_to_create = [OSM_DATA_BASE_DIR, OSM_DATA_REGIONS_DIR, OSRM_BASE_PROCESSED_DIR]
    for dir_path in dirs_to_create:
        if not os.path.exists(dir_path):
            run_elevated_command(["mkdir", "-p", dir_path], current_logger=logger_to_use)
            run_elevated_command(["chown", f"{current_uid_str}:{current_gid_str}", dir_path],
                                 current_logger=logger_to_use)
            run_elevated_command(["chmod", "u+rwx", dir_path], current_logger=logger_to_use)  # Ensure user can write
            log_map_server(f"{config.SYMBOLS['success']} Created and permissioned directory: {dir_path}", "success",
                           logger_to_use)
        else:
            # Ensure permissions if it exists
            run_elevated_command(["chown", f"{current_uid_str}:{current_gid_str}", dir_path],
                                 current_logger=logger_to_use)
            run_elevated_command(["chmod", "u+rwx", dir_path], current_logger=logger_to_use)
            log_map_server(
                f"{config.SYMBOLS['info']} Ensured ownership and permissions for existing directory: {dir_path}",
                "info", logger_to_use)


def download_base_pbf(current_logger: Optional[logging.Logger] = None) -> str:
    """Downloads the base PBF file (e.g., australia-latest.osm.pbf). Returns path to downloaded file."""
    logger_to_use = current_logger if current_logger else module_logger
    pbf_download_url = GEOFABRIK_AUSTRALIA_PBF_URL  # Could be made a config variable
    pbf_filename = AUSTRALIA_PBF_FILENAME
    pbf_full_path = os.path.join(OSM_DATA_BASE_DIR, pbf_filename)

    log_map_server(f"{config.SYMBOLS['step']} Managing base PBF file: {pbf_filename}...", "info", logger_to_use)

    if not os.path.isfile(pbf_full_path):
        log_map_server(
            f"{config.SYMBOLS['info']} Downloading {pbf_filename} from {pbf_download_url} to {OSM_DATA_BASE_DIR}...",
            "info", logger_to_use)
        # Download to a directory the current user has write access to, then move if needed,
        # or ensure OSM_DATA_BASE_DIR is writable by current user (done in setup_osrm_data_directories)
        run_command(
            ["wget", pbf_download_url, "-O", pbf_full_path],
            cwd=OSM_DATA_BASE_DIR,  # wget -O specifies full path, cwd might be redundant but harmless
            current_logger=logger_to_use
        )
        log_map_server(f"{config.SYMBOLS['success']} Downloaded {pbf_filename}.", "success", logger_to_use)
    else:
        log_map_server(f"{config.SYMBOLS['info']} Base PBF file {pbf_full_path} already exists. Skipping download.",
                       "info", logger_to_use)

    if not os.path.isfile(pbf_full_path):
        raise FileNotFoundError(f"Base PBF file {pbf_full_path} not found after download attempt.")
    return pbf_full_path


def prepare_region_boundaries(current_logger: Optional[logging.Logger] = None) -> None:
    """Copies GeoJSON region boundary files from project assets to OSM_DATA_REGIONS_DIR."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Preparing region boundary files (GeoJSON)...", "info", logger_to_use)

    # Assumes config.OSM_PROJECT_ROOT points to the root of your cloned project
    assets_source_regions_dir = config.OSM_PROJECT_ROOT / "assets" / "regions"
    target_osm_data_regions_dir = Path(OSM_DATA_REGIONS_DIR)

    if not assets_source_regions_dir.is_dir():
        log_map_server(
            f"{config.SYMBOLS['warning']} Local assets regions directory NOT FOUND: {assets_source_regions_dir}. Cannot copy GeoJSON files.",
            "warning", logger_to_use)
        return

    # Ensure target base directory exists (should be by setup_osrm_data_directories)
    target_osm_data_regions_dir.mkdir(parents=True, exist_ok=True)

    current_uid_str = str(os.getuid())
    current_gid_str = str(os.getgid())

    for root, dirs, files in os.walk(assets_source_regions_dir):
        source_root_path = Path(root)
        relative_path_from_assets = source_root_path.relative_to(assets_source_regions_dir)
        target_current_dir = target_osm_data_regions_dir / relative_path_from_assets

        if not target_current_dir.exists():
            target_current_dir.mkdir(parents=True, exist_ok=True)
            # Ownership of subdirs within OSM_DATA_REGIONS_DIR should also be current user
            # if created here by the script before Docker potentially writes as root.
            # However, the parent OSM_DATA_REGIONS_DIR is already chowned.
            # For simplicity, we'll rely on parent dir permissions.

        for file_name in files:
            if file_name.endswith(".json"):  # Assuming GeoJSON files
                source_file = source_root_path / file_name
                target_file = target_current_dir / file_name
                shutil.copy2(source_file, target_file)  # copy2 preserves metadata
                # Ensure copied files are also owned by current user for osmium processing
                # run_elevated_command(["chown", f"{current_uid_str}:{current_gid_str}", str(target_file)], current_logger=logger_to_use)
                log_map_server(f"Copied boundary file: {target_file}", "debug", logger_to_use)

    log_map_server(f"{config.SYMBOLS['success']} Region boundary files copied to {target_osm_data_regions_dir}",
                   "success", logger_to_use)