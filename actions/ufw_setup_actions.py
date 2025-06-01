# setup/ufw_setup_actions.py
# -*- coding: utf-8 -*-
"""
Handles setup (installation checks, activation) of UFW.
"""
import logging
import subprocess
from typing import Optional

from common.command_utils import (
    check_package_installed,
    log_map_server,
    run_elevated_command,
)
from setup import config  # For SYMBOLS

module_logger = logging.getLogger(__name__)


def ensure_ufw_package_installed(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Confirms UFW package is installed (as it's a core prerequisite).
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['info']} Checking UFW package installation status...", "info", logger_to_use)
    if check_package_installed("ufw", current_logger=logger_to_use):
        log_map_server(f"{config.SYMBOLS['success']} UFW package is installed.", "success", logger_to_use)
    else:
        log_map_server(
            f"{config.SYMBOLS['error']} UFW package is NOT installed. This should have been handled by core prerequisites.",
            "error", logger_to_use)
        # Depending on strictness, you might raise an error here.
        # For now, subsequent steps will likely fail if it's truly missing.
        raise EnvironmentError("UFW package not found, but is a core prerequisite.")


def enable_ufw_service(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Enables the UFW service if it is currently inactive.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Enabling UFW service if inactive...", "info", logger_to_use)

    try:
        ensure_ufw_package_installed(current_logger=logger_to_use)  # Double check

        status_result = run_elevated_command(
            ["ufw", "status"],
            capture_output=True,
            check=False,
            current_logger=logger_to_use,
        )

        if status_result.stdout and "inactive" in status_result.stdout.lower():
            log_map_server(
                f"{config.SYMBOLS['warning']} UFW is inactive. Enabling now. "
                "Ensure your SSH access and other essential ports are allowed by rules.",
                "warning",
                logger_to_use,
            )
            run_elevated_command(
                ["ufw", "enable"],
                cmd_input="y\n",  # Auto-confirm the enabling prompt
                check=True,
                current_logger=logger_to_use,
            )
            log_map_server(f"{config.SYMBOLS['success']} UFW enabled.", "success", logger_to_use)
        else:
            status_output = status_result.stdout.strip() if status_result.stdout else "N/A"
            log_map_server(
                f"{config.SYMBOLS['info']} UFW is already active or status not 'inactive'. Status: {status_output}",
                "info",
                logger_to_use,
            )

        # Log final UFW status
        log_map_server(f"{config.SYMBOLS['info']} Final UFW status:", "info", logger_to_use)
        run_elevated_command(["ufw", "status", "verbose"], current_logger=logger_to_use)

    except subprocess.CalledProcessError as e:
        log_map_server(
            f"{config.SYMBOLS['error']} A UFW command failed during enabling. Command: '{e.cmd}', Error: {e.stderr or e.stdout}",
            "error",
            logger_to_use,
        )
        raise
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} An unexpected error occurred during UFW enabling: {e}",
            "error",
            logger_to_use,
        )
        raise
