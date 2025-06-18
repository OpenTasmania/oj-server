# dataproc/osrm_data_processor.py
# -*- coding: utf-8 -*-
"""
Handles OSRM data processing: Osmium extraction and OSRM graph building using container runtime.
"""

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.command_utils import (
    log_map_server,
    run_command,
    run_elevated_command,
)
from installer.config_models import AppSettings

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
    """
    Executes a container-based OSRM (Open Source Routing Machine) command using specified
    arguments and configuration settings. The function provides detailed logging during
    execution and handles potential exceptions. It also supports mounting host directories
    to the container for data processing.

    Args:
        command_args (List[str]): Command line arguments to pass to the container.
        app_settings (AppSettings): Application settings object containing container runtime
            configuration and other settings.
        region_osrm_data_dir_host (str): Host directory path containing OSRM data to be
            mounted into the container.
        pbf_host_path_for_mount (Optional[str]): Host directory path containing PBF data
            to be mounted into the container.
        pbf_filename_in_container_mount (Optional[str]): Filename of the PBF file in the
            container mount directory.
        current_logger (Optional[logging.Logger]): Logger object to be used for logging.
            Defaults to module-level logger if None.
        step_name (str): Name of the process step for logging purposes.
        region_name_log (str): Name of the region being processed, used for logging.

    Returns:
        bool: Returns True if the OSRM container command is executed successfully without errors;
            otherwise, returns False.

    Raises:
        subprocess.CalledProcessError: If the container command execution fails with a
            non-zero exit code.
        Exception: For any other unforeseen runtime exceptions during the command execution.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    container_cmd = app_settings.container_runtime_command
    osrm_image = app_settings.osrm_service.image_tag

    docker_exec_uid = str(os.getuid())
    docker_exec_gid = str(os.getgid())

    container_base_cmd = [
        container_cmd,
        "run",
        "--rm",
        "-u",
        f"{docker_exec_uid}:{docker_exec_gid}",
    ]
    volume_mounts = []

    if pbf_host_path_for_mount and pbf_filename_in_container_mount:
        volume_mounts.extend([
            "-v",
            f"{pbf_host_path_for_mount}:/mnt_readonly_pbf/{pbf_filename_in_container_mount}:ro",
        ])

    volume_mounts.extend([
        "-v",
        f"{region_osrm_data_dir_host}:/data_processing",
    ])

    full_container_cmd = (
        container_base_cmd
        + volume_mounts
        + ["-w", "/data_processing", osrm_image]
        + command_args
    )

    log_map_server(
        f"{symbols.get('info', 'ℹ️')} Running {container_cmd} {step_name} for {region_name_log}...",
        "info",
        logger_to_use,
        app_settings,
    )
    log_map_server(
        f"{symbols.get('debug', '🐛')} {container_cmd} command: {' '.join(full_container_cmd)}",
        "debug",
        logger_to_use,
        app_settings,
    )

    try:
        run_elevated_command(
            full_container_cmd,
            app_settings,
            current_logger=logger_to_use,
            capture_output=True,
            check=True,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} {container_cmd} {step_name} for {region_name_log} completed successfully.",
            "success",
            logger_to_use,
            app_settings,
        )
        return True
    except subprocess.CalledProcessError:
        log_map_server(
            f"{symbols.get('critical', '🔥')} {container_cmd} {step_name} for {region_name_log} FAILED. Check logs.",
            "critical",
            logger_to_use,
            app_settings,
        )
        return False
    except Exception as e:
        log_map_server(
            f"{symbols.get('critical', '🔥')} Exception during {container_cmd} {step_name} for {region_name_log}: {e}",
            "critical",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        return False


def extract_regional_pbfs_with_osmium(
    base_pbf_full_path: str,
    app_settings: AppSettings,
    current_logger: Optional[logging.Logger] = None,
) -> Dict[str, str]:
    """
    Extract regional PBF files using Osmium from a base PBF file and specified GeoJSON boundaries.

    This function processes a given base PBF file and a directory of GeoJSON boundary files
    to create region-specific PBF files using the Osmium tool. It extracts regions defined
    in the GeoJSON boundaries and saves the extracted PBF files in the same directory as
    the corresponding GeoJSON file. The function also logs various stages of the process
    and handles scenarios where the required files or directories are missing.

    Args:
        base_pbf_full_path (str): The filesystem path to the base PBF file to extract regions from.
        app_settings (AppSettings): Application settings object containing configurations
            like symbols and directory paths.
        current_logger (Optional[logging.Logger]): Logger instance to use for logging messages.
            Defaults to a module-level logger.

    Returns:
        Dict[str, str]: A dictionary mapping unique region keys to the filesystem paths
            of the extracted PBF files.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    osrm_data_cfg = app_settings.osrm_data

    geojson_base_dir = Path(osrm_data_cfg.base_dir) / "regions"

    log_map_server(
        f"{symbols.get('step', '➡️')} Extracting regional PBFs using Osmium from base: {base_pbf_full_path}, boundaries in: {geojson_base_dir}",
        "info",
        logger_to_use,
        app_settings,
    )

    extracted_pbf_paths: Dict[str, str] = {}
    geojson_suffix = "RegionMap.json"

    if not Path(base_pbf_full_path).is_file():
        log_map_server(
            f"{symbols.get('error', '❌')} Base PBF file {base_pbf_full_path} not found.",
            "error",
            logger_to_use,
            app_settings,
        )
        return extracted_pbf_paths

    if not geojson_base_dir.is_dir():
        log_map_server(
            f"{symbols.get('warning', '!')} GeoJSON boundary directory {geojson_base_dir} not found.",
            "warning",
            logger_to_use,
            app_settings,
        )
        return extracted_pbf_paths

    for root, _, files in os.walk(geojson_base_dir):
        for geojson_filename in files:
            if geojson_filename.endswith(geojson_suffix):
                geojson_full_path = Path(root) / geojson_filename
                region_base_name_from_file = geojson_filename.removesuffix(
                    geojson_suffix
                )
                relative_path_from_regions_root = (
                    geojson_full_path.parent.relative_to(geojson_base_dir)
                )
                unique_region_key_parts = list(
                    relative_path_from_regions_root.parts
                ) + [region_base_name_from_file]
                unique_region_key = "_".join(
                    filter(None, unique_region_key_parts)
                ).replace(" ", "_")

                output_pbf_filename = f"{unique_region_key}.osm.pbf"
                output_pbf_full_path = (
                    geojson_full_path.parent / output_pbf_filename
                )

                if output_pbf_full_path.is_file():
                    log_map_server(
                        f"{symbols.get('info', 'ℹ️')} Regional PBF {output_pbf_full_path} already exists. Skipping.",
                        "info",
                        logger_to_use,
                        app_settings,
                    )
                    extracted_pbf_paths[unique_region_key] = str(
                        output_pbf_full_path
                    )
                    continue

                osmium_cmd = [
                    "osmium",
                    "extract",
                    "--strategy",
                    "smart",
                    "-p",
                    str(geojson_full_path),
                    str(base_pbf_full_path),
                    "-o",
                    str(output_pbf_full_path),
                    "--overwrite",
                ]
                try:
                    run_command(
                        osmium_cmd,
                        app_settings,
                        check=True,
                        current_logger=logger_to_use,
                    )
                    log_map_server(
                        f"{symbols.get('success', '✅')} Extracted {output_pbf_full_path} for {unique_region_key}.",
                        "success",
                        logger_to_use,
                        app_settings,
                    )
                    extracted_pbf_paths[unique_region_key] = str(
                        output_pbf_full_path
                    )
                except (subprocess.CalledProcessError, Exception) as e:
                    log_map_server(
                        f"{symbols.get('error', '❌')} Osmium extraction failed for {unique_region_key}: {e}",
                        "error",
                        logger_to_use,
                        app_settings,
                        exc_info=True,
                    )

    if not extracted_pbf_paths:
        log_map_server(
            f"{symbols.get('warning', '!')} No regional PBFs extracted by Osmium.",
            "warning",
            logger_to_use,
            app_settings,
        )
    return extracted_pbf_paths


def build_osrm_graphs_for_region(
    region_name_key: str,
    regional_pbf_host_path: str,
    app_settings: AppSettings,
    current_logger: Optional[logging.Logger] = None,
) -> bool:
    """
    Builds OSRM graphs for a specified region based on a regional PBF file.

    This function orchestrates the processing pipeline for generating OSRM routing graphs
    for a given region. The process includes verifying the availability of the regional
    PBF file, executing OSRM processing commands such as `osrm-extract`, `osrm-partition`,
    and `osrm-customize`, and finally storing the processed data in a designated directory.
    Temporary directories are used for intermediate steps, and appropriate permissions
    are managed when files are processed within Docker containers. Results are logged
    throughout the operation, and error handling ensures that any failures are logged
    and the operation is aborted when necessary.

    Args:
        region_name_key (str): Unique identifier for the region to be processed.
        regional_pbf_host_path (str): File path to the regional PBF file used for routing data.
        app_settings (AppSettings): Settings object containing configuration parameters.
        current_logger (Optional[logging.Logger]): Logger to log messages; defaults to a module-specific logger if not provided.

    Returns:
        bool: True if OSRM graph building completed successfully, else False.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    osrm_data_cfg = app_settings.osrm_data

    log_map_server(
        f"{symbols.get('step', '➡️')} Building OSRM graphs for region: {region_name_key} from PBF: {regional_pbf_host_path}",
        "info",
        logger_to_use,
        app_settings,
    )

    if not Path(regional_pbf_host_path).is_file():
        log_map_server(
            f"{symbols.get('error', '❌')} Regional PBF file not found: {regional_pbf_host_path}",
            "error",
            logger_to_use,
            app_settings,
        )
        return False

    final_output_dir = Path(osrm_data_cfg.processed_dir) / region_name_key
    parent_dir = Path(osrm_data_cfg.processed_dir)
    parent_dir.mkdir(exist_ok=True, parents=True)

    with tempfile.TemporaryDirectory(
        prefix=f"{region_name_key}_", dir=parent_dir
    ) as tmp_dir_str:
        tmp_dir_path = Path(tmp_dir_str)
        log_map_server(
            f"Using temporary directory for processing: {tmp_dir_path}",
            "debug",
            logger_to_use,
            app_settings,
        )

        docker_exec_uid = str(os.getuid())
        docker_exec_gid = str(os.getgid())
        try:
            run_elevated_command(
                [
                    "chown",
                    "-R",
                    f"{docker_exec_uid}:{docker_exec_gid}",
                    str(tmp_dir_path),
                ],
                app_settings,
                current_logger=logger_to_use,
                check=True,
            )
        except (subprocess.CalledProcessError, Exception) as e:
            log_map_server(
                f"{symbols.get('critical', '🔥')} Failed to set permissions for temp directory {tmp_dir_path}: {e}",
                "critical",
                logger_to_use,
                app_settings,
            )
            return False

        pbf_filename_on_host = Path(regional_pbf_host_path).name
        osrm_base_filename_in_container = region_name_key
        pbf_readonly_path_in_container = (
            f"/mnt_readonly_pbf/{pbf_filename_on_host}"
        )
        profile_path_in_container = str(
            osrm_data_cfg.profile_script_in_container
        )

        shell_command_for_extract = (
            f'set -e; cp "{pbf_readonly_path_in_container}" "./{pbf_filename_on_host}"; '
            f'osrm-extract -p "{profile_path_in_container}" "./{pbf_filename_on_host}"; '
            f'rm "./{pbf_filename_on_host}";'
        )

        steps: List[Dict[str, Any]] = [
            {
                "name": "osrm-extract",
                "args": ["sh", "-c", shell_command_for_extract],
                "pbf_mount": True,
            },
            {
                "name": "osrm-partition",
                "args": [
                    "osrm-partition",
                    f"./{osrm_base_filename_in_container}.osrm",
                ],
            },
            {
                "name": "osrm-customize",
                "args": [
                    "osrm-customize",
                    f"./{osrm_base_filename_in_container}.osrm",
                ],
            },
        ]

        for step in steps:
            pbf_mount_path = (
                regional_pbf_host_path if step.get("pbf_mount") else None
            )
            pbf_mount_name = (
                pbf_filename_on_host if step.get("pbf_mount") else None
            )

            if not _run_osrm_container_command_internal(
                step["args"],
                app_settings,
                str(tmp_dir_path),
                pbf_mount_path,
                pbf_mount_name,
                logger_to_use,
                step["name"],
                region_name_key,
            ):
                log_map_server(
                    f"Processing failed at step: {step['name']}. Aborting and cleaning up temp dir.",
                    "error",
                    logger_to_use,
                    app_settings,
                )
                return False

        log_map_server(
            f"All OSRM processing steps for {region_name_key} completed successfully.",
            "info",
            logger_to_use,
            app_settings,
        )

        if final_output_dir.exists():
            log_map_server(
                f"Removing existing directory to replace with new data: {final_output_dir}",
                "info",
                logger_to_use,
                app_settings,
            )
            shutil.rmtree(final_output_dir)

        shutil.move(str(tmp_dir_path), final_output_dir)
        log_map_server(
            f"Committed processed data to final directory: {final_output_dir}",
            "success",
            logger_to_use,
            app_settings,
        )

    log_map_server(
        f"{symbols.get('success', '✅')} OSRM graphs built for region: {region_name_key}",
        "success",
        logger_to_use,
        app_settings,
    )
    return True
