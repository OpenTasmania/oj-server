# setup/services/ufw.py
# -*- coding: utf-8 -*-
"""
Handles the setup and configuration of UFW (Uncomplicated Firewall).

This module provides a function to configure UFW with default policies,
allow necessary ports (SSH, PostgreSQL for admin, HTTP/HTTPS for public),
and enable the firewall if it's not already active.
"""

import logging
import subprocess  # For CalledProcessError
from typing import Optional

from setup import config  # Access config.ADMIN_GROUP_IP, config.SYMBOLS
from setup.command_utils import run_elevated_command, log_map_server
from setup.helpers import validate_cidr  # Import necessary helpers

module_logger = logging.getLogger(__name__)


def ufw_setup(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Set up Uncomplicated Firewall (UFW).

    - Sets default incoming policy to deny and outgoing to allow.
    - Allows traffic on the loopback interface.
    - Allows SSH (port 22) and PostgreSQL (port 5432) from the admin IP.
    - Allows HTTP (port 80) and HTTPS (port 443) from any source.
    - Enables UFW if it is currently inactive.
    - Logs the UFW status.

    Args:
        current_logger: Optional logger instance to use. If None,
                        the module's default logger is used.

    Raises:
        ValueError: If the `ADMIN_GROUP_IP` in the configuration is not a
                    valid CIDR format.
        subprocess.CalledProcessError: If any `ufw` command fails critically
                                     (and `check=True` is used in
                                     `run_elevated_command`).
        Exception: For other unexpected errors during setup.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Setting up firewall with ufw...",
        "info",
        logger_to_use,
    )

    if not validate_cidr(config.ADMIN_GROUP_IP, current_logger=logger_to_use):
        msg = (
            f"Firewall setup aborted: Invalid ADMIN_GROUP_IP CIDR format "
            f"'{config.ADMIN_GROUP_IP}'."
        )
        log_map_server(
            f"{config.SYMBOLS['error']} {msg}", "error", logger_to_use
        )
        raise ValueError(msg)

    try:
        # Set default policies
        run_elevated_command(
            ["ufw", "default", "deny", "incoming"],
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["ufw", "default", "allow", "outgoing"],
            current_logger=logger_to_use,
        )

        # Allow traffic on loopback interface
        run_elevated_command(
            ["ufw", "allow", "in", "on", "lo"], current_logger=logger_to_use
        )
        run_elevated_command(
            ["ufw", "allow", "out", "on", "lo"], current_logger=logger_to_use
        )

        # Allow SSH and PostgreSQL from admin IP
        run_elevated_command(
            [
                "ufw", "allow", "from", config.ADMIN_GROUP_IP, "to", "any",
                "port", "22", "proto", "tcp", "comment", "SSH from Admin",
            ],
            current_logger=logger_to_use,
        )
        run_elevated_command(
            [
                "ufw", "allow", "from", config.ADMIN_GROUP_IP, "to", "any",
                "port", "5432", "proto", "tcp",
                "comment", "PostgreSQL from Admin",
            ],
            current_logger=logger_to_use,
        )

        # Allow public HTTP and HTTPS
        run_elevated_command(
            ["ufw", "allow", "http", "comment", "Nginx HTTP"],
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["ufw", "allow", "https", "comment", "Nginx HTTPS"],
            current_logger=logger_to_use,
        )

        log_map_server(
            f"{config.SYMBOLS['warning']} UFW will be enabled. Ensure your "
            f"SSH access from '{config.ADMIN_GROUP_IP}' and Nginx ports "
            "(80, 443) are correctly allowed.",
            "warning",
            logger_to_use,
        )

        # Check UFW status and enable if inactive
        status_result = run_elevated_command(
            ["ufw", "status"],
            capture_output=True,
            check=False,  # Do not raise error if status command fails
            current_logger=logger_to_use,
        )

        if status_result.stdout and \
                "inactive" in status_result.stdout.lower():
            # The 'ufw enable' command prompts for confirmation.
            # 'cmd_input="y\n"' provides 'y' followed by a newline.
            run_elevated_command(
                ["ufw", "enable"],
                cmd_input="y\n",
                check=True,  # Ensure enable command itself succeeds
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{config.SYMBOLS['success']} UFW enabled.",
                "success",
                logger_to_use,
            )
        else:
            status_output = status_result.stdout.strip() if status_result.stdout else "N/A"
            log_map_server(
                f"{config.SYMBOLS['info']} UFW is already active or status "
                f"not 'inactive'. Status: {status_output}",
                "info",
                logger_to_use,
            )

        # Log final UFW status
        log_map_server(
            f"{config.SYMBOLS['info']} UFW status details:",
            "info",
            logger_to_use,
        )
        run_elevated_command(
            ["ufw", "status", "verbose"], current_logger=logger_to_use
        )
        log_map_server(
            f"{config.SYMBOLS['success']} UFW setup completed.",
            "success",
            logger_to_use,
        )
    except subprocess.CalledProcessError as e:
        # Errors from run_elevated_command (if check=True) are caught here
        # if not handled by run_command itself.
        log_map_server(
            f"{config.SYMBOLS['error']} A UFW command failed. "
            f"Command: '{e.cmd}', Error: {e.stderr or e.stdout}",
            "error",
            logger_to_use,
        )
        raise  # Re-raise to indicate failure of this setup step
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} An unexpected error occurred "
            f"during UFW setup: {e}",
            "error",
            logger_to_use,
        )
        raise  # Re-raise to indicate failure
