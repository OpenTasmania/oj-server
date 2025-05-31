# setup/helpers.py
# -*- coding: utf-8 -*-
"""
General helper utility functions for the map server setup script.

This module includes functions for system operations like reloading systemd,
backing up files, validating CIDR notation, setting up .pgpass,
and determining the Debian codename and project hash.
"""

import datetime
import getpass
import hashlib
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import List, Optional

from setup import config
from common.command_utils import (
    log_map_server,
    run_command,
    run_elevated_command,
)

module_logger = logging.getLogger(__name__)


def systemd_reload(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Reload the systemd daemon.

    Args:
        current_logger: Optional logger instance to use.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['gear']} Reloading systemd daemon...",
        "info",
        logger_to_use,
    )
    try:
        run_elevated_command(
            ["systemctl", "daemon-reload"], current_logger=logger_to_use
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Systemd daemon reloaded.",
            "success",
            logger_to_use,
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to reload systemd: {e}",
            "error",
            logger_to_use,
        )
        # Depending on script's overall error handling,
        # you might want to raise e here.


def backup_file(
    file_path: str, current_logger: Optional[logging.Logger] = None
) -> bool:
    """
    Create a timestamped backup of a file using elevated privileges.

    Args:
        file_path: The absolute path to the file to back up.
        current_logger: Optional logger instance to use.

    Returns:
        True if the backup was successful, False otherwise.
    """
    logger_to_use = current_logger if current_logger else module_logger

    # Check file existence with elevated privileges first.
    try:
        run_elevated_command(
            ["test", "-f", file_path],
            check=True,
            capture_output=True,  # Suppress "test" command's own output.
            current_logger=logger_to_use,
        )
    except subprocess.CalledProcessError:
        # test -f returns 1 if file does not exist or is not a regular file.
        log_map_server(
            f"{config.SYMBOLS['warning']} File {file_path} does not exist, "
            "is not a regular file, or is not accessible (even with "
            "elevation). Cannot backup.",
            "warning",
            logger_to_use,
        )
        return False
    except Exception as e:
        # Other errors like sudo itself failing, or test command missing.
        log_map_server(
            f"{config.SYMBOLS['error']} Error pre-checking file existence "
            f"for backup of {file_path}: {e}",
            "error",
            logger_to_use,
        )
        return False

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = f"{file_path}.bak.{timestamp}"
    try:
        run_elevated_command(
            ["cp", "-a", file_path, backup_path], current_logger=logger_to_use
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Backed up {file_path} to "
            f"{backup_path}",
            "success",
            logger_to_use,
        )
        return True
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to backup {file_path} to "
            f"{backup_path}: {e}",
            "error",
            logger_to_use,
        )
        return False


def validate_cidr(
    cidr: str, current_logger: Optional[logging.Logger] = None
) -> bool:
    """
    Validate a CIDR (Classless Inter-Domain Routing) notation IP address range.

    Checks for format xxx.xxx.xxx.xxx/yy and valid ranges for octets and prefix.

    Args:
        cidr: The CIDR string to validate.
        current_logger: Optional logger instance to use.

    Returns:
        True if the CIDR notation is valid, False otherwise.
    """
    logger_to_use = current_logger if current_logger else module_logger
    if not isinstance(cidr, str):
        log_map_server(
            f"{config.SYMBOLS['error']} Invalid input for CIDR validation: "
            "not a string.",
            "error",
            logger_to_use,
        )
        return False

    # Regex for basic CIDR format: e.g., 192.168.1.0/24
    match = re.fullmatch(
        r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$", cidr
    )
    if not match:
        log_map_server(
            f"{config.SYMBOLS['warning']} CIDR '{cidr}' has invalid format.",
            "warning",
            logger_to_use,
        )
        return False

    ip_part, prefix_str = cidr.split("/")
    try:
        prefix = int(prefix_str)
        if not (0 <= prefix <= 32):
            log_map_server(
                f"{config.SYMBOLS['warning']} CIDR prefix '/{prefix}' is out "
                "of range (0-32).",
                "warning",
                logger_to_use,
            )
            return False

        octets_str = ip_part.split(".")
        if len(octets_str) != 4:
            log_map_server(
                f"{config.SYMBOLS['warning']} CIDR IP part '{ip_part}' does "
                "not have 4 octets.",
                "warning",
                logger_to_use,
            )
            return False
        for o_str in octets_str:
            octet_val = int(o_str)
            if not (0 <= octet_val <= 255):
                log_map_server(
                    f"{config.SYMBOLS['warning']} CIDR IP octet '{octet_val}' "
                    "is out of range (0-255).",
                    "warning",
                    logger_to_use,
                )
                return False
        return True
    except ValueError:  # Catches errors from int() conversion
        log_map_server(
            f"{config.SYMBOLS['warning']} CIDR '{cidr}' contains non-integer "
            "parts where numbers were expected.",
            "warning",
            logger_to_use,
        )
        return False


def setup_pgpass(
    pg_host: str,
    pg_port: str,
    pg_database: str,
    pg_user: str,
    pg_password: str,
    pg_password_default: str,
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
        pg_password_default: The default placeholder password to check against.
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
        # Try to get specific user's home, fallback to generic expanduser.
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
                    # Read and strip empty lines.
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

        # Filter out any existing entries for the same host:port:db:user.
        prefix_to_filter = (
            f"{str(pg_host)}:{str(pg_port)}:{str(pg_database)}:"
            f"{str(pg_user)}:"
        )
        updated_pgpass_content_lines = [
            line
            for line in current_pgpass_lines
            if not line.startswith(prefix_to_filter)
        ]
        # Add the new or updated entry.
        updated_pgpass_content_lines.append(pgpass_entry_content)

        try:
            # Overwrite with filtered + new content.
            with open(pgpass_file_path, "w", encoding="utf-8") as f_write:
                for line in updated_pgpass_content_lines:
                    f_write.write(line + "\n")
            os.chmod(pgpass_file_path, 0o600)  # Set permissions to user-only.
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


def get_debian_codename(
    current_logger: Optional[logging.Logger] = None,
) -> Optional[str]:
    """
    Get the Debian codename (e.g., 'bookworm', 'bullseye').

    Args:
        current_logger: Optional logger instance.

    Returns:
        The Debian codename as a string if successful, None otherwise.
    """
    logger_to_use = current_logger if current_logger else module_logger
    try:
        # Use run_command as lsb_release doesn't need sudo.
        result = run_command(
            ["lsb_release", "-cs"],
            capture_output=True,
            check=True,  # Expect lsb_release to succeed.
            current_logger=logger_to_use,
        )
        return result.stdout.strip()
    except FileNotFoundError:
        # This should be caught by run_command if lsb_release is missing.
        log_map_server(
            f"{config.SYMBOLS['warning']} lsb_release command not found. "
            "Cannot determine Debian codename.",
            "warning",
            logger_to_use,
        )
        return None
    except subprocess.CalledProcessError:
        # Error already logged by run_command if check=True.
        return None
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['warning']} Unexpected error getting Debian "
            f"codename: {e}",
            "warning",
            logger_to_use,
        )
        return None


def calculate_project_hash(
    project_root_dir: Path, current_logger: Optional[logging.Logger] = None
) -> Optional[str]:
    """
    Calculate a SHA256 hash of all .py files within the project directory.

    The hash includes both file content and relative file paths (normalized to
    POSIX style) to detect additions, deletions, renames, and content changes.

    Args:
        project_root_dir: The root directory of the project (Path object).
        current_logger: Optional logger instance.

    Returns:
        The hex digest of the SHA256 hash as a string, or None if an error
        occurs.
    """
    logger_to_use = current_logger if current_logger else module_logger
    hasher = hashlib.sha256()
    py_files_found: List[Path] = []

    try:
        project_root = Path(project_root_dir)
        if not project_root.is_dir():
            log_map_server(
                f"{config.SYMBOLS['error']} Project root directory "
                f"'{project_root}' not found for hashing.",
                "error",
                logger_to_use,
            )
            return None

        # Recursively find all .py files.
        for path_object in project_root.rglob("*.py"):
            if path_object.is_file():
                py_files_found.append(path_object)

        if not py_files_found:
            log_map_server(
                f"{config.SYMBOLS['warning']} No .py files found under "
                f"'{project_root}' for hashing.",
                "warning",
                logger_to_use,
            )
            # Return a default hash for an empty set of files.
            return hasher.hexdigest()

        # Sort files by their relative path to ensure deterministic hashing.
        # Convert to relative paths from project_root for hashing filenames.
        sorted_files = sorted(
            py_files_found,
            key=lambda p: p.relative_to(project_root).as_posix(),
        )

        for file_path in sorted_files:
            try:
                # Add relative file path to the hash (normalized for consistency).
                relative_path_str = file_path.relative_to(
                    project_root
                ).as_posix()
                hasher.update(relative_path_str.encode("utf-8"))

                # Add file content to the hash.
                file_content = file_path.read_bytes()
                hasher.update(file_content)
            except Exception as e_file:
                log_map_server(
                    f"{config.SYMBOLS['error']} Error reading file "
                    f"{file_path} for hashing: {e_file}",
                    "error",
                    logger_to_use,
                )
                return None  # Error during hashing a specific file.

        final_hash = hasher.hexdigest()
        log_map_server(
            f"{config.SYMBOLS['debug']} Calculated SCRIPT_HASH: {final_hash} "
            f"from {len(sorted_files)} .py files.",
            "debug",  # Changed to debug as this is verbose for normal runs
            logger_to_use,
        )
        return final_hash

    except Exception as e_hash:
        log_map_server(
            f"{config.SYMBOLS['error']} Critical error during project "
            f"hashing: {e_hash}",
            "error",
            logger_to_use,
        )
        return None
