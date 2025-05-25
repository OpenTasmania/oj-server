# setup/helpers.py
"""
General helper utility functions for the map server setup script.
"""
import datetime
import getpass
import logging
import os
import re
import subprocess
from typing import Optional, List

from setup import config
from setup.command_utils import run_command, run_elevated_command, log_map_server

module_logger = logging.getLogger(__name__)


def systemd_reload(current_logger: Optional[logging.Logger] = None) -> None:
    """Reload systemd daemon."""
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


def backup_file(
        file_path: str, current_logger: Optional[logging.Logger] = None
) -> bool:
    """Create a backup of a file with timestamp using elevated privileges."""
    logger_to_use = current_logger if current_logger else module_logger

    # Check existence with elevated privileges first
    try:
        # Use capture_output=True to prevent "test" command's own output (if any) from cluttering logs
        run_elevated_command(
            ["test", "-f", file_path],
            check=True,
            capture_output=True,
            current_logger=logger_to_use,
        )
    except (
            subprocess.CalledProcessError
    ):  # test -f returns 1 if file does not exist
        log_map_server(
            f"{config.SYMBOLS['warning']} File {file_path} does not exist or is not accessible (even with elevation). Cannot backup.",
            "warning",
            logger_to_use,
        )
        return False
    except (
            Exception
    ) as e:  # Other errors like sudo itself failing, or test command missing
        log_map_server(
            f"{config.SYMBOLS['error']} Error pre-checking file existence for backup of {file_path}: {e}",
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
            f"{config.SYMBOLS['success']} Backed up {file_path} to {backup_path}",
            "success",
            logger_to_use,
        )
        return True
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to backup {file_path} to {backup_path}: {e}",
            "error",
            logger_to_use,
        )
        return False


def validate_cidr(
        cidr: str, current_logger: Optional[logging.Logger] = None
) -> bool:
    """Validate a CIDR notation IP address range."""
    logger_to_use = current_logger if current_logger else module_logger
    if not isinstance(cidr, str):
        log_map_server(
            f"{config.SYMBOLS['error']} Invalid input for CIDR validation: not a string.",
            "error",
            logger_to_use,
        )
        return False

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
                f"{config.SYMBOLS['warning']} CIDR prefix '/{prefix}' out of range (0-32).",
                "warning",
                logger_to_use,
            )
            return False

        octets = ip_part.split(".")
        if len(octets) != 4:
            log_map_server(
                f"{config.SYMBOLS['warning']} CIDR IP part '{ip_part}' does not have 4 octets.",
                "warning",
                logger_to_use,
            )
            return False
        for o_str in octets:
            octet_val = int(o_str)
            if not (0 <= octet_val <= 255):
                log_map_server(
                    f"{config.SYMBOLS['warning']} CIDR IP octet '{octet_val}' out of range (0-255).",
                    "warning",
                    logger_to_use,
                )
                return False
        return True
    except ValueError:
        log_map_server(
            f"{config.SYMBOLS['warning']} CIDR '{cidr}' contains non-integer parts where expected.",
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
    """Set up .pgpass file for PostgreSQL authentication for the current user."""
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
            f"{config.SYMBOLS['warning']} DEV OVERRIDE: Proceeding with .pgpass creation using the default (unsafe) password.",
            "warning",
            logger_to_use,
        )
        can_create_pgpass = True

    if not can_create_pgpass:
        log_map_server(
            f"{config.SYMBOLS['info']} PGPASSWORD is not set, is default (and dev override is not active), or other issue. .pgpass file not created/updated.",
            "info",
            logger_to_use,
        )
        if pg_password == pg_password_default and not allow_default_for_dev:
            log_map_server(
                "   Specify a unique password with -W or use --dev-override-unsafe-password to use the default.",
                "info",
                logger_to_use,
            )
        return

    try:
        current_user_name = getpass.getuser()
        home_dir = os.path.expanduser(f"~{current_user_name}")
        if not os.path.isdir(home_dir):
            home_dir_fallback = os.path.expanduser("~")
            if os.path.isdir(home_dir_fallback):
                home_dir = home_dir_fallback
                log_map_server(
                    f"{config.SYMBOLS['info']} Using generic home directory {home_dir} for .pgpass for user {current_user_name}.",
                    "info",
                    logger_to_use,
                )
            else:
                log_map_server(
                    f"{config.SYMBOLS['error']} Home directory for user '{current_user_name}' not found. Cannot create .pgpass.",
                    "error",
                    logger_to_use,
                )
                return

        pgpass_file = os.path.join(home_dir, ".pgpass")
        pgpass_entry_content = f"{str(pg_host)}:{str(pg_port)}:{str(pg_database)}:{str(pg_user)}:{str(pg_password)}"
        #        pgpass_entry_line = f"{pgpass_entry_content}\n"

        #        entry_exists = False
        current_pgpass_lines: List[str] = []
        if os.path.isfile(pgpass_file):
            try:
                with open(pgpass_file, "r") as f_read:
                    current_pgpass_lines = [
                        line.strip() for line in f_read if line.strip()
                    ]  # Read and strip empty lines
            #                if pgpass_entry_content in current_pgpass_lines:
            #                    entry_exists = True
            except Exception as e_read:
                log_map_server(
                    f"{config.SYMBOLS['warning']} Could not read existing .pgpass file at {pgpass_file}: {e_read}",
                    "warning",
                    logger_to_use,
                )

        # Always write/overwrite to ensure the current password is set and old one for same combo is removed
        # Filter out any existing entries for the same host:port:db:user combination
        prefix_to_filter = f"{str(pg_host)}:{str(pg_port)}:{str(pg_database)}:{str(pg_user)}:"
        updated_pgpass_content_lines = [
            line
            for line in current_pgpass_lines
            if not line.startswith(prefix_to_filter)
        ]
        updated_pgpass_content_lines.append(
            pgpass_entry_content
        )  # Add the new or updated entry

        try:
            with open(
                    pgpass_file, "w"
            ) as f_write:  # Overwrite with filtered + new content
                for line in updated_pgpass_content_lines:
                    f_write.write(line + "\n")
            os.chmod(pgpass_file, 0o600)
            log_map_server(
                f"{config.SYMBOLS['success']} .pgpass file configured/updated at {pgpass_file} for user {current_user_name}.",
                "success",
                logger_to_use,
            )
        except IOError as e_write:
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to write to .pgpass file {pgpass_file}: {e_write}",
                "error",
                logger_to_use,
            )
            log_map_server(
                f"   Ensure user {current_user_name} has write permissions to their home directory.",
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
    """Get the Debian codename."""
    logger_to_use = current_logger if current_logger else module_logger
    try:
        # Use run_command as lsb_release doesn't need sudo
        result = run_command(
            ["lsb_release", "-cs"],
            capture_output=True,
            check=True,
            current_logger=logger_to_use,
        )
        return result.stdout.strip()
    except FileNotFoundError:  # Should be caught by run_command
        log_map_server(
            f"{config.SYMBOLS['warning']} lsb_release command not found. Cannot determine Debian codename.",
            "warning",
            logger_to_use,
        )
        return None
    except subprocess.CalledProcessError:
        # Error already logged by run_command if check=True.
        return None
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['warning']} Unexpected error getting Debian codename: {e}",
            "warning",
            logger_to_use,
        )
        return None
