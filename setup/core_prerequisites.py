# setup/core_prerequisites.py
# -*- coding: utf-8 -*-
"""
Functions for installing ALL core system prerequisites, including initial setup,
package installations, Docker, and Node.js.
"""
import getpass
import logging
import os
# import tempfile # No longer needed as docker/nodejs installers are separate
from typing import Optional

from common.command_utils import log_map_server, run_command, run_elevated_command
from common.file_utils import backup_file  # Used by boot_verbosity
from setup import config
from setup.cli_handler import cli_prompt_for_rerun  # For the group function
from setup.step_executor import execute_step  # For the group function

# Import the new installer functions
from installer.docker_installer import install_docker_engine
from installer.nodejs_installer import install_nodejs_lts

module_logger = logging.getLogger(__name__)


# --- Functions moved from core_setup.py ---

def boot_verbosity(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Improve boot verbosity, add user to systemd-journal, update system,
    and install some essential utilities.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Improving boot verbosity & core utils (in core_prerequisites)...",
        "info",
        logger_to_use,
    )
    grub_file = "/etc/default/grub"
    if backup_file(grub_file, current_logger=logger_to_use):
        try:
            sed_expressions = [
                r"-e", r"/^GRUB_CMDLINE_LINUX_DEFAULT=/s/\bquiet\b//g",
                r"-e", r"/^GRUB_CMDLINE_LINUX_DEFAULT=/s/\bsplash\b//g",
                r"-e", r"/^GRUB_CMDLINE_LINUX_DEFAULT=/s/  +/ /g",
                r"-e", r'/^GRUB_CMDLINE_LINUX_DEFAULT=/s/" /"/g',
                r"-e", r'/^GRUB_CMDLINE_LINUX_DEFAULT=/s/ "/"/g',
            ]
            run_elevated_command(["sed", "-i"] + sed_expressions + [grub_file], current_logger=logger_to_use)
            run_elevated_command(["update-grub"], current_logger=logger_to_use)
            run_elevated_command(["update-initramfs", "-u"], current_logger=logger_to_use)
            log_map_server(f"{config.SYMBOLS['success']} Boot verbosity improved.", "success", logger_to_use)
        except Exception as e:  # pragma: no cover
            log_map_server(f"{config.SYMBOLS['error']} Failed to update grub for boot verbosity: {e}", "error",
                           logger_to_use)

    current_user_name = getpass.getuser()
    log_map_server(f"{config.SYMBOLS['gear']} Adding user '{current_user_name}' to 'systemd-journal' group...", "info",
                   logger_to_use)
    try:
        run_elevated_command(["usermod", "--append", "--group", "systemd-journal", current_user_name],
                             current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} User {current_user_name} added to systemd-journal group.",
                       "success", logger_to_use)
    except Exception as e:  # pragma: no cover
        log_map_server(
            f"{config.SYMBOLS['warning']} Could not add user {current_user_name} to systemd-journal group: {e}. This may be non-critical.",
            "warning", logger_to_use)

    # Note: install_essential_utilities will handle the system update and basic utils.
    # The original boot_verbosity also did some of this. We'll let install_essential_utilities be the main place.
    log_map_server(f"{config.SYMBOLS['info']} Boot verbosity and journal group steps completed.", "info", logger_to_use)


def core_conflict_removal(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Remove potentially conflicting system-installed Node.js packages.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Removing conflicting system Node.js (if any, in core_prerequisites)...",
        "info",
        logger_to_use,
    )
    try:
        result = run_command(["dpkg", "-s", "nodejs"], check=False, capture_output=True, current_logger=logger_to_use)
        if result.returncode == 0:
            log_map_server(f"{config.SYMBOLS['info']} System 'nodejs' package found. Attempting removal...", "info",
                           logger_to_use)
            run_elevated_command(["apt", "remove", "--purge", "--yes", "nodejs", "npm"], current_logger=logger_to_use)
            run_elevated_command(["apt", "--purge", "--yes", "autoremove"], current_logger=logger_to_use)
            log_map_server(f"{config.SYMBOLS['success']} System nodejs and npm removed.", "success", logger_to_use)
        else:
            log_map_server(f"{config.SYMBOLS['info']} System 'nodejs' not found via dpkg, skipping removal.", "info",
                           logger_to_use)
    except Exception as e:  # pragma: no cover
        log_map_server(f"{config.SYMBOLS['error']} Error during core conflict removal: {e}", "error", logger_to_use)


# --- Existing functions from core_prerequisites.py ---

def install_essential_utilities(current_logger=None):
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['package']} System update and essential utilities install (in core_prerequisites)...", "info",
        logger_to_use)
    try:
        run_elevated_command(["apt", "update"], current_logger=logger_to_use)
        run_elevated_command(["apt", "--yes", "upgrade"], current_logger=logger_to_use)
        # Consolidate essential utils here, including those previously in boot_verbosity's apt install part
        essential_utils_and_core_prereqs = list(set(  # Use set to avoid duplicates
            config.CORE_PREREQ_PACKAGES +
            ["curl", "wget", "bash", "btop", "screen", "ca-certificates", "lsb-release", "gnupg", "dirmngr"]
        ))
        # Remove 'ufw' if it's handled by a dedicated UFW setup step later, to avoid premature enabling.
        if "ufw" in essential_utils_and_core_prereqs:  # pragma: no cover
            essential_utils_and_core_prereqs.remove("ufw")  # Assuming UFW setup is a distinct phase

        if essential_utils_and_core_prereqs:
            run_elevated_command(
                ["apt", "--yes", "install"] + essential_utils_and_core_prereqs,
                current_logger=logger_to_use,
            )
        log_map_server(f"{config.SYMBOLS['success']} System updated and essential utilities/prerequisites ensured.",
                       "success", logger_to_use)
    except Exception as e:  # pragma: no cover
        log_map_server(f"{config.SYMBOLS['error']} Failed during system update/essential util install: {e}", "error",
                       logger_to_use)
        raise


def install_python_system_packages(current_logger=None):
    logger_to_use = current_logger if current_logger else module_logger
    if not config.PYTHON_SYSTEM_PACKAGES:  # pragma: no cover
        log_map_server(f"{config.SYMBOLS['info']} No Python system packages listed to install.", "info", logger_to_use)
        return
    log_map_server(
        f"{config.SYMBOLS['package']} Installing Python system packages: {', '.join(config.PYTHON_SYSTEM_PACKAGES)}...",
        "info", logger_to_use)
    try:
        run_elevated_command(["apt", "--yes", "install"] + config.PYTHON_SYSTEM_PACKAGES, current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} Python system packages installed.", "success", logger_to_use)
    except Exception as e:  # pragma: no cover
        log_map_server(f"{config.SYMBOLS['error']} Failed to install Python system packages: {e}", "error",
                       logger_to_use)
        raise


def install_postgres_packages(current_logger=None):
    logger_to_use = current_logger if current_logger else module_logger
    if not config.POSTGRES_PACKAGES:  # pragma: no cover
        log_map_server(f"{config.SYMBOLS['info']} No PostgreSQL packages listed to install.", "info", logger_to_use)
        return
    log_map_server(
        f"{config.SYMBOLS['package']} Installing PostgreSQL packages: {', '.join(config.POSTGRES_PACKAGES)}...", "info",
        logger_to_use)
    try:
        run_elevated_command(["apt", "--yes", "install"] + config.POSTGRES_PACKAGES, current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} PostgreSQL packages installed.", "success", logger_to_use)
    except Exception as e:  # pragma: no cover
        log_map_server(f"{config.SYMBOLS['error']} Failed to install PostgreSQL packages: {e}", "error", logger_to_use)
        raise


def install_mapping_and_font_packages(current_logger=None):
    logger_to_use = current_logger if current_logger else module_logger
    packages_to_install = config.MAPPING_PACKAGES + config.FONT_PACKAGES
    if not packages_to_install:  # pragma: no cover
        log_map_server(f"{config.SYMBOLS['info']} No mapping or font packages listed to install.", "info",
                       logger_to_use)
        return
    log_map_server(f"{config.SYMBOLS['package']} Installing mapping and font packages...", "info", logger_to_use)
    try:  # pragma: no cover
        if config.MAPPING_PACKAGES: log_map_server(f"  Mapping packages: {', '.join(config.MAPPING_PACKAGES)}", "debug",
                                                   logger_to_use)
        if config.FONT_PACKAGES: log_map_server(f"  Font packages: {', '.join(config.FONT_PACKAGES)}", "debug",
                                                logger_to_use)
        run_elevated_command(["apt", "--yes", "install"] + packages_to_install, current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} Mapping and font packages installed.", "success", logger_to_use)
    except Exception as e:  # pragma: no cover
        log_map_server(f"{config.SYMBOLS['error']} Failed to install mapping/font packages: {e}", "error",
                       logger_to_use)
        raise


def install_unattended_upgrades(current_logger=None):
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['package']} Installing unattended-upgrades...", "info", logger_to_use)
    try:
        run_elevated_command(["apt", "--yes", "install", "unattended-upgrades"], current_logger=logger_to_use)
        run_elevated_command(["dpkg-reconfigure", "--priority=low", "unattended-upgrades"], cmd_input="yes\n",
                             current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} unattended-upgrades installed and basic enable attempted.",
                       "success", logger_to_use)
    except Exception as e:  # pragma: no cover
        log_map_server(f"{config.SYMBOLS['error']} Failed to install or configure unattended-upgrades: {e}", "error",
                       logger_to_use)
        # Non-critical, don't raise


# Docker and Node.js install functions are now imported from installer/

def core_prerequisites_group(current_logger: Optional[logging.Logger] = None) -> bool:
    """Runs ALL core prerequisite installation steps."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"--- {config.SYMBOLS['info']} Starting Comprehensive Core Prerequisites Installation Group ---",
                   "info", logger_to_use)
    overall_success = True

    # Define unique tags for steps within this group for state management
    prereq_steps = [
        ("PREREQ_BOOT_VERBOSITY", "Improve Boot Verbosity & Journal Group", boot_verbosity),
        ("PREREQ_CORE_CONFLICTS", "Remove Core Conflicts (System Node.js)", core_conflict_removal),
        ("PREREQ_ESSENTIAL_UTILS", "Install Essential Utilities & Update System", install_essential_utilities),
        ("PREREQ_PYTHON_PACKAGES", "Install Python System Packages", install_python_system_packages),
        ("PREREQ_POSTGRES_PACKAGES", "Install PostgreSQL Packages", install_postgres_packages),
        ("PREREQ_MAPPING_FONT_PACKAGES", "Install Mapping & Font Packages", install_mapping_and_font_packages),
        ("PREREQ_UNATTENDED_UPGRADES", "Install Unattended Upgrades", install_unattended_upgrades),
        ("PREREQ_DOCKER_ENGINE", "Install Docker Engine (via installer module)", install_docker_engine),
        # Uses imported
        ("PREREQ_NODEJS_LTS", "Install Node.js LTS (via installer module)", install_nodejs_lts),  # Uses imported
    ]

    for tag, desc, func_ref in prereq_steps:
        if not execute_step(tag, desc, func_ref, logger_to_use, cli_prompt_for_rerun):  # pragma: no cover
            overall_success = False
            log_map_server(f"{config.SYMBOLS['error']} Prerequisite step '{desc}' ({tag}) failed. Aborting group.",
                           "error", logger_to_use)
            break

    log_map_server(
        f"--- {config.SYMBOLS['info']} Comprehensive Core Prerequisites Group Finished (Success: {overall_success}) ---",
        "info" if overall_success else "error", logger_to_use)  # pragma: no cover
    return overall_success