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
    Determine the next available port not currently in use within the region port map.

    This function iterates over the pre-configured region port map to identify the next
    free port. It starts at a default base port and increments until an available port
    not conflicting with existing ports is found.

    Parameters:
        app_settings (AppSettings): The application settings containing OSRM service
            configuration, including the default host port and the mapping of regions
            to their respective ports.
        logger (logging.Logger): A logger for capturing diagnostic and debug information.

    Returns:
        int: The next available port number starting from the default host port.
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
    """
    Creates or updates a systemd service file for an OSRM routed service for a particular region.

    This function generates and writes a systemd service file for running the OSRM routed
    server for a specified region. The service file is created using a provided template
    and fills in placeholders related to the region, OSRM configuration, and system
    settings. If necessary, it also assigns a port for the service, either from preconfigured
    values or by determining the next available port.

    Parameters:
        region_name_key (str): Unique key for the region, such as "Australia_Tasmania_Hobart".
        app_settings (AppSettings): Application settings instance containing configuration
                                     details for OSRM and system settings.
        current_logger (Optional[logging.Logger]): Logger instance for logging activities.
                                                   If None, a predefined module-level logger
                                                   is used.

    Raises:
        FileNotFoundError: If the required OSRM data file for the specified region is not
                           found.
        KeyError: If a required placeholder key is missing in the systemd service template.
        Exception: For any other errors occurring while generating or writing the service file.
    """
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
    """
    Imports a PBF (Protocolbuffer Binary Format) file into a PostGIS database using the
    osm2pgsql tool. The function validates the existence of the required PBF file and
    OSM-Carto Lua script, constructs the osm2pgsql command, and executes it. Logs are
    generated at each step to track the progress and results of the import operation.

    The function also allows specifying a logger to use for logging messages. If no
    logger is provided, a default module-level logger is used. Additionally, it
    utilizes environment variables to securely pass the database password to osm2pgsql.

    Parameters:
    pbf_full_path: str
        Full path to the PBF file to be imported.

    app_settings: AppSettings
        Settings configuration containing PostGIS connection details, OSRM (Open
        Source Routing Machine) data settings, and symbols for logging.

    current_logger: Optional[logging.Logger]
        Logger instance to be used for logging messages related to the import process.
        If None, a default logger is used.

    Returns:
    bool
        True if the import is successful, False otherwise.

    Raises:
    CalledProcessError
        Raised when the osm2pgsql command returns a non-zero exit status.

    Exception
        Raised for any other unexpected errors encountered during the import process.
    """
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

    osm_carto_dir = (
        static_config.OSM_PROJECT_ROOT / "external" / "openstreetmap-carto"
    )
    osm_carto_lua_script = osm_carto_dir / "openstreetmap-carto.lua"

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
        f"--style={osm_carto_lua_script}",
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
    """
    Activates and ensures the proper startup and status of an OSRM (Open Source Routing
    Machine) routed service corresponding to a specific region. This involves enabling,
    restarting, and verifying the service using system commands, with appropriate logging
    throughout the process.

    Parameters
    ----------
    region_name_key : str
        The key corresponding to the region-specific service name.
    app_settings : AppSettings
        An instance of `AppSettings` containing configuration and symbols needed during the
        process.
    current_logger : Optional[logging.Logger], optional
        A custom logger to use for logging. If not provided, the module's default logger
        will be used.

    Raises
    ------
    CalledProcessError
        Raised if the systemctl command indicates the service has failed to start.
    Exception
        Raised for unexpected errors during service status verification, logging the issue
        with traceback information when available.
    """
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
    Configures the OSRM services based on the specified application settings and
    logged information. The function handles configuration for all processed
    regions listed in the OSRM data directory, logging progress, warnings, and
    errors encountered during the process. It verifies the presence of required
    directories and files, then activates corresponding OSRM routed services.

    Arguments:
        app_settings (AppSettings): Application settings containing information
            about OSRM service configuration, including paths and symbols used
            for logging.
        current_logger (Optional[logging.Logger]): Logger instance to use for
            logging. If not provided, a default logger (`module_logger`) is used.

    Returns:
        bool: True if all OSRM services are successfully configured, otherwise
            False in case of any errors during the process.
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
