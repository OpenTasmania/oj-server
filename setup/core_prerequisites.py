# setup/core_prerequisites.py
# -*- coding: utf-8 -*-
"""
Functions for installing core system prerequisites.
Docker and Node.js installation are now handled by dedicated installer modules.
"""
# import getpass # No longer needed here directly
import logging
# import os # No longer needed here directly
# import tempfile # No longer needed here directly

from common.command_utils import log_map_server, run_command, run_elevated_command
from setup import config

# Import the new installer functions
from installer.docker_installer import install_docker_engine
from installer.nodejs_installer import install_nodejs_lts

module_logger = logging.getLogger(__name__)


def install_essential_utilities(current_logger=None):
    # ... (implementation as before) ...
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['package']} System update and essential utilities install...",
        "info",
        logger_to_use,
    )
    try:
        run_elevated_command(["apt", "update"], current_logger=logger_to_use)
        run_elevated_command(
            ["apt", "--yes", "upgrade"], current_logger=logger_to_use
        )
        essential_utils = [
            "curl", "wget", "bash", "btop", "screen",
            "ca-certificates", "lsb-release", "gnupg", "dirmngr",
            "git", "unzip", "vim", "build-essential",
            "packagekit", "python-apt-common", "apt-transport-https",
            "qemu-guest-agent"
        ]
        initial_core_prereqs = [
            pkg for pkg in config.CORE_PREREQ_PACKAGES
            if pkg not in essential_utils and pkg not in ["ufw"]
        ]
        run_elevated_command(
            ["apt", "--yes", "install"] + essential_utils + initial_core_prereqs,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} System updated and essential utilities/prerequisites ensured.",
            "success",
            logger_to_use,
        )
    except Exception as e: # pragma: no cover
        log_map_server(
            f"{config.SYMBOLS['error']} Failed during system update/essential util install: {e}", "error", logger_to_use)
        raise


def install_python_system_packages(current_logger=None):
    # ... (implementation as before) ...
    logger_to_use = current_logger if current_logger else module_logger
    if not config.PYTHON_SYSTEM_PACKAGES: # pragma: no cover
        log_map_server(f"{config.SYMBOLS['info']} No Python system packages listed to install.", "info", logger_to_use)
        return
    log_map_server(
        f"{config.SYMBOLS['package']} Installing Python system packages: {', '.join(config.PYTHON_SYSTEM_PACKAGES)}...",
        "info", logger_to_use)
    try:
        run_elevated_command(
            ["apt", "--yes", "install"] + config.PYTHON_SYSTEM_PACKAGES,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Python system packages installed.", "success", logger_to_use)
    except Exception as e: # pragma: no cover
        log_map_server(f"{config.SYMBOLS['error']} Failed to install Python system packages: {e}", "error", logger_to_use)
        raise

def install_postgres_packages(current_logger=None):
    # ... (implementation as before) ...
    logger_to_use = current_logger if current_logger else module_logger
    if not config.POSTGRES_PACKAGES: # pragma: no cover
        log_map_server(f"{config.SYMBOLS['info']} No PostgreSQL packages listed to install.", "info", logger_to_use)
        return
    log_map_server(
        f"{config.SYMBOLS['package']} Installing PostgreSQL packages: {', '.join(config.POSTGRES_PACKAGES)}...",
        "info", logger_to_use)
    try:
        run_elevated_command(
            ["apt", "--yes", "install"] + config.POSTGRES_PACKAGES,
            current_logger=logger_to_use,
        )
        log_map_server(f"{config.SYMBOLS['success']} PostgreSQL packages installed.", "success", logger_to_use)
    except Exception as e: # pragma: no cover
        log_map_server(f"{config.SYMBOLS['error']} Failed to install PostgreSQL packages: {e}", "error", logger_to_use)
        raise


def install_mapping_and_font_packages(current_logger=None):
    # ... (implementation as before) ...
    logger_to_use = current_logger if current_logger else module_logger
    packages_to_install = config.MAPPING_PACKAGES + config.FONT_PACKAGES
    if not packages_to_install: # pragma: no cover
        log_map_server(f"{config.SYMBOLS['info']} No mapping or font packages listed to install.", "info", logger_to_use)
        return
    log_map_server(f"{config.SYMBOLS['package']} Installing mapping and font packages...", "info", logger_to_use)
    try:
        if config.MAPPING_PACKAGES: # pragma: no cover
            log_map_server(f"  Mapping packages: {', '.join(config.MAPPING_PACKAGES)}", "debug", logger_to_use)
        if config.FONT_PACKAGES: # pragma: no cover
            log_map_server(f"  Font packages: {', '.join(config.FONT_PACKAGES)}", "debug", logger_to_use)
        run_elevated_command(
            ["apt", "--yes", "install"] + packages_to_install,
            current_logger=logger_to_use,
        )
        log_map_server(f"{config.SYMBOLS['success']} Mapping and font packages installed.", "success", logger_to_use)
    except Exception as e: # pragma: no cover
        log_map_server(f"{config.SYMBOLS['error']} Failed to install mapping/font packages: {e}", "error", logger_to_use)
        raise


def install_unattended_upgrades(current_logger=None):
    # ... (implementation as before) ...
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['package']} Installing unattended-upgrades...", "info", logger_to_use)
    try:
        run_elevated_command(
            ["apt", "--yes", "install", "unattended-upgrades"],
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["dpkg-reconfigure", "--priority=low", "unattended-upgrades"],
            cmd_input="yes\n",
            current_logger=logger_to_use,
        )
        log_map_server(f"{config.SYMBOLS['success']} unattended-upgrades installed and basic enable attempted.", "success", logger_to_use)
    except Exception as e: # pragma: no cover
        log_map_server(f"{config.SYMBOLS['error']} Failed to install or configure unattended-upgrades: {e}", "error", logger_to_use)


# REMOVE install_docker_engine function implementation
# REMOVE install_nodejs_lts function implementation


def core_prerequisites_group(current_logger=None): # pragma: no cover
    """Runs all core prerequisite installation steps."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"--- {config.SYMBOLS['info']} Starting Core Prerequisites Installation Group ---", "info",
                   logger_to_use)
    overall_success = True

    # Import step_executor and cli_handler locally for the group function
    # to avoid making them global imports if this module is imported elsewhere early.
    # However, it's generally fine to have them at module level if this file is part of the 'setup' package.
    from setup.step_executor import execute_step
    from setup.cli_handler import cli_prompt_for_rerun

    prereq_steps = [
        ("ESSENTIAL_UTILS_UPDATE", "Install Essential Utilities & Update System", install_essential_utilities),
        ("PYTHON_PACKAGES", "Install Python System Packages", install_python_system_packages),
        ("POSTGRES_PACKAGES", "Install PostgreSQL Packages", install_postgres_packages),
        ("MAPPING_FONT_PACKAGES", "Install Mapping & Font Packages", install_mapping_and_font_packages),
        ("UNATTENDED_UPGRADES", "Install Unattended Upgrades", install_unattended_upgrades),
        # Call the imported functions for Docker and Node.js
        ("DOCKER_ENGINE", "Install Docker Engine", install_docker_engine),
        ("NODEJS_LTS", "Install Node.js LTS", install_nodejs_lts),
    ]

    for tag, desc, func_ref in prereq_steps:
        if not execute_step(tag, desc, func_ref, logger_to_use, cli_prompt_for_rerun):
            overall_success = False
            log_map_server(f"{config.SYMBOLS['error']} Prerequisite step '{desc}' failed. Aborting group.", "error",
                           logger_to_use)
            break

    log_map_server(
        f"--- {config.SYMBOLS['info']} Core Prerequisites Installation Group Finished (Success: {overall_success}) ---",
        "info" if overall_success else "error", logger_to_use)
    return overall_success