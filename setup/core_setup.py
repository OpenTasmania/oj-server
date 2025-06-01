# setup/core_setup.py
# -*- coding: utf-8 -*-
"""
Functions for core system setup tasks.
This module includes functions for improving boot verbosity, removing
conflicting packages, and installing some core system packages.
Docker and Node.js installation are handled by dedicated installer modules.
"""

import getpass
import logging
import os
# import tempfile # Not used anymore after docker/node removal
from typing import Optional

from common.command_utils import (
    log_map_server,
    run_command,
    run_elevated_command,
)
from common.file_utils import backup_file
from setup import config
from setup.cli_handler import cli_prompt_for_rerun
from setup.step_executor import execute_step

# Import the definitive Docker and Node.js installation functions from their new locations
from installer.docker_installer import install_docker_engine
from installer.nodejs_installer import install_nodejs_lts


module_logger = logging.getLogger(__name__)


def boot_verbosity(current_logger: Optional[logging.Logger] = None) -> None:
    # ... (implementation as before) ...
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Improving boot verbosity & core utils...", "info", logger_to_use)
    grub_file = "/etc/default/grub"
    if backup_file(grub_file, current_logger=logger_to_use):
        try:
            sed_expressions = [r"-e", r"/^GRUB_CMDLINE_LINUX_DEFAULT=/s/\bquiet\b//g", r"-e", r"/^GRUB_CMDLINE_LINUX_DEFAULT=/s/\bsplash\b//g", r"-e", r"/^GRUB_CMDLINE_LINUX_DEFAULT=/s/  +/ /g", r"-e", r'/^GRUB_CMDLINE_LINUX_DEFAULT=/s/" /"/g', r"-e", r'/^GRUB_CMDLINE_LINUX_DEFAULT=/s/ "/"/g']
            run_elevated_command(["sed", "-i"] + sed_expressions + [grub_file], current_logger=logger_to_use)
            run_elevated_command(["update-grub"], current_logger=logger_to_use)
            run_elevated_command(["update-initramfs", "-u"], current_logger=logger_to_use)
            log_map_server(f"{config.SYMBOLS['success']} Boot verbosity improved.", "success", logger_to_use)
        except Exception as e: log_map_server(f"{config.SYMBOLS['error']} Failed to update grub for boot verbosity: {e}", "error", logger_to_use) # pragma: no cover
    current_user_name = getpass.getuser()
    log_map_server(f"{config.SYMBOLS['gear']} Adding user '{current_user_name}' to 'systemd-journal' group...", "info", logger_to_use)
    try:
        run_elevated_command(["usermod", "--append", "--group", "systemd-journal", current_user_name], current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} User {current_user_name} added to systemd-journal group.", "success", logger_to_use)
    except Exception as e: log_map_server(f"{config.SYMBOLS['warning']} Could not add user {current_user_name} to systemd-journal group: {e}. This may be non-critical.", "warning", logger_to_use) # pragma: no cover
    log_map_server(f"{config.SYMBOLS['package']} System update and essential utilities install...", "info", logger_to_use)
    try:
        run_elevated_command(["apt", "update"], current_logger=logger_to_use)
        run_elevated_command(["apt", "--yes", "upgrade"], current_logger=logger_to_use)
        essential_utils = ["curl", "wget", "bash", "btop", "screen", "ca-certificates", "lsb-release", "gnupg"]
        run_elevated_command(["apt", "--yes", "install"] + essential_utils, current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} System updated and essential utilities ensured.", "success", logger_to_use)
    except Exception as e: log_map_server(f"{config.SYMBOLS['error']} Failed during system update/essential util install: {e}", "error", logger_to_use); raise # pragma: no cover


def core_conflict_removal(current_logger: Optional[logging.Logger] = None) -> None:
    # ... (implementation as before) ...
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Removing conflicting system Node.js (if any)...", "info", logger_to_use)
    try:
        result = run_command(["dpkg", "-s", "nodejs"], check=False, capture_output=True, current_logger=logger_to_use)
        if result.returncode == 0:
            log_map_server(f"{config.SYMBOLS['info']} System 'nodejs' package found. Attempting removal...", "info", logger_to_use)
            run_elevated_command(["apt", "remove", "--purge", "--yes", "nodejs", "npm"], current_logger=logger_to_use)
            run_elevated_command(["apt", "--purge", "--yes", "autoremove"], current_logger=logger_to_use)
            log_map_server(f"{config.SYMBOLS['success']} System nodejs and npm removed.", "success", logger_to_use)
        else:
            log_map_server(f"{config.SYMBOLS['info']} System 'nodejs' not found via dpkg, skipping removal.", "info", logger_to_use)
    except Exception as e: log_map_server(f"{config.SYMBOLS['error']} Error during core conflict removal: {e}", "error", logger_to_use) # pragma: no cover


def core_install(current_logger: Optional[logging.Logger] = None) -> None:
    # ... (implementation as before, ensuring it doesn't duplicate what core_prerequisites might do) ...
    # This function should now focus on packages NOT covered by core_prerequisites.py's groups.
    # Based on current core_prerequisites.py, core_install in core_setup.py might become very lean
    # or be merged if its remaining packages fit better in core_prerequisites.py lists.
    # For now, assuming it installs things not in core_prerequisites.py's package lists.
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Installing core system packages specified in core_setup.py...", "info", logger_to_use)
    try:
        run_elevated_command(["apt", "update"], current_logger=logger_to_use)
        # Example: only install packages specific to core_setup if any remain distinct
        core_setup_specific_packages = [] # Add any if they exist, e.g. config.CORE_SETUP_SPECIFIC_PACKAGES
        if core_setup_specific_packages: # pragma: no cover
             run_elevated_command(["apt", "--yes", "install"] + core_setup_specific_packages, current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} Core setup specific packages (if any) installation process completed.", "success", logger_to_use)
    except Exception as e: # pragma: no cover
        log_map_server(f"{config.SYMBOLS['error']} Error during core_setup specific package installation: {e}", "error", logger_to_use)
        raise


def core_conflict_removal_group(current_logger: logging.Logger) -> bool: # pragma: no cover
    # ... (implementation as before) ...
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"--- {config.SYMBOLS['info']} Starting Core Conflict Removal Group ---", "info", logger_to_use)
    success = execute_step("CORE_CONFLICTS", "Remove Core Conflicts (e.g. system node)", core_conflict_removal, logger_to_use, cli_prompt_for_rerun)
    log_map_server(f"--- {config.SYMBOLS['info']} Core Conflict Removal Group Finished (Success: {success}) ---", "info" if success else "error", logger_to_use)
    return success


def prereqs_install_group(current_logger: logging.Logger) -> bool:
    """
    Execute all prerequisite installation steps as a group.
    Now calls imported functions for Docker and Node.js from their new installer files.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"--- {config.SYMBOLS['info']} Starting Prerequisites Installation "
        "Group (core_setup version) ---", # Clarify which group this is
        "info",
        logger_to_use,
    )

    overall_success = True
    steps_in_group = [
        (
            "BOOT_VERBOSITY",
            "Improve Boot Verbosity & Core Utils", # This function also does essential util install
            boot_verbosity,
        ),
        # core_install might be lean now if core_prerequisites.py handles most packages.
        # Review if CORE_INSTALL is still needed or if its packages are now in core_prerequisites.py
        ("CORE_INSTALL", "Install Core System Packages (core_setup specific)", core_install),
        # Use the imported functions for Docker and Node.js from their new locations
        # installer.docker_installer and installer.nodejs_installer
        ("DOCKER_INSTALL", "Install Docker Engine (via installer module)", install_docker_engine),
        ("NODEJS_INSTALL", "Install Node.js LTS (via installer module)", install_nodejs_lts),
    ]

    for tag, desc, func in steps_in_group:
        if not execute_step(
            step_tag=tag,
            step_description=desc,
            step_function=func,
            current_logger_instance=logger_to_use,
            prompt_user_for_rerun=cli_prompt_for_rerun,
        ): # pragma: no cover
            overall_success = False
            log_map_server(
                f"{config.SYMBOLS['error']} Step '{desc}' failed in "
                "Prerequisites group (core_setup).",
                "error",
                logger_to_use,
            )
            break

    log_map_server(
        f"--- {config.SYMBOLS['info']} Prerequisites Installation Group (core_setup version) "
        f"Finished (Overall Success: {overall_success}) ---",
        "info" if overall_success else "error", # pragma: no cover
        logger_to_use,
    )
    return overall_success