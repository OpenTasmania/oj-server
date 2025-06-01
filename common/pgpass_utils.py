# common/pgpass_utils.py
# -*- coding: utf-8 -*-
"""
Utility function for setting up the .pgpass file for PostgreSQL.
"""

import getpass
import logging
import os
from typing import List, Optional

from setup.config_models import AppSettings, PGPASSWORD_DEFAULT  # Import AppSettings and specific default
# from setup import config as static_config # For SYMBOLS, if not from app_settings
from .command_utils import log_map_server

module_logger = logging.getLogger(__name__)


def setup_pgpass(
        # Remove individual pg_ params, use app_settings directly
        app_settings: AppSettings,  # Added app_settings
        # pg_password_default is now sourced from config_models
        current_logger: Optional[logging.Logger] = None,
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols

    # Access pg settings via app_settings.pg
    pg_host = app_settings.pg.host
    pg_port = str(app_settings.pg.port)  # Ensure string for file
    pg_database = app_settings.pg.database
    pg_user = app_settings.pg.user
    pg_password = app_settings.pg.password

    # Use imported PGPASSWORD_DEFAULT for comparison
    allow_default_for_dev = app_settings.dev_override_unsafe_password

    can_create_pgpass = False
    if pg_password and pg_password != PGPASSWORD_DEFAULT:
        can_create_pgpass = True
    elif pg_password and pg_password == PGPASSWORD_DEFAULT and allow_default_for_dev:
        log_map_server(
            f"{symbols.get('warning', '')} DEV OVERRIDE: Proceeding with .pgpass creation using the default (unsafe) password.",
            "warning", logger_to_use, app_settings)
        can_create_pgpass = True

    if not can_create_pgpass:
        log_map_server(
            f"{symbols.get('info', '')} PGPASSWORD is not set, is default (and dev override is not active), or other issue. "
            ".pgpass file not created/updated.", "info", logger_to_use, app_settings)
        if pg_password == PGPASSWORD_DEFAULT and not allow_default_for_dev:
            log_map_server("   Specify a unique password with -W or use --dev-override-unsafe-password.",
                           "info", logger_to_use, app_settings)
        return

    try:
        current_user_name = getpass.getuser()
        home_dir_user_specific = os.path.expanduser(f"~{current_user_name}")
        if not os.path.isdir(home_dir_user_specific):
            home_dir = os.path.expanduser("~")  # Fallback
            if os.path.isdir(home_dir):
                log_map_server(
                    f"{symbols.get('info', '')} Using generic home directory {home_dir} for .pgpass for user {current_user_name}.",
                    "info", logger_to_use, app_settings)
            else:  # Should be rare
                log_map_server(
                    f"{symbols.get('error', '')} Home directory for user '{current_user_name}' not found. Cannot create .pgpass.",
                    "error", logger_to_use, app_settings)
                return
        else:
            home_dir = home_dir_user_specific

        pgpass_file_path = os.path.join(home_dir, ".pgpass")
        pgpass_entry_content = f"{pg_host}:{pg_port}:{pg_database}:{pg_user}:{pg_password}"
        current_pgpass_lines: List[str] = []

        if os.path.isfile(pgpass_file_path):
            try:
                with open(pgpass_file_path, "r", encoding="utf-8") as f_read:
                    current_pgpass_lines = [line.strip() for line in f_read if line.strip()]
            except Exception as e_read:
                log_map_server(
                    f"{symbols.get('warning', '')} Could not read existing .pgpass file at {pgpass_file_path}: {e_read}",
                    "warning", logger_to_use, app_settings)

        prefix_to_filter = f"{pg_host}:{pg_port}:{pg_database}:{pg_user}:"
        updated_pgpass_content_lines = [line for line in current_pgpass_lines if not line.startswith(prefix_to_filter)]
        updated_pgpass_content_lines.append(pgpass_entry_content)

        try:
            with open(pgpass_file_path, "w", encoding="utf-8") as f_write:
                for line in updated_pgpass_content_lines: f_write.write(line + "\n")
            os.chmod(pgpass_file_path, 0o600)
            log_map_server(
                f"{symbols.get('success', '')} .pgpass file configured/updated at {pgpass_file_path} for user {current_user_name}.",
                "success", logger_to_use, app_settings)
        except IOError as e_write:
            log_map_server(f"{symbols.get('error', '')} Failed to write to .pgpass file {pgpass_file_path}: {e_write}",
                           "error", logger_to_use, app_settings)
            log_map_server(f"   Ensure user {current_user_name} has write permissions to their home directory.",
                           "error", logger_to_use, app_settings)
    except Exception as e:
        log_map_server(f"{symbols.get('error', '')} Failed to set up .pgpass file: {e}", "error", logger_to_use,
                       app_settings)