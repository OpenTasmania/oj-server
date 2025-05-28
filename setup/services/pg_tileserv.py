# osm/setup/services/pg_tileserv.py
# -*- coding: utf-8 -*-
"""
Handles the setup and configuration of pg_tileserv.

This module includes functions to download and install the pg_tileserv binary
if it's not already present, create its configuration file, set up a dedicated
system user, configure necessary PostgreSQL roles and permissions, and
establish a systemd service for pg_tileserv.
"""

import logging
import os
import shutil
import subprocess
import tempfile
from typing import Optional

from setup import config
from setup.command_utils import (
    command_exists,
    log_map_server,
    run_command,
    run_elevated_command,
)
from setup.helpers import systemd_reload
from setup.state_manager import get_current_script_hash

module_logger = logging.getLogger(__name__)


def pg_tileserv_setup(
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Set up and configure pg_tileserv.

    - Downloads pg_tileserv binary if not found.
    - Creates configuration directory and file (`config.toml`).
    - Creates a system user (`pgtileserv_user`) for running the service.
    - Sets file permissions for the binary and configuration.
    - Ensures a corresponding PostgreSQL role exists with LOGIN and CONNECT
      permissions.
    - Creates and enables a systemd service file for pg_tileserv.

    Args:
        current_logger: Optional logger instance to use. If None,
                        the module's default logger is used.

    Raises:
        Exception: If critical steps like downloading or configuring
                   pg_tileserv fail.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Setting up pg_tileserv...",
        "info",
        logger_to_use,
    )
    script_hash_for_comments = (
        get_current_script_hash(logger_instance=logger_to_use)
        or "UNKNOWN_HASH"
    )
    pg_tileserv_bin_path = "/usr/local/bin/pg_tileserv"

    # Download and install pg_tileserv if not present
    if not command_exists(pg_tileserv_bin_path):
        log_map_server(
            f"{config.SYMBOLS['info']} pg_tileserv not found at "
            f"{pg_tileserv_bin_path}, downloading from "
            f"{config.PG_TILESERV_BINARY_LOCATION}...",
            "info",
            logger_to_use,
        )
        temp_zip_path = ""
        temp_dir_extract = ""
        try:
            # Create a temporary file to download the zip to.
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".zip", prefix="pgtileserv_dl_"
            ) as temp_file_obj:
                temp_zip_path = temp_file_obj.name

            # Download as current user to the temporary file path.
            run_command(
                [
                    "wget",
                    config.PG_TILESERV_BINARY_LOCATION,
                    "-O",
                    temp_zip_path,
                ],
                current_logger=logger_to_use,
            )

            # Create a temporary directory to extract the zip into.
            temp_dir_extract = tempfile.mkdtemp(prefix="pgtileserv_extract_")
            # Unzip, -j junks paths, ensuring pg_tileserv binary is
            # directly in temp_dir_extract.
            run_command(
                [
                    "unzip",
                    "-j",
                    temp_zip_path,
                    "pg_tileserv",
                    "-d",
                    temp_dir_extract,
                ],
                current_logger=logger_to_use,
            )

            # Move the binary to the final destination with elevation.
            source_binary_path = os.path.join(temp_dir_extract, "pg_tileserv")
            run_elevated_command(
                ["mv", source_binary_path, pg_tileserv_bin_path],
                current_logger=logger_to_use,
            )
            run_elevated_command(
                ["chmod", "+x", pg_tileserv_bin_path],
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{config.SYMBOLS['success']} pg_tileserv installed to "
                f"{pg_tileserv_bin_path}.",
                "success",
                logger_to_use,
            )
        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to download or install "
                f"pg_tileserv: {e}",
                "error",
                logger_to_use,
            )
            raise  # Propagate error to stop the step.
        finally:
            if temp_zip_path and os.path.exists(temp_zip_path):
                os.unlink(temp_zip_path)
            if temp_dir_extract and os.path.isdir(temp_dir_extract):
                shutil.rmtree(temp_dir_extract)
    else:
        log_map_server(
            f"{config.SYMBOLS['info']} pg_tileserv already exists at "
            f"{pg_tileserv_bin_path}.",
            "info",
            logger_to_use,
        )

    # Check pg_tileserv version (run as current user).
    try:
        run_command(
            [pg_tileserv_bin_path, "--version"], current_logger=logger_to_use
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['warning']} Could not determine pg_tileserv "
            f"version: {e}",
            "warning",
            logger_to_use,
        )

    # Create configuration directory and file
    pg_tileserv_config_dir = "/etc/pg_tileserv"
    pg_tileserv_config_file = os.path.join(
        pg_tileserv_config_dir, "config.toml"
    )
    run_elevated_command(
        ["mkdir", "-p", pg_tileserv_config_dir], current_logger=logger_to_use
    )

    # Construct DatabaseURL for pg_tileserv config
    # Ensure PGPASSWORD is not the default if used in connection string,
    # or if dev override is active.
    db_url_for_config = (
        f"postgresql://{config.PGUSER}:{config.PGPASSWORD}@"
        f"{config.PGHOST}:{config.PGPORT}/{config.PGDATABASE}"
    )
    if (
        config.PGPASSWORD == config.PGPASSWORD_DEFAULT
        and not config.DEV_OVERRIDE_UNSAFE_PASSWORD
    ):
        log_map_server(
            f"{config.SYMBOLS['warning']} Default PGPASSWORD detected and dev "
            "override not active. Using placeholder in pg_tileserv config. "
            "Service may not connect.",
            "warning",
            logger_to_use,
        )
        db_url_for_config = (
            f"postgresql://{config.PGUSER}:YOUR_PASSWORD_HERE@"
            f"{config.PGHOST}:{config.PGPORT}/{config.PGDATABASE}"
        )

    pg_tileserv_config_content = f"""# pg_tileserv config generated by script V{script_hash_for_comments}
HttpHost = "0.0.0.0"
HttpPort = 7800
DatabaseURL = "{db_url_for_config}" # pg_tileserv key name for connection string
DefaultMaxFeatures = 10000
PublishSchemas = "public,gtfs" # Schemas to publish
URIPrefix = "/vector"          # Base URI for tile requests
DevelopmentMode = false        # Set to true for more verbose logging if needed
AllowFunctionSources = true    # Allow functions to be sources for tiles
"""
    try:
        run_elevated_command(
            ["tee", pg_tileserv_config_file],
            cmd_input=pg_tileserv_config_content,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Created/Updated "
            f"{pg_tileserv_config_file}",
            "success",
            logger_to_use,
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to write pg_tileserv config: {e}",
            "error",
            logger_to_use,
        )
        raise

    # Create system user for pg_tileserv
    pgtileserv_system_user = "pgtileserv_user"
    try:
        # Check if user already exists
        run_command(
            ["id", pgtileserv_system_user],
            check=True,
            capture_output=True,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['info']} System user {pgtileserv_system_user} "
            "already exists.",
            "info",
            logger_to_use,
        )
    except subprocess.CalledProcessError:
        # User does not exist, create them
        log_map_server(
            f"{config.SYMBOLS['info']} Creating system user "
            f"{pgtileserv_system_user}...",
            "info",
            logger_to_use,
        )
        run_elevated_command(
            [
                "useradd",
                "--system",
                "--shell",
                "/usr/sbin/nologin",
                "--home-dir",
                "/var/empty",
                "--user-group",  # Creates group with same name
                pgtileserv_system_user,
            ],
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Created system user "
            f"{pgtileserv_system_user}.",
            "success",
            logger_to_use,
        )

    # Set ownership and permissions for pg_tileserv files
    run_elevated_command(
        [
            "chown",
            f"{pgtileserv_system_user}:{pgtileserv_system_user}",
            pg_tileserv_bin_path,
        ],
        current_logger=logger_to_use,
    )
    run_elevated_command(
        ["chmod", "750", pg_tileserv_bin_path], current_logger=logger_to_use
    )
    run_elevated_command(
        [
            "chown",
            f"{pgtileserv_system_user}:{pgtileserv_system_user}",
            pg_tileserv_config_file,
        ],
        current_logger=logger_to_use,
    )
    run_elevated_command(
        ["chmod", "640", pg_tileserv_config_file],
        current_logger=logger_to_use,
    )

    # Ensure PostgreSQL role for pg_tileserv exists
    pg_db_port = config.PGPORT
    pgtileserv_db_role = (
        pgtileserv_system_user  # Use the same name for simplicity
    )
    app_db_name = config.PGDATABASE

    log_map_server(
        f"{config.SYMBOLS['info']} Ensuring PostgreSQL role "
        f"'{pgtileserv_db_role}' exists with LOGIN permission...",
        "info",
        logger_to_use,
    )
    # SQL command to create the role with LOGIN permission.
    sql_create_role_cmd_list = [
        "sudo",
        "-u",
        "postgres",
        "psql",
        "-p",
        pg_db_port,
        "-d",
        "postgres",  # Connect to 'postgres' db to create roles
        "-c",
        f"CREATE ROLE {pgtileserv_db_role} WITH LOGIN;",
    ]
    try:
        log_map_server(
            f"{config.SYMBOLS['gear']} Attempting to create PostgreSQL role "
            f"'{pgtileserv_db_role}' with LOGIN permission...",
            "info",
            logger_to_use,
        )
        run_command(
            sql_create_role_cmd_list,
            capture_output=True,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Successfully created PostgreSQL role "
            f"'{pgtileserv_db_role}' with LOGIN.",
            "success",
            logger_to_use,
        )
    except subprocess.CalledProcessError as e:
        if (
            hasattr(e, "stderr")
            and e.stderr
            and "already exists" in e.stderr.lower()
        ):
            log_map_server(
                f"{config.SYMBOLS['info']} PostgreSQL role "
                f"'{pgtileserv_db_role}' already exists. Ensuring LOGIN "
                "permission...",
                "info",
                logger_to_use,
            )
            # If role exists, try to grant LOGIN permission (idempotent)
            sql_alter_role_login_cmd_list = [
                "sudo",
                "-u",
                "postgres",
                "psql",
                "-p",
                pg_db_port,
                "-d",
                "postgres",
                "-c",
                f"ALTER ROLE {pgtileserv_db_role} WITH LOGIN;",
            ]
            try:
                run_command(
                    sql_alter_role_login_cmd_list,
                    capture_output=True,
                    current_logger=logger_to_use,
                )
                log_map_server(
                    f"{config.SYMBOLS['success']} Ensured LOGIN permission for "
                    f"existing role '{pgtileserv_db_role}'.",
                    "success",
                    logger_to_use,
                )
            except subprocess.CalledProcessError as alter_e:
                err_msg_alter = (
                    alter_e.stderr.strip()
                    if hasattr(alter_e, "stderr") and alter_e.stderr
                    else f"Unknown psql error during ALTER ROLE {pgtileserv_db_role} LOGIN."
                )
                log_map_server(
                    f"{config.SYMBOLS['warning']} Failed to grant LOGIN to "
                    f"existing role '{pgtileserv_db_role}'. Error: {err_msg_alter}",
                    "warning",
                    logger_to_use,
                )
        else:
            err_msg_create = (
                e.stderr.strip()
                if hasattr(e, "stderr") and e.stderr
                else f"Unknown psql error during CREATE ROLE {pgtileserv_db_role}."
            )
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to create PostgreSQL role "
                f"'{pgtileserv_db_role}'. Error: {err_msg_create}",
                "error",
                logger_to_use,
            )
            # Consider raising an error here if role creation is critical

    # Grant CONNECT permission on the application database
    sql_grant_connect_cmd_list = [
        "sudo",
        "-u",
        "postgres",
        "psql",
        "-p",
        pg_db_port,
        "-d",
        app_db_name,  # Connect to the specific app database
        "-c",
        f"GRANT CONNECT ON DATABASE {app_db_name} TO {pgtileserv_db_role};",
    ]
    try:
        log_map_server(
            f"{config.SYMBOLS['gear']} Attempting to grant CONNECT on "
            f"database '{app_db_name}' to role '{pgtileserv_db_role}'...",
            "info",
            logger_to_use,
        )
        run_command(
            sql_grant_connect_cmd_list,
            capture_output=True,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Successfully granted CONNECT on "
            f"database '{app_db_name}' to role '{pgtileserv_db_role}'.",
            "success",
            logger_to_use,
        )
    except subprocess.CalledProcessError as e:
        err_msg_grant = (
            e.stderr.strip()
            if hasattr(e, "stderr") and e.stderr
            else f"Unknown psql error during GRANT CONNECT to {pgtileserv_db_role} on {app_db_name}."
        )
        log_map_server(
            f"{config.SYMBOLS['warning']} Failed to grant CONNECT on database "
            f"'{app_db_name}' to role '{pgtileserv_db_role}'. "
            f"Error: {err_msg_grant}",
            "warning",
            logger_to_use,
        )

    # Create systemd service file for pg_tileserv
    pg_tileserv_service_file = "/etc/systemd/system/pg_tileserv.service"
    # Construct DATABASE_URL for the service environment.
    # This uses the main application's DB credentials.
    # Consider if pg_tileserv should have its own less-privileged DB user.
    database_url_for_service = (
        f"postgresql://{config.PGUSER}:{config.PGPASSWORD}@"
        f"{config.PGHOST}:{config.PGPORT}/{config.PGDATABASE}"
    )
    pg_tileserv_service_content = f"""[Unit]
Description=pg_tileserv - Vector Tile Server for PostGIS
Wants=network-online.target postgresql.service
After=network-online.target postgresql.service

[Service]
User={pgtileserv_system_user}
Group={pgtileserv_system_user}
# Pass database connection string via environment variable for security.
Environment="DATABASE_URL={database_url_for_service}"
# Ensure the chosen user can read /etc/pg_tileserv/config.toml
ExecStart={pg_tileserv_bin_path} --config {pg_tileserv_config_file}
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=pg_tileserv
# Security hardening options (consider uncommenting and testing)
# PrivateTmp=true
# ProtectSystem=full
# NoNewPrivileges=true
# Resource limits (adjust as needed)
# MemoryAccounting=true
# MemoryHigh=2G # Example: Soft limit
# MemoryMax=3G  # Example: Hard limit

[Install]
WantedBy=multi-user.target
"""
    try:
        run_elevated_command(
            ["tee", pg_tileserv_service_file],
            cmd_input=pg_tileserv_service_content,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Created/Updated "
            f"{pg_tileserv_service_file}",
            "success",
            logger_to_use,
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to write pg_tileserv systemd "
            f"service file: {e}",
            "error",
            logger_to_use,
        )
        raise

    # Reload systemd, enable and restart pg_tileserv service
    systemd_reload(current_logger=logger_to_use)
    run_elevated_command(
        ["systemctl", "enable", "pg_tileserv.service"],
        current_logger=logger_to_use,
    )
    run_elevated_command(
        ["systemctl", "restart", "pg_tileserv.service"],
        current_logger=logger_to_use,
    )
    log_map_server(
        f"{config.SYMBOLS['info']} pg_tileserv service status:",
        "info",
        logger_to_use,
    )
    run_elevated_command(
        ["systemctl", "status", "pg_tileserv.service", "--no-pager", "-l"],
        current_logger=logger_to_use,
    )
    log_map_server(
        f"{config.SYMBOLS['success']} pg_tileserv setup completed.",
        "success",
        logger_to_use,
    )
