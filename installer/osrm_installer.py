# installer/osrm_installer.py
# -*- coding: utf-8 -*-
"""
Handles initial setup for OSRM: dependency checks, directory creation,
PBF download, and region boundary file preparation.
"""

from logging import Logger, getLogger
from os import getgid, getuid, walk
from os.path import isfile
from pathlib import Path
from shutil import copy2
from typing import Optional

from common.command_utils import (
    check_package_installed,
    command_exists,
    log_map_server,
    run_command,
    run_elevated_command,
)
from common.file_utils import ensure_directory_owned_by_current_user
from common.json_utils import JsonFileType, check_json_file
from setup import config as static_config
from setup.config_models import AppSettings

module_logger = getLogger(__name__)


def ensure_osrm_dependencies(
    app_settings: AppSettings, current_logger: Optional[Logger] = None
) -> None:
    """
    Ensures that the necessary dependencies for the OSRM (Open Source Routing
    Machine) are available and functional in the environment. This includes
    verifying the availability of a container runtime, the 'osmium-tool' package,
    and the 'wget' command. If any dependency is missing or non-functional, the
    appropriate error is logged and an exception is raised.

    Parameters:
        app_settings (AppSettings): An object containing configuration settings
            for the application, including OSRM-related configurations.
        current_logger (Optional[Logger]): Optional custom logger to use for
            logging. If not provided, a module-level logger is used.

    Raises:
        EnvironmentError: Raised if any of the required dependencies (container
            runtime, 'osmium-tool', 'wget') is not available or non-functional.
    """
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
    app_settings: AppSettings, current_logger: Optional[Logger] = None
) -> None:
    """
    Sets up the required OSRM data directories and ensures appropriate permissions.

    The function creates specified directories if they do not exist, sets their
    ownership to the current user, and grants necessary permissions, ensuring that
    they are ready for use by OSRM processes. This setup process includes logging
    of actions performed during the creation and configuration steps.

    Arguments:
        app_settings (AppSettings): The application settings containing configuration details
            including paths for OSRM data and logging symbols.
        current_logger (Optional[Logger]): An optional logger instance to log the directory
            setup process. Defaults to the module-level logger if not provided.

    Returns:
        None
    """
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

    current_uid_str = str(getuid())
    current_gid_str = str(getgid())

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
    app_settings: AppSettings, current_logger: Optional[Logger] = None
) -> str:
    """
    Downloads the base PBF (Protocolbuffer Binary Format) file required for map data
    processing if it does not already exist in the specified directory, ensuring the
    directory's ownership is properly managed. The function utilizes configurations
    from the provided application settings and logging mechanisms.

    If the file is absent, it attempts a download using the provided URL, places the
    file in the target directory, and verifies its presence post-download.

    Arguments:
        app_settings (AppSettings): The application settings containing configuration
            for OSRM data, symbols, and other related settings.
        current_logger (Optional[Logger]): Optional logger instance for capturing log
            messages. Defaults to the module-level logger if not provided.

    Returns:
        str: Full path to the base PBF file.

    Raises:
        FileNotFoundError: Raised if the base PBF file is not found after a download
            attempt.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    osrm_data_cfg = app_settings.osrm_data

    pbf_download_url = str(osrm_data_cfg.base_pbf_url)
    pbf_filename = osrm_data_cfg.base_pbf_filename
    base_dir_path = Path(osrm_data_cfg.base_dir)
    pbf_full_path = str(base_dir_path / pbf_filename)

    ensure_directory_owned_by_current_user(
        dir_path=base_dir_path,
        make_directory=True,
        world_access=False,
        app_settings=app_settings,
        current_logger=logger_to_use,
    )

    log_map_server(
        f"{symbols.get('step', '➡️')} Managing base PBF file: {pbf_filename}...",
        "info",
        logger_to_use,
        app_settings,
    )

    if not isfile(pbf_full_path):
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Downloading {pbf_filename} from {pbf_download_url} to {base_dir_path}...",
            "info",
            logger_to_use,
            app_settings,
        )
        # This command runs as the current user, who now owns the directory
        run_command(
            ["wget", pbf_download_url, "-O", pbf_full_path],
            app_settings,
            cwd=str(base_dir_path),
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

    if not isfile(pbf_full_path):
        raise FileNotFoundError(
            f"Base PBF file {pbf_full_path} not found after download attempt."
        )
    return pbf_full_path


def prepare_region_boundaries(
    app_settings: AppSettings, current_logger: Optional[Logger] = None
) -> None:
    """
    Prepare region boundary files by copying GeoJSON files from a source directory to a
    target directory, validating JSON files, and setting their file permissions.

    This function processes all GeoJSON files located in the specified "assets/regions"
    directory. It validates their formatting, copies valid files to the target directory,
    applies proper permissions, and logs the results. If the source directory does not
    exist or if files are malformed, appropriate warnings are logged.

    This function relies on external commands for file permissions management and assumes
    specific user/group ownership for the copied files. The function is designed to be
    resilient by handling errors during file operations, and malformed files are
    skipped without halting the overall process. It provides detailed logging at each
    step, including informational, debug, warning, and error messages.

    Parameters:
        app_settings (AppSettings): Application-specific settings containing
            configurations such as symbol mappings and directory paths.
        current_logger (Optional[Logger]): Logger to use for logging information.
            If not provided, a default module logger will be used.

    Returns:
        None
    """
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
    current_uid_str = str(getuid())
    current_gid_str = str(getgid())

    for root, _, files in walk(assets_source_regions_dir):
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
                    copy2(source_file, target_file)
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
