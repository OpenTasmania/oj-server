# installer/nodejs_installer.py
# -*- coding: utf-8 -*-
"""
Handles the installation of Node.js LTS (Long Term Support).
"""
import logging
from typing import Optional # Added Optional

from common.command_utils import log_map_server, run_command, run_elevated_command
from setup import config # For SYMBOLS

module_logger = logging.getLogger(__name__)

def install_nodejs_lts(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Install Node.js LTS (Long Term Support) version using NodeSource repository.

    Args:
        current_logger: Optional logger instance to use.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Installing Node.js LTS version using "
        "NodeSource...",
        "info",
        logger_to_use,
    )
    try:
        nodesource_setup_url = "https://deb.nodesource.com/setup_lts.x" # Or specific e.g. setup_20.x
        log_map_server(
            f"{config.SYMBOLS['gear']} Downloading NodeSource setup script "
            f"from {nodesource_setup_url}...",
            "info",
            logger_to_use,
        )
        curl_result = run_command(
            ["curl", "-fsSL", nodesource_setup_url],
            capture_output=True,
            check=True,
            current_logger=logger_to_use,
        )
        nodesource_script_content = curl_result.stdout

        log_map_server(
            f"{config.SYMBOLS['gear']} Executing NodeSource setup script with "
            "elevated privileges...",
            "info",
            logger_to_use,
        )
        run_elevated_command(
            ["bash", "-"],
            cmd_input=nodesource_script_content,
            current_logger=logger_to_use,
        )

        log_map_server(
            f"{config.SYMBOLS['gear']} Updating apt package list after adding "
            "NodeSource repo...",
            "info",
            logger_to_use,
        )
        run_elevated_command(["apt", "update"], current_logger=logger_to_use)

        log_map_server(
            f"{config.SYMBOLS['package']} Installing Node.js...",
            "info",
            logger_to_use,
        )
        run_elevated_command(
            ["apt", "--yes", "install", "nodejs"],
            current_logger=logger_to_use,
        )

        node_version = (
            run_command(
                ["node", "--version"],
                capture_output=True,
                check=False, # Allow to fail if somehow not in path yet
                current_logger=logger_to_use,
            ).stdout.strip()
            or "Not detected"
        )
        npm_version = (
            run_command(
                ["npm", "--version"],
                capture_output=True,
                check=False, # Allow to fail
                current_logger=logger_to_use,
            ).stdout.strip()
            or "Not detected"
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Node.js installed. Version: "
            f"{node_version}, NPM Version: {npm_version}",
            "success",
            logger_to_use,
        )
    except Exception as e: # pragma: no cover
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to install Node.js LTS: {e}",
            "error",
            logger_to_use,
        )
        raise