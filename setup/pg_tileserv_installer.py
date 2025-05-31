# setup/pg_tileserv_installer.py
# -*- coding: utf-8 -*-
"""
Handles setup of pg_tileserv: binary installation, system user creation,
and systemd service file definition.
"""
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Optional

from common.command_utils import (
    command_exists,
    log_map_server,
    run_command,
    run_elevated_command,
)
from setup import config  # For config vars and SYMBOLS
from setup.state_manager import get_current_script_hash

module_logger = logging.getLogger(__name__)

PG_TILESERV_BIN_PATH = "/usr/local/bin/pg_tileserv"
PGTILESERV_SYSTEM_USER = "pgtileserv_user"


def download_and_install_pg_tileserv_binary(current_logger: Optional[logging.Logger] = None) -> None:
    """Downloads and installs pg_tileserv binary if not found."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Checking for pg_tileserv binary...", "info", logger_to_use)

    if not command_exists(PG_TILESERV_BIN_PATH):
        log_map_server(
            f"{config.SYMBOLS['info']} pg_tileserv not found at {PG_TILESERV_BIN_PATH}, "
            f"downloading from {config.PG_TILESERV_BINARY_LOCATION}...",
            "info",
            logger_to_use,
        )
        temp_zip_path = ""
        temp_dir_extract = ""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip", prefix="pgtileserv_dl_") as temp_file_obj:
                temp_zip_path = temp_file_obj.name

            run_command(
                ["wget", config.PG_TILESERV_BINARY_LOCATION, "-O", temp_zip_path],
                current_logger=logger_to_use
            )
            temp_dir_extract = tempfile.mkdtemp(prefix="pgtileserv_extract_")
            run_command(
                ["unzip", "-j", temp_zip_path, "pg_tileserv", "-d", temp_dir_extract],
                current_logger=logger_to_use
            )
            source_binary_path = os.path.join(temp_dir_extract, "pg_tileserv")
            run_elevated_command(["mv", source_binary_path, PG_TILESERV_BIN_PATH], current_logger=logger_to_use)
            log_map_server(f"{config.SYMBOLS['success']} pg_tileserv installed to {PG_TILESERV_BIN_PATH}.", "success",
                           logger_to_use)
        except Exception as e:
            log_map_server(f"{config.SYMBOLS['error']} Failed to download or install pg_tileserv: {e}", "error",
                           logger_to_use)
            raise
        finally:
            if temp_zip_path and os.path.exists(temp_zip_path):
                os.unlink(temp_zip_path)
            if temp_dir_extract and os.path.isdir(temp_dir_extract):
                shutil.rmtree(temp_dir_extract)
    else:
        log_map_server(f"{config.SYMBOLS['info']} pg_tileserv already exists at {PG_TILESERV_BIN_PATH}.", "info",
                       logger_to_use)

    try:  # Verify version
        run_command([PG_TILESERV_BIN_PATH, "--version"], current_logger=logger_to_use)
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['warning']} Could not determine pg_tileserv version: {e}", "warning",
                       logger_to_use)


def create_pg_tileserv_system_user(current_logger: Optional[logging.Logger] = None) -> None:
    """Creates the system user for running pg_tileserv service."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Setting up system user '{PGTILESERV_SYSTEM_USER}'...", "info",
                   logger_to_use)
    try:
        run_command(["id", PGTILESERV_SYSTEM_USER], check=True, capture_output=True, current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['info']} System user {PGTILESERV_SYSTEM_USER} already exists.", "info",
                       logger_to_use)
    except subprocess.CalledProcessError:
        log_map_server(f"{config.SYMBOLS['info']} Creating system user {PGTILESERV_SYSTEM_USER}...", "info",
                       logger_to_use)
        run_elevated_command(
            ["useradd", "--system", "--shell", "/usr/sbin/nologin", "--home-dir", "/var/empty", "--user-group",
             PGTILESERV_SYSTEM_USER],
            current_logger=logger_to_use
        )
        log_map_server(f"{config.SYMBOLS['success']} Created system user {PGTILESERV_SYSTEM_USER}.", "success",
                       logger_to_use)


def setup_pg_tileserv_binary_permissions(current_logger: Optional[logging.Logger] = None) -> None:
    """Sets ownership and permissions for the pg_tileserv binary."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Setting permissions for pg_tileserv binary...", "info", logger_to_use)

    if not os.path.exists(PG_TILESERV_BIN_PATH):
        log_map_server(
            f"{config.SYMBOLS['error']} pg_tileserv binary not found at {PG_TILESERV_BIN_PATH}. Cannot set permissions.",
            "error", logger_to_use)
        raise FileNotFoundError(f"{PG_TILESERV_BIN_PATH} not found for permission setup.")

    run_elevated_command(
        ["chown", f"{PGTILESERV_SYSTEM_USER}:{PGTILESERV_SYSTEM_USER}", PG_TILESERV_BIN_PATH],
        current_logger=logger_to_use
    )
    run_elevated_command(["chmod", "750", PG_TILESERV_BIN_PATH], current_logger=logger_to_use)
    log_map_server(f"{config.SYMBOLS['success']} Permissions set for {PG_TILESERV_BIN_PATH}.", "success", logger_to_use)


def create_pg_tileserv_systemd_service_file(current_logger: Optional[logging.Logger] = None) -> None:
    """Creates the systemd service file for pg_tileserv."""
    logger_to_use = current_logger if current_logger else module_logger
    script_hash = get_current_script_hash(logger_instance=logger_to_use) or "UNKNOWN_HASH"
    log_map_server(f"{config.SYMBOLS['step']} Creating pg_tileserv systemd service file...", "info", logger_to_use)

    pg_tileserv_service_file = "/etc/systemd/system/pg_tileserv.service"
    pg_tileserv_config_file_path = "/etc/pg_tileserv/config.toml"  # Path defined here for service file

    # DATABASE_URL uses the main application's DB credentials (config.PGUSER)
    database_url_for_service = (
        f"postgresql://{config.PGUSER}:{config.PGPASSWORD}@"
        f"{config.PGHOST}:{config.PGPORT}/{config.PGDATABASE}"
    )
    if config.PGPASSWORD == config.PGPASSWORD_DEFAULT and not config.DEV_OVERRIDE_UNSAFE_PASSWORD:
        log_map_server(
            f"{config.SYMBOLS['warning']} Default PGPASSWORD in use for pg_tileserv service. Service may fail if password is not updated.",
            "warning", logger_to_use)
        # The service might fail if it literally tries to use "yourStrongPasswordHere"
        # Consider how to handle this; maybe the service shouldn't rely on PGPASSWORD env var directly
        # but have it in its config file, which is protected.
        # For now, mirroring original script's behavior where config.toml gets this.

    pg_tileserv_service_content = f"""[Unit]
Description=pg_tileserv - Vector Tile Server for PostGIS
Documentation=https://github.com/CrunchyData/pg_tileserv
Wants=network-online.target postgresql.service
After=network-online.target postgresql.service

[Service]
User={PGTILESERV_SYSTEM_USER}
Group={PGTILESERV_SYSTEM_USER}
# pg_tileserv will read its DB connection from its config file.
# The config file itself can contain DatabaseURL or it can be set via Environment.
# If set via Environment here, it might override the config file.
# Let's ensure the config file is the source of truth for DatabaseURL.
# Environment="DATABASE_URL={database_url_for_service}" # Keep commented if config.toml has it
ExecStart={PG_TILESERV_BIN_PATH} --config {pg_tileserv_config_file_path}
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=pg_tileserv
# Consider security hardening options from original script

[Install]
WantedBy=multi-user.target
# File created by script V{script_hash}
"""
    try:
        run_elevated_command(
            ["tee", pg_tileserv_service_file],
            cmd_input=pg_tileserv_service_content,
            current_logger=logger_to_use
        )
        log_map_server(f"{config.SYMBOLS['success']} Created/Updated {pg_tileserv_service_file}", "success",
                       logger_to_use)
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['error']} Failed to write pg_tileserv systemd service file: {e}", "error",
                       logger_to_use)
        raise