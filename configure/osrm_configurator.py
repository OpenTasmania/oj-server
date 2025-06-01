# configure/osrm_configurator.py
# -*- coding: utf-8 -*-
"""
Handles configuration of OSRM services, primarily setting up and activating
systemd services for osrm-routed for processed regions.
"""
import logging
from pathlib import Path
from typing import Optional

from common.command_utils import log_map_server, run_elevated_command
from common.system_utils import get_current_script_hash, systemd_reload
from setup import config as static_config
from setup.config_models import AppSettings

module_logger = logging.getLogger(__name__)


# OSRM_BASE_PROCESSED_DIR is now app_settings.osrm_data.processed_dir
# OSRM_DOCKER_IMAGE is now app_settings.osrm_service.image_tag
# CONTAINER_RUNTIME_COMMAND is app_settings.container_runtime_command


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

    # Path to the directory on host containing this region's .osrm files (e.g., /opt/osrm_processed_data/Australia_Tasmania_Hobart/)
    host_osrm_data_dir_for_this_region = (
        Path(osrm_data_cfg.processed_dir) / region_name_key
    )
    # The OSRM filename inside the container (relative to its /data_processing mount)
    # OSRM tools use region_name_key as the base, e.g., Australia_Tasmania_Hobart.osrm
    osrm_filename_stem_in_container = region_name_key

    log_map_server(
        f"{symbols.get('step', '➡️')} Creating systemd service file for {service_name} at {service_file_path} from template...",
        "info",
        logger_to_use,
        app_settings,
    )

    # Check if the main .osrm data file exists on host to ensure data processing was successful for this region
    # The actual file might be region_name_key.osrm, region_name_key.hsgr etc.
    # Checking for the base .osrm file is a good indicator.
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

    # Port mapping: Use a configured default host port for now.
    # For multiple regions, a port management strategy is needed.
    # This could involve a dictionary in AppSettings: osrm_service.region_port_map = {"region_key": port}
    # Or incrementing from car_profile_default_host_port.
    # For simplicity here, using the default car profile port.
    host_port_for_this_region = osrm_service_cfg.car_profile_default_host_port
    # A more robust way for multiple regions might be:
    # host_port_for_this_region = osrm_service_cfg.car_profile_default_host_port + index_of_region (if regions are processed in a list)
    # This needs to be coordinated with Nginx config if Nginx proxies to specific ports per region.

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
        # osrm-routed expects the .osrm extension
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


def activate_osrm_routed_service(
    region_name_key: str,  # Unique key for the region
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

    log_map_server(
        f"{symbols.get('info', 'ℹ️')} {service_name} status:",
        "info",
        logger_to_use,
        app_settings,
    )
    run_elevated_command(
        ["systemctl", "status", service_name, "--no-pager", "-l"],
        app_settings,
        current_logger=logger_to_use,
        check=False,
    )  # Allow status to show failure
    log_map_server(
        f"{symbols.get('success', '✅')} {service_name} activation process completed (check status above).",
        "success",
        logger_to_use,
        app_settings,
    )
