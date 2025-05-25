# setup/services/osrm.py
"""
Handles setup of OSM data import via osm2pgsql and OSRM routing engine via Docker.
"""
import datetime
import logging
import os
from typing import Optional

from setup import config
from setup.command_utils import (
    run_command,
    run_elevated_command,
    log_map_server,
)
from setup.helpers import systemd_reload

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
    osm_data_regions_dir = os.path.join(osm_data_base_dir, "regions")
    osrm_data_host_dir = (
        "/opt/osrm_data"  # For processed OSRM files, mounted into Docker
    )

    current_uid = str(os.getuid())
    current_gid = str(os.getgid())

    run_elevated_command(
        ["mkdir", "-p", osm_data_base_dir], current_logger=logger_to_use
    )
    run_elevated_command(
        ["mkdir", "-p", osm_data_regions_dir], current_logger=logger_to_use
    )
    run_elevated_command(
        ["mkdir", "-p", osrm_data_host_dir], current_logger=logger_to_use
    )

    # TODO: Super ugly, needs to be dynamic. See later.
    # Copy region GeoJSON files from assets/regions to /opt/osm_data/regions
    script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assets_regions_dir = os.path.join(script_dir, "assets", "regions")

    australia_dir = os.path.join(assets_regions_dir, "Australia")
    tasmania_dir = os.path.join(australia_dir, "Tasmania")

    run_elevated_command(
        ["mkdir", "-p", australia_dir], current_logger=logger_to_use
    )

    run_elevated_command(
        ["mkdir", "-p", tasmania_dir], current_logger=logger_to_use
    )

    if os.path.exists(assets_regions_dir):
        log_map_server(
            f"{config.SYMBOLS['info']} Copying region GeoJSON files from {assets_regions_dir} to {osm_data_regions_dir}...",
            "info",
            logger_to_use,
        )

        for root, dirs, files in os.walk(assets_regions_dir):
            rel_path = os.path.relpath(root, assets_regions_dir)
            if rel_path != '.':
                target_dir = os.path.join(osm_data_regions_dir, rel_path)
                run_elevated_command(
                    ["mkdir", "-p", target_dir],
                    current_logger=logger_to_use)
                run_elevated_command(
                    ["chown", f"{current_uid}:{current_gid}", target_dir],
                    current_logger=logger_to_use,
                )

            for file in files:
                if file.endswith('.json'):
                    source_file = os.path.join(root, file)
                    if rel_path == '.':
                        target_file = os.path.join(osm_data_regions_dir, file)
                    else:
                        target_file = os.path.join(osm_data_regions_dir, rel_path, file)

                    run_elevated_command(
                        ["cp", source_file, target_file],
                        current_logger=logger_to_use,
                    )
                    run_elevated_command(
                        ["chown", f"{current_uid}:{current_gid}", target_file],
                        current_logger=logger_to_use,
                    )

        log_map_server(
            f"{config.SYMBOLS['success']} Region GeoJSON files copied to {osm_data_regions_dir}",
            "success",
            logger_to_use,
        )

    run_elevated_command(
        ["chown", f"{current_uid}:{current_gid}", osm_data_base_dir],
        current_logger=logger_to_use,
    )
    run_elevated_command(
        ["chown", f"{current_uid}:{current_gid}", osrm_data_host_dir],
        current_logger=logger_to_use,
    )
    run_elevated_command(["chmod", "u+rwx", osm_data_base_dir], current_logger=logger_to_use)
    run_elevated_command(["chmod", "u+rwx", osrm_data_host_dir], current_logger=logger_to_use)

    log_map_server(
        f"{config.SYMBOLS['info']} Ensured data directories exist and have user permissions for processing.",
        "info",
        logger_to_use,
    )

    original_cwd = os.getcwd()
    try:
        australia_pbf_filename = "australia-latest.osm.pbf"
        australia_pbf_fullpath = os.path.join(osm_data_base_dir, australia_pbf_filename)

        if not os.path.isfile(australia_pbf_fullpath):
            log_map_server(
                f"{config.SYMBOLS['info']} Downloading {australia_pbf_filename} from Geofabrik to {osm_data_base_dir}...",
                "info",
                logger_to_use,
            )
            run_command(
                [
                    "wget",
                    f"https://download.geofabrik.de/australia-oceania/{australia_pbf_filename}",
                    "-O",
                    australia_pbf_fullpath,
                ],
                current_logger=logger_to_use,
            )
        else:
            log_map_server(
                f"{config.SYMBOLS['info']} {australia_pbf_fullpath} already exists.",
                "info",
                logger_to_use,
            )

        if not os.path.isfile(australia_pbf_fullpath):
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to download {australia_pbf_fullpath}. OSRM/OSM setup cannot continue.",
                "error",
                logger_to_use,
            )
            raise FileNotFoundError(
                f"{australia_pbf_fullpath} not found after download attempt."
            )

        # --- Extract regions (Hobart, Tasmania) using osmium ---
        regions_to_extract = {
            "TasmaniaRegionMap": "TasmaniaRegionMap.osm.pbf",
            "HobartRegionMap": "HobartRegionMap.osm.pbf",
        }
        extracted_pbf_paths = {}

        def find_region_file(region_name, base_dir):
            for root, dirs, files in os.walk(base_dir):
                for file in files:
                    if file == f"{region_name}.json":
                        return os.path.join(root, file)
            return None

        for region_name, pbf_out_name in regions_to_extract.items():
            json_path_in_regions_dir = find_region_file(region_name, osm_data_regions_dir)

            if not json_path_in_regions_dir:
                json_filename = f"{region_name}.json"
                json_path_in_regions_dir = os.path.join(osm_data_base_dir, json_filename)

            output_pbf_path = os.path.join(osm_data_base_dir, pbf_out_name)
            extracted_pbf_paths[region_name] = output_pbf_path

            if os.path.isfile(json_path_in_regions_dir):
                log_map_server(
                    f"{config.SYMBOLS['gear']} Extracting {region_name} using {os.path.basename(json_path_in_regions_dir)} to {pbf_out_name}...",
                    "info",
                    logger_to_use,
                )
                run_command(
                    [
                        "osmium", "extract", "--overwrite",
                        "--strategy", "smart",
                        "-p", json_path_in_regions_dir,
                        australia_pbf_fullpath,
                        "-o", output_pbf_path,
                    ],
                    current_logger=logger_to_use,
                )
            else:
                log_map_server(
                    f"{config.SYMBOLS['warning']} Region definition for {region_name} not found in {osm_data_regions_dir} or {osm_data_base_dir}. Skipping {region_name} extract.",
                    "warning",
                    logger_to_use,
                )
                extracted_pbf_paths[region_name] = None

        # TODO: Work out how to manage this much better given the /assets/regions/ files. See previous
        if extracted_pbf_paths.get("HobartRegionMap") and os.path.isfile(extracted_pbf_paths["HobartRegionMap"]):
            osm_pbf_for_processing = extracted_pbf_paths["HobartRegionMap"]
            log_map_server(
                f"{config.SYMBOLS['info']} Using Hobart PBF for subsequent processing: {osm_pbf_for_processing}",
                "info", logger_to_use)
        elif extracted_pbf_paths.get("TasmaniaRegionMap") and os.path.isfile(extracted_pbf_paths["TasmaniaRegionMap"]):
            osm_pbf_for_processing = extracted_pbf_paths["TasmaniaRegionMap"]
            log_map_server(
                f"{config.SYMBOLS['info']} Using Tasmania PBF for subsequent processing: {osm_pbf_for_processing}",
                "info", logger_to_use)
        else:
            osm_pbf_for_processing = australia_pbf_fullpath
            log_map_server(
                f"{config.SYMBOLS['info']} Using full Australia PBF for subsequent processing: {osm_pbf_for_processing}",
                "info", logger_to_use)

        if not osm_pbf_for_processing or not os.path.isfile(osm_pbf_for_processing):
            log_map_server(f"{config.SYMBOLS['error']} No suitable PBF file found for processing. Aborting.", "error",
                           logger_to_use)
            raise FileNotFoundError("Suitable PBF file for processing is missing.")

        # --- osm2pgsql Import ---
        log_map_server(
            f"{config.SYMBOLS['info']} Using PBF: {osm_pbf_for_processing} for osm2pgsql import (tiles).",
            "info",
            logger_to_use,
        )

        osm_carto_dir = "/opt/openstreetmap-carto"
        osm_carto_lua_script = os.path.join(osm_carto_dir, "openstreetmap-carto.lua")
        if not os.path.isfile(osm_carto_lua_script):
            osm_carto_lua_script = os.path.join(osm_carto_dir, "openstreetmap-carto-flex.lua")
        if not os.path.isfile(osm_carto_lua_script):
            log_map_server(
                f"{config.SYMBOLS['error']} OpenStreetMap-Carto Lua style script not found in {osm_carto_dir}.",
                "error", logger_to_use,
            )
            raise FileNotFoundError(f"OSM Carto Lua script missing from {osm_carto_dir}.")

        osm2pgsql_cache_mb = os.environ.get("OSM2PGSQL_CACHE_DEFAULT", "2048")
        flat_nodes_storage_dir = os.path.join(osm_data_base_dir, "flat_nodes_temp")
        os.makedirs(flat_nodes_storage_dir, exist_ok=True)
        run_elevated_command(
            ["chown", f"{current_uid}:{current_gid}", flat_nodes_storage_dir],
            current_logger=logger_to_use,
        )

        flat_nodes_file = os.path.join(
            flat_nodes_storage_dir,
            f"flatnodes_{datetime.datetime.now().strftime('%Y%m%d')}.bin",
        )

        log_map_server(
            f"{config.SYMBOLS['gear']} Starting osm2pgsql import (Flex backend)... Ensure PGPASSWORD for user {config.PGUSER} is set or .pgpass is configured.",
            "info", logger_to_use,
        )
        osm2pgsql_cmd = [
            "osm2pgsql", "--create", "--slim",
            "-d", config.PGDATABASE, "-U", config.PGUSER,
            "-H", config.PGHOST, "-P", config.PGPORT,
            "--hstore", "--multi-geometry",
            "--tag-transform-script", osm_carto_lua_script,
            "--style", osm_carto_lua_script,
            "--output=flex", f"-C{osm2pgsql_cache_mb}",
            f"--number-processes={str(os.cpu_count() or 1)}",
            f"--flat-nodes={flat_nodes_file}",
            osm_pbf_for_processing,
        ]
        run_command(osm2pgsql_cmd, current_logger=logger_to_use)
        log_map_server(
            f"{config.SYMBOLS['success']} osm2pgsql import completed.", "success", logger_to_use,
        )

        # --- OSRM Setup ---
        log_map_server(
            f"{config.SYMBOLS['rocket']} Setting up OSRM routing engine via Docker...",
            "info", logger_to_use,
        )
        # Use the same PBF as for tiles, or you could specify a different one
        pbf_host_full_path_for_osrm = osm_pbf_for_processing
        pbf_filename_only_for_osrm = os.path.basename(pbf_host_full_path_for_osrm)

        log_map_server(
            f"{config.SYMBOLS['info']} Using PBF: {pbf_host_full_path_for_osrm} for OSRM processing.",
            "info", logger_to_use,
        )

        osrm_image = "osrm/osrm-backend:latest"
        osrm_profile_in_container = "/opt/car.lua"
        osrm_map_label = "map_routing_data"

        log_map_server(
            f"{config.SYMBOLS['gear']} Running osrm-extract via Docker (user {current_uid}:{current_gid})...",
            "info", logger_to_use,
        )

        container_temp_ro_pbf_mount_path = f"/mnt_readonly_pbf/{pbf_filename_only_for_osrm}"
        container_writable_pbf_path_in_workdir = f"./{pbf_filename_only_for_osrm}"

        extract_shell_command = (
            f"cp \"{container_temp_ro_pbf_mount_path}\" \"{container_writable_pbf_path_in_workdir}\" && "
            f"osrm-extract -p \"{osrm_profile_in_container}\" \"{container_writable_pbf_path_in_workdir}\" && "
            f"rm \"{container_writable_pbf_path_in_workdir}\""
        )

        docker_extract_cmd = [
            "docker", "run", "--rm",
            "-u", f"{current_uid}:{current_gid}",
            "-v", f"{pbf_host_full_path_for_osrm}:{container_temp_ro_pbf_mount_path}:ro",
            "-v", f"{osrm_data_host_dir}:/data_output",
            "-w", "/data_output",
            osrm_image,
            "sh", "-c", extract_shell_command
        ]
        run_elevated_command(docker_extract_cmd,
                             current_logger=logger_to_use)

        pbf_basename_for_renaming = os.path.splitext(pbf_filename_only_for_osrm)[0]
        if ".osm" in pbf_basename_for_renaming:
            pbf_basename_for_renaming = os.path.splitext(pbf_basename_for_renaming)[0]

        log_map_server(
            f"{config.SYMBOLS['gear']} Renaming OSRM files from base '{pbf_basename_for_renaming}' to '{osrm_map_label}' in {osrm_data_host_dir}...",
            "info", logger_to_use,
        )

        expected_main_osrm_file_original_name = f"{pbf_basename_for_renaming}.osrm"
        if os.path.exists(os.path.join(osrm_data_host_dir, expected_main_osrm_file_original_name)):
            if pbf_basename_for_renaming != osrm_map_label:
                for item_name in os.listdir(osrm_data_host_dir):
                    if item_name.startswith(pbf_basename_for_renaming + ".osrm"):
                        new_item_name = osrm_map_label + item_name[len(pbf_basename_for_renaming):]
                        run_elevated_command(
                            [
                                "mv",
                                os.path.join(osrm_data_host_dir, item_name),
                                os.path.join(osrm_data_host_dir, new_item_name),
                            ],
                            current_logger=logger_to_use,
                        )
                log_map_server(
                    f"{config.SYMBOLS['success']} OSRM files renamed to use '{osrm_map_label}' base.", "success",
                    logger_to_use,
                )
            else:
                log_map_server(
                    f"{config.SYMBOLS['info']} OSRM output base name '{pbf_basename_for_renaming}' matches target label '{osrm_map_label}'. No rename needed.",
                    "info", logger_to_use,
                )
        else:
            log_map_server(
                f"{config.SYMBOLS['warning']} Expected OSRM output file {expected_main_osrm_file_original_name} not found in {osrm_data_host_dir}. Skipping rename. Check osrm-extract step.",
                "warning", logger_to_use,
            )

        osrm_base_file_in_container_for_processing = f"/data/{osrm_map_label}.osrm"

        # Step 2: osrm-partition
        log_map_server(
            f"{config.SYMBOLS['gear']} Running osrm-partition via Docker...", "info", logger_to_use,
        )
        run_elevated_command(
            [
                "docker", "run", "--rm", "-u", f"{current_uid}:{current_gid}",
                "-v", f"{osrm_data_host_dir}:/data",
                "-w", "/data",
                osrm_image,
                "osrm-partition", osrm_base_file_in_container_for_processing,
            ],
            current_logger=logger_to_use,
        )

        # Step 3: osrm-customize
        log_map_server(
            f"{config.SYMBOLS['gear']} Running osrm-customize via Docker...", "info", logger_to_use,
        )
        run_elevated_command(
            [
                "docker", "run", "--rm", "-u", f"{current_uid}:{current_gid}",
                "-v", f"{osrm_data_host_dir}:/data",
                "-w", "/data",
                osrm_image,
                "osrm-customize", osrm_base_file_in_container_for_processing,
            ],
            current_logger=logger_to_use,
        )

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

[Install]
WantedBy=multi-user.target
"""
        run_elevated_command(
            ["tee", osrm_service_file_path],
            cmd_input=osrm_service_content,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Created {osrm_service_file_path}", "success", logger_to_use,
        )

        systemd_reload(current_logger=logger_to_use)
        run_elevated_command(
            ["systemctl", "enable", osrm_service_name], current_logger=logger_to_use,
        )
        run_elevated_command(
            ["systemctl", "restart", osrm_service_name], current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['info']} OSRM Docker service '{osrm_service_name}' status:", "info", logger_to_use,
        )
        run_elevated_command(
            ["systemctl", "status", osrm_service_name, "--no-pager", "-l"],
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} OSRM setup completed.", "success", logger_to_use,
        )

    finally:
        os.chdir(original_cwd)


if __name__ == '__main__':
    if not os.path.exists("/opt/osm_data"):
        os.makedirs("/opt/osm_data")

    # Create regions directory structure
    regions_dir = "/opt/osm_data/regions"
    australia_dir = os.path.join(regions_dir, "Australia")
    tasmania_dir = os.path.join(australia_dir, "Tasmania")

    os.makedirs(regions_dir, exist_ok=True)
    os.makedirs(australia_dir, exist_ok=True)
    os.makedirs(tasmania_dir, exist_ok=True)

    # TODO: No dummies
    # Create dummy JSON for osmium to avoid error if you run the osmium part
    # These would need to be actual GeoJSON polygon definitions for osmium to work.
    with open(os.path.join(tasmania_dir, "HobartRegionMap.json"), "w") as f:
        f.write('{"type": "FeatureCollection", "features": []}')  # Dummy content
    with open(os.path.join(australia_dir, "TasmaniaRegionMap.json"), "w") as f:
        f.write('{"type": "FeatureCollection", "features": []}')  # Dummy content

    # TODO: No dummies
    # Create dummy OSM Carto lua script
    if not os.path.exists("/opt/openstreetmap-carto"):
        os.makedirs("/opt/openstreetmap-carto")
    with open("/opt/openstreetmap-carto/openstreetmap-carto.lua", "w") as f:
        f.write('-- Dummy Lua for osm2pgsql')

    try:
        module_logger.info("Starting OSRM server setup process...")
        osm_osrm_server_setup(current_logger=module_logger)
        module_logger.info("OSRM server setup process finished.")
    except Exception as e:
        module_logger.error(f"An error occurred during OSRM setup: {e}", exc_info=True)
