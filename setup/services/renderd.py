# setup/services/renderd.py
# -*- coding: utf-8 -*-
"""
Handles the setup and configuration of Renderd for raster tile generation.

This module configures Renderd, which works with Mapnik to render raster map
tiles. It creates the `renderd.conf` file, sets up necessary directories
and permissions, and establishes a systemd service for Renderd.
"""

import logging
import os
from typing import Optional

from setup import config
from setup.command_utils import (
    run_command,
    run_elevated_command,
    log_map_server,
    command_exists,
)
from setup.helpers import systemd_reload # For reloading systemd after service file changes

module_logger = logging.getLogger(__name__)


def renderd_setup(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Set up and configure the Renderd tile rendering daemon.

    - Determines Mapnik plugins directory.
    - Creates `renderd.conf` with appropriate settings.
    - Creates a systemd service file for `renderd`.
    - Sets up required directories (`/var/lib/mod_tile`, `/var/run/renderd`)
      and their permissions.
    - Enables and restarts the `renderd` service.

    Args:
        current_logger: Optional logger instance to use. If None,
                        the module's default logger is used.

    Raises:
        Exception: If critical steps like writing configuration files or
                   setting up the systemd service fail.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Setting up renderd for raster tiles...",
        "info",
        logger_to_use,
    )

    # Determine the number of CPU cores for Renderd threads.
    num_cores = os.cpu_count() or 2  # Default to 2 if os.cpu_count() is None

    # Determine Mapnik plugins directory.
    mapnik_plugins_dir_resolved = "/usr/lib/mapnik/3.0/input/"  # Default path
    if command_exists("mapnik-config"):
        try:
            mapnik_config_res = run_command(
                ["mapnik-config", "--input-plugins"],
                capture_output=True,
                check=True, # Expect mapnik-config to succeed
                current_logger=logger_to_use,
            )
            # Output of mapnik-config --input-plugins is the directory path.
            mapnik_plugins_dir_resolved = mapnik_config_res.stdout.strip()
            log_map_server(
                f"{config.SYMBOLS['info']} Determined Mapnik plugins "
                f"directory: {mapnik_plugins_dir_resolved}",
                "info",
                logger_to_use,
            )
        except Exception as e_mapnik:
            log_map_server(
                f"{config.SYMBOLS['warning']} Could not determine Mapnik "
                "plugins directory via mapnik-config "
                f"({e_mapnik}). Using fallback: {mapnik_plugins_dir_resolved}",
                "warning",
                logger_to_use,
            )
    else:
        log_map_server(
            f"{config.SYMBOLS['warning']} 'mapnik-config' command not found. "
            f"Using fallback Mapnik plugins directory: "
            f"{mapnik_plugins_dir_resolved}",
            "warning",
            logger_to_use,
        )

    renderd_conf_path = "/etc/renderd.conf"
    # Use VM_IP_OR_DOMAIN for HOST if it's not the default placeholder,
    # otherwise use localhost for local rendering.
    renderd_host = (
        config.VM_IP_OR_DOMAIN
        if config.VM_IP_OR_DOMAIN != config.VM_IP_OR_DOMAIN_DEFAULT
        else "localhost"
    )

    # Content for renderd.conf
    renderd_conf_content = f"""[renderd]
num_threads={num_cores * 2}
tile_dir=/var/lib/mod_tile
stats_file=/var/run/renderd/renderd.stats
font_dir_recurse=1

[mapnik]
plugins_dir={mapnik_plugins_dir_resolved}
font_dir=/usr/share/fonts/
font_dir_recurse=1

[default]
URI=/hot/
XML=/usr/local/share/maps/style/openstreetmap-carto/mapnik.xml
HOST={renderd_host}
TILESIZE=256
# MAXZOOM=20 ; Maximum zoom level, usually defined in the style XML itself.
"""
    try:
        run_elevated_command(
            ["tee", renderd_conf_path], # Overwrites or creates the file
            cmd_input=renderd_conf_content,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Created/Updated {renderd_conf_path}",
            "success",
            logger_to_use,
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to write {renderd_conf_path}: {e}",
            "error",
            logger_to_use,
        )
        raise # This configuration is critical.

    # Systemd service file for Renderd
    renderd_service_path = "/etc/systemd/system/renderd.service"
    renderd_service_content = f"""[Unit]
Description=Map tile rendering daemon (renderd)
Documentation=man:renderd(8)
After=network.target auditd.service postgresql.service # Ensure DB is up if style needs it

[Service]
User=www-data
Group=www-data
# Systemd will create /var/run/renderd with appropriate permissions.
RuntimeDirectory=renderd
RuntimeDirectoryMode=0755
# The -f flag keeps renderd in the foreground, standard for systemd services.
ExecStart=/usr/bin/renderd -f -c {renderd_conf_path}
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=renderd
# Security hardening options (consider enabling these after testing)
# PrivateTmp=true
# ProtectSystem=full
# NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
"""
    try:
        run_elevated_command(
            ["tee", renderd_service_path], # Overwrites or creates the file
            cmd_input=renderd_service_content,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Created/Updated {renderd_service_path}",
            "success",
            logger_to_use,
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to write {renderd_service_path}: {e}",
            "error",
            logger_to_use,
        )
        raise # Service file is critical.

    # Create necessary directories and set permissions
    log_map_server(
        f"{config.SYMBOLS['gear']} Creating necessary directories and "
        "setting permissions for renderd...",
        "info",
        logger_to_use,
    )
    # Tile cache directory for mod_tile
    run_elevated_command(
        ["mkdir", "-p", "/var/lib/mod_tile"], current_logger=logger_to_use
    )
    # Runtime directory for renderd (also handled by RuntimeDirectory in service)
    run_elevated_command(
        ["mkdir", "-p", "/var/run/renderd"], current_logger=logger_to_use
    )
    run_elevated_command(
        ["chown", "-R", "www-data:www-data", "/var/lib/mod_tile"],
        current_logger=logger_to_use,
    )
    run_elevated_command(
        ["chown", "-R", "www-data:www-data", "/var/run/renderd"],
        current_logger=logger_to_use,
    )

    # Reload systemd, enable and restart renderd service
    systemd_reload(current_logger=logger_to_use)
    log_map_server(
        f"{config.SYMBOLS['gear']} Enabling and restarting renderd service...",
        "info",
        logger_to_use,
    )
    run_elevated_command(
        ["systemctl", "enable", "renderd.service"],
        current_logger=logger_to_use,
    )
    run_elevated_command(
        ["systemctl", "restart", "renderd.service"],
        current_logger=logger_to_use,
    )
    log_map_server(
        f"{config.SYMBOLS['info']} renderd service status:",
        "info",
        logger_to_use,
    )
    run_elevated_command(
        ["systemctl", "status", "renderd.service", "--no-pager", "-l"],
        current_logger=logger_to_use,
    )
    log_map_server(
        f"{config.SYMBOLS['success']} Renderd setup complete.",
        "success",
        logger_to_use,
    )