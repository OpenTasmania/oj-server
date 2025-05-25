# setup/services/ufw.py
"""
Handles the setup and configuration of UFW (Uncomplicated Firewall).
"""
import logging
from typing import Optional

from .. import config  # Access config.ADMIN_GROUP_IP, config.SYMBOLS
from ..command_utils import run_elevated_command, log_map_server
from ..helpers import validate_cidr  # Import necessary helpers

module_logger = logging.getLogger(__name__)


def ufw_setup(current_logger: Optional[logging.Logger] = None) -> None:
    """Set up Uncomplicated Firewall (ufw)."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Setting up firewall with ufw...",
        "info",
        logger_to_use,
    )

    if not validate_cidr(config.ADMIN_GROUP_IP, current_logger=logger_to_use):
        msg = f"Firewall setup aborted: Invalid ADMIN_GROUP_IP CIDR format '{config.ADMIN_GROUP_IP}'."
        log_map_server(
            f"{config.SYMBOLS['error']} {msg}", "error", logger_to_use
        )
        raise ValueError(msg)

    try:
        run_elevated_command(
            ["ufw", "default", "deny", "incoming"],
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["ufw", "default", "allow", "outgoing"],
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["ufw", "allow", "in", "on", "lo"], current_logger=logger_to_use
        )
        run_elevated_command(
            ["ufw", "allow", "out", "on", "lo"], current_logger=logger_to_use
        )

        run_elevated_command(
            [
                "ufw",
                "allow",
                "from",
                config.ADMIN_GROUP_IP,
                "to",
                "any",
                "port",
                "22",
                "proto",
                "tcp",
                "comment",
                "SSH from Admin",
            ],
            current_logger=logger_to_use,
        )
        run_elevated_command(
            [
                "ufw",
                "allow",
                "from",
                config.ADMIN_GROUP_IP,
                "to",
                "any",
                "port",
                "5432",
                "proto",
                "tcp",
                "comment",
                "PostgreSQL from Admin",
            ],
            current_logger=logger_to_use,
        )

        run_elevated_command(
            ["ufw", "allow", "http", "comment", "Nginx HTTP"],
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["ufw", "allow", "https", "comment", "Nginx HTTPS"],
            current_logger=logger_to_use,
        )

        log_map_server(
            f"{config.SYMBOLS['warning']} UFW will be enabled. Ensure your SSH access from '{config.ADMIN_GROUP_IP}' and Nginx ports (80, 443) are correctly allowed.",
            "warning",
            logger_to_use,
        )

        status_result = run_elevated_command(
            ["ufw", "status"],
            capture_output=True,
            check=False,
            current_logger=logger_to_use,
        )
        if (
            status_result.stdout
            and "inactive" in status_result.stdout.lower()
        ):
            run_elevated_command(
                ["ufw", "enable"],
                cmd_input="y\n",
                check=True,
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{config.SYMBOLS['success']} UFW enabled.",
                "success",
                logger_to_use,
            )
        else:
            log_map_server(
                f"{config.SYMBOLS['info']} UFW is already active or status not 'inactive'. Status: {status_result.stdout.strip() if status_result.stdout else 'N/A'}",
                "info",
                logger_to_use,
            )

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
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Error during UFW setup: {e}",
            "error",
            logger_to_use,
        )
        raise
