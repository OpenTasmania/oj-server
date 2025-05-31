# configure/ufw_configurator.py
# -*- coding: utf-8 -*-
"""
Handles configuration of UFW rules.
"""
import logging
import subprocess
from typing import Optional

from common.command_utils import log_map_server, run_elevated_command
from common.network_utils import validate_cidr  # Import from common
from setup import config  # For ADMIN_GROUP_IP, SYMBOLS

module_logger = logging.getLogger(__name__)


def apply_ufw_rules(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Applies the defined UFW rules (default policies and allows).
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Applying UFW rules...", "info", logger_to_use)

    if not validate_cidr(config.ADMIN_GROUP_IP, current_logger=logger_to_use):
        msg = (
            f"UFW rule application aborted: Invalid ADMIN_GROUP_IP CIDR format "
            f"'{config.ADMIN_GROUP_IP}'."
        )
        log_map_server(f"{config.SYMBOLS['error']} {msg}", "error", logger_to_use)
        raise ValueError(msg)

    try:
        # Set default policies
        run_elevated_command(["ufw", "default", "deny", "incoming"], current_logger=logger_to_use)
        run_elevated_command(["ufw", "default", "allow", "outgoing"], current_logger=logger_to_use)

        # Allow traffic on loopback interface
        run_elevated_command(["ufw", "allow", "in", "on", "lo"], current_logger=logger_to_use)
        run_elevated_command(["ufw", "allow", "out", "on", "lo"], current_logger=logger_to_use)

        # Allow SSH and PostgreSQL from admin IP
        admin_rules = [
            (["ufw", "allow", "from", config.ADMIN_GROUP_IP, "to", "any", "port", "22", "proto", "tcp", "comment",
              "SSH from Admin"], "SSH from Admin"),
            (["ufw", "allow", "from", config.ADMIN_GROUP_IP, "to", "any", "port", "5432", "proto", "tcp", "comment",
              "PostgreSQL from Admin"], "PostgreSQL from Admin"),
        ]
        for cmd_list, desc in admin_rules:
            log_map_server(f"{config.SYMBOLS['info']} Allowing {desc} via UFW...", "info", logger_to_use)
            run_elevated_command(cmd_list, current_logger=logger_to_use)

        # Allow public HTTP and HTTPS
        public_rules = [
            (["ufw", "allow", "http", "comment", "Nginx HTTP"], "HTTP (port 80)"),
            (["ufw", "allow", "https", "comment", "Nginx HTTPS"], "HTTPS (port 443)"),
        ]
        for cmd_list, desc in public_rules:
            log_map_server(f"{config.SYMBOLS['info']} Allowing {desc} via UFW...", "info", logger_to_use)
            run_elevated_command(cmd_list, current_logger=logger_to_use)

        log_map_server(f"{config.SYMBOLS['success']} UFW rules applied successfully.", "success", logger_to_use)

    except subprocess.CalledProcessError as e:
        log_map_server(
            f"{config.SYMBOLS['error']} A UFW command failed during rule application. Command: '{e.cmd}', Error: {e.stderr or e.stdout}",
            "error",
            logger_to_use,
        )
        raise
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} An unexpected error occurred during UFW rule application: {e}",
            "error",
            logger_to_use,
        )
        raise