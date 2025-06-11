# installer/osrm_installer.py
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
    check_package_installed,
    command_exists,
    log_map_server,
    run_command,
    run_elevated_command,
)
from common.json_utils import JsonFileType, check_json_file
from setup import config as static_config  # For OSM_PROJECT_ROOT
from setup.config_models import AppSettings

module_logger = logging.getLogger(__name__)


def ensure_osrm_dependencies(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Ensures configured container runtime and Osmium (via osmium-tool) are available."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    container_cmd = app_settings.container_runtime_command

    log_map_server(
        f"{symbols.get('info', 'ℹ️')} Checking OSRM dependencies ({container_cmd}, osmium-tool)...",
        "info",
        logger_to_use,
        app_settings,
    )

    if not command_exists(container_cmd):
        log_map_server(
            f"{symbols.get('error', '❌')} Container runtime '{container_cmd}' not found. OSRM processing requires it.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise EnvironmentError(
            f"Container runtime '{container_cmd}' not installed. Please run Docker/Podman installation."
        )
    log_map_server(
        f"{symbols.get('success', '✅')} Container runtime '{container_cmd}' is available.",
        "success",
        logger_to_use,
        app_settings,
    )

    if not check_package_installed(
        "osmium-tool", app_settings=app_settings, current_logger=logger_to_use
    ):
        log_map_server(
            f"{symbols.get('error', '❌')} 'osmium-tool' not installed. Required for PBF extraction.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise EnvironmentError(
            "'osmium-tool' not found. Ensure mapping packages are installed."
        )
    log_map_server(
        f"{symbols.get('success', '✅')} 'osmium-tool' is available.",
        "success",
        logger_to_use,
        app_settings,
    )

    if not command_exists("wget"):
        log_map_server(
            f"{symbols.get('error', '❌')} 'wget' not installed. Required for PBF download.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise EnvironmentError("'wget' not found.")
    log_map_server(
        f"{symbols.get('success', '✅')} 'wget' is available.",
        "success",
        logger_to_use,
        app_settings,
    )


def setup_osrm_data_directories(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Creates base directories for OSRM source data and processed files from app_settings."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    osrm_data_cfg = app_settings.osrm_data

    log_map_server(
        f"{symbols.get('step', '➡️')} Setting up OSRM data directories...",
        "info",
        logger_to_use,
        app_settings,
    )

    osm_data_base_dir = str(osrm_data_cfg.base_dir)
    osm_data_regions_dir = str(Path(osm_data_base_dir) / "regions")
    osrm_base_processed_dir = str(osrm_data_cfg.processed_dir)

    current_uid_str = str(os.getuid())
    current_gid_str = str(os.getgid())

    dirs_to_create = [
        osm_data_base_dir,
        osm_data_regions_dir,
        osrm_base_processed_dir,
    ]
    for dir_path_str in dirs_to_create:
        dir_path = Path(dir_path_str)
        if not dir_path.exists():
            run_elevated_command(
                ["mkdir", "-p", str(dir_path)],
                app_settings,
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{symbols.get('success', '✅')} Created directory: {dir_path}",
                "info",
                logger_to_use,
                app_settings,
            )

        run_elevated_command(
            ["chown", f"{current_uid_str}:{current_gid_str}", str(dir_path)],
            app_settings,
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["chmod", "u+rwx,g+rx,o+rx", str(dir_path)],
            app_settings,
            current_logger=logger_to_use,
        )  # 755 effectively for user focus
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Ensured ownership and permissions for directory: {dir_path}",
            "info",
            logger_to_use,
            app_settings,
        )


def download_base_pbf(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> str:
    """Downloads the base PBF file using URLs and paths from app_settings.osrm_data."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    osrm_data_cfg = app_settings.osrm_data

    pbf_download_url = str(osrm_data_cfg.base_pbf_url)
    pbf_filename = osrm_data_cfg.base_pbf_filename
    pbf_full_path = str(Path(osrm_data_cfg.base_dir) / pbf_filename)

    log_map_server(
        f"{symbols.get('step', '➡️')} Managing base PBF file: {pbf_filename}...",
        "info",
        logger_to_use,
        app_settings,
    )

    if not os.path.isfile(pbf_full_path):
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Downloading {pbf_filename} from {pbf_download_url} to {osrm_data_cfg.base_dir}...",
            "info",
            logger_to_use,
            app_settings,
        )
        run_command(
            ["wget", pbf_download_url, "-O", pbf_full_path],
            app_settings,
            cwd=str(osrm_data_cfg.base_dir),
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Downloaded {pbf_filename}.",
            "success",
            logger_to_use,
            app_settings,
        )
    else:
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Base PBF file {pbf_full_path} already exists. Skipping download.",
            "info",
            logger_to_use,
            app_settings,
        )

    if not os.path.isfile(pbf_full_path):
        raise FileNotFoundError(
            f"Base PBF file {pbf_full_path} not found after download attempt."
        )
    return pbf_full_path


def prepare_region_boundaries(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Copies GeoJSON region boundary files from project assets to OSRM data regions directory."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    osrm_data_cfg = app_settings.osrm_data

    log_map_server(
        f"{symbols.get('step', '➡️')} Preparing region boundary files (GeoJSON)...",
        "info",
        logger_to_use,
        app_settings,
    )

    assets_source_regions_dir = (
        static_config.OSM_PROJECT_ROOT / "assets" / "regions"
    )
    target_osm_data_regions_dir = Path(osrm_data_cfg.base_dir) / "regions"

    if not assets_source_regions_dir.is_dir():
        log_map_server(
            f"{symbols.get('warning', '!')} Local assets regions directory NOT FOUND: {assets_source_regions_dir}. Cannot copy GeoJSONs.",
            "warning",
            logger_to_use,
            app_settings,
        )
        return

    target_osm_data_regions_dir.mkdir(parents=True, exist_ok=True)

    copied_files_count = 0
    malformed_files = []
    current_uid_str = str(os.getuid())
    current_gid_str = str(os.getgid())

    for root, _, files in os.walk(assets_source_regions_dir):
        source_root_path = Path(root)
        relative_path = source_root_path.relative_to(
            assets_source_regions_dir
        )
        target_current_dir = target_osm_data_regions_dir / relative_path

        if not target_current_dir.exists():
            target_current_dir.mkdir(parents=True, exist_ok=True)

        for file_name in files:
            source_file = source_root_path / file_name
            json_status = check_json_file(source_file)

            if json_status == JsonFileType.VALID_JSON:
                target_file = target_current_dir / file_name
                try:
                    shutil.copy2(source_file, target_file)
                    run_elevated_command(
                        [
                            "chown",
                            f"{current_uid_str}:{current_gid_str}",
                            str(target_file),
                        ],
                        app_settings,
                        current_logger=logger_to_use,
                    )
                    run_elevated_command(
                        ["chmod", "644", str(target_file)],  # rw-r--r--
                        app_settings,
                        current_logger=logger_to_use,
                    )

                    log_map_server(
                        f"Copied boundary file: {target_file}",
                        "debug",
                        logger_to_use,
                        app_settings,
                    )
                    copied_files_count += 1
                except Exception as e_copy:
                    log_map_server(
                        f"{symbols.get('error', '❌')} Failed to copy {source_file} to {target_file}: {e_copy}",
                        "error",
                        logger_to_use,
                        app_settings,
                    )
            elif json_status == JsonFileType.MALFORMED_JSON:
                malformed_files.append(source_file)

    if malformed_files:
        log_map_server(
            f"{symbols.get('warning', '!')} {len(malformed_files)} malformed JSON file(s) detected and skipped:",
            "warning",
            logger_to_use,
            app_settings,
        )
        for f in malformed_files:
            log_map_server(f"  - {f}", "warning", logger_to_use, app_settings)

    if copied_files_count > 0:
        log_map_server(
            f"{symbols.get('success', '✅')} {copied_files_count} region boundary file(s) copied to {target_osm_data_regions_dir}",
            "success",
            logger_to_use,
            app_settings,
        )
    else:
        log_map_server(
            f"{symbols.get('warning', '!')} No valid boundary files were copied. Check assets directory.",
            "warning",
            logger_to_use,
            app_settings,
        )
