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
from setup.config_models import AppSettings

module_logger = logging.getLogger(__name__)


def download_and_install_pg_tileserv_binary(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Downloads and installs the pg_tileserv binary if it is not already available at the specified location.
    The function verifies the presence of the pg_tileserv binary at the given path. If it's missing,
    it downloads the binary from a specified URL, extracts it, and installs it to the provided path.
    Basic validation is done to ensure the downloaded binary is functional.

    Arguments:
        app_settings (AppSettings): The application settings containing configuration details,
            including binary URL and installation path.
        current_logger (Optional[logging.Logger]): Logger to use during the operation.
            If None, a default module-level logger is used.

    Raises:
        FileNotFoundError: Raised if the pg_tileserv binary is not found after extraction.
        Exception: Any exceptions encountered during the download, extraction, or installation process.
    """
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

    if not command_exists(binary_install_path):
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} pg_tileserv not found, downloading from {binary_url}...",
            "info",
            logger_to_use,
            app_settings,
        )
        temp_zip_path = ""
        temp_dir_extract = ""
        try:
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
    """
    Sets up a system user for pg_tileserv.

    This function is responsible for ensuring that a system user required for the
    pg_tileserv service exists on the system. If the user does not exist, it is
    created with appropriate options for a service account.

    Arguments:
        app_settings (AppSettings): The application settings containing system
                                    configurations including user details.
        current_logger (Optional[logging.Logger]): A specific logger to be used.
                                                   If not provided, a default
                                                   module-level logger is used.

    Raises:
        subprocess.CalledProcessError: If there is an error while executing system
                                       commands like 'id' or 'useradd'.
    """
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
    except subprocess.CalledProcessError:
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
    """
    Sets up file permissions for the pg_tileserv binary, ensuring the correct ownership
    and executable permissions are applied for the system user specified in the application
    settings.

    Parameters:
        app_settings (AppSettings): Application settings containing configuration details
            required for setting permissions.
        current_logger (Optional[logging.Logger]): Logger instance to use for logging the
            procedure. If not provided, the module's default logger will be used.

    Raises:
        FileNotFoundError: If the pg_tileserv binary does not exist at the specified binary
            installation path in the application settings.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    pgts_settings = app_settings.pg_tileserv
    binary_path = str(pgts_settings.binary_install_path)
    system_user = pgts_settings.system_user

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
