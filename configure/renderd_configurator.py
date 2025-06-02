# configure/renderd_configurator.py
# -*- coding: utf-8 -*-
"""
Handles configuration of Renderd, including its .conf file,
and service activation.
"""

import logging
import os
import subprocess  # Ensure subprocess is imported for subprocess.CompletedProcess type hint
from pathlib import Path
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
) -> str:  # Return type is str
    """Determines the Mapnik plugins directory. Uses override from app_settings if provided."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols

    # 1. Check for override path
    mapnik_plugins_dir_override_val = (
        app_settings.renderd.mapnik_plugins_dir_override
    )
    if mapnik_plugins_dir_override_val is not None:
        override_path_str = str(mapnik_plugins_dir_override_val)
        if Path(override_path_str).is_dir():
            log_map_server(
                f"{symbols.get('info', 'ℹ️')} Using Mapnik plugins directory from override: {override_path_str}",
                "info",
                logger_to_use,
                app_settings,
            )
            return override_path_str  # This is str
        else:
            log_map_server(
                f"{symbols.get('warning', '!')} Override Mapnik plugins directory '{override_path_str}' not found or not a directory. Trying auto-detection.",
                "warning",
                logger_to_use,
                app_settings,
            )

    # 2. Default logic if no valid override: Try mapnik-config
    default_debian_plugins_dir = (
        "/usr/lib/mapnik/input/"  # Generic for Mapnik 3.x/4.x
    )

    if command_exists("mapnik-config"):
        try:
            mapnik_config_res: subprocess.CompletedProcess = run_command(
                ["mapnik-config", "--input-plugins"],
                app_settings,
                capture_output=True,
                check=True,  # Will raise CalledProcessError if command fails
                current_logger=logger_to_use,
            )
            stdout_val: Optional[str] = mapnik_config_res.stdout
            if stdout_val is not None:
                resolved_dir: str = stdout_val.strip()
                if (
                    resolved_dir and Path(resolved_dir).is_dir()
                ):  # Check non-empty and is directory
                    log_map_server(
                        f"{symbols.get('info', 'ℹ️')} Determined Mapnik plugins directory via mapnik-config: {resolved_dir}",
                        "info",
                        logger_to_use,
                        app_settings,
                    )
                    return resolved_dir  # This is str
                else:
                    log_map_server(
                        f"{symbols.get('warning', '!')} mapnik-config provided non-existent or empty directory path: '{resolved_dir}'. Trying default Debian path.",
                        "warning",
                        logger_to_use,
                        app_settings,
                    )
            else:  # stdout_val is None
                log_map_server(
                    f"{symbols.get('warning', '!')} mapnik-config command succeeded but produced no output. Trying default Debian path.",
                    "warning",
                    logger_to_use,
                    app_settings,
                )
        except (
            Exception
        ) as e_mapnik:  # Catches CalledProcessError or other issues
            log_map_server(
                f"{symbols.get('warning', '!')} mapnik-config failed or error during processing ({e_mapnik}). Trying default Debian path: {default_debian_plugins_dir}",
                "warning",
                logger_to_use,
                app_settings,
            )

    # 3. Try default Debian path if mapnik-config failed or didn't yield a valid path
    if Path(default_debian_plugins_dir).is_dir():
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Using default Mapnik plugins directory: {default_debian_plugins_dir}",
            "info",
            logger_to_use,
            app_settings,
        )
        return default_debian_plugins_dir  # This is str

    # 4. Fallback if everything else fails
    final_fallback_dir = "/usr/lib/mapnik/input/"  # A common older default
    log_map_server(
        f"{symbols.get('critical', '🔥')} Mapnik plugins directory not found via override, mapnik-config, or common defaults. Fallback to: {final_fallback_dir}. Renderd may fail if this path is incorrect.",
        "critical",  # Changed from critical to warning as it's a fallback
        logger_to_use,
        app_settings,
    )
    return final_fallback_dir  # This is str


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

    systemd_reload(app_settings, current_logger=logger_to_use)
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
    )  # Removed check=False as status should ideally be checked, run_elevated_command logs errors
    log_map_server(
        f"{symbols.get('success', '✅')} Renderd service activated.",
        "success",
        logger_to_use,
        app_settings,
    )
