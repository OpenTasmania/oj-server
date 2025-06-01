# configure/apache_configurator.py
# -*- coding: utf-8 -*-
"""
Handles configuration of Apache webserver with mod_tile.
"""
import logging
import os
from typing import Optional

from common.command_utils import (
    elevated_command_exists,
    log_map_server,
    run_elevated_command,
)
from common.file_utils import backup_file
from common.system_utils import systemd_reload
# Import static_config for fixed paths or truly static values
from setup import config as static_config
# Import AppSettings for type hinting
from setup.config_models import (  # For default comparison
    VM_IP_OR_DOMAIN_DEFAULT,
    AppSettings,
)
from setup.state_manager import get_current_script_hash

module_logger = logging.getLogger(__name__)

# These paths are standard Apache paths, less likely to be runtime configurable
# but could be if needed (e.g. app_settings.apache.ports_conf_path)
PORTS_CONF_PATH = "/etc/apache2/ports.conf"
MOD_TILE_CONF_AVAILABLE_PATH = "/etc/apache2/conf-available/mod_tile.conf"
APACHE_TILES_SITE_CONF_AVAILABLE_PATH = (
    "/etc/apache2/sites-available/001-tiles.conf"
)


def configure_apache_ports(
        app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Modifies Apache's listening port using app_settings.apache.listen_port."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    target_listen_port = app_settings.apache.listen_port

    log_map_server(
        f"{symbols.get('step', '➡️')} Configuring Apache listening ports to {target_listen_port}...",
        "info",
        logger_to_use,
        app_settings,
    )

    if not os.path.exists(PORTS_CONF_PATH):
        try:
            run_elevated_command(
                ["test", "-f", PORTS_CONF_PATH],
                app_settings,
                check=True,
                capture_output=True,
                current_logger=logger_to_use,
            )
        except Exception:
            log_map_server(
                f"{symbols.get('critical', '🔥')} Apache ports configuration file {PORTS_CONF_PATH} not found.",
                "critical",
                logger_to_use,
                app_settings,
            )
            raise FileNotFoundError(f"{PORTS_CONF_PATH} not found.")

    if backup_file(
            PORTS_CONF_PATH, app_settings, current_logger=logger_to_use
    ):
        # Replace "Listen 80" with "Listen <target_listen_port>"
        # And "Listen [::]:80" with "Listen [::]:<target_listen_port>"
        # Using f-strings for sed expressions requires careful quoting if port could have special chars (not an issue for int)
        sed_cmd_ipv4 = [
            "sed",
            "-i.bak_ports_sed",
            f"s/^Listen 80$/Listen {target_listen_port}/",
            PORTS_CONF_PATH,
        ]
        sed_cmd_ipv6 = [
            "sed",
            "-i",
            f"s/^Listen \\[::\\]:80$/Listen [::]:{target_listen_port}/",
            PORTS_CONF_PATH,
        ]

        run_elevated_command(
            sed_cmd_ipv4, app_settings, current_logger=logger_to_use
        )
        run_elevated_command(
            sed_cmd_ipv6,
            app_settings,
            current_logger=logger_to_use,
            check=False,
        )  # Allow to fail if IPv6 line not present

        log_map_server(
            f"{symbols.get('success', '✅')} Apache configured to listen on port {target_listen_port} (original backed up).",
            "success",
            logger_to_use,
            app_settings,
        )


def create_mod_tile_config(
        app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Creates /etc/apache2/conf-available/mod_tile.conf using template from app_settings."""
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
        f"{symbols.get('step', '➡️')} Creating mod_tile Apache configuration from template...",
        "info",
        logger_to_use,
        app_settings,
    )

    mod_tile_template = app_settings.apache.mod_tile_conf_template
    format_vars = {
        "script_hash": script_hash,
        "mod_tile_request_timeout": app_settings.apache.mod_tile_request_timeout,
        "mod_tile_missing_request_timeout": app_settings.apache.mod_tile_missing_request_timeout,
        "mod_tile_max_load_old": app_settings.apache.mod_tile_max_load_old,
        "mod_tile_max_load_missing": app_settings.apache.mod_tile_max_load_missing,
    }

    try:
        mod_tile_conf_content_final = mod_tile_template.format(**format_vars)
        run_elevated_command(
            ["tee", MOD_TILE_CONF_AVAILABLE_PATH],
            app_settings,
            cmd_input=mod_tile_conf_content_final,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Created/Updated {MOD_TILE_CONF_AVAILABLE_PATH}",
            "success",
            logger_to_use,
            app_settings,
        )
    except KeyError as e_key:
        log_map_server(
            f"{symbols.get('error', '❌')} Missing placeholder key '{e_key}' for mod_tile.conf template. Check config.yaml/models.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to write {MOD_TILE_CONF_AVAILABLE_PATH}: {e}",
            "error",
            logger_to_use,
            app_settings,
        )
        raise


def create_apache_tile_site_config(
        app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Creates the Apache site configuration for serving tiles using template from app_settings."""
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
        f"{symbols.get('step', '➡️')} Creating Apache tile serving site configuration from template...",
        "info",
        logger_to_use,
        app_settings,
    )

    # Determine ServerName and ServerAdmin for the template
    # VM_IP_OR_DOMAIN_DEFAULT imported from config_models for comparison
    server_name_val = app_settings.vm_ip_or_domain
    if (
            server_name_val == VM_IP_OR_DOMAIN_DEFAULT
    ):  # Compare with imported default
        server_name_val = (
            "tiles.localhost"  # Default if using placeholder domain
        )

    admin_email_val = f"webmaster@{app_settings.vm_ip_or_domain}"
    if app_settings.vm_ip_or_domain == VM_IP_OR_DOMAIN_DEFAULT:
        admin_email_val = "webmaster@localhost"

    tile_site_template = app_settings.apache.tile_site_template
    format_vars = {
        "script_hash": script_hash,
        "apache_listen_port": app_settings.apache.listen_port,
        "server_name_apache": server_name_val,
        "admin_email_apache": admin_email_val,
    }

    try:
        apache_tiles_site_content_final = tile_site_template.format(
            **format_vars
        )
        run_elevated_command(
            ["tee", APACHE_TILES_SITE_CONF_AVAILABLE_PATH],
            app_settings,
            cmd_input=apache_tiles_site_content_final,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Created/Updated {APACHE_TILES_SITE_CONF_AVAILABLE_PATH}",
            "success",
            logger_to_use,
            app_settings,
        )
    except KeyError as e_key:
        log_map_server(
            f"{symbols.get('error', '❌')} Missing placeholder key '{e_key}' for Apache tile site template. Check config.yaml/models.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to write {APACHE_TILES_SITE_CONF_AVAILABLE_PATH}: {e}",
            "error",
            logger_to_use,
            app_settings,
        )
        raise


def manage_apache_modules_and_sites(
        app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Enables necessary Apache configurations, modules, and sites."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('step', '➡️')} Enabling Apache modules and site configurations...",
        "info",
        logger_to_use,
        app_settings,
    )

    run_elevated_command(
        ["a2enconf", "mod_tile"], app_settings, current_logger=logger_to_use
    )
    for mod in ["expires", "headers"]:  # These module names are static
        run_elevated_command(
            ["a2enmod", mod], app_settings, current_logger=logger_to_use
        )

    tile_site_name = os.path.basename(
        APACHE_TILES_SITE_CONF_AVAILABLE_PATH
    ).replace(".conf", "")
    run_elevated_command(
        ["a2ensite", tile_site_name],
        app_settings,
        current_logger=logger_to_use,
    )

    default_site_enabled_path = "/etc/apache2/sites-enabled/000-default.conf"
    # elevated_command_exists now takes app_settings
    if elevated_command_exists(
            f"test -L {default_site_enabled_path}",
            app_settings,
            current_logger=logger_to_use,
    ):
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Disabling default Apache site (000-default)...",
            "info",
            logger_to_use,
            app_settings,
        )
        run_elevated_command(
            ["a2dissite", "000-default"],
            app_settings,
            current_logger=logger_to_use,
        )
    else:
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Default Apache site not enabled or not found. Skipping disable.",
            "info",
            logger_to_use,
            app_settings,
        )
    log_map_server(
        f"{symbols.get('success', '✅')} Apache modules and sites configured.",
        "success",
        logger_to_use,
        app_settings,
    )


def activate_apache_service(
        app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Reloads systemd, restarts and enables the Apache service."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('step', '➡️')} Activating Apache service...",
        "info",
        logger_to_use,
        app_settings,
    )

    systemd_reload(
        app_settings, current_logger=logger_to_use
    )  # Pass app_settings
    run_elevated_command(
        ["systemctl", "restart", "apache2.service"],
        app_settings,
        current_logger=logger_to_use,
    )
    run_elevated_command(
        ["systemctl", "enable", "apache2.service"],
        app_settings,
        current_logger=logger_to_use,
    )

    log_map_server(
        f"{symbols.get('info', 'ℹ️')} Apache service status:",
        "info",
        logger_to_use,
        app_settings,
    )
    run_elevated_command(
        ["systemctl", "status", "apache2.service", "--no-pager", "-l"],
        app_settings,
        current_logger=logger_to_use,
    )
    log_map_server(
        f"{symbols.get('success', '✅')} Apache service activated.",
        "success",
        logger_to_use,
        app_settings,
    )
