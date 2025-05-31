# setup/osrm_data_processor.py
# -*- coding: utf-8 -*-
"""
Handles OSRM data processing: Osmium extraction and OSRM graph building via Docker.
"""
import logging
import os
import subprocess  # For CalledProcessError
from pathlib import Path
from typing import Optional, Dict, List

from common.command_utils import log_map_server, run_elevated_command, run_command
from setup import config

module_logger = logging.getLogger(__name__)

# Constants from original osrm.py relevant to Docker processing
OSM_DATA_REGIONS_DIR = "/opt/osm_data/regions"  # Source for GeoJSONs and where regional PBFs will be placed
OSRM_BASE_PROCESSED_DIR = "/opt/osrm_processed_data"
OSRM_DOCKER_IMAGE = "osrm/osrm-backend:latest"
OSRM_PROFILE_LUA_IN_CONTAINER = "/opt/car.lua"  # Default car profile in OSRM container


def _run_osrm_docker_command_internal(  # Renamed to avoid direct call, now internal helper
        command_args: List[str],
        region_osrm_data_dir_host: str,  # Host path for OSRM outputs for this region
        pbf_host_path_for_mount: Optional[str],  # Host path to input PBF for this step (if any)
        pbf_filename_in_container_mount: Optional[str],  # Name of PBF inside /mnt_readonly_pbf
        logger: logging.Logger,
        step_name: str,
        region_name_log: str,
) -> bool:
    """Helper to run OSRM Docker commands for processing steps."""
    # Docker execution usually needs current user's UID/GID if creating files on host
    # to avoid root-owned files in host-mounted volumes.
    docker_exec_uid = str(os.getuid())
    docker_exec_gid = str(os.getgid())

    docker_base_cmd = ["docker", "run", "--rm", "-u", f"{docker_exec_uid}:{docker_exec_gid}"]
    volume_mounts = []

    if pbf_host_path_for_mount and pbf_filename_in_container_mount:
        volume_mounts.extend(
            ["-v", f"{pbf_host_path_for_mount}:/mnt_readonly_pbf/{pbf_filename_in_container_mount}:ro"])

    # Mount the processing directory read-write for OSRM tool outputs
    Path(region_osrm_data_dir_host).mkdir(parents=True, exist_ok=True)  # Ensure it exists
    volume_mounts.extend(["-v", f"{region_osrm_data_dir_host}:/data_processing"])

    full_docker_cmd = (
            docker_base_cmd + volume_mounts +
            ["-w", "/data_processing", OSRM_DOCKER_IMAGE] + command_args
    )

    log_map_server(f"{config.SYMBOLS['info']} Running Docker {step_name} for {region_name_log}...", "info", logger)
    log_map_server(f"{config.SYMBOLS['debug']} Docker command: {' '.join(full_docker_cmd)}", "debug", logger)

    try:
        # Docker commands are often run with sudo if user isn't in docker group,
        # but run_elevated_command handles this.
        result = run_elevated_command(full_docker_cmd, current_logger=logger, capture_output=True, check=True)
        # check=True will raise CalledProcessError on failure. Output is logged by run_elevated_command.
        log_map_server(f"{config.SYMBOLS['success']} Docker {step_name} for {region_name_log} completed successfully.",
                       "success", logger)
        return True
    except subprocess.CalledProcessError as e:
        # Error already logged by run_elevated_command
        log_map_server(f"{config.SYMBOLS['critical']} Docker {step_name} for {region_name_log} FAILED. See logs.",
                       "critical", logger)
        return False
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['critical']} Exception during Docker {step_name} for {region_name_log}: {e}",
                       "critical", logger)
        return False


def extract_regional_pbfs_with_osmium(
        base_pbf_full_path: str,
        current_logger: Optional[logging.Logger] = None
) -> Dict[str, str]:
    """
    Extracts regional PBFs using Osmium based on GeoJSON files in OSM_DATA_REGIONS_DIR.
    Returns a dictionary mapping region base name to its extracted PBF file path.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Extracting regional PBFs using Osmium...", "info", logger_to_use)

    extracted_pbf_paths: Dict[str, str] = {}
    geojson_suffix = "RegionMap.json"  # From original osrm.py

    # Ensure the user running osmium can write to OSM_DATA_REGIONS_DIR
    # This should be covered by setup_osrm_data_directories in the installer part.

    for root, _, files in os.walk(OSM_DATA_REGIONS_DIR):
        for geojson_filename in files:
            if geojson_filename.endswith(geojson_suffix):
                geojson_full_path = os.path.join(root, geojson_filename)
                region_base_name = geojson_filename.removesuffix(geojson_suffix)

                output_pbf_filename = f"{region_base_name}.osm.pbf"
                # Regional PBFs are stored alongside their GeoJSONs
                output_pbf_full_path = os.path.join(root, output_pbf_filename)

                log_map_server(f"Processing region: {region_base_name} from {geojson_filename}", "debug", logger_to_use)

                if os.path.isfile(output_pbf_full_path):
                    log_map_server(
                        f"{config.SYMBOLS['info']} Regional PBF {output_pbf_full_path} already exists. Skipping Osmium extraction.",
                        "info", logger_to_use)
                    extracted_pbf_paths[region_base_name] = output_pbf_full_path
                    continue

                osmium_cmd = [
                    "osmium", "extract", "--strategy", "smart",
                    "-p", geojson_full_path, base_pbf_full_path,
                    "-o", output_pbf_full_path, "--overwrite"
                ]
                try:
                    # Osmium runs as current user. Assumes current user has write access to OSM_DATA_REGIONS_DIR.
                    run_command(osmium_cmd, check=True, current_logger=logger_to_use)
                    log_map_server(
                        f"{config.SYMBOLS['success']} Extracted {output_pbf_full_path} for {region_base_name}.",
                        "success", logger_to_use)
                    extracted_pbf_paths[region_base_name] = output_pbf_full_path
                except subprocess.CalledProcessError as e:
                    log_map_server(f"{config.SYMBOLS['error']} Osmium extraction failed for {region_base_name}: {e}",
                                   "error", logger_to_use)
                    # Decide if one failure should stop all. For now, continue.
                except Exception as e:
                    log_map_server(
                        f"{config.SYMBOLS['error']} Unexpected error during Osmium extraction for {region_base_name}: {e}",
                        "error", logger_to_use)

    if not extracted_pbf_paths:
        log_map_server(f"{config.SYMBOLS['warning']} No regional PBFs were extracted by Osmium.", "warning",
                       logger_to_use)
    return extracted_pbf_paths


def build_osrm_graphs_for_region(
        region_name: str,
        regional_pbf_path: str,  # Host path to the specific regional PBF
        current_logger: Optional[logging.Logger] = None
) -> bool:
    """Runs osrm-extract, osrm-partition, and osrm-customize for a given regional PBF."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Building OSRM graphs for region: {region_name} from PBF: {regional_pbf_path}",
        "info", logger_to_use)

    region_osrm_output_dir_host = os.path.join(OSRM_BASE_PROCESSED_DIR, region_name)
    Path(region_osrm_output_dir_host).mkdir(parents=True, exist_ok=True)
    # Ensure this dir is writable by user `docker_exec_uid` inside container
    # This typically means current host user if UID/GID mapping is used,
    # or root if not (leading to root-owned files on host).
    # The _run_osrm_docker_command_internal uses current UID/GID for -u flag.

    pbf_filename_on_host = os.path.basename(regional_pbf_path)

    # OSRM output files will use region_name as base, e.g., region_name.osrm
    osrm_base_filename_in_container = f"{region_name}.osrm"  # This is what osrm-extract -o expects
    # For osrm-extract, the input PBF is copied inside the Docker command
    internal_pbf_copy_name_in_container = f"{region_name}_processing.osm.pbf"

    # 1. osrm-extract
    # Command inside container: cp /mnt_readonly_pbf/<pbf_file> ./<internal_copy_name>.osm.pbf && osrm-extract -p <profile> ./<internal_copy_name>.osm.pbf -o ./<region_name>.osrm && rm ./<internal_copy_name>.osm.pbf
    extract_shell_cmd = (
        f'cp "/mnt_readonly_pbf/{pbf_filename_on_host}" "./{internal_pbf_copy_name_in_container}" && '
        f'osrm-extract -p "{OSRM_PROFILE_LUA_IN_CONTAINER}" "./{internal_pbf_copy_name_in_container}" && '  # Default osrm-extract output is input_basename.osrm
        f'mv "./{Path(internal_pbf_copy_name_in_container).stem}.osrm" "./{osrm_base_filename_in_container}" && '  # Ensure output is region_name.osrm
        f'rm "./{internal_pbf_copy_name_in_container}"'
    )
    extract_ok = _run_osrm_docker_command_internal(
        command_args=["sh", "-c", extract_shell_cmd],
        region_osrm_data_dir_host=region_osrm_output_dir_host,
        pbf_host_path_for_mount=regional_pbf_path,
        pbf_filename_in_container_mount=pbf_filename_on_host,
        logger=logger_to_use,
        step_name="osrm-extract",
        region_name_log=region_name
    )
    if not extract_ok: return False

    # 2. osrm-partition
    partition_cmd_args = ["osrm-partition", f"./{osrm_base_filename_in_container}"]
    partition_ok = _run_osrm_docker_command_internal(
        command_args=partition_cmd_args,
        region_osrm_data_dir_host=region_osrm_output_dir_host,
        pbf_host_path_for_mount=None, pbf_filename_in_container_mount=None,  # No PBF input here
        logger=logger_to_use,
        step_name="osrm-partition",
        region_name_log=region_name
    )
    if not partition_ok: return False

    # 3. osrm-customize
    customize_cmd_args = ["osrm-customize", f"./{osrm_base_filename_in_container}"]
    customize_ok = _run_osrm_docker_command_internal(
        command_args=customize_cmd_args,
        region_osrm_data_dir_host=region_osrm_output_dir_host,
        pbf_host_path_for_mount=None, pbf_filename_in_container_mount=None,  # No PBF input here
        logger=logger_to_use,
        step_name="osrm-customize",
        region_name_log=region_name
    )
    return customize_ok