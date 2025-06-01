# dataproc/osrm_data_processor.py
# -*- coding: utf-8 -*-
"""
Handles OSRM data processing: Osmium extraction and OSRM graph building using container runtime.
"""
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from common.command_utils import (
    log_map_server,
    run_command,
    run_elevated_command,
)
from setup.config_models import AppSettings

module_logger = logging.getLogger(__name__)


def _run_osrm_container_command_internal(
        command_args: List[str],
        app_settings: AppSettings,
        region_osrm_data_dir_host: str,
        pbf_host_path_for_mount: Optional[str],
        pbf_filename_in_container_mount: Optional[str],
        current_logger: Optional[logging.Logger],
        step_name: str,
        region_name_log: str,
) -> bool:
    """Helper to run OSRM tools via configured container runtime."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    container_cmd = app_settings.container_runtime_command
    osrm_image = app_settings.osrm_service.image_tag

    docker_exec_uid = str(os.getuid())
    docker_exec_gid = str(os.getgid())

    container_base_cmd = [container_cmd, "run", "--rm", "-u", f"{docker_exec_uid}:{docker_exec_gid}"]
    volume_mounts = []

    if pbf_host_path_for_mount and pbf_filename_in_container_mount:
        volume_mounts.extend(
            ["-v", f"{pbf_host_path_for_mount}:/mnt_readonly_pbf/{pbf_filename_in_container_mount}:ro"])

    Path(region_osrm_data_dir_host).mkdir(parents=True, exist_ok=True)
    volume_mounts.extend(["-v", f"{region_osrm_data_dir_host}:/data_processing"])

    full_container_cmd = (
            container_base_cmd + volume_mounts +
            ["-w", "/data_processing", osrm_image] +
            command_args
    )

    log_map_server(f"{symbols.get('info', 'ℹ️')} Running {container_cmd} {step_name} for {region_name_log}...", "info",
                   logger_to_use, app_settings)
    log_map_server(f"{symbols.get('debug', '🐛')} {container_cmd} command: {' '.join(full_container_cmd)}", "debug",
                   logger_to_use, app_settings)

    try:
        run_elevated_command(full_container_cmd, app_settings, current_logger=logger_to_use, capture_output=True,
                             check=True)
        log_map_server(
            f"{symbols.get('success', '✅')} {container_cmd} {step_name} for {region_name_log} completed successfully.",
            "success", logger_to_use, app_settings)
        return True
    except subprocess.CalledProcessError:  # Error logged by run_elevated_command
        log_map_server(
            f"{symbols.get('critical', '🔥')} {container_cmd} {step_name} for {region_name_log} FAILED. Check logs.",
            "critical", logger_to_use, app_settings)
        return False
    except Exception as e:
        log_map_server(
            f"{symbols.get('critical', '🔥')} Exception during {container_cmd} {step_name} for {region_name_log}: {e}",
            "critical", logger_to_use, app_settings, exc_info=True)
        return False


def extract_regional_pbfs_with_osmium(
        base_pbf_full_path: str,
        app_settings: AppSettings,
        current_logger: Optional[logging.Logger] = None
) -> Dict[str, str]:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    osrm_data_cfg = app_settings.osrm_data

    geojson_base_dir = Path(osrm_data_cfg.base_dir) / "regions"

    log_map_server(
        f"{symbols.get('step', '➡️')} Extracting regional PBFs using Osmium from base: {base_pbf_full_path}, boundaries in: {geojson_base_dir}",
        "info", logger_to_use, app_settings)

    extracted_pbf_paths: Dict[str, str] = {}
    geojson_suffix = "RegionMap.json"

    if not Path(base_pbf_full_path).is_file():
        log_map_server(f"{symbols.get('error', '❌')} Base PBF file {base_pbf_full_path} not found.", "error",
                       logger_to_use, app_settings)
        return extracted_pbf_paths

    if not geojson_base_dir.is_dir():
        log_map_server(f"{symbols.get('warning', '!')} GeoJSON boundary directory {geojson_base_dir} not found.",
                       "warning", logger_to_use, app_settings)
        return extracted_pbf_paths

    for root, _, files in os.walk(geojson_base_dir):
        for geojson_filename in files:
            if geojson_filename.endswith(geojson_suffix):
                geojson_full_path = Path(root) / geojson_filename
                region_base_name_from_file = geojson_filename.removesuffix(geojson_suffix)
                relative_path_from_regions_root = geojson_full_path.parent.relative_to(geojson_base_dir)
                unique_region_key_parts = list(relative_path_from_regions_root.parts) + [region_base_name_from_file]
                unique_region_key = "_".join(filter(None, unique_region_key_parts)).replace(" ", "_")

                output_pbf_filename = f"{unique_region_key}.osm.pbf"
                output_pbf_full_path = geojson_full_path.parent / output_pbf_filename

                log_map_server(f"Processing Osmium for region key: {unique_region_key} from {geojson_filename}",
                               "debug", logger_to_use, app_settings)

                if output_pbf_full_path.is_file():
                    log_map_server(
                        f"{symbols.get('info', 'ℹ️')} Regional PBF {output_pbf_full_path} already exists. Skipping.",
                        "info", logger_to_use, app_settings)
                    extracted_pbf_paths[unique_region_key] = str(output_pbf_full_path)
                    continue

                osmium_cmd = ["osmium", "extract", "--strategy", "smart", "-p", str(geojson_full_path),
                              str(base_pbf_full_path), "-o", str(output_pbf_full_path), "--overwrite"]
                try:
                    run_command(osmium_cmd, app_settings, check=True, current_logger=logger_to_use)
                    log_map_server(
                        f"{symbols.get('success', '✅')} Extracted {output_pbf_full_path} for {unique_region_key}.",
                        "success", logger_to_use, app_settings)
                    extracted_pbf_paths[unique_region_key] = str(output_pbf_full_path)
                except subprocess.CalledProcessError as e:
                    log_map_server(f"{symbols.get('error', '❌')} Osmium extraction failed for {unique_region_key}: {e}",
                                   "error", logger_to_use, app_settings)
                except Exception as e:
                    log_map_server(f"{symbols.get('error', '❌')} Unexpected Osmium error for {unique_region_key}: {e}",
                                   "error", logger_to_use, app_settings, exc_info=True)

    if not extracted_pbf_paths:
        log_map_server(f"{symbols.get('warning', '!')} No regional PBFs extracted by Osmium.", "warning", logger_to_use,
                       app_settings)
    return extracted_pbf_paths


def build_osrm_graphs_for_region(
        region_name_key: str,
        regional_pbf_host_path: str,
        app_settings: AppSettings,
        current_logger: Optional[logging.Logger] = None
) -> bool:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    osrm_data_cfg = app_settings.osrm_data

    log_map_server(
        f"{symbols.get('step', '➡️')} Building OSRM graphs for region: {region_name_key} from PBF: {regional_pbf_host_path}",
        "info", logger_to_use, app_settings)

    region_processed_output_dir_host = str(Path(osrm_data_cfg.processed_dir) / region_name_key)
    pbf_filename_on_host = Path(regional_pbf_host_path).name
    osrm_base_filename_in_container = region_name_key
    pbf_path_for_extract_in_container = f"/mnt_readonly_pbf/{pbf_filename_on_host}"

    extract_cmd_args = ["osrm-extract", "-p", str(osrm_data_cfg.profile_script_in_container),
                        pbf_path_for_extract_in_container]
    if not _run_osrm_container_command_internal(
            extract_cmd_args, app_settings, region_processed_output_dir_host,
            regional_pbf_host_path, pbf_filename_on_host,
            logger_to_use, "osrm-extract", region_name_key):
        return False

    # Ensure output of osrm-extract (e.g., pbf_filename_on_host_stem.osrm) is renamed to region_name_key.osrm if different
    # OSRM typically uses the input PBF stem for its output files.
    # If pbf_filename_on_host's stem is not already region_name_key, a rename is needed inside the container or on host.
    # For simplicity, current logic assumes the stem of pbf_filename_on_host matches region_name_key or that
    # osrm-extract output is correctly named region_name_key.osrm (e.g. input was region_name_key.osm.pbf)
    # This might need a robust rename step if input PBF names are arbitrary.
    # Example rename logic (if needed, inside the container or via another docker exec):
    # pbf_stem = Path(pbf_filename_on_host).stem.removesuffix('.osm') # Common pattern
    # if pbf_stem != region_name_key:
    #     rename_cmd = ["mv", f"./{pbf_stem}.osrm", f"./{region_name_key}.osrm"] # Plus all other extensions
    #     _run_osrm_container_command_internal(rename_cmd, ...)

    partition_cmd_args = ["osrm-partition", f"./{osrm_base_filename_in_container}.osrm"]
    if not _run_osrm_container_command_internal(
            partition_cmd_args, app_settings, region_processed_output_dir_host,
            None, None, logger_to_use, "osrm-partition", region_name_key):
        return False

    customize_cmd_args = ["osrm-customize", f"./{osrm_base_filename_in_container}.osrm"]
    if not _run_osrm_container_command_internal(
            customize_cmd_args, app_settings, region_processed_output_dir_host,
            None, None, logger_to_use, "osrm-customize", region_name_key):
        return False

    log_map_server(f"{symbols.get('success', '✅')} OSRM graphs built for region: {region_name_key}", "success",
                   logger_to_use, app_settings)
    return True