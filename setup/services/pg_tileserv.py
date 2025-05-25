# setup/services/pg_tileserv.py
"""
Handles the setup and configuration of pg_tileserv.
"""
import logging
import os
import shutil
import tempfile
from typing import Optional
import subprocess
from setup import config
from setup.command_utils import (
    run_command,
    run_elevated_command,
    log_map_server,
    command_exists,
)
from ..helpers import systemd_reload

module_logger = logging.getLogger(__name__)


def pg_tileserv_setup(
    current_logger: Optional[logging.Logger] = None,
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Setting up pg_tileserv...",
        "info",
        logger_to_use,
    )

    pg_tileserv_bin_path = "/usr/local/bin/pg_tileserv"
    if not command_exists(pg_tileserv_bin_path):
        log_map_server(
            f"{config.SYMBOLS['info']} pg_tileserv not found at {pg_tileserv_bin_path}, downloading from {config.PG_TILESERV_BINARY_LOCATION}...",
            "info",
            logger_to_use,
        )
        temp_zip_path = ""
        temp_dir_extract = ""  # Changed variable name to avoid conflict
        try:
            # Create a temporary file to download the zip to
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".zip", prefix="pgtileserv_dl_"
            ) as temp_file_obj:
                temp_zip_path = temp_file_obj.name

            # Download as current user to the temporary file path
            run_command(
                [
                    "wget",
                    config.PG_TILESERV_BINARY_LOCATION,
                    "-O",
                    temp_zip_path,
                ],
                current_logger=logger_to_use,
            )

            # Create a temporary directory to extract the zip into
            temp_dir_extract = tempfile.mkdtemp(prefix="pgtileserv_extract_")
            # Unzip, -j junks paths, ensuring pg_tileserv binary is directly in temp_dir_extract
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

            # Move the binary to the final destination with elevation
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
                f"{config.SYMBOLS['success']} pg_tileserv installed to {pg_tileserv_bin_path}.",
                "success",
                logger_to_use,
            )
        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to download or install pg_tileserv: {e}",
                "error",
                logger_to_use,
            )
            raise  # Propagate error to stop the step
        finally:
            if temp_zip_path and os.path.exists(temp_zip_path):
                os.unlink(temp_zip_path)
            if temp_dir_extract and os.path.isdir(temp_dir_extract):
                shutil.rmtree(
                    temp_dir_extract
                )  # Clean up extraction directory
    else:
        log_map_server(
            f"{config.SYMBOLS['info']} pg_tileserv already exists at {pg_tileserv_bin_path}.",
            "info",
            logger_to_use,
        )

    # Check pg_tileserv version (run as current user)
    try:
        run_command(
            [pg_tileserv_bin_path, "--version"], current_logger=logger_to_use
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['warning']} Could not determine pg_tileserv version: {e}",
            "warning",
            logger_to_use,
        )

    pg_tileserv_config_dir = "/etc/pg_tileserv"
    pg_tileserv_config_file = os.path.join(
        pg_tileserv_config_dir, "config.toml"
    )
    run_elevated_command(
        ["mkdir", "-p", pg_tileserv_config_dir], current_logger=logger_to_use
    )

    # Ensure PGPASSWORD is not the default if used in connection string, or dev override is active
    db_url_for_config = f"postgresql://{config.PGUSER}:{config.PGPASSWORD}@{config.PGHOST}:{config.PGPORT}/{config.PGDATABASE}"
    if (
        config.PGPASSWORD == config.PGPASSWORD_DEFAULT
        and not config.DEV_OVERRIDE_UNSAFE_PASSWORD
    ):
        log_map_server(
            f"{config.SYMBOLS['warning']} Default PGPASSWORD detected and dev override not active. Using placeholder in pg_tileserv config. Service may not connect.",
            "warning",
            logger_to_use,
        )
        db_url_for_config = f"postgresql://{config.PGUSER}:YOUR_PASSWORD_HERE@{config.PGHOST}:{config.PGPORT}/{config.PGDATABASE}"

    pg_tileserv_config_content = f"""# pg_tileserv config generated by script V{config.SCRIPT_HASH}
HttpHost = "0.0.0.0"
HttpPort = 7800
DatabaseURL = "{db_url_for_config}" # Check pg_tileserv docs for exact key: DatabaseUrl or DatabaseURL
DefaultMaxFeatures = 10000
PublishSchemas = "public,gtfs" 
URIPrefix = "/vector"
DevelopmentMode = false
AllowFunctionSources = true
"""
    try:
        run_elevated_command(
            ["tee", pg_tileserv_config_file],
            cmd_input=pg_tileserv_config_content,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Created/Updated {pg_tileserv_config_file}",
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

    pgtileserv_system_user = "pgtileservuser"
    try:
        run_command(
            ["id", pgtileserv_system_user],
            check=True,
            capture_output=True,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['info']} System user {pgtileserv_system_user} already exists.",
            "info",
            logger_to_use,
        )
    except subprocess.CalledProcessError:
        log_map_server(
            f"{config.SYMBOLS['info']} Creating system user {pgtileserv_system_user}...",
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
                "--user-group",
                pgtileserv_system_user,  # Creates group with same name
            ],
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Created system user {pgtileserv_system_user}.",
            "success",
            logger_to_use,
        )

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

    pg_tileserv_service_file = "/etc/systemd/system/pg_tileserv.service"
    pg_tileserv_service_content = f"""[Unit]
Description=pg_tileserv - Vector Tile Server for PostGIS
Wants=network-online.target postgresql.service
After=network-online.target postgresql.service

[Service]
User={pgtileserv_system_user}
Group={pgtileserv_system_user}
ExecStart={pg_tileserv_bin_path} --config {pg_tileserv_config_file}
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=pg_tileserv
PrivateTmp=true
ProtectSystem=full
NoNewPrivileges=true

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
            f"{config.SYMBOLS['success']} Created/Updated {pg_tileserv_service_file}",
            "success",
            logger_to_use,
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to write pg_tileserv systemd service file: {e}",
            "error",
            logger_to_use,
        )
        raise

    systemd_reload(current_logger=logger_to_use)
    run_elevated_command(
        ["systemctl", "enable", "pg_tileserv.service"],
        current_logger=logger_to_use,
    )  # Add .service suffix
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
