# configure/nginx_configurator.py
# -*- coding: utf-8 -*-
"""
Handles configuration of Nginx as a reverse proxy for map services.
"""

import logging
import os
import subprocess
from typing import Optional

from common.command_utils import (
    elevated_command_exists,
    log_map_server,
    run_elevated_command,
)
from common.system_utils import get_current_script_hash, systemd_reload
from setup import (
    config as static_config,  # For fixed paths if any, or SCRIPT_VERSION
)
from setup.config_models import (  # For default comparison
    VM_IP_OR_DOMAIN_DEFAULT,
    AppSettings,
)

module_logger = logging.getLogger(__name__)

# Standard Nginx paths
NGINX_SITES_AVAILABLE_DIR = "/etc/nginx/sites-available"
NGINX_SITES_ENABLED_DIR = "/etc/nginx/sites-enabled"


# PROXY_CONF_NAME is now app_settings.nginx.proxy_conf_name_base
# WEBSITE_ROOT_DIR is now app_settings.webapp.root_dir


def create_nginx_proxy_site_config(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Creates the Nginx site configuration file for reverse proxying using template from app_settings."""
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

    proxy_conf_filename = (
        app_settings.nginx.proxy_conf_name_base
    )  # e.g., "transit_proxy"
    # If you want .conf extension to always be there:
    if not proxy_conf_filename.endswith(".conf"):
        # proxy_conf_filename_with_ext = f"{proxy_conf_filename}.conf" # Use this for actual file name if desired
        pass  # For now, assume proxy_conf_name_base is the full filename part

    nginx_conf_path = os.path.join(
        NGINX_SITES_AVAILABLE_DIR, proxy_conf_filename
    )
    log_map_server(
        f"{symbols.get('step', '➡️')} Creating Nginx site configuration: {nginx_conf_path} from template...",
        "info",
        logger_to_use,
        app_settings,
    )

    server_name_val = app_settings.vm_ip_or_domain
    if (
        server_name_val == VM_IP_OR_DOMAIN_DEFAULT
    ):  # Compare with imported default
        server_name_val = "_"  # Catch-all if default example.com is used

    nginx_template = app_settings.nginx.proxy_site_template
    format_vars = {
        "script_hash": script_hash,
        "server_name_nginx": server_name_val,
        "proxy_conf_filename_base": proxy_conf_filename,  # For log file names
        "pg_tileserv_port": app_settings.pg_tileserv.http_port,
        "apache_port": app_settings.apache.listen_port,
        "osrm_port_car": app_settings.osrm_service.car_profile_default_host_port,  # Add other OSRM profiles if needed
        "website_root_dir": app_settings.webapp.root_dir,
    }

    try:
        nginx_conf_content_final = nginx_template.format(**format_vars)
        run_elevated_command(
            ["tee", nginx_conf_path],
            app_settings,
            cmd_input=nginx_conf_content_final,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Created Nginx site configuration: {nginx_conf_path}",
            "success",
            logger_to_use,
            app_settings,
        )
    except KeyError as e_key:
        log_map_server(
            f"{symbols.get('error', '❌')} Missing placeholder key '{e_key}' for Nginx proxy template. Check config.yaml/models.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to write Nginx site configuration {nginx_conf_path}: {e}",
            "error",
            logger_to_use,
            app_settings,
        )
        raise


def manage_nginx_sites(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Enables the new Nginx proxy site and disables the default site."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    proxy_conf_filename = (
        app_settings.nginx.proxy_conf_name_base
    )  # e.g., "transit_proxy"

    log_map_server(
        f"{symbols.get('step', '➡️')} Managing Nginx sites (enabling {proxy_conf_filename}, disabling default)...",
        "info",
        logger_to_use,
        app_settings,
    )

    source_conf_path = os.path.join(
        NGINX_SITES_AVAILABLE_DIR, proxy_conf_filename
    )
    symlink_path = os.path.join(NGINX_SITES_ENABLED_DIR, proxy_conf_filename)

    if not os.path.exists(source_conf_path):
        try:
            run_elevated_command(
                ["test", "-f", source_conf_path],
                app_settings,
                check=True,
                current_logger=logger_to_use,
            )
        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '❌')} Nginx site file {source_conf_path} does not exist. Cannot enable.",
                "error",
                logger_to_use,
                app_settings,
            )
            raise FileNotFoundError(f"{source_conf_path} not found.") from e

    run_elevated_command(
        ["ln", "-sf", source_conf_path, symlink_path],
        app_settings,
        current_logger=logger_to_use,
    )
    log_map_server(
        f"{symbols.get('success', '✅')} Enabled Nginx site '{proxy_conf_filename}'.",
        "success",
        logger_to_use,
        app_settings,
    )

    default_nginx_symlink = os.path.join(NGINX_SITES_ENABLED_DIR, "default")
    try:
        # Check if 'default' symlink exists in sites-enabled
        # elevated_command_exists was refactored
        if elevated_command_exists(
            f"test -L {default_nginx_symlink}",
            app_settings,
            current_logger=logger_to_use,
        ):
            run_elevated_command(
                ["rm", default_nginx_symlink],
                app_settings,
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{symbols.get('info', 'ℹ️')} Disabled default Nginx site.",
                "info",
                logger_to_use,
                app_settings,
            )
        else:
            log_map_server(
                f"{symbols.get('info', 'ℹ️')} Default Nginx site not enabled or symlink not found. Skipping disable.",
                "info",
                logger_to_use,
                app_settings,
            )
    except Exception as e:  # Catch any error during disable, log as warning
        log_map_server(
            f"{symbols.get('warning', '!')} Could not disable default Nginx site (error: {e}). This might be okay.",
            "warning",
            logger_to_use,
            app_settings,
        )


def test_nginx_configuration(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Tests the Nginx configuration for syntax errors."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('step', '➡️')} Testing Nginx configuration (nginx -t)...",
        "info",
        logger_to_use,
        app_settings,
    )
    try:
        run_elevated_command(
            ["nginx", "-t"],
            app_settings,
            current_logger=logger_to_use,
            check=True,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Nginx configuration test successful.",
            "success",
            logger_to_use,
            app_settings,
        )
    except (
        subprocess.CalledProcessError
    ):  # check=True will raise this on failure
        # Error already logged by run_elevated_command
        # log_map_server(f"{symbols.get('error','❌')} Nginx configuration test FAILED. Output: {e.stderr or e.stdout}", "error", logger_to_use, app_settings)
        raise  # Propagate failure, this is critical


def activate_nginx_service(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Reloads systemd, restarts and enables the Nginx service."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('step', '➡️')} Activating Nginx service...",
        "info",
        logger_to_use,
        app_settings,
    )

    systemd_reload(
        app_settings, current_logger=logger_to_use
    )  # Pass app_settings
    run_elevated_command(
        ["systemctl", "restart", "nginx.service"],
        app_settings,
        current_logger=logger_to_use,
    )
    run_elevated_command(
        ["systemctl", "enable", "nginx.service"],
        app_settings,
        current_logger=logger_to_use,
    )

    log_map_server(
        f"{symbols.get('info', 'ℹ️')} Nginx service status:",
        "info",
        logger_to_use,
        app_settings,
    )
    run_elevated_command(
        ["systemctl", "status", "nginx.service", "--no-pager", "-l"],
        app_settings,
        current_logger=logger_to_use,
    )
    log_map_server(
        f"{symbols.get('success', '✅')} Nginx service activated.",
        "success",
        logger_to_use,
        app_settings,
    )
