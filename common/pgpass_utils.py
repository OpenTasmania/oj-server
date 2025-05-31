# common/pgpass_utils.py
# -*- coding: utf-8 -*-
"""
Utility function for setting up the .pgpass file for PostgreSQL.
"""

import getpass
import logging
import os
from typing import Optional

# Assuming config.py is accessible from the project root or PYTHONPATH is set up
# If config.py moves to root, this would be: from config import SYMBOLS, PGPASSWORD_DEFAULT
from setup import config
# Assuming command_utils is now in the common package
from .command_utils import log_map_server

module_logger = logging.getLogger(__name__)

def setup_pgpass(
    pg_host: str,
    pg_port: str,
    pg_database: str,
    pg_user: str,
    pg_password: str,
    pg_password_default: str, # Keep this to compare against the actual default
    allow_default_for_dev: bool = False,
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Set up or update the .pgpass file for PostgreSQL authentication.

    The .pgpass file allows password-less connection to PostgreSQL for the
    current user when connection parameters match an entry in the file.
    This function handles creating the file if it doesn't exist, adding or
    updating the entry for the specified connection, and setting appropriate
    permissions (0600).

    Args:
        pg_host: PostgreSQL host address.
        pg_port: PostgreSQL port number.
        pg_database: PostgreSQL database name.
        pg_user: PostgreSQL username.
        pg_password: PostgreSQL password for the user.
        pg_password_default: The default placeholder password from config to check against.
        allow_default_for_dev: If True, allows using the default password
                               for .pgpass creation (for development).
        current_logger: Optional logger instance.
    """
    logger_to_use = current_logger if current_logger else module_logger

    can_create_pgpass = False
    if pg_password and pg_password != pg_password_default:
        can_create_pgpass = True
    elif (
        pg_password
        and pg_password == pg_password_default
        and allow_default_for_dev
    ):
        log_map_server(
            f"{config.SYMBOLS['warning']} DEV OVERRIDE: Proceeding with "
            ".pgpass creation using the default (unsafe) password.",
            "warning",
            logger_to_use,
        )
        can_create_pgpass = True

    if not can_create_pgpass:
        log_map_server(
            f"{config.SYMBOLS['info']} PGPASSWORD is not set, is default "
            "(and dev override is not active), or other issue. .pgpass file "
            "not created/updated.",
            "info",
            logger_to_use,
        )
        if pg_password == pg_password_default and not allow_default_for_dev:
            log_map_server(
                "   Specify a unique password with -W or use "
                "--dev-override-unsafe-password to use the default.",
                "info",
                logger_to_use,
            )
        return

    try:
        current_user_name = getpass.getuser()
        home_dir_user_specific = os.path.expanduser(f"~{current_user_name}")
        if not os.path.isdir(home_dir_user_specific):
            home_dir = os.path.expanduser("~")
            if os.path.isdir(home_dir):
                log_map_server(
                    f"{config.SYMBOLS['info']} Using generic home directory "
                    f"{home_dir} for .pgpass for user {current_user_name}.",
                    "info",
                    logger_to_use,
                )
            else:
                log_map_server(
                    f"{config.SYMBOLS['error']} Home directory for user "
                    f"'{current_user_name}' not found. Cannot create .pgpass.",
                    "error",
                    logger_to_use,
                )
                return
        else:
            home_dir = home_dir_user_specific

        pgpass_file_path = os.path.join(home_dir, ".pgpass")
        pgpass_entry_content = (
            f"{str(pg_host)}:{str(pg_port)}:{str(pg_database)}:"
            f"{str(pg_user)}:{str(pg_password)}"
        )

        current_pgpass_lines: List[str] = []
        if os.path.isfile(pgpass_file_path):
            try:
                with open(pgpass_file_path, "r", encoding="utf-8") as f_read:
                    current_pgpass_lines = [
                        line.strip() for line in f_read if line.strip()
                    ]
            except Exception as e_read:
                log_map_server(
                    f"{config.SYMBOLS['warning']} Could not read existing "
                    f".pgpass file at {pgpass_file_path}: {e_read}",
                    "warning",
                    logger_to_use,
                )

        prefix_to_filter = (
            f"{str(pg_host)}:{str(pg_port)}:{str(pg_database)}:"
            f"{str(pg_user)}:"
        )
        updated_pgpass_content_lines = [
            line
            for line in current_pgpass_lines
            if not line.startswith(prefix_to_filter)
        ]
        updated_pgpass_content_lines.append(pgpass_entry_content)

        try:
            with open(pgpass_file_path, "w", encoding="utf-8") as f_write:
                for line in updated_pgpass_content_lines:
                    f_write.write(line + "\n")
            os.chmod(pgpass_file_path, 0o600)
            log_map_server(
                f"{config.SYMBOLS['success']} .pgpass file configured/updated "
                f"at {pgpass_file_path} for user {current_user_name}.",
                "success",
                logger_to_use,
            )
        except IOError as e_write:
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to write to .pgpass file "
                f"{pgpass_file_path}: {e_write}",
                "error",
                logger_to_use,
            )
            log_map_server(
                f"   Ensure user {current_user_name} has write permissions "
                "to their home directory.",
                "error",
                logger_to_use,
            )

    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to set up .pgpass file: {e}",
            "error",
            logger_to_use,
        )