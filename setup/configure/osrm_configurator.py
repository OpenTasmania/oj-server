# configure/osrm_configurator.py
# -*- coding: utf-8 -*-
"""
Handles configuration of OSRM services, primarily setting up and activating
systemd services for osrm-routed for processed regions.
"""

import logging
from os import cpu_count, environ
from pathlib import Path
from subprocess import CalledProcessError
from typing import Optional

from common.command_utils import (
    log_map_server,
    run_command,
    run_elevated_command,
)
from common.system_utils import get_current_script_hash, systemd_reload
from setup import config as static_config
from setup.config_models import AppSettings

module_logger = logging.getLogger(__name__)


def get_next_available_port(
    app_settings: AppSettings, logger: logging.Logger
) -> int:
    """
    Returns the next available port for OSRM services.
    Tracks used ports to avoid conflicts.
    """
    # TODO: Use logger
    osrm_service_cfg = app_settings.osrm_service
    base_port = osrm_service_cfg.car_profile_default_host_port

    used_ports = set(osrm_service_cfg.region_port_map.values())

    next_port = base_port
    while next_port in used_ports:
        next_port += 1

    return next_port


def create_osrm_routed_service_file(
    region_name_key: str,  # Unique key for the region, e.g., "Australia_Tasmania_Hobart"
    app_settings: AppSettings,
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """Creates a systemd service file for osrm-routed for a specific region using template from app_settings."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    script_hash = (
        get_current_script_hash(
            project_root_dir=static_config.OSM_PROJECT_ROOT,
            app_settings=app_settings,
            logger_instance=logger_to_use,
        )
        or "UNKNOWN_HASH"
    )

    osrm_data_cfg = app_settings.osrm_data
    osrm_service_cfg = app_settings.osrm_service

    service_name = f"osrm-routed-{region_name_key}.service"
    service_file_path = f"/etc/systemd/system/{service_name}"

    host_osrm_data_dir_for_this_region = (
        Path(osrm_data_cfg.processed_dir) / region_name_key
    )
    osrm_filename_stem_in_container = region_name_key

    log_map_server(
        f"{symbols.get('step', '➡️')} Creating systemd service file for {service_name} at {service_file_path} from template...",
        "info",
        logger_to_use,
        app_settings,
    )

    expected_osrm_file_on_host = (
        host_osrm_data_dir_for_this_region
        / f"{osrm_filename_stem_in_container}.osrm"
    )
    if not expected_osrm_file_on_host.exists():
        log_map_server(
            f"{symbols.get('error', '❌')} OSRM data file {expected_osrm_file_on_host} not found. Cannot create service for {region_name_key}.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise FileNotFoundError(
            f"OSRM data file {expected_osrm_file_on_host} missing for service {service_name}"
        )

    if region_name_key in osrm_service_cfg.region_port_map:
        host_port_for_this_region = osrm_service_cfg.region_port_map[
            region_name_key
        ]
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Using configured port {host_port_for_this_region} for region {region_name_key}",
            "info",
            logger_to_use,
            app_settings,
        )
    else:
        host_port_for_this_region = get_next_available_port(
            app_settings, logger_to_use
        )
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Auto-assigned port {host_port_for_this_region} for region {region_name_key}",
            "info",
            logger_to_use,
            app_settings,
        )

    osrm_service_cfg.region_port_map[region_name_key] = (
        host_port_for_this_region
    )

    systemd_template_str = osrm_service_cfg.systemd_template
    format_vars = {
        "script_hash": script_hash,
        "region_name": region_name_key,
        "container_runtime_command": app_settings.container_runtime_command,
        "host_port_for_region": host_port_for_this_region,
        "container_osrm_port": osrm_service_cfg.container_osrm_port,
        "host_osrm_data_dir_for_region": str(
            host_osrm_data_dir_for_this_region
        ),
        "osrm_image_tag": osrm_service_cfg.image_tag,
        "osrm_filename_in_container": f"{osrm_filename_stem_in_container}.osrm",
        "max_table_size_routed": osrm_data_cfg.max_table_size_routed,
        "extra_osrm_routed_args": osrm_service_cfg.extra_routed_args,
    }

    try:
        service_content_final = systemd_template_str.format(**format_vars)
        run_elevated_command(
            ["tee", service_file_path],
            app_settings,
            cmd_input=service_content_final,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Created/Updated {service_file_path}",
            "success",
            logger_to_use,
            app_settings,
        )
    except KeyError as e_key:
        log_map_server(
            f"{symbols.get('error', '❌')} Missing placeholder key '{e_key}' for OSRM systemd template. Check config.yaml/models.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to write {service_file_path}: {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        raise


def import_pbf_to_postgis_with_osm2pgsql(
    pbf_full_path: str,
    app_settings: AppSettings,
    current_logger: Optional[logging.Logger] = None,
) -> bool:
    """Imports a PBF file into PostGIS using osm2pgsql."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    postgis_cfg = app_settings.pg
    osm_data_cfg = app_settings.osrm_data

    log_map_server(
        f"{symbols.get('step', '➡️')} Starting osm2pgsql import for {Path(pbf_full_path).name}...",
        "info",
        logger_to_use,
        app_settings,
    )

    if not Path(pbf_full_path).is_file():
        log_map_server(
            f"{symbols.get('error', '❌')} PBF file not found for osm2pgsql import: {pbf_full_path}",
            "error",
            logger_to_use,
            app_settings,
        )
        return False

    # Define paths for Carto style and lua files
    osm_carto_dir = (
        static_config.OSM_PROJECT_ROOT / "external" / "openstreetmap-carto"
    )
    osm_carto_style_file = osm_carto_dir / "openstreetmap-carto.style"
    osm_carto_lua_script = osm_carto_dir / "openstreetmap-carto.lua"

    if not osm_carto_style_file.is_file():
        log_map_server(
            f"{symbols.get('error', '❌')} OSM-Carto style file not found at {osm_carto_style_file}. Cannot proceed.",
            "error",
            logger_to_use,
            app_settings,
        )
        return False

    if not osm_carto_lua_script.is_file():
        log_map_server(
            f"{symbols.get('error', '❌')} OSM-Carto LUA script not found at {osm_carto_lua_script}. Cannot proceed.",
            "error",
            logger_to_use,
            app_settings,
        )
        return False

    env_vars = environ.copy()
    env_vars["PGPASSWORD"] = postgis_cfg.password

    # Command using flex output, as recommended by modern CartoCSS
    osm2pgsql_cmd = [
        "osm2pgsql",
        "--create",
        "--database",
        str(postgis_cfg.database),
        "--username",
        str(postgis_cfg.user),
        "--host",
        str(postgis_cfg.host),
        "--port",
        str(postgis_cfg.port),
        "--slim",
        "--hstore",
        "--multi-geometry",
        f"--tag-transform-script={osm_carto_lua_script}",
        f"--style={osm_carto_style_file}",
        "--output=flex",
        "-C",
        str(osm_data_cfg.osm2pgsql_cache_mb),
        f"--number-processes={str(cpu_count() or 1)}",
        pbf_full_path,
    ]

    log_map_server(
        f"osm2pgsql command: {' '.join(osm2pgsql_cmd)}",
        "debug",
        logger_to_use,
        app_settings,
    )

    try:
        # Using run_command as osm2pgsql should not require root if permissions are correct.
        run_command(
            osm2pgsql_cmd,
            app_settings,
            current_logger=logger_to_use,
            check=True,
            env=env_vars,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} osm2pgsql import for {Path(pbf_full_path).name} completed successfully.",
            "success",
            logger_to_use,
            app_settings,
        )
        return True
    except CalledProcessError as e:
        log_map_server(
            f"{symbols.get('critical', '🔥')} osm2pgsql import FAILED with exit code {e.returncode}. Output: {e.stderr or e.stdout}",
            "critical",
            logger_to_use,
            app_settings,
        )
        return False
    except Exception as e:
        log_map_server(
            f"{symbols.get('critical', '🔥')} Unexpected error during osm2pgsql import: {e}",
            "critical",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        return False


def activate_osrm_routed_service(
    region_name_key: str,
    app_settings: AppSettings,
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """Reloads systemd, enables and restarts the osrm-routed service for a region."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    service_name = f"osrm-routed-{region_name_key}.service"
    log_map_server(
        f"{symbols.get('step', '➡️')} Activating {service_name}...",
        "info",
        logger_to_use,
        app_settings,
    )

    systemd_reload(app_settings, current_logger=logger_to_use)
    run_elevated_command(
        ["systemctl", "enable", service_name],
        app_settings,
        current_logger=logger_to_use,
    )
    run_elevated_command(
        ["systemctl", "restart", service_name],
        app_settings,
        current_logger=logger_to_use,
    )

    try:
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Checking status of {service_name}...",
            "info",
            logger_to_use,
            app_settings,
        )
        run_elevated_command(
            ["systemctl", "status", service_name, "--no-pager", "-l"],
            app_settings,
            current_logger=logger_to_use,
            check=True,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} {service_name} is active.",
            "success",
            logger_to_use,
            app_settings,
        )
    except CalledProcessError:
        log_map_server(
            f"{symbols.get('critical', '🔥')} {service_name} FAILED to start. Aborting OSRM configuration.",
            "critical",
            logger_to_use,
            app_settings,
        )
        raise
    except Exception as e:
        log_map_server(
            f"{symbols.get('critical', '🔥')} Unexpected error while checking {service_name} status: {e}",
            "critical",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        raise

    log_map_server(
        f"{symbols.get('success', '✅')} {service_name} activation process completed.",
        "success",
        logger_to_use,
        app_settings,
    )


def configure_osrm_services(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> bool:
    """
    Finds all processed OSRM regions and creates and activates systemd services for them.

    This function orchestrates the configuration of all OSRM services based on the
    processed data found in the specified directory.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    processed_dir = Path(app_settings.osrm_data.processed_dir)

    log_map_server(
        f"{symbols.get('step', '➡️')} Starting OSRM service configuration...",
        "info",
        logger_to_use,
        app_settings,
    )

    if not processed_dir.is_dir():
        log_map_server(
            f"{symbols.get('warning', '!')} Processed OSRM data directory not found at {processed_dir}. Nothing to configure.",
            "warning",
            logger_to_use,
            app_settings,
        )
        return True

    processed_regions = [
        d.name for d in processed_dir.iterdir() if d.is_dir()
    ]

    if not processed_regions:
        log_map_server(
            f"{symbols.get('warning', '!')} No processed OSRM regions found in {processed_dir}. No services to create.",
            "warning",
            logger_to_use,
            app_settings,
        )
        return True

    all_successful = True
    for region_name_key in processed_regions:
        try:
            log_map_server(
                f"--- Configuring OSRM service for region: {region_name_key} ---",
                "info",
                logger_to_use,
                app_settings,
            )
            create_osrm_routed_service_file(
                region_name_key, app_settings, logger_to_use
            )
            activate_osrm_routed_service(
                region_name_key, app_settings, logger_to_use
            )
        except FileNotFoundError as e:
            log_map_server(
                f"{symbols.get('error', '❌')} Skipping configuration for {region_name_key}: {e}",
                "error",
                logger_to_use,
                app_settings,
            )
            all_successful = False
            continue
        except Exception as e:
            log_map_server(
                f"{symbols.get('critical', '🔥')} Unexpected error configuring {region_name_key}: {e}",
                "critical",
                logger_to_use,
                app_settings,
                exc_info=True,
            )
            all_successful = False

    if all_successful:
        log_map_server(
            f"{symbols.get('success', '✅')} All OSRM services configured successfully.",
            "success",
            logger_to_use,
            app_settings,
        )
    else:
        log_map_server(
            f"{symbols.get('error', '❌')} Some OSRM services failed to configure. Please check the logs.",
            "error",
            logger_to_use,
            app_settings,
        )

    return all_successful
