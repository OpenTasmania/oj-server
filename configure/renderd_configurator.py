# configure/renderd_configurator.py
# -*- coding: utf-8 -*-
"""
Handles configuration of Renderd, including its .conf file,
and service activation.
"""
import logging
import os
from pathlib import Path  # Changed from os.path import isdir
from typing import Optional

from common.command_utils import (
    command_exists,
    log_map_server,
    run_command,
    run_elevated_command,
)
from common.system_utils import get_current_script_hash, systemd_reload
from setup import config as static_config  # For OSM_PROJECT_ROOT
from setup.config_models import (  # For type hinting and default comparison
    VM_IP_OR_DOMAIN_DEFAULT,
    AppSettings,
)

module_logger = logging.getLogger(__name__)

# RENDERD_CONF_PATH is now a static system path, the content is templated
RENDERD_CONF_FILE_SYSTEM_PATH = "/etc/renderd.conf"
RENDERD_SYSTEM_GROUP = (
    "www-data"  # Group for config file readability, matches installer
)


def get_mapnik_plugin_dir(
        app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> str:
    """Determines the Mapnik plugins directory. Uses override from app_settings if provided."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols

    if app_settings.renderd.mapnik_plugins_dir_override:
        override_path = str(app_settings.renderd.mapnik_plugins_dir_override)
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Using Mapnik plugins directory from override: {override_path}",
            "info",
            logger_to_use,
            app_settings,
        )
        return override_path

    # Default logic if no override
    # This path can vary by system/Mapnik version. Consider making it more robust or a required config.
    # For Debian Bookworm with mapnik 4.0 from default repos, this path is common.
    # However, mapnik-config is the more reliable way if mapnik-utils is installed.
    default_debian_plugins_dir = (
        "/usr/lib/mapnik/input/"  # Generic for Mapnik 3.x/4.x
    )
    # More specific for potential Mapnik 4.0 if other versions coexist.
    # default_debian_plugins_dir_mapnik4 = "/usr/lib/x86_64-linux-gnu/mapnik/4.0/input/"

    if command_exists("mapnik-config"):
        try:
            mapnik_config_res = run_command(
                ["mapnik-config", "--input-plugins"],
                app_settings,  # Pass app_settings
                capture_output=True,
                check=True,
                current_logger=logger_to_use,
            )
            resolved_dir = mapnik_config_res.stdout.strip()
            if Path(resolved_dir).is_dir():
                log_map_server(
                    f"{symbols.get('info', 'ℹ️')} Determined Mapnik plugins directory via mapnik-config: {resolved_dir}",
                    "info",
                    logger_to_use,
                    app_settings,
                )
                return resolved_dir
            else:
                log_map_server(
                    f"{symbols.get('warning', '!')} mapnik-config provided non-existent directory: {resolved_dir}. Trying default.",
                    "warning",
                    logger_to_use,
                    app_settings,
                )
        except Exception as e_mapnik:
            log_map_server(
                f"{symbols.get('warning', '!')} mapnik-config failed ({e_mapnik}). Trying default: {default_debian_plugins_dir}",
                "warning",
                logger_to_use,
                app_settings,
            )

    if Path(default_debian_plugins_dir).is_dir():
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Using default Mapnik plugins directory: {default_debian_plugins_dir}",
            "info",
            logger_to_use,
            app_settings,
        )
        return default_debian_plugins_dir

    # Fallback if everything else fails - this might lead to renderd errors if incorrect.
    final_fallback_dir = "/usr/lib/mapnik/input/"  # A common older default
    log_map_server(
        f"{symbols.get('critical', '🔥')} Mapnik plugins directory not found via mapnik-config or common defaults. Fallback to: {final_fallback_dir}. Renderd may fail.",
        "critical",
        logger_to_use,
        app_settings,
    )
    return final_fallback_dir


def create_renderd_conf_file(
        app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Creates the /etc/renderd.conf file using template from app_settings."""
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

    log_map_server(
        f"{symbols.get('step', '➡️')} Creating {RENDERD_CONF_FILE_SYSTEM_PATH} from template...",
        "info",
        logger_to_use,
        app_settings,
    )

    # Calculate num_threads for renderd
    num_threads_val = 0
    if app_settings.renderd.num_threads_multiplier > 0:
        cpu_c = os.cpu_count()
        if cpu_c:
            num_threads_val = int(
                cpu_c * app_settings.renderd.num_threads_multiplier
            )
        else:  # Fallback if cpu_count() is None
            num_threads_val = int(
                2 * app_settings.renderd.num_threads_multiplier
            )  # e.g. 2*2=4
        if num_threads_val == 0:
            num_threads_val = 2  # Ensure at least 2 if multiplier is very small leading to 0
    # If num_threads_multiplier is 0 or less, renderd itself might use an auto-detected value.
    # The template uses {num_threads_renderd}, so we pass the calculated value or a suitable default like "0" for auto.
    # For now, if multiplier is 0, it will result in num_threads_val = 0.
    # Renderd's own default is often 4 if NUMTHREADS is 0 in its C code.
    # Let's ensure it's at least 1 if calculated, or use "0" for full auto.
    # If app_settings.renderd.num_threads_multiplier is 0, pass "0" to template for auto.
    # If > 0, pass calculated.
    num_threads_renderd_str = (
        str(num_threads_val)
        if app_settings.renderd.num_threads_multiplier > 0
        else "0"
    )

    mapnik_plugins_dir_val = get_mapnik_plugin_dir(
        app_settings, logger_to_use
    )

    renderd_host_val = app_settings.vm_ip_or_domain
    if (
            renderd_host_val == VM_IP_OR_DOMAIN_DEFAULT
    ):  # Compare with imported default
        renderd_host_val = "localhost"

    renderd_conf_template_str = app_settings.renderd.renderd_conf_template
    format_vars = {
        "renderd_conf_path": RENDERD_CONF_FILE_SYSTEM_PATH,
        "script_hash": script_hash,
        "num_threads_renderd": num_threads_renderd_str,
        "renderd_tile_cache_dir": str(app_settings.renderd.tile_cache_dir),
        "renderd_run_dir": str(app_settings.renderd.run_dir),
        "mapnik_plugins_dir": mapnik_plugins_dir_val,
        "renderd_uri_path_segment": app_settings.renderd.uri_path_segment,
        "mapnik_xml_stylesheet_path": str(
            app_settings.renderd.mapnik_xml_stylesheet_path
        ),
        "renderd_host": renderd_host_val,
    }

    try:
        renderd_conf_content_final = renderd_conf_template_str.format(
            **format_vars
        )
        run_elevated_command(
            ["tee", RENDERD_CONF_FILE_SYSTEM_PATH],
            app_settings,
            cmd_input=renderd_conf_content_final,
            current_logger=logger_to_use,
        )
        # Config file should be readable by the renderd user (e.g., www-data)
        run_elevated_command(
            [
                "chown",
                f"root:{RENDERD_SYSTEM_GROUP}",
                RENDERD_CONF_FILE_SYSTEM_PATH,
            ],
            app_settings,
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["chmod", "640", RENDERD_CONF_FILE_SYSTEM_PATH],
            app_settings,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Created/Updated and secured {RENDERD_CONF_FILE_SYSTEM_PATH}",
            "success",
            logger_to_use,
            app_settings,
        )
    except KeyError as e_key:
        log_map_server(
            f"{symbols.get('error', '❌')} Missing placeholder key '{e_key}' for renderd.conf template. Check config.yaml/models.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to write or set permissions for {RENDERD_CONF_FILE_SYSTEM_PATH}: {e}",
            "error",
            logger_to_use,
            app_settings,
        )
        raise


def activate_renderd_service(
        app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Reloads systemd, enables and restarts the renderd service."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('step', '➡️')} Activating Renderd systemd service...",
        "info",
        logger_to_use,
        app_settings,
    )

    systemd_reload(
        app_settings, current_logger=logger_to_use
    )  # Pass app_settings
    run_elevated_command(
        ["systemctl", "enable", "renderd.service"],
        app_settings,
        current_logger=logger_to_use,
    )
    run_elevated_command(
        ["systemctl", "restart", "renderd.service"],
        app_settings,
        current_logger=logger_to_use,
    )

    log_map_server(
        f"{symbols.get('info', 'ℹ️')} Renderd service status:",
        "info",
        logger_to_use,
        app_settings,
    )
    run_elevated_command(
        ["systemctl", "status", "renderd.service", "--no-pager", "-l"],
        app_settings,
        current_logger=logger_to_use,
    )
    log_map_server(
        f"{symbols.get('success', '✅')} Renderd service activated.",
        "success",
        logger_to_use,
        app_settings,
    )
