# setup/services/osrm.py
# -*- coding: utf-8 -*-
"""
Handles setup of OSM data import via osm2pgsql and OSRM routing engine.

This module automates the download of OpenStreetMap (OSM) PBF data,
extraction of regional data using Osmium, import into PostGIS using osm2pgsql
(Flex backend), and processing with OSRM (Open Source Routing Machine) via
Docker for generating routing graphs.
"""

import datetime
import logging
import os
import subprocess
import traceback
from typing import Dict, List, Optional

from setup import config
from configure.command_utils import log_map_server, run_elevated_command

module_logger = logging.getLogger(__name__)

# --- Constants ---
OSM_DATA_BASE_DIR = "/opt/osm_data"
OSM_DATA_REGIONS_DIR = os.path.join(OSM_DATA_BASE_DIR, "regions")
# Host directory for OSRM processed files.
OSRM_BASE_PROCESSED_DIR = "/opt/osrm_processed_data"

AUSTRALIA_PBF_FILENAME = "australia-latest.osm.pbf"
GEOFABRIK_AUSTRALIA_PBF_URL = (
    f"https://download.geofabrik.de/australia-oceania/"
    f"{AUSTRALIA_PBF_FILENAME}"
)
OSM_CARTO_DIR = "/opt/openstreetmap-carto"  # Used for osm2pgsql style

# OSRM Docker processing constants
OSRM_DOCKER_IMAGE = "osrm/osrm-backend:latest"  # Or a specific version
# Default car profile Lua script path within the OSRM container.
OSRM_PROFILE_LUA_IN_CONTAINER = "/opt/car.lua"

DEFAULT_DB_CONFIG: Dict[str, str] = {
    "host": "localhost",
    "port": "5432",
    "dbname": "gis",
    "user": "osmuser",
    "password": "yourStrongPasswordHere",  # Should be overridden by config
}


def _ensure_directory_exists(
    path: str,
    logger: logging.Logger,
    uid: Optional[str] = None,
    gid: Optional[str] = None,
) -> None:
    """
    Ensure a directory exists, creating it if necessary.

    Uses elevated privileges for creation and optionally sets ownership.

    Args:
        path: The absolute path to the directory.
        logger: The logger instance to use for messages.
        uid: Optional user ID for chown.
        gid: Optional group ID for chown.
    """
    if not os.path.exists(path):
        log_map_server(
            f"{config.SYMBOLS['gear']} Creating directory: {path}",
            "info",
            logger,
        )
        run_elevated_command(["mkdir", "-p", path], current_logger=logger)
        if uid and gid:
            run_elevated_command(
                ["chown", f"{uid}:{gid}", path], current_logger=logger
            )
            # Ensure user has rwx for the created directory.
            run_elevated_command(
                ["chmod", "u+rwx", path], current_logger=logger
            )
    elif uid and gid:
        # If directory exists, still ensure ownership and permissions.
        # For simplicity, re-apply. More advanced checks could be added.
        log_map_server(
            f"{config.SYMBOLS['gear']} Ensuring ownership "
            f"({uid}:{gid}) and permissions for existing directory: {path}",
            "debug",
            logger,  # More of a debug log if it already exists
        )
        run_elevated_command(
            ["chown", f"{uid}:{gid}", path], current_logger=logger
        )
        run_elevated_command(["chmod", "u+rwx", path], current_logger=logger)


def _setup_asset_directories(
    base_script_dir: str, logger: logging.Logger
) -> str:
    """
    Set up local asset directories for storing region GeoJSON files.

    Args:
        base_script_dir: The base directory of the setup script, used to
                         locate the 'assets/regions' subdirectory.
        logger: The logger instance.

    Returns:
        The absolute path to the 'assets/regions' directory.
    """
    log_map_server(
        f"{config.SYMBOLS['debug']} Calculating asset directories.",
        "debug",
        logger,  # Changed to debug as it's an internal step
    )
    assets_regions_dir = os.path.join(base_script_dir, "assets", "regions")
    australia_dir = os.path.join(assets_regions_dir, "Australia")
    tasmania_dir = os.path.join(australia_dir, "Tasmania")

    # These directories are local to the script execution,
    # so _ensure_directory_exists with sudo isn't strictly needed
    # unless script itself is run in a restricted environment.
    # Assuming they are part of the deployment package.
    for dir_path in [assets_regions_dir, australia_dir, tasmania_dir]:
        if not os.path.isdir(dir_path):
            logger.warning(
                f"Local asset directory not found: {dir_path}. "
                "GeoJSON files might be missing."
            )
            # Depending on requirements, could create them: os.makedirs(dir_path, exist_ok=True)
    return assets_regions_dir


def _copy_geojson_files(
    assets_regions_dir: str,
    target_osm_data_regions_dir: str,
    uid: str,
    gid: str,
    logger: logging.Logger,
) -> None:
    """
    Copy GeoJSON region boundary files from local assets to the OSM data directory.

    Args:
        assets_regions_dir: Source directory containing GeoJSON files.
        target_osm_data_regions_dir: Destination directory for GeoJSON files.
        uid: User ID for setting ownership of copied files.
        gid: Group ID for setting ownership of copied files.
        logger: The logger instance.
    """
    if not os.path.exists(assets_regions_dir):
        log_map_server(
            f"{config.SYMBOLS['warning']} Local assets_regions_dir NOT FOUND: "
            f"{assets_regions_dir}. Cannot copy GeoJSON files.",
            "warning",
            logger,
        )
        return

    log_map_server(
        f"{config.SYMBOLS['info']} Copying region GeoJSON files from "
        f"{assets_regions_dir} to {target_osm_data_regions_dir}...",
        "info",
        logger,
    )
    for root, dirs, files in os.walk(assets_regions_dir):
        # Create corresponding subdirectories in the target.
        for dir_name in dirs:
            source_dir_path = os.path.join(root, dir_name)
            rel_path_dir = os.path.relpath(
                source_dir_path, assets_regions_dir
            )
            target_subdir = os.path.join(
                target_osm_data_regions_dir, rel_path_dir
            )
            _ensure_directory_exists(target_subdir, logger, uid, gid)

        # Copy .json files.
        for file_name in files:
            if file_name.endswith(".json"):
                source_file = os.path.join(root, file_name)
                rel_path_file = os.path.relpath(
                    source_file, assets_regions_dir
                )
                target_file = os.path.join(
                    target_osm_data_regions_dir, rel_path_file
                )
                target_file_parent_dir = os.path.dirname(target_file)
                # Ensure parent directory exists in target (redundant if dirs loop worked, but safe)
                _ensure_directory_exists(
                    target_file_parent_dir, logger, uid, gid
                )

                run_elevated_command(
                    ["cp", source_file, target_file], current_logger=logger
                )
                run_elevated_command(
                    ["chown", f"{uid}:{gid}", target_file],
                    current_logger=logger,
                )
    log_map_server(
        f"{config.SYMBOLS['success']} Region GeoJSON files copied to "
        f"{target_osm_data_regions_dir}",
        "success",
        logger,
    )


def _download_osm_pbf(
    pbf_full_path: str, download_url: str, logger: logging.Logger
) -> None:
    """
    Download an OSM PBF file if it doesn't already exist.

    Args:
        pbf_full_path: The full local path to save the PBF file.
        download_url: The URL to download the PBF file from.
        logger: The logger instance.

    Raises:
        FileNotFoundError: If the download fails and the PBF file is not found.
    """
    if not os.path.isfile(pbf_full_path):
        log_map_server(
            f"{config.SYMBOLS['info']} Downloading "
            f"{os.path.basename(pbf_full_path)} from Geofabrik to "
            f"{os.path.dirname(pbf_full_path)}...",
            "info",
            logger,
        )
        run_elevated_command(  # wget might need sudo if path is restricted
            ["wget", download_url, "-O", pbf_full_path], current_logger=logger
        )
    else:
        log_map_server(
            f"{config.SYMBOLS['info']} OSM PBF file {pbf_full_path} "
            "already exists. Skipping download.",
            "info",
            logger,
        )

    if not os.path.isfile(pbf_full_path):
        error_message = (
            f"Failed to download {pbf_full_path}. OSRM/OSM setup "
            "cannot continue."
        )
        log_map_server(
            f"{config.SYMBOLS['critical']} {error_message}",
            "critical",
            logger,
        )
        raise FileNotFoundError(error_message)


def _extract_region_with_osmium(
    region_name_log: str,
    geojson_boundary_file_path: str,
    source_pbf_path: str,
    output_pbf_path: str,
    uid: str,
    gid: str,
    logger: logging.Logger,
) -> Optional[str]:
    """
    Extract a specific region from a larger PBF file using Osmium.

    Args:
        region_name_log: A human-readable name for the region (for logging).
        geojson_boundary_file_path: Path to the GeoJSON file defining the
                                    region's boundary.
        source_pbf_path: Path to the source (larger) PBF file.
        output_pbf_path: Path where the extracted regional PBF will be saved.
        uid: User ID for setting ownership of the output PBF.
        gid: Group ID for setting ownership of the output PBF.
        logger: The logger instance.

    Returns:
        The path to the extracted PBF file if successful, None otherwise.
    """
    log_map_server(
        f"{config.SYMBOLS['info']} Preparing to extract {region_name_log} "
        f"region using {os.path.basename(geojson_boundary_file_path)}.",
        "info",
        logger,
    )
    if os.path.isfile(output_pbf_path):
        log_map_server(
            f"{config.SYMBOLS['info']} Regional PBF {output_pbf_path} for "
            f"{region_name_log} already exists. Skipping extraction.",
            "info",
            logger,
        )
        return output_pbf_path

    if not os.path.isfile(geojson_boundary_file_path):
        log_map_server(
            f"{config.SYMBOLS['warning']} Boundary file "
            f"{geojson_boundary_file_path} not found for {region_name_log}. "
            "Cannot extract.",
            "warning",
            logger,
        )
        return None

    log_map_server(
        f"{config.SYMBOLS['info']} Extracting {region_name_log} from "
        f"{os.path.basename(source_pbf_path)} to {output_pbf_path}...",
        "info",
        logger,
    )
    # Osmium command for extraction.
    # --strategy smart: Balances speed and completeness.
    # -p: Path to polygon file (GeoJSON).
    # -o: Output file path.
    # --overwrite: Overwrite output file if it exists (though we check first).
    command = [
        "osmium",
        "extract",
        "--strategy",
        "smart",
        "-p",
        geojson_boundary_file_path,
        source_pbf_path,
        "-o",
        output_pbf_path,
        "--overwrite",
    ]
    try:
        # Osmium is typically run as the current user if it has read/write perms.
        # If source/target paths require elevation, run_elevated_command
        # would be needed, but that complicates UID/GID for output.
        # Assuming Osmium is in PATH and script has perms for OSM_DATA_REGIONS_DIR.
        result = subprocess.run(
            command, capture_output=True, text=True, check=False
        )
        if result.stdout:
            logger.debug(
                f"Osmium stdout for {region_name_log}:\n{result.stdout}"
            )
        if result.stderr:  # Osmium can be verbose on stderr for progress.
            log_level = "error" if result.returncode != 0 else "debug"
            logger.log(
                getattr(logging, log_level.upper()),
                f"Osmium stderr for {region_name_log}:\n{result.stderr}",
            )

        if result.returncode == 0 and os.path.isfile(output_pbf_path):
            log_map_server(
                f"{config.SYMBOLS['success']} Successfully extracted "
                f"{output_pbf_path} for {region_name_log}.",
                "success",
                logger,
            )
            # Set ownership for the newly created PBF file.
            run_elevated_command(
                ["chown", f"{uid}:{gid}", output_pbf_path],
                current_logger=logger,
            )
            return output_pbf_path
        else:
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to extract "
                f"{output_pbf_path} for {region_name_log} (Osmium RC: "
                f"{result.returncode}). File not found or error during osmium run.",
                "error",
                logger,
            )
            return None
    except Exception as e_osmium:
        log_map_server(
            f"{config.SYMBOLS['critical']} ERROR during osmium extraction for "
            f"{region_name_log}: {e_osmium}",
            "critical",
            logger,
        )
        return None


def _import_pbf_to_postgis_flex(
    pbf_file_path: str,
    db_config_dict: Dict[str, str],  # Renamed for clarity
    osm_carto_style_dir: str,
    flat_nodes_storage_dir: str,
    logger: logging.Logger,
    osm2pgsql_cache_mb: Optional[int] = None,
) -> bool:
    """
    Import a PBF file into PostGIS using osm2pgsql with the Flex backend.

    Args:
        pbf_file_path: Path to the PBF file to import.
        db_config_dict: Dictionary with database connection parameters
                        (host, port, dbname, user, password).
        osm_carto_style_dir: Directory of the OpenStreetMap Carto style,
                             containing the Lua script.
        flat_nodes_storage_dir: Directory to store flat nodes file.
        logger: The logger instance.
        osm2pgsql_cache_mb: Optional cache size in MB for osm2pgsql.
                            Defaults to environment variable or 20000MB.

    Returns:
        True if the import was successful, False otherwise.
    """
    region_name = os.path.basename(pbf_file_path).replace(".osm.pbf", "")
    log_map_server(
        f"{config.SYMBOLS['info']} Starting PostGIS import for {region_name} "
        "using osm2pgsql (Flex backend)...",
        "info",
        logger,
    )

    # Locate the Lua transformation script for osm2pgsql Flex backend.
    lua_candidates = [
        os.path.join(osm_carto_style_dir, "openstreetmap-carto-flex.lua"),
        os.path.join(
            osm_carto_style_dir, "openstreetmap-carto.lua"
        ),  # Fallback
    ]
    lua_script_found = next(
        (
            candidate
            for candidate in lua_candidates
            if os.path.isfile(candidate)
        ),
        None,
    )
    if not lua_script_found:
        log_map_server(
            f"{config.SYMBOLS['critical']} OSM-Carto Lua script (flex output) "
            f"not found in {osm_carto_style_dir}. Searched: {lua_candidates}.",
            "critical",
            logger,
        )
        return False
    log_map_server(
        f"{config.SYMBOLS['debug']} Found OSM-Carto Lua script: "
        f"{lua_script_found}",
        "debug",
        logger,
    )

    num_processes = os.cpu_count() or 1  # Default to 1 if cpu_count is None
    # Determine cache size for osm2pgsql.
    default_cache_str = "20000"  # Default 20GB
    cache_size_to_use = osm2pgsql_cache_mb
    if cache_size_to_use is None:
        try:
            cache_size_to_use = int(
                os.environ.get("OSM2PGSQL_CACHE_DEFAULT", default_cache_str)
            )
        except ValueError:
            log_map_server(
                f"{config.SYMBOLS['warning']} Invalid OSM2PGSQL_CACHE_DEFAULT "
                f"env var. Using default: {default_cache_str}MB.",
                "warning",
                logger,
            )
            cache_size_to_use = int(default_cache_str)

    _ensure_directory_exists(flat_nodes_storage_dir, logger)
    flat_nodes_file = os.path.join(
        flat_nodes_storage_dir,
        f"flat-nodes-{region_name}-{datetime.date.today().isoformat()}.bin",
    )

    # Construct osm2pgsql command.
    # This typically runs as postgres user or a user with DB creation rights.
    # PGPASSWORD environment variable is used for authentication.
    command = [
        "osm2pgsql",
        "--verbose",
        "--create",
        "--database",
        db_config_dict["dbname"],
        "--username",
        db_config_dict["user"],
        "--host",
        db_config_dict["host"],
        "--port",
        str(db_config_dict["port"]),
        "--slim",
        "--hstore",
        "--multi-geometry",
        "--tag-transform-script",
        lua_script_found,
        "--style",
        lua_script_found,  # Style and transform can be same for flex
        "--output=flex",
        "-C",
        str(cache_size_to_use),
        "--number-processes",
        str(num_processes),
        "--flat-nodes",
        flat_nodes_file,
        pbf_file_path,
    ]
    log_map_server(
        f"{config.SYMBOLS['debug']} osm2pgsql command: {' '.join(command)}",
        "debug",
        logger,
    )

    process_env = os.environ.copy()
    if "password" in db_config_dict and db_config_dict["password"]:
        process_env["PGPASSWORD"] = db_config_dict["password"]

    try:
        # osm2pgsql can take a long time; direct subprocess call.
        # It's usually run by a user who can write to the DB (e.g., postgres).
        # If the script user is 'postgres', sudo might not be needed.
        # Assuming this script might be run by a non-postgres user who uses
        # sudo for `psql` earlier, but osm2pgsql might be different.
        # For now, assume it runs as current user with PGPASSWORD set.
        completed_process = subprocess.run(
            command,
            env=process_env,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed_process.stdout:
            logger.debug(
                f"osm2pgsql STDOUT for {region_name}:\n{completed_process.stdout}"
            )
        if (
            completed_process.stderr
        ):  # osm2pgsql often uses stderr for progress.
            log_level_stderr = (
                "error" if completed_process.returncode != 0 else "debug"
            )
            logger.log(
                getattr(logging, log_level_stderr.upper()),
                f"osm2pgsql STDERR for {region_name}:\n{completed_process.stderr}",
            )

        if completed_process.returncode == 0:
            log_map_server(
                f"{config.SYMBOLS['success']} osm2pgsql import for {region_name} "
                "completed successfully.",
                "success",
                logger,
            )
            return True
        else:
            log_map_server(
                f"{config.SYMBOLS['critical']} ERROR: osm2pgsql import for "
                f"{region_name} failed (RC: {completed_process.returncode}).",
                "critical",
                logger,
            )
            return False
    except FileNotFoundError:
        log_map_server(
            f"{config.SYMBOLS['critical']} osm2pgsql command not found. "
            "Is it installed and in PATH?",
            "critical",
            logger,
        )
        return False
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['critical']} Unexpected error during osm2pgsql "
            f"for {region_name}: {e}",
            "critical",
            logger,
        )
        return False


def _run_osrm_docker_command(
    command_args: List[str],
    region_osrm_data_dir: str,  # Host path where OSRM will write processed files
    pbf_host_path: Optional[str],  # Host path to the input PBF
    pbf_filename_in_container: Optional[
        str
    ],  # Name of PBF inside /mnt_readonly_pbf
    uid: str,
    gid: str,
    docker_image: str,
    logger: logging.Logger,
    step_name: str,  # e.g., "osrm-extract"
    region_name: str,  # For logging
) -> bool:
    """
    Helper to run OSRM Docker commands for processing steps.

    Args:
        command_args: List of arguments for the OSRM tool inside Docker.
        region_osrm_data_dir: Host directory mapped to /data_processing in
                              the container, for OSRM outputs.
        pbf_host_path: Optional host path to the input PBF file.
        pbf_filename_in_container: Optional name for the PBF file when mounted
                                   read-only inside the container.
        uid: User ID to run Docker commands as (for file permissions).
        gid: Group ID to run Docker commands as.
        docker_image: The OSRM Docker image to use.
        logger: The logger instance.
        step_name: Name of the OSRM step (e.g., "osrm-extract") for logging.
        region_name: Name of the region being processed (for logging).

    Returns:
        True if the Docker command executed successfully, False otherwise.
    """
    # Docker base command. run_elevated_command handles sudo if needed.
    # -u {uid}:{gid} ensures files created in mapped volumes have correct ownership.
    docker_base_cmd = ["docker", "run", "--rm", "-u", f"{uid}:{gid}"]
    volume_mounts = []

    if pbf_host_path and pbf_filename_in_container:
        # Mount the input PBF read-only.
        volume_mounts.extend([
            "-v",
            f"{pbf_host_path}:/mnt_readonly_pbf/{pbf_filename_in_container}:ro",
        ])

    # Mount the processing directory read-write.
    # OSRM tools will write their output here.
    volume_mounts.extend(["-v", f"{region_osrm_data_dir}:/data_processing"])

    # Full Docker command: docker run --rm -u ... -v ... -v ... -w ... image cmd ...
    full_docker_cmd = (
        docker_base_cmd
        + volume_mounts
        + [
            "-w",
            "/data_processing",
            docker_image,
        ]  # Set working dir in container
        + command_args
    )

    log_map_server(
        f"{config.SYMBOLS['info']} Running Docker {step_name} for {region_name}...",
        "info",
        logger,
    )
    log_map_server(
        f"{config.SYMBOLS['debug']} Docker command for {step_name}: "
        f"{' '.join(full_docker_cmd)}",
        "debug",
        logger,
    )

    try:
        # run_elevated_command is expected to prepend sudo if necessary.
        result = run_elevated_command(
            full_docker_cmd, current_logger=logger, capture_output=True
        )

        if not (result and hasattr(result, "returncode")):
            log_map_server(
                f"{config.SYMBOLS['critical']} Docker {step_name} for "
                f"{region_name} did not return a valid result object from "
                "run_elevated_command.",
                "critical",
                logger,
            )
            return False

        if result.stdout:  # OSRM tools often use stdout for progress/info.
            logger.debug(
                f"Docker {step_name} STDOUT for {region_name}:\n{result.stdout}"
            )
        if (
            result.stderr
        ):  # OSRM tools often use stderr for progress and errors.
            log_level_stderr = "error" if result.returncode != 0 else "debug"
            logger.log(
                getattr(logging, log_level_stderr.upper()),
                f"Docker {step_name} STDERR for {region_name}:\n{result.stderr}",
            )

        if result.returncode == 0:
            log_map_server(
                f"{config.SYMBOLS['success']} Docker {step_name} for "
                f"{region_name} completed successfully.",
                "success",
                logger,
            )
            return True
        else:
            log_map_server(
                f"{config.SYMBOLS['critical']} Docker {step_name} for "
                f"{region_name} FAILED with exit code {result.returncode}.",
                "critical",
                logger,
            )
            log_map_server(
                "Review STDERR output above for details from the OSRM tool.",
                "info",
                logger,
            )
            return False
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['critical']} Exception during Docker {step_name} "
            f"for {region_name}: {e}",
            "critical",
            logger,
        )
        logger.error(
            traceback.format_exc()
        )  # Log full traceback for exceptions
        return False


def _run_osrm_extract_docker(
    pbf_host_path: str,  # Full path to PBF on host
    region_osrm_data_dir: str,  # Host dir for OSRM processed files for this region
    data_label_for_outputs: str,  # Basename for output files (e.g., "TasmaniaRegionMap")
    uid: str,
    gid: str,
    docker_image: str,
    profile_in_container: str,  # Path to LUA profile in container
    logger: logging.Logger,
) -> bool:
    """
    Run the osrm-extract step using Docker.

    Args:
        pbf_host_path: Absolute path to the input .osm.pbf file on the host.
        region_osrm_data_dir: Host directory where OSRM processed files for this
                              region will be stored.
        data_label_for_outputs: Basename used for OSRM output files
                                (e.g., "TasmaniaRegionMap" for
                                TasmaniaRegionMap.osrm).
        uid: User ID for Docker execution.
        gid: Group ID for Docker execution.
        docker_image: OSRM Docker image name.
        profile_in_container: Path to the LUA profile script inside the container.
        logger: Logger instance.

    Returns:
        True if extraction was successful, False otherwise.
    """
    pbf_filename_on_host = os.path.basename(pbf_host_path)
    # Internal name for PBF inside container's /data_processing, ensures consistent naming for osrm-extract
    internal_pbf_copy_name = f"{data_label_for_outputs}.osm.pbf"

    # Shell command executed inside the container:
    # 1. Copy the read-only mounted PBF to the writable /data_processing directory.
    # 2. Run osrm-extract on this internal copy.
    # 3. Remove the internal copy after processing.
    # Outputs (e.g., data_label_for_outputs.osrm) are created in /data_processing.
    shell_command_inside_container = (
        f'cp "/mnt_readonly_pbf/{pbf_filename_on_host}" "./{internal_pbf_copy_name}" && '
        f'osrm-extract -p "{profile_in_container}" "./{internal_pbf_copy_name}" && '
        f'rm "./{internal_pbf_copy_name}"'
    )
    docker_command_args = ["sh", "-c", shell_command_inside_container]

    return _run_osrm_docker_command(
        command_args=docker_command_args,
        region_osrm_data_dir=region_osrm_data_dir,
        pbf_host_path=pbf_host_path,  # Mount original PBF read-only
        pbf_filename_in_container=pbf_filename_on_host,  # Name it as on host in mount
        uid=uid,
        gid=gid,
        docker_image=docker_image,
        logger=logger,
        step_name="osrm-extract",
        region_name=data_label_for_outputs,
    )


def _run_osrm_partition_docker(
    region_osrm_data_dir: str,
    data_label: str,  # Basename of the .osrm file (e.g., "TasmaniaRegionMap")
    uid: str,
    gid: str,
    docker_image: str,
    logger: logging.Logger,
) -> bool:
    """Run the osrm-partition step using Docker."""
    osrm_base_file_in_container = (
        f"./{data_label}.osrm"  # Relative to /data_processing
    )
    docker_command_args = ["osrm-partition", osrm_base_file_in_container]
    return _run_osrm_docker_command(
        command_args=docker_command_args,
        region_osrm_data_dir=region_osrm_data_dir,
        pbf_host_path=None,  # No PBF input for this step
        pbf_filename_in_container=None,
        uid=uid,
        gid=gid,
        docker_image=docker_image,
        logger=logger,
        step_name="osrm-partition",
        region_name=data_label,
    )


def _run_osrm_customize_docker(
    region_osrm_data_dir: str,
    data_label: str,  # Basename of the .osrm file
    uid: str,
    gid: str,
    docker_image: str,
    logger: logging.Logger,
) -> bool:
    """Run the osrm-customize step using Docker."""
    osrm_base_file_in_container = (
        f"./{data_label}.osrm"  # Relative to /data_processing
    )
    docker_command_args = ["osrm-customize", osrm_base_file_in_container]
    return _run_osrm_docker_command(
        command_args=docker_command_args,
        region_osrm_data_dir=region_osrm_data_dir,
        pbf_host_path=None,  # No PBF input for this step
        pbf_filename_in_container=None,
        uid=uid,
        gid=gid,
        docker_image=docker_image,
        logger=logger,
        step_name="osrm-customize",
        region_name=data_label,
    )


def osm_osrm_server_setup(
    current_logger: Optional[logging.Logger] = None,
    db_connection_info: Optional[Dict[str, str]] = None,
) -> None:
    """
    Main function to set up OSM data import, PostGIS, and OSRM processing.

    Args:
        current_logger: Optional logger instance.
        db_connection_info: Optional dictionary with database connection parameters.
                            Defaults to DEFAULT_DB_CONFIG if None.

    Raises:
        FileNotFoundError: If essential files (like downloaded PBF) are missing.
        Exception: For critical failures in subprocesses or Docker commands.
    """
    logger_to_use = current_logger or module_logger
    # Use provided DB connection info or fall back to defaults from config.py
    # (which themselves might be updated by CLI args).
    effective_db_config = (
        db_connection_info
        if db_connection_info
        else {
            "host": config.PGHOST,
            "port": config.PGPORT,
            "dbname": config.PGDATABASE,
            "user": config.PGUSER,
            "password": config.PGPASSWORD,
        }
    )

    log_map_server(
        f"{config.SYMBOLS['step']} Setting up OSM data, OSRM, and PostGIS...",
        "info",
        logger_to_use,
    )

    current_uid = str(os.getuid())
    current_gid = str(os.getgid())

    # Ensure base directories exist with correct ownership.
    _ensure_directory_exists(
        OSM_DATA_BASE_DIR, logger_to_use, current_uid, current_gid
    )
    _ensure_directory_exists(
        OSM_DATA_REGIONS_DIR, logger_to_use, current_uid, current_gid
    )
    _ensure_directory_exists(
        OSRM_BASE_PROCESSED_DIR, logger_to_use, current_uid, current_gid
    )
    # Directory for osm2pgsql flat nodes files.
    flat_nodes_dir_for_postgis = OSM_DATA_BASE_DIR
    _ensure_directory_exists(
        flat_nodes_dir_for_postgis, logger_to_use, current_uid, current_gid
    )

    try:
        # Determine project script directory to find assets.
        script_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )  # Assumes this file is in setup/services/
        assets_regions_dir = _setup_asset_directories(
            script_dir, logger_to_use
        )
    except Exception as e_setup_paths:
        log_map_server(
            f"{config.SYMBOLS['critical']} ERROR during path setup for assets: "
            f"{e_setup_paths}",
            "critical",
            logger_to_use,
        )
        raise

    _copy_geojson_files(
        assets_regions_dir,
        OSM_DATA_REGIONS_DIR,
        current_uid,
        current_gid,
        logger_to_use,
    )

    # Download the main Australia PBF file.
    australia_pbf_fullpath = os.path.join(
        OSM_DATA_BASE_DIR, AUSTRALIA_PBF_FILENAME
    )
    _download_osm_pbf(
        australia_pbf_fullpath, GEOFABRIK_AUSTRALIA_PBF_URL, logger_to_use
    )

    # Discover and extract regional PBFs using Osmium.
    extracted_pbf_paths: Dict[
        str, str
    ] = {}  # {region_base_name: full_pbf_path}
    log_map_server(
        f"{config.SYMBOLS['step']} Discovering and extracting regional PBFs "
        "(using Osmium)...",
        "info",
        logger_to_use,
    )
    # Suffix for GeoJSON files defining regions (e.g., TasmaniaRegionMap.json)
    geojson_suffix_to_identify_regions = "RegionMap.json"
    for root, _, files in os.walk(OSM_DATA_REGIONS_DIR):
        for geojson_filename in files:
            if geojson_filename.endswith(geojson_suffix_to_identify_regions):
                geojson_full_path = os.path.join(root, geojson_filename)
                # region_base_name will be e.g., "Tasmania"
                region_base_name = geojson_filename.removesuffix(
                    geojson_suffix_to_identify_regions
                )
                if not region_base_name:
                    log_map_server(
                        f"{config.SYMBOLS['warning']} Invalid region name from "
                        f"{geojson_filename}. Skipping.",
                        "warning",
                        logger_to_use,
                    )
                    continue

                # PBF filename will be e.g., "Tasmania.osm.pbf"
                output_pbf_filename = f"{region_base_name}.osm.pbf"
                # Store extracted PBFs in the same subdirectory as their GeoJSON.
                output_pbf_full_path = os.path.join(root, output_pbf_filename)

                extracted_path = _extract_region_with_osmium(
                    region_base_name,
                    geojson_full_path,
                    australia_pbf_fullpath,
                    output_pbf_full_path,
                    current_uid,
                    current_gid,
                    logger_to_use,
                )
                if extracted_path:
                    extracted_pbf_paths[region_base_name] = extracted_path
            elif geojson_filename.endswith(".json"):  # Log other JSONs if any
                logger_to_use.debug(
                    f"Found non-regionmap JSON: {os.path.join(root, geojson_filename)}"
                )

    if not extracted_pbf_paths:
        log_map_server(
            f"{config.SYMBOLS['warning']} No regional PBFs extracted. "
            "OSRM/PostGIS data import steps will be skipped.",
            "warning",
            logger_to_use,
        )
    else:
        log_map_server(
            f"{config.SYMBOLS['success']} Osmium extraction complete. "
            f"PBFs ready for: {list(extracted_pbf_paths.keys())}",
            "success",
            logger_to_use,
        )

        # Import extracted PBFs into PostGIS.
        log_map_server(
            f"{config.SYMBOLS['step']} Importing regional PBFs into PostGIS "
            "(using osm2pgsql Flex backend)...",
            "info",
            logger_to_use,
        )
        for region_name, pbf_path in extracted_pbf_paths.items():
            log_map_server(
                f"Starting PostGIS import for region: {region_name} "
                f"(PBF: {pbf_path})",
                "info",
                logger_to_use,
            )
            import_success = _import_pbf_to_postgis_flex(
                pbf_file_path=pbf_path,
                db_config_dict=effective_db_config,
                osm_carto_style_dir=OSM_CARTO_DIR,
                flat_nodes_storage_dir=flat_nodes_dir_for_postgis,
                logger=logger_to_use,
                # osm2pgsql_cache_mb can be passed here if needed
            )
            if not import_success:
                log_map_server(
                    f"{config.SYMBOLS['error']} PostGIS import FAILED for "
                    f"region {region_name}. Check logs.",
                    "error",
                    logger_to_use,
                )
                # Decide if one failure should stop all, or just skip this region.
                # For now, continue with other regions.

        # Process extracted PBFs with OSRM via Docker.
        log_map_server(
            f"{config.SYMBOLS['step']} Processing regional PBFs with OSRM "
            "(using Docker)...",
            "info",
            logger_to_use,
        )
        osrm_processed_regions_count = 0
        for data_label, pbf_host_path in extracted_pbf_paths.items():
            log_map_server(
                f"Starting OSRM processing for region: {data_label} "
                f"(PBF: {pbf_host_path})",
                "info",
                logger_to_use,
            )

            # Directory on host for this region's OSRM processed files.
            region_osrm_data_dir_host = os.path.join(
                OSRM_BASE_PROCESSED_DIR, data_label
            )
            _ensure_directory_exists(
                region_osrm_data_dir_host,
                logger_to_use,
                current_uid,
                current_gid,
            )

            # data_label (e.g., "Tasmania") is used for naming outputs.
            extract_ok = _run_osrm_extract_docker(
                pbf_host_path=pbf_host_path,
                region_osrm_data_dir=region_osrm_data_dir_host,
                data_label_for_outputs=data_label,
                uid=current_uid,
                gid=current_gid,
                docker_image=OSRM_DOCKER_IMAGE,
                profile_in_container=OSRM_PROFILE_LUA_IN_CONTAINER,
                logger=logger_to_use,
            )
            if not extract_ok:
                log_map_server(
                    f"{config.SYMBOLS['error']} OSRM extract FAILED for "
                    f"{data_label}. Skipping subsequent OSRM steps for this region.",
                    "error",
                    logger_to_use,
                )
                # Log contents of the region's OSRM data directory for debugging.
                try:
                    host_dir_contents = os.listdir(region_osrm_data_dir_host)
                    logger_to_use.debug(
                        f"Contents of {region_osrm_data_dir_host} after "
                        f"failed extract: {host_dir_contents}"
                    )
                except Exception as e_ls:
                    logger_to_use.debug(
                        f"Could not list contents of {region_osrm_data_dir_host}: {e_ls}"
                    )
                continue  # Skip to the next region.

            # Verify expected files after extract before proceeding.
            expected_base_osrm_file = os.path.join(
                region_osrm_data_dir_host, f"{data_label}.osrm"
            )
            # expected_ebg_file = os.path.join(  # Example, actual files may vary
            #     region_osrm_data_dir_host, f"{data_label}.osrm.ebg"
            #  )
            logger_to_use.debug(
                f"Checking for OSRM files post-extract for {data_label}:"
            )
            logger_to_use.debug(
                f"  {expected_base_osrm_file} exists: "
                f"{os.path.isfile(expected_base_osrm_file)}"
            )
            # Add more checks for other essential files created by osrm-extract.

            if not (os.path.isfile(expected_base_osrm_file)):  # Basic check
                log_map_server(
                    f"{config.SYMBOLS['error']} OSRM extract for {data_label} "
                    f"reported success, but essential file ({data_label}.osrm) "
                    "is MISSING on host. Skipping further OSRM steps for this region.",
                    "error",
                    logger_to_use,
                )
                continue

            partition_ok = _run_osrm_partition_docker(
                region_osrm_data_dir=region_osrm_data_dir_host,
                data_label=data_label,
                uid=current_uid,
                gid=current_gid,
                docker_image=OSRM_DOCKER_IMAGE,
                logger=logger_to_use,
            )
            if not partition_ok:
                log_map_server(
                    f"{config.SYMBOLS['error']} OSRM partition FAILED for "
                    f"{data_label}. Skipping customize step.",
                    "error",
                    logger_to_use,
                )
                continue

            customize_ok = _run_osrm_customize_docker(
                region_osrm_data_dir=region_osrm_data_dir_host,
                data_label=data_label,
                uid=current_uid,
                gid=current_gid,
                docker_image=OSRM_DOCKER_IMAGE,
                logger=logger_to_use,
            )
            if customize_ok:
                log_map_server(
                    f"{config.SYMBOLS['success']} OSRM processing successful "
                    f"for region {data_label}.",
                    "success",
                    logger_to_use,
                )
                osrm_processed_regions_count += 1
            else:
                log_map_server(
                    f"{config.SYMBOLS['error']} OSRM customize FAILED for "
                    f"region {data_label}.",
                    "error",
                    logger_to_use,
                )

        log_map_server(
            f"{config.SYMBOLS['info']} OSRM Docker processing finished. "
            f"Successfully processed {osrm_processed_regions_count} / "
            f"{len(extracted_pbf_paths)} regions for OSRM.",
            "info",
            logger_to_use,
        )

    log_map_server(
        f"{config.SYMBOLS['success']} Full OSRM and PostGIS data setup "
        "script finished.",
        "info",
        logger_to_use,  # Changed to info as it's an end-of-function log
    )
