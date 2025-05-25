# setup/services/osrm.py
"""
Handles setup of OSM data import via osm2pgsql and OSRM routing engine via Docker.
"""
import logging
import os
import getpass
import datetime
from typing import Optional

from .. import config
from ..command_utils import (
    run_command,
    run_elevated_command,
    log_map_server,
)  # Removed command_exists as not used here
from ..helpers import systemd_reload

module_logger = logging.getLogger(__name__)


def osm_osrm_server_setup(
    current_logger: Optional[logging.Logger] = None,
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Setting up OSM data and OSRM routing engine...",
        "info",
        logger_to_use,
    )

    osm_data_base_dir = "/opt/osm_data"
    osrm_data_host_dir = (
        "/opt/osrm_data"  # For processed OSRM files, mounted into Docker
    )

    run_elevated_command(
        ["mkdir", "-p", osm_data_base_dir], current_logger=logger_to_use
    )
    run_elevated_command(
        ["mkdir", "-p", osrm_data_host_dir], current_logger=logger_to_use
    )

    current_user = getpass.getuser()
    try:
        current_group = getpass.getgrgid(os.getgid()).gr_name
    except KeyError:
        current_group = str(os.getgid())

    # osm_data_base_dir needs to be writable by current user for wget/osmium
    run_elevated_command(
        ["chown", f"{current_user}:{current_group}", osm_data_base_dir],
        current_logger=logger_to_use,
    )
    # osrm_data_host_dir needs to be writable by user UID/GID used in docker -u flag
    run_elevated_command(
        ["chown", f"{current_user}:{current_group}", osrm_data_host_dir],
        current_logger=logger_to_use,
    )

    log_map_server(
        f"{config.SYMBOLS['info']} Ensured data directories exist and have user permissions for initial processing.",
        "info",
        logger_to_use,
    )

    original_cwd = os.getcwd()
    try:
        os.chdir(osm_data_base_dir)
        australia_pbf = "australia-latest.osm.pbf"
        if not os.path.isfile(australia_pbf):
            log_map_server(
                f"{config.SYMBOLS['info']} Downloading {australia_pbf} from Geofabrik...",
                "info",
                logger_to_use,
            )
            run_command(
                [
                    "wget",
                    f"https://download.geofabrik.de/australia-oceania/{australia_pbf}",
                    "-O",
                    australia_pbf,
                ],
                current_logger=logger_to_use,
            )
        else:
            log_map_server(
                f"{config.SYMBOLS['info']} {australia_pbf} already exists.",
                "info",
                logger_to_use,
            )

        if not os.path.isfile(australia_pbf):
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to download {australia_pbf}. OSRM/OSM setup cannot continue.",
                "error",
                logger_to_use,
            )
            raise FileNotFoundError(
                f"{australia_pbf} not found after download attempt."
            )

        # --- Extract regions (Hobart, Tasmania) using osmium ---
        # This assumes *.json files for osmium are placed in osm_data_base_dir manually or by another script.
        # For example, copy them from a 'sampledata' directory if they exist.
        # TODO: Make sourcing of these JSON boundary files more robust if they are part of the project.
        # Example: shutil.copy(os.path.join(config.PROJECT_ROOT_DIR, "sampledata", json_filename), json_path_in_data_dir)

        regions_to_extract = {
            "TasmaniaRegionMap": "TasmaniaRegionMap.osm.pbf",
            "HobartRegionMap": "HobartRegionMap.osm.pbf",
        }
        for region_name, pbf_out_name in regions_to_extract.items():
            json_filename = f"{region_name}.json"
            json_path_in_data_dir = os.path.join(
                osm_data_base_dir, json_filename
            )  # Assumes json is here
            if os.path.isfile(json_path_in_data_dir):
                log_map_server(
                    f"{config.SYMBOLS['gear']} Extracting {region_name} using {json_filename} to {pbf_out_name}...",
                    "info",
                    logger_to_use,
                )
                run_command(
                    [
                        "osmium",
                        "extract",
                        "--overwrite",
                        "--strategy",
                        "smart",
                        "-p",
                        json_path_in_data_dir,
                        australia_pbf,
                        "-o",
                        os.path.join(osm_data_base_dir, pbf_out_name),
                    ],
                    current_logger=logger_to_use,
                )
            else:
                log_map_server(
                    f"{config.SYMBOLS['warning']} Region definition {json_path_in_data_dir} not found. Skipping {region_name} extract.",
                    "warning",
                    logger_to_use,
                )

        # --- osm2pgsql Import ---
        osm_pbf_to_import_for_tiles = os.path.join(
            osm_data_base_dir, "HobartRegionMap.osm.pbf"
        )
        if not os.path.isfile(osm_pbf_to_import_for_tiles) and os.path.isfile(
            os.path.join(osm_data_base_dir, "TasmaniaRegionMap.osm.pbf")
        ):
            osm_pbf_to_import_for_tiles = os.path.join(
                osm_data_base_dir, "TasmaniaRegionMap.osm.pbf"
            )
        elif not os.path.isfile(
            osm_pbf_to_import_for_tiles
        ):  # If neither extract exists, use full Australia
            osm_pbf_to_import_for_tiles = os.path.join(
                osm_data_base_dir, australia_pbf
            )

        log_map_server(
            f"{config.SYMBOLS['info']} Using PBF: {osm_pbf_to_import_for_tiles} for osm2pgsql import (tiles).",
            "info",
            logger_to_use,
        )

        osm_carto_dir = (
            "/opt/openstreetmap-carto"  # Assumes Carto setup was done
        )
        osm_carto_lua_script = os.path.join(
            osm_carto_dir, "openstreetmap-carto.lua"
        )
        if not os.path.isfile(osm_carto_lua_script):
            osm_carto_lua_script = os.path.join(
                osm_carto_dir, "openstreetmap-carto-flex.lua"
            )  # Try flex
        if not os.path.isfile(osm_carto_lua_script):
            log_map_server(
                f"{config.SYMBOLS['error']} OpenStreetMap-Carto Lua style script not found in {osm_carto_dir}. osm2pgsql needs this for flex output.",
                "error",
                logger_to_use,
            )
            raise FileNotFoundError(
                f"OSM Carto Lua script missing from {osm_carto_dir}."
            )

        osm2pgsql_cache_mb = os.environ.get(
            "OSM2PGSQL_CACHE_DEFAULT", "2048"
        )  # Default cache in MB
        # Ensure flat nodes dir is writable by user running osm2pgsql
        flat_nodes_storage_dir = os.path.join(
            osm_data_base_dir, "flat_nodes_temp"
        )
        os.makedirs(
            flat_nodes_storage_dir, exist_ok=True
        )  # run_command can't create dir for user usually
        run_command(
            [
                "chown",
                f"{current_user}:{current_group}",
                flat_nodes_storage_dir,
            ],
            current_logger=logger_to_use,
        )  # Use run_command if current user needs to write

        flat_nodes_file = os.path.join(
            flat_nodes_storage_dir,
            f"flatnodes_{datetime.datetime.now().strftime('%Y%m%d')}.bin",
        )

        log_map_server(
            f"{config.SYMBOLS['gear']} Starting osm2pgsql import (Flex backend)... Ensure PGPASSWORD for user {config.PGUSER} is in env or .pgpass is setup.",
            "info",
            logger_to_use,
        )
        osm2pgsql_cmd = [
            "osm2pgsql",
            "--create",
            "--slim",
            "-d",
            config.PGDATABASE,
            "-U",
            config.PGUSER,
            "-H",
            config.PGHOST,
            "-P",
            config.PGPORT,
            "--hstore",
            "--multi-geometry",
            "--tag-transform-script",
            osm_carto_lua_script,
            "--style",
            osm_carto_lua_script,  # For style-specific tables/tags
            "--output=flex",
            f"-C{osm2pgsql_cache_mb}",  # Note: -C not -C空格
            f"--number-processes={str(os.cpu_count() or 1)}",
            f"--flat-nodes={flat_nodes_file}",
            osm_pbf_to_import_for_tiles,
        ]
        # osm2pgsql should be run as a user that can connect to PostgreSQL (e.g. current_user if .pgpass is set)
        # PGPASSWORD should be in environment if .pgpass is not used/working for PGUSER
        run_command(osm2pgsql_cmd, current_logger=logger_to_use)
        log_map_server(
            f"{config.SYMBOLS['success']} osm2pgsql import completed.",
            "success",
            logger_to_use,
        )

        # --- OSRM Setup ---
        log_map_server(
            f"{config.SYMBOLS['rocket']} Setting up OSRM routing engine via Docker...",
            "info",
            logger_to_use,
        )
        osm_pbf_for_osrm = osm_pbf_to_import_for_tiles  # Use the same PBF as for tiles, or a specific smaller one
        log_map_server(
            f"{config.SYMBOLS['info']} Using PBF: {osm_pbf_for_osrm} for OSRM processing.",
            "info",
            logger_to_use,
        )

        osrm_image = "osrm/osrm-backend:latest"
        osrm_profile_in_container = (
            "/opt/car.lua"  # Standard profile shipped with OSRM docker image
        )
        osrm_map_label = (
            "map_data"  # Label for processed osrm files, e.g., map_data.osrm
        )

        pbf_filename_for_docker = os.path.basename(osm_pbf_for_osrm)

        uid = str(os.getuid())
        gid = str(os.getgid())

        # OSRM tools output files based on the input PBF name by default, in their working directory.
        # So, /data/$(basename $PBF_FILE .osm.pbf).osrm
        # We want them named as {osrm_map_label}.osrm

        # Step 1: osrm-extract
        log_map_server(
            f"{config.SYMBOLS['gear']} Running osrm-extract via Docker (user {uid}:{gid})...",
            "info",
            logger_to_use,
        )
        # Mount PBF source dir and output dir. Set working dir to output dir.
        # Output files will be like /data/australia-latest.osrm if input is /input_data/australia-latest.osm.pbf
        docker_extract_cmd = [
            "docker",
            "run",
            "--rm",
            "-u",
            f"{uid}:{gid}",
            "-v",
            f"{osm_data_base_dir}:/input_data:ro",  # Mount PBF source
            "-v",
            f"{osrm_data_host_dir}:/data_output",  # Mount output dir for osrm files
            "-w",
            "/data_output",  # Set working dir inside container
            osrm_image,
            "osrm-extract",
            "-p",
            osrm_profile_in_container,
            f"/input_data/{pbf_filename_for_docker}",
        ]
        run_elevated_command(
            docker_extract_cmd, current_logger=logger_to_use
        )  # Docker command may need sudo

        # Rename OSRM files to use the osrm_map_label
        pbf_basename_for_osrm_files = os.path.splitext(
            pbf_filename_for_docker
        )[
            0
        ]  # remove .pbf
        if (
            ".osm" in pbf_basename_for_osrm_files
        ):  # remove .osm if it was .osm.pbf
            pbf_basename_for_osrm_files = os.path.splitext(
                pbf_basename_for_osrm_files
            )[0]

        log_map_server(
            f"{config.SYMBOLS['gear']} Renaming OSRM files from base '{pbf_basename_for_osrm_files}' to '{osrm_map_label}' in {osrm_data_host_dir}...",
            "info",
            logger_to_use,
        )
        # Check if files exist before renaming, and handle if osrm_map_label is same as pbf_basename_for_osrm_files
        if os.path.exists(
            os.path.join(
                osrm_data_host_dir, f"{pbf_basename_for_osrm_files}.osrm"
            )
        ):  # Check for main file
            if pbf_basename_for_osrm_files != osrm_map_label:
                for item_name in os.listdir(osrm_data_host_dir):
                    if item_name.startswith(
                        pbf_basename_for_osrm_files + ".osrm"
                    ):
                        new_item_name = item_name.replace(
                            pbf_basename_for_osrm_files + ".osrm",
                            osrm_map_label + ".osrm",
                            1,
                        )
                        run_elevated_command(
                            [
                                "mv",
                                os.path.join(osrm_data_host_dir, item_name),
                                os.path.join(
                                    osrm_data_host_dir, new_item_name
                                ),
                            ],
                            current_logger=logger_to_use,
                        )
                log_map_server(
                    f"{config.SYMBOLS['success']} OSRM files renamed.",
                    "success",
                    logger_to_use,
                )
            else:
                log_map_server(
                    f"{config.SYMBOLS['info']} OSRM output base name '{pbf_basename_for_osrm_files}' matches target label '{osrm_map_label}'. No rename needed.",
                    "info",
                    logger_to_use,
                )
        else:
            log_map_server(
                f"{config.SYMBOLS['warning']} Expected OSRM output file {pbf_basename_for_osrm_files}.osrm not found in {osrm_data_host_dir}. Skipping rename. Check osrm-extract step.",
                "warning",
                logger_to_use,
            )

        osrm_base_file_in_container = f"/data/{osrm_map_label}.osrm"  # Path inside container for subsequent steps

        # Step 2: osrm-partition
        log_map_server(
            f"{config.SYMBOLS['gear']} Running osrm-partition via Docker...",
            "info",
            logger_to_use,
        )
        run_elevated_command(
            [
                "docker",
                "run",
                "--rm",
                "-u",
                f"{uid}:{gid}",
                "-v",
                f"{osrm_data_host_dir}:/data",
                "-w",
                "/data",
                osrm_image,
                "osrm-partition",
                osrm_base_file_in_container,
            ],
            current_logger=logger_to_use,
        )

        # Step 3: osrm-customize
        log_map_server(
            f"{config.SYMBOLS['gear']} Running osrm-customize via Docker...",
            "info",
            logger_to_use,
        )
        run_elevated_command(
            [
                "docker",
                "run",
                "--rm",
                "-u",
                f"{uid}:{gid}",
                "-v",
                f"{osrm_data_host_dir}:/data",
                "-w",
                "/data",
                osrm_image,
                "osrm-customize",
                osrm_base_file_in_container,
            ],
            current_logger=logger_to_use,
        )

        # OSRM Systemd Service to run osrm-routed
        osrm_service_name = f"osrm-routed-docker-{osrm_map_label}.service"
        osrm_service_file_path = f"/etc/systemd/system/{osrm_service_name}"
        osrm_container_name = f"osrm_routed_container_{osrm_map_label}"

        osrm_service_content = f"""[Unit]
Description=OSRM Routing Engine (Docker) for {osrm_map_label} dataset
Requires=docker.service
After=docker.service network-online.target

[Service]
Restart=always
RestartSec=10s
ExecStartPre=-/usr/bin/docker stop {osrm_container_name}
ExecStartPre=-/usr/bin/docker rm {osrm_container_name}
ExecStart=/usr/bin/docker run --rm --name {osrm_container_name} \\
          -p 127.0.0.1:5000:5000 \\
          -v {osrm_data_host_dir}:/data:ro \\
          {osrm_image} \\
          osrm-routed --algorithm MLD /data/{osrm_map_label}.osrm --max-table-size 8000
ExecStop=/usr/bin/docker stop {osrm_container_name}
# --rm on docker run should handle removal on stop, so ExecStopPost for rm might be redundant.

[Install]
WantedBy=multi-user.target
"""
        run_elevated_command(
            ["tee", osrm_service_file_path],
            cmd_input=osrm_service_content,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Created {osrm_service_file_path}",
            "success",
            logger_to_use,
        )

        systemd_reload(current_logger=logger_to_use)
        run_elevated_command(
            ["systemctl", "enable", osrm_service_name],
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["systemctl", "restart", osrm_service_name],
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['info']} OSRM Docker service '{osrm_service_name}' status:",
            "info",
            logger_to_use,
        )
        run_elevated_command(
            ["systemctl", "status", osrm_service_name, "--no-pager", "-l"],
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} OSRM setup completed.",
            "success",
            logger_to_use,
        )

    finally:
        os.chdir(original_cwd)
