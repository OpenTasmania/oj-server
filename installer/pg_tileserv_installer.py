# installer/pg_tileserv_installer.py
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
from pathlib import Path  # Added Path
from typing import Optional

from common.command_utils import (
    command_exists,
    log_map_server,
    run_command,
    run_elevated_command,
)
from common.system_utils import get_current_script_hash
from setup import config as static_config
from setup.config_models import AppSettings

module_logger = logging.getLogger(__name__)


# PG_TILESERV_BIN_PATH and PGTILESERV_SYSTEM_USER are now sourced from app_settings.pg_tileserv


def download_and_install_pg_tileserv_binary(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Downloads and installs pg_tileserv binary if not found, using paths from app_settings."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols

    pgts_settings = app_settings.pg_tileserv
    binary_install_path = str(pgts_settings.binary_install_path)
    binary_url = str(
        pgts_settings.binary_url
    )  # Ensure it's a string for wget

    log_map_server(
        f"{symbols.get('step', '➡️')} Checking for pg_tileserv binary at {binary_install_path}...",
        "info",
        logger_to_use,
        app_settings,
    )

    if not command_exists(
        binary_install_path
    ):  # Checks if file exists and is executable
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} pg_tileserv not found, downloading from {binary_url}...",
            "info",
            logger_to_use,
            app_settings,
        )
        temp_zip_path = ""
        temp_dir_extract = ""
        try:
            # Ensure parent directory for binary exists
            Path(binary_install_path).parent.mkdir(
                parents=True, exist_ok=True
            )

            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".zip", prefix="pgtileserv_dl_"
            ) as temp_file_obj:
                temp_zip_path = temp_file_obj.name

            run_command(
                ["wget", binary_url, "-O", temp_zip_path],
                app_settings,
                current_logger=logger_to_use,
            )
            temp_dir_extract = tempfile.mkdtemp(prefix="pgtileserv_extract_")
            # Unzip just the 'pg_tileserv' binary, ignoring paths in zip (-j)
            run_command(
                [
                    "unzip",
                    "-j",
                    temp_zip_path,
                    "pg_tileserv",
                    "-d",
                    temp_dir_extract,
                ],
                app_settings,
                current_logger=logger_to_use,
            )

            source_binary_in_extract = os.path.join(
                temp_dir_extract, "pg_tileserv"
            )
            if not os.path.exists(source_binary_in_extract):
                raise FileNotFoundError(
                    f"pg_tileserv binary not found in downloaded zip at {source_binary_in_extract}"
                )

            run_elevated_command(
                ["mv", source_binary_in_extract, binary_install_path],
                app_settings,
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{symbols.get('success', '✅')} pg_tileserv installed to {binary_install_path}.",
                "success",
                logger_to_use,
                app_settings,
            )
        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '❌')} Failed to download or install pg_tileserv: {e}",
                "error",
                logger_to_use,
                app_settings,
                exc_info=True,
            )
            raise
        finally:
            if temp_zip_path and os.path.exists(temp_zip_path):
                os.unlink(temp_zip_path)
            if temp_dir_extract and os.path.isdir(temp_dir_extract):
                shutil.rmtree(temp_dir_extract)
    else:
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} pg_tileserv already exists at {binary_install_path}.",
            "info",
            logger_to_use,
            app_settings,
        )

    try:
        run_command(
            [binary_install_path, "--version"],
            app_settings,
            current_logger=logger_to_use,
            capture_output=True,
        )
    except Exception as e:
        log_map_server(
            f"{symbols.get('warning', '!')} Could not determine pg_tileserv version: {e}",
            "warning",
            logger_to_use,
            app_settings,
        )


def create_pg_tileserv_system_user(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Creates the system user for running pg_tileserv service, from app_settings."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    system_user = app_settings.pg_tileserv.system_user

    log_map_server(
        f"{symbols.get('step', '➡️')} Setting up system user '{system_user}' for pg_tileserv...",
        "info",
        logger_to_use,
        app_settings,
    )
    try:
        # Check if user exists
        run_command(
            ["id", system_user],
            app_settings,
            check=True,
            capture_output=True,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} System user {system_user} already exists.",
            "info",
            logger_to_use,
            app_settings,
        )
    except subprocess.CalledProcessError:  # User does not exist
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Creating system user {system_user}...",
            "info",
            logger_to_use,
            app_settings,
        )
        # Standard options for a service user
        run_elevated_command(
            [
                "useradd",
                "--system",
                "--shell",
                "/usr/sbin/nologin",
                "--home-dir",
                "/var/empty",
                "--user-group",
                system_user,
            ],
            app_settings,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Created system user {system_user}.",
            "success",
            logger_to_use,
            app_settings,
        )


def setup_pg_tileserv_binary_permissions(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Sets ownership and permissions for the pg_tileserv binary using paths from app_settings."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    pgts_settings = app_settings.pg_tileserv
    binary_path = str(pgts_settings.binary_install_path)
    system_user = (
        pgts_settings.system_user
    )  # Group assumed to be same as user by useradd --user-group

    log_map_server(
        f"{symbols.get('step', '➡️')} Setting permissions for pg_tileserv binary: {binary_path}...",
        "info",
        logger_to_use,
        app_settings,
    )

    if not os.path.exists(binary_path):
        log_map_server(
            f"{symbols.get('error', '❌')} pg_tileserv binary not found at {binary_path}. Cannot set permissions.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise FileNotFoundError(
            f"{binary_path} not found for permission setup."
        )

    run_elevated_command(
        ["chown", f"{system_user}:{system_user}", binary_path],
        app_settings,
        current_logger=logger_to_use,
    )
    run_elevated_command(
        ["chmod", "750", binary_path],
        app_settings,
        current_logger=logger_to_use,
    )  # Executable for owner and group
    log_map_server(
        f"{symbols.get('success', '✅')} Permissions set for {binary_path}.",
        "success",
        logger_to_use,
        app_settings,
    )


def create_pg_tileserv_systemd_service_file(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Creates the systemd service file for pg_tileserv using template from app_settings."""
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

    pgts_settings = app_settings.pg_tileserv
    service_file_path = (
        "/etc/systemd/system/pg_tileserv.service"  # Standard system path
    )
    config_file_full_path = str(
        Path(pgts_settings.config_dir) / pgts_settings.config_filename
    )

    log_map_server(
        f"{symbols.get('step', '➡️')} Creating pg_tileserv systemd service file at {service_file_path} from template...",
        "info",
        logger_to_use,
        app_settings,
    )

    systemd_template = pgts_settings.systemd_template
    format_vars = {
        "script_hash": script_hash,
        "pg_tileserv_system_user": pgts_settings.system_user,
        "pg_tileserv_system_group": pgts_settings.system_user,  # Assumes group is same as user
        "pg_tileserv_binary_path": str(pgts_settings.binary_install_path),
        "pg_tileserv_config_file_path_systemd": config_file_full_path,
    }

    try:
        pg_tileserv_service_content_final = systemd_template.format(
            **format_vars
        )
        run_elevated_command(
            ["tee", service_file_path],
            app_settings,
            cmd_input=pg_tileserv_service_content_final,
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
            f"{symbols.get('error', '❌')} Missing placeholder key '{e_key}' for pg_tileserv systemd template. Check config.yaml/models.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to write pg_tileserv systemd service file: {e}",
            "error",
            logger_to_use,
            app_settings,
        )
        raise
