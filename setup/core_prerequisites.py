# setup/core_prerequisites.py
# -*- coding: utf-8 -*-
"""
Functions for installing core system prerequisites, Docker, and Node.js.
"""
import getpass  # For docker_install user add to group
import logging
import os
import tempfile

# Corrected import after moving command_utils
from common.command_utils import log_map_server, run_command, run_elevated_command

from setup import config  # For package lists and symbols

module_logger = logging.getLogger(__name__)


def install_essential_utilities(current_logger=None):
    """Installs essential command-line utilities and updates the system."""
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
        # These were part of boot_verbosity in core_setup.py
        essential_utils = [
            "curl", "wget", "bash", "btop", "screen",
            "ca-certificates", "lsb-release", "gnupg", "dirmngr",  # dirmngr added as it was a core_prereq
            "git", "unzip", "vim", "build-essential",  # from CORE_PREREQ_PACKAGES
            "packagekit", "python-apt-common", "apt-transport-https",  # from CORE_PREREQ_PACKAGES
            "qemu-guest-agent"  # from CORE_PREREQ_PACKAGES
        ]
        # Add other initial CORE_PREREQ_PACKAGES that are basic utils
        initial_core_prereqs = [
            pkg for pkg in config.CORE_PREREQ_PACKAGES
            if pkg not in essential_utils and pkg not in ["ufw"]  # ufw has its own setup
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
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed during system update/essential util install: {e}",
            "error",
            logger_to_use,
        )
        raise


def install_python_system_packages(current_logger=None):
    """Installs system-level Python packages."""
    logger_to_use = current_logger if current_logger else module_logger
    if not config.PYTHON_SYSTEM_PACKAGES:
        log_map_server(f"{config.SYMBOLS['info']} No Python system packages listed to install.", "info", logger_to_use)
        return
    log_map_server(
        f"{config.SYMBOLS['package']} Installing Python system packages: {', '.join(config.PYTHON_SYSTEM_PACKAGES)}...",
        "info",
        logger_to_use,
    )
    try:
        run_elevated_command(
            ["apt", "--yes", "install"] + config.PYTHON_SYSTEM_PACKAGES,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Python system packages installed.", "success", logger_to_use
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to install Python system packages: {e}", "error", logger_to_use
        )
        raise


def install_postgres_packages(current_logger=None):
    """Installs PostgreSQL and PostGIS packages."""
    logger_to_use = current_logger if current_logger else module_logger
    if not config.POSTGRES_PACKAGES:
        log_map_server(f"{config.SYMBOLS['info']} No PostgreSQL packages listed to install.", "info", logger_to_use)
        return
    log_map_server(
        f"{config.SYMBOLS['package']} Installing PostgreSQL packages: {', '.join(config.POSTGRES_PACKAGES)}...",
        "info",
        logger_to_use,
    )
    try:
        run_elevated_command(
            ["apt", "--yes", "install"] + config.POSTGRES_PACKAGES,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} PostgreSQL packages installed.", "success", logger_to_use
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to install PostgreSQL packages: {e}", "error", logger_to_use
        )
        raise


def install_mapping_and_font_packages(current_logger=None):
    """Installs mapping tools and font packages."""
    logger_to_use = current_logger if current_logger else module_logger

    packages_to_install = config.MAPPING_PACKAGES + config.FONT_PACKAGES
    if not packages_to_install:
        log_map_server(f"{config.SYMBOLS['info']} No mapping or font packages listed to install.", "info",
                       logger_to_use)
        return

    log_map_server(
        f"{config.SYMBOLS['package']} Installing mapping and font packages...",
        "info",
        logger_to_use,
    )
    # We can split them if detailed logging per category is needed
    # For now, batch install
    try:
        if config.MAPPING_PACKAGES:
            log_map_server(f"  Mapping packages: {', '.join(config.MAPPING_PACKAGES)}", "debug", logger_to_use)
        if config.FONT_PACKAGES:
            log_map_server(f"  Font packages: {', '.join(config.FONT_PACKAGES)}", "debug", logger_to_use)

        run_elevated_command(
            ["apt", "--yes", "install"] + packages_to_install,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Mapping and font packages installed.", "success", logger_to_use
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to install mapping/font packages: {e}", "error", logger_to_use
        )
        raise


def install_unattended_upgrades(current_logger=None):
    """Installs and configures unattended-upgrades."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['package']} Installing unattended-upgrades...",
        "info",
        logger_to_use,
    )
    try:
        run_elevated_command(
            ["apt", "--yes", "install", "unattended-upgrades"],
            current_logger=logger_to_use,
        )
        # Basic configuration: enable it by reconfiguring.
        # More advanced configuration would go into a configure/system_config.py
        run_elevated_command(
            ["dpkg-reconfigure", "--priority=low", "unattended-upgrades"],
            cmd_input="yes\n",  # Assuming it might ask to confirm enabling.
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} unattended-upgrades installed and basic enable attempted.",
            "success",
            logger_to_use,
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to install or configure unattended-upgrades: {e}", "error", logger_to_use
        )
        # Non-critical, don't raise


def install_docker_engine(current_logger=None):
    """Installs Docker Engine from Docker's official repository."""
    # This function's content would be moved from setup/core_setup.py::docker_install()
    # Remember to update imports to use common.command_utils
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Setting up Docker Engine...",
        "info",
        logger_to_use,
    )

    key_dest_final = "/etc/apt/keyrings/docker.asc"
    key_url = "https://download.docker.com/linux/debian/gpg"
    key_dest_tmp = ""

    try:
        log_map_server(f"{config.SYMBOLS['gear']} Ensuring Docker GPG key directory exists...", "info", logger_to_use)
        run_elevated_command(
            ["install", "-m", "0755", "-d", os.path.dirname(key_dest_final)],
            current_logger=logger_to_use,
        )

        with tempfile.NamedTemporaryFile(delete=False, prefix="dockerkey_", suffix=".asc") as temp_f:
            key_dest_tmp = temp_f.name
        run_command(
            ["curl", "-fsSL", key_url, "-o", key_dest_tmp], current_logger=logger_to_use
        )
        run_elevated_command(["cp", key_dest_tmp, key_dest_final], current_logger=logger_to_use)
        run_elevated_command(["chmod", "a+r", key_dest_final], current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} Docker GPG key installed.", "success", logger_to_use)
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['error']} Failed to download or install Docker GPG key: {e}", "error",
                       logger_to_use)
        if key_dest_tmp and os.path.exists(key_dest_tmp): os.unlink(key_dest_tmp)
        raise
    finally:
        if key_dest_tmp and os.path.exists(key_dest_tmp): os.unlink(key_dest_tmp)

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

    docker_source_list_content = (
        f"deb [arch={arch} signed-by={key_dest_final}] "
        f"https://download.docker.com/linux/debian {codename} stable\n"
    )
    docker_sources_file = "/etc/apt/sources.list.d/docker.list"
    try:
        run_elevated_command(["tee", docker_sources_file], cmd_input=docker_source_list_content,
                             current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} Docker apt source configured: {docker_sources_file}", "success",
                       logger_to_use)
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['error']} Failed to write Docker apt source list: {e}", "error", logger_to_use)
        raise

    run_elevated_command(["apt", "update"], current_logger=logger_to_use)
    docker_packages_list = ["docker-ce", "docker-ce-cli", "containerd.io", "docker-buildx-plugin",
                            "docker-compose-plugin"]
    log_map_server(f"{config.SYMBOLS['package']} Installing Docker packages: {', '.join(docker_packages_list)}...",
                   "info", logger_to_use)
    run_elevated_command(["apt", "--yes", "install"] + docker_packages_list, current_logger=logger_to_use)

    current_user_name = getpass.getuser()
    try:
        run_elevated_command(["usermod", "-aG", "docker", current_user_name], current_logger=logger_to_use)
        log_map_server(
            f"{config.SYMBOLS['success']} User {current_user_name} added to 'docker' group. You MUST log out and log back in for this to take effect.",
            "success", logger_to_use)
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['warning']} Could not add user {current_user_name} to docker group: {e}.",
                       "warning", logger_to_use)

    log_map_server(
        f"{config.SYMBOLS['success']} Docker Engine setup complete (service enabling/start handled by service setup phase).",
        "success", logger_to_use)


def install_nodejs_lts(current_logger=None):
    """Installs Node.js LTS from NodeSource."""
    # This function's content would be moved from setup/core_setup.py::node_js_lts_install()
    # Remember to update imports to use common.command_utils
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Installing Node.js LTS version using NodeSource...", "info",
                   logger_to_use)
    try:
        nodesource_setup_url = "https://deb.nodesource.com/setup_lts.x"  # Or specific version like setup_20.x
        curl_result = run_command(["curl", "-fsSL", nodesource_setup_url], capture_output=True, check=True,
                                  current_logger=logger_to_use)
        nodesource_script_content = curl_result.stdout
        run_elevated_command(["bash", "-"], cmd_input=nodesource_script_content, current_logger=logger_to_use)
        run_elevated_command(["apt", "update"], current_logger=logger_to_use)
        run_elevated_command(["apt", "--yes", "install", "nodejs"], current_logger=logger_to_use)
        node_version = (run_command(["node", "--version"], capture_output=True, check=False,
                                    current_logger=logger_to_use).stdout.strip() or "Not detected")
        npm_version = (run_command(["npm", "--version"], capture_output=True, check=False,
                                   current_logger=logger_to_use).stdout.strip() or "Not detected")
        log_map_server(
            f"{config.SYMBOLS['success']} Node.js installed. Version: {node_version}, NPM Version: {npm_version}",
            "success", logger_to_use)
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['error']} Failed to install Node.js LTS: {e}", "error", logger_to_use)
        raise


# This group function would be called by main_installer.py
def core_prerequisites_group(current_logger=None):
    """Runs all core prerequisite installation steps."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"--- {config.SYMBOLS['info']} Starting Core Prerequisites Installation Group ---", "info",
                   logger_to_use)
    overall_success = True

    prereq_steps = [
        ("ESSENTIAL_UTILS_UPDATE", "Install Essential Utilities & Update System", install_essential_utilities),
        ("PYTHON_PACKAGES", "Install Python System Packages", install_python_system_packages),
        ("POSTGRES_PACKAGES", "Install PostgreSQL Packages", install_postgres_packages),
        ("MAPPING_FONT_PACKAGES", "Install Mapping & Font Packages", install_mapping_and_font_packages),
        ("UNATTENDED_UPGRADES", "Install Unattended Upgrades", install_unattended_upgrades),
        ("DOCKER_ENGINE", "Install Docker Engine", install_docker_engine),
        ("NODEJS_LTS", "Install Node.js LTS", install_nodejs_lts),
    ]

    from setup.step_executor import \
        execute_step  # Local import to avoid circularity if this file is imported elsewhere early
    from setup.cli_handler import cli_prompt_for_rerun  # Same reason

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
