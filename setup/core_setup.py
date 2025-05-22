# setup/core_setup.py
"""
Functions for core system setup: package installation, Docker, Node.js, etc.
"""
import getpass  # For user-related operations
import logging
import os
import tempfile

from . import config  # For package lists, default values, and config.SYMBOLS
# Corrected import: SYMBOLS removed from here
from .command_utils import run_command, run_elevated_command, log_map_server
from .helpers import backup_file  # For backing up grub config
from .ui import execute_step

module_logger = logging.getLogger(__name__)


def boot_verbosity(current_logger=None) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    # Use config.SYMBOLS for direct access
    log_map_server(f"{config.SYMBOLS['step']} Improving boot verbosity & core utils...", "info", logger_to_use)

    grub_file = "/etc/default/grub"
    if backup_file(grub_file, current_logger=logger_to_use):
        try:
            sed_expressions = [
                r"-e", r'/^GRUB_CMDLINE_LINUX_DEFAULT=/s/\bquiet\b//g',
                r"-e", r'/^GRUB_CMDLINE_LINUX_DEFAULT=/s/\bsplash\b//g',
                r"-e", r'/^GRUB_CMDLINE_LINUX_DEFAULT=/s/  +/ /g',
                r"-e", r'/^GRUB_CMDLINE_LINUX_DEFAULT=/s/" /"/g',
                r"-e", r'/^GRUB_CMDLINE_LINUX_DEFAULT=/s/ "/"/g',
            ]
            run_elevated_command(["sed", "-i"] + sed_expressions + [grub_file], current_logger=logger_to_use)
            run_elevated_command(["update-grub"], current_logger=logger_to_use)
            run_elevated_command(["update-initramfs", "-u"], current_logger=logger_to_use)
            log_map_server(f"{config.SYMBOLS['success']} Boot verbosity improved.", "success", logger_to_use)
        except Exception as e:
            log_map_server(f"{config.SYMBOLS['error']} Failed to update grub for boot verbosity: {e}", "error",
                           logger_to_use)

    current_user = getpass.getuser()
    log_map_server(f"{config.SYMBOLS['gear']} Adding user '{current_user}' to 'systemd-journal' group...", "info",
                   logger_to_use)
    try:
        run_elevated_command(["usermod", "--append", "--group", "systemd-journal", current_user],
                             current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} User {current_user} added to systemd-journal group.", "success",
                       logger_to_use)
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['warning']} Could not add user {current_user} to systemd-journal group: {e}. This may be non-critical.",
            "warning", logger_to_use)

    log_map_server(f"{config.SYMBOLS['package']} System update and essential utilities install...", "info",
                   logger_to_use)
    try:
        run_elevated_command(["apt", "update"], current_logger=logger_to_use)
        run_elevated_command(["apt", "--yes", "upgrade"], current_logger=logger_to_use)
        essential_utils = ["curl", "wget", "bash", "btop", "screen", "ca-certificates", "lsb-release", "gnupg"]
        run_elevated_command(["apt", "--yes", "install"] + essential_utils, current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} System updated and essential utilities ensured.", "success",
                       logger_to_use)
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['error']} Failed during system update/essential util install: {e}", "error",
                       logger_to_use)
        raise


def core_conflict_removal(current_logger=None) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Removing conflicting system Node.js (if any)...", "info", logger_to_use)
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
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['error']} Error during core conflict removal: {e}", "error", logger_to_use)


def core_install(current_logger=None) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Installing core system packages...", "info", logger_to_use)
    try:
        run_elevated_command(["apt", "update"], current_logger=logger_to_use)

        log_map_server(
            f"{config.SYMBOLS['package']} Installing prerequisite system utilities (git, build-essential, etc.)...",
            "info", logger_to_use)
        run_elevated_command(["apt", "--yes", "install"] + config.CORE_PREREQ_PACKAGES, current_logger=logger_to_use)

        log_map_server(f"{config.SYMBOLS['package']} Installing Python system packages...", "info", logger_to_use)
        run_elevated_command(["apt", "--yes", "install"] + config.PYTHON_SYSTEM_PACKAGES, current_logger=logger_to_use)

        log_map_server(f"{config.SYMBOLS['package']} Installing PostgreSQL system packages...", "info", logger_to_use)
        run_elevated_command(["apt", "--yes", "install"] + config.POSTGRES_PACKAGES, current_logger=logger_to_use)

        log_map_server(f"{config.SYMBOLS['package']} Installing mapping system packages...", "info", logger_to_use)
        run_elevated_command(["apt", "--yes", "install"] + config.MAPPING_PACKAGES, current_logger=logger_to_use)

        log_map_server(f"{config.SYMBOLS['package']} Installing font system packages...", "info", logger_to_use)
        run_elevated_command(["apt", "--yes", "install"] + config.FONT_PACKAGES, current_logger=logger_to_use)

        log_map_server(f"{config.SYMBOLS['package']} Installing unattended-upgrades...", "info", logger_to_use)
        run_elevated_command(["apt", "--yes", "install", "unattended-upgrades"], current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} Core system packages installation process completed.", "success",
                       logger_to_use)
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['error']} Error during core package installation: {e}", "error", logger_to_use)
        raise


def docker_install(current_logger=None) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Setting up Docker Engine...", "info", logger_to_use)

    key_dest_final = "/etc/apt/keyrings/docker.asc"
    key_url = "https://download.docker.com/linux/debian/gpg"
    key_dest_tmp = ""

    try:
        log_map_server(f"{config.SYMBOLS['gear']} Ensuring Docker GPG key directory exists...", "info", logger_to_use)
        run_elevated_command(["install", "-m", "0755", "-d", os.path.dirname(key_dest_final)],
                             current_logger=logger_to_use)

        log_map_server(f"{config.SYMBOLS['gear']} Downloading Docker's GPG key to temporary location...", "info",
                       logger_to_use)
        with tempfile.NamedTemporaryFile(delete=False, prefix="dockerkey_", suffix=".asc") as temp_f:
            key_dest_tmp = temp_f.name
        run_command(["curl", "-fsSL", key_url, "-o", key_dest_tmp], current_logger=logger_to_use)

        log_map_server(f"{config.SYMBOLS['gear']} Installing Docker GPG key to {key_dest_final}...", "info",
                       logger_to_use)
        run_elevated_command(["cp", key_dest_tmp, key_dest_final], current_logger=logger_to_use)
        run_elevated_command(["chmod", "a+r", key_dest_final], current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} Docker GPG key installed.", "success", logger_to_use)
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['error']} Failed to download or install Docker GPG key: {e}", "error",
                       logger_to_use)
        if key_dest_tmp and os.path.exists(key_dest_tmp): os.unlink(key_dest_tmp)
        raise
    finally:
        if key_dest_tmp and os.path.exists(key_dest_tmp):
            os.unlink(key_dest_tmp)

    log_map_server(f"{config.SYMBOLS['gear']} Adding Docker repository to Apt sources...", "info", logger_to_use)
    try:
        arch_result = run_command(["dpkg", "--print-architecture"], capture_output=True, check=True,
                                  current_logger=logger_to_use)
        arch = arch_result.stdout.strip()
        codename_result = run_command(["lsb_release", "-cs"], capture_output=True, check=True,
                                      current_logger=logger_to_use)
        codename = codename_result.stdout.strip()
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Could not determine system architecture or codename for Docker setup: {e}",
            "error", logger_to_use)
        raise

    docker_source_list_content = f"deb [arch={arch} signed-by={key_dest_final}] https://download.docker.com/linux/debian {codename} stable\n"
    docker_sources_file = "/etc/apt/sources.list.d/docker.list"
    try:
        run_elevated_command(["tee", docker_sources_file], cmd_input=docker_source_list_content,
                             current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} Docker apt source configured: {docker_sources_file}", "success",
                       logger_to_use)
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['error']} Failed to write Docker apt source list: {e}", "error", logger_to_use)
        raise

    log_map_server(f"{config.SYMBOLS['gear']} Updating apt package list for Docker...", "info", logger_to_use)
    run_elevated_command(["apt", "update"], current_logger=logger_to_use)

    docker_packages_list = ["docker-ce", "docker-ce-cli", "containerd.io", "docker-buildx-plugin",
                            "docker-compose-plugin"]
    log_map_server(f"{config.SYMBOLS['package']} Installing Docker packages: {', '.join(docker_packages_list)}...",
                   "info", logger_to_use)
    run_elevated_command(["apt", "--yes", "install"] + docker_packages_list, current_logger=logger_to_use)

    current_user = getpass.getuser()
    log_map_server(f"{config.SYMBOLS['gear']} Adding current user ({current_user}) to the 'docker' group...", "info",
                   logger_to_use)
    try:
        run_elevated_command(["usermod", "-aG", "docker", current_user], current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} User {current_user} added to 'docker' group.", "success",
                       logger_to_use)
        log_map_server(
            f"   {config.SYMBOLS['warning']} You MUST log out and log back in for this group change to take full effect for your current session.",
            "warning", logger_to_use)
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['warning']} Could not add user {current_user} to docker group: {e}. Docker commands might require 'sudo' prefix from this user until re-login.",
            "warning", logger_to_use)

    log_map_server(f"{config.SYMBOLS['gear']} Enabling and starting Docker services...", "info", logger_to_use)
    run_elevated_command(["systemctl", "enable", "docker.service"], current_logger=logger_to_use)
    run_elevated_command(["systemctl", "enable", "containerd.service"], current_logger=logger_to_use)
    run_elevated_command(["systemctl", "start", "docker.service"], current_logger=logger_to_use)
    log_map_server(f"{config.SYMBOLS['success']} Docker setup complete.", "success", logger_to_use)


def node_js_lts_install(current_logger=None) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Installing Node.js LTS version using NodeSource...", "info",
                   logger_to_use)
    try:
        nodesource_setup_url = "https://deb.nodesource.com/setup_lts.x"
        log_map_server(f"{config.SYMBOLS['gear']} Downloading NodeSource setup script from {nodesource_setup_url}...",
                       "info", logger_to_use)
        curl_result = run_command(["curl", "-fsSL", nodesource_setup_url], capture_output=True, check=True,
                                  current_logger=logger_to_use)
        nodesource_script_content = curl_result.stdout

        log_map_server(f"{config.SYMBOLS['gear']} Executing NodeSource setup script with elevated privileges...",
                       "info", logger_to_use)
        run_elevated_command(["bash", "-"], cmd_input=nodesource_script_content, current_logger=logger_to_use)

        log_map_server(f"{config.SYMBOLS['gear']} Updating apt package list after adding NodeSource repo...", "info",
                       logger_to_use)
        run_elevated_command(["apt", "update"], current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['package']} Installing Node.js...", "info", logger_to_use)
        run_elevated_command(["apt", "--yes", "install", "nodejs"], current_logger=logger_to_use)

        node_version = run_command(["node", "--version"], capture_output=True, check=False,
                                   current_logger=logger_to_use).stdout.strip() or "Not detected"
        npm_version = run_command(["npm", "--version"], capture_output=True, check=False,
                                  current_logger=logger_to_use).stdout.strip() or "Not detected"
        log_map_server(
            f"{config.SYMBOLS['success']} Node.js installed. Version: {node_version}, NPM Version: {npm_version}",
            "success", logger_to_use)
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['error']} Failed to install Node.js LTS: {e}", "error", logger_to_use)
        raise


def core_conflict_removal_group(current_logger) -> bool:
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"--- {config.SYMBOLS['info']} Starting Core Conflict Removal Group ---", "info", logger_to_use)
    success = execute_step("CORE_CONFLICTS", "Remove Core Conflicts (e.g. system node)",
                           core_conflict_removal,
                           logger_to_use)
    log_map_server(f"--- {config.SYMBOLS['info']} Core Conflict Removal Group Finished (Success: {success}) ---",
                   "info" if success else "error", logger_to_use)
    return success


def prereqs_install_group(current_logger) -> bool:
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"--- {config.SYMBOLS['info']} Starting Prerequisites Installation Group ---", "info", logger_to_use)

    overall_success = True
    steps_in_group = [
        ("BOOT_VERBOSITY", "Improve Boot Verbosity & Core Utils", boot_verbosity),
        # core_conflict_removal is now its own group, called before this by main if --full
        ("CORE_INSTALL", "Install Core System Packages", core_install),
        ("DOCKER_INSTALL", "Install Docker Engine", docker_install),
        ("NODEJS_INSTALL", "Install Node.js (LTS from NodeSource)", node_js_lts_install),
    ]

    for tag, desc, func in steps_in_group:
        if not execute_step(tag, desc, func, logger_to_use):
            overall_success = False
            log_map_server(f"{config.SYMBOLS['error']} Step '{desc}' failed in Prerequisites group.", "error",
                           logger_to_use)
            # Decide if you want to break on first failure within a group
            # break

    log_map_server(
        f"--- {config.SYMBOLS['info']} Prerequisites Installation Group Finished (Overall Success: {overall_success}) ---",
        "info" if overall_success else "error", logger_to_use)
    return overall_success