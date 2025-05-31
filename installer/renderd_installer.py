# setup/renderd_installer.py
# -*- coding: utf-8 -*-
"""
Handles setup of Renderd: package checks, directory creation,
and systemd service file definition.
"""
import logging
from typing import Optional

from common.command_utils import (
    log_map_server,
    run_elevated_command,
    check_package_installed
)
from setup import config  # For SYMBOLS
from setup.state_manager import get_current_script_hash

module_logger = logging.getLogger(__name__)

RENDERD_USER = "www-data"
RENDERD_GROUP = "www-data"
TILE_CACHE_DIR = "/var/lib/mod_tile"
RENDERD_RUN_DIR = "/var/run/renderd"  # Also specified as RuntimeDirectory in service
RENDERD_CONF_PATH = "/etc/renderd.conf"  # Path to be used in service file


def ensure_renderd_packages_installed(current_logger: Optional[logging.Logger] = None) -> None:
    """Confirms Renderd and mapnik-utils packages are installed."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['info']} Checking Renderd package installation status...", "info", logger_to_use)

    packages_to_check = ["renderd", "mapnik-utils"]  # mapnik-utils for mapnik-config
    all_found = True
    for pkg in packages_to_check:
        if check_package_installed(pkg, current_logger=logger_to_use):
            log_map_server(f"{config.SYMBOLS['success']} Package '{pkg}' is installed.", "debug", logger_to_use)
        else:
            log_map_server(
                f"{config.SYMBOLS['error']} Package '{pkg}' is NOT installed. "
                "This should have been handled by core prerequisite installation.", "error", logger_to_use
            )
            all_found = False
    if not all_found:
        raise EnvironmentError("One or more essential Renderd/Mapnik packages are missing.")
    log_map_server(f"{config.SYMBOLS['success']} Renderd related packages confirmed.", "success", logger_to_use)


def create_renderd_directories(current_logger: Optional[logging.Logger] = None) -> None:
    """Creates necessary directories for Renderd and sets permissions."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Creating directories for Renderd...", "info", logger_to_use)

    dirs_to_create = {
        TILE_CACHE_DIR: (RENDERD_USER, RENDERD_GROUP),
        RENDERD_RUN_DIR: (RENDERD_USER, RENDERD_GROUP)
    }

    for dir_path, (owner, group) in dirs_to_create.items():
        run_elevated_command(["mkdir", "-p", dir_path], current_logger=logger_to_use)
        run_elevated_command(["chown", "-R", f"{owner}:{group}", dir_path], current_logger=logger_to_use)
        # Permissions can be more specific if needed, e.g., 755 for dirs
        run_elevated_command(["chmod", "-R", "u+rwX,g+rX,o+rX", dir_path],
                             current_logger=logger_to_use)  # Example: 755 like
        log_map_server(
            f"{config.SYMBOLS['success']} Directory '{dir_path}' created/permissions set for {owner}:{group}.",
            "success", logger_to_use)


def create_renderd_systemd_service_file(current_logger: Optional[logging.Logger] = None) -> None:
    """Creates the systemd service file for Renderd."""
    logger_to_use = current_logger if current_logger else module_logger
    script_hash = get_current_script_hash(logger_instance=logger_to_use) or "UNKNOWN_HASH"
    log_map_server(f"{config.SYMBOLS['step']} Creating Renderd systemd service file...", "info", logger_to_use)

    renderd_service_path = "/etc/systemd/system/renderd.service"
    renderd_service_content = f"""[Unit]
Description=Map tile rendering daemon (renderd)
Documentation=man:renderd(8)
# Ensure DB is up if style needs it (PostgreSQL might be a soft dependency for some styles)
After=network.target auditd.service postgresql.service

[Service]
User={RENDERD_USER}
Group={RENDERD_GROUP}
# Systemd will create /var/run/renderd with appropriate permissions if RuntimeDirectory is used.
# However, we create it manually in create_renderd_directories to ensure www-data owns it.
# If RuntimeDirectory is used, ensure its mode allows www-data write if renderd itself doesn't chown.
# RuntimeDirectory=renderd 
# RuntimeDirectoryMode=0755
ExecStart=/usr/bin/renderd -f -c {RENDERD_CONF_PATH}
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
# File created by script V{script_hash}
"""
    try:
        run_elevated_command(
            ["tee", renderd_service_path],
            cmd_input=renderd_service_content,
            current_logger=logger_to_use
        )
        log_map_server(f"{config.SYMBOLS['success']} Created/Updated {renderd_service_path}", "success", logger_to_use)
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['error']} Failed to write {renderd_service_path}: {e}", "error", logger_to_use)
        raise