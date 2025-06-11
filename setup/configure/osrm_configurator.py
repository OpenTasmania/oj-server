# configure/osrm_configurator.py
# -*- coding: utf-8 -*-
"""
Handles configuration of OSRM services, primarily setting up and activating
systemd services for osrm-routed for processed regions.
"""

import logging
from datetime import datetime
from os import cpu_count, environ
from pathlib import Path
from subprocess import CalledProcessError
from typing import Optional

from common.command_utils import log_map_server, run_elevated_command
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

    try:
        postgis_cfg = app_settings.pg
        osm_data_cfg = app_settings.osrm_data
    except AttributeError as e:
        log_map_server(
            f"{symbols.get('critical', '🔥')} Missing required PostGIS or OSRM data configuration in app_settings: {e}",
            "critical",
            logger_to_use,
            app_settings,
        )
        return False

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

    osm_carto_dir = (
        static_config.OSM_PROJECT_ROOT / "external" / "openstreetmap-carto"
    )
    osm_carto_lua_candidates = [
        osm_carto_dir / "openstreetmap-carto-flex.lua",
        osm_carto_dir / "openstreetmap-carto.lua",
    ]
    osm_carto_lua_found = None
    for lua_candidate in osm_carto_lua_candidates:
        if lua_candidate.is_file():
            osm_carto_lua_found = str(lua_candidate)
            break

    if osm_carto_lua_found is None:
        log_map_server(
            f"{symbols.get('error', '❌')} OSM-Carto Lua script not found at expected location ({osm_carto_dir}). Cannot proceed with osm2pgsql.",
            "error",
            logger_to_use,
            app_settings,
        )
        return False
    log_map_server(
        f"{symbols.get('info', 'ℹ️')} Found OSM-Carto Lua script: {osm_carto_lua_found}",
        "info",
        logger_to_use,
        app_settings,
    )

    env_vars = environ.copy()
    if postgis_cfg.password:
        env_vars["PGPASSWORD"] = postgis_cfg.password
    else:
        log_map_server(
            f"{symbols.get('warning', '!')} PostgreSQL password not configured in app_settings.postgis_db. osm2pgsql may fail without PGPASSWORD or a ~/.pgpass entry.",
            "warning",
            logger_to_use,
            app_settings,
        )

    osm2pgsql_cmd = [
        "osm2pgsql",
        "--verbose",
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
        "--tag-transform-script",
        osm_carto_lua_found,
        "--style",
        osm_carto_lua_found,
        "--output=flex",
        "-C",
        str(getattr(osm_data_cfg, "osm2pgsql_cache_mb", 20000)),
        "--number-processes",
        str(cpu_count()),
        "--flat-nodes",
        str(
            Path(osm_data_cfg.base_dir)
            / f"flat-nodes-{datetime.now().strftime('%Y-%m-%d')}.bin"
        ),
        pbf_full_path,
    ]

    try:
        run_elevated_command(
            osm2pgsql_cmd,
            app_settings,
            current_logger=logger_to_use,
            capture_output=True,
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
            f"{symbols.get('critical', '🔥')} osm2pgsql import for {Path(pbf_full_path).name} FAILED with exit code {e.returncode}. Output: {e.stderr.decode()}",
            "critical",
            logger_to_use,
            app_settings,
        )
        return False
    except Exception as e:
        log_map_server(
            f"{symbols.get('critical', '🔥')} Unexpected error during osm2pgsql import for {Path(pbf_full_path).name}: {e}",
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
