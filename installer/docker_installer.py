# installer/docker_installer.py
# -*- coding: utf-8 -*-
"""
Handles the installation of Docker Engine.
"""
import getpass
import logging
import os
import tempfile
from typing import Optional # Added Optional

from common.command_utils import log_map_server, run_command, run_elevated_command
from setup import config # For SYMBOLS

module_logger = logging.getLogger(__name__)

def install_docker_engine(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Install Docker Engine from Docker's official repository.

    Args:
        current_logger: Optional logger instance to use.
    """
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
        log_map_server(
            f"{config.SYMBOLS['gear']} Ensuring Docker GPG key directory "
            "exists...",
            "info",
            logger_to_use,
        )
        run_elevated_command(
            ["install", "-m", "0755", "-d", os.path.dirname(key_dest_final)],
            current_logger=logger_to_use,
        )

        log_map_server(
            f"{config.SYMBOLS['gear']} Downloading Docker's GPG key to "
            "temporary location...",
            "info",
            logger_to_use,
        )
        with tempfile.NamedTemporaryFile(
            delete=False, prefix="dockerkey_", suffix=".asc"
        ) as temp_f:
            key_dest_tmp = temp_f.name
        run_command(
            ["curl", "-fsSL", key_url, "-o", key_dest_tmp],
            current_logger=logger_to_use,
        )

        log_map_server(
            f"{config.SYMBOLS['gear']} Installing Docker GPG key to "
            f"{key_dest_final}...",
            "info",
            logger_to_use,
        )
        run_elevated_command(
            ["cp", key_dest_tmp, key_dest_final], current_logger=logger_to_use
        )
        run_elevated_command(
            ["chmod", "a+r", key_dest_final], current_logger=logger_to_use
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Docker GPG key installed.",
            "success",
            logger_to_use,
        )
    except Exception as e: # pragma: no cover
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to download or install Docker "
            f"GPG key: {e}",
            "error",
            logger_to_use,
        )
        if key_dest_tmp and os.path.exists(key_dest_tmp):
            os.unlink(key_dest_tmp)
        raise
    finally:
        if key_dest_tmp and os.path.exists(key_dest_tmp):
            os.unlink(key_dest_tmp)

    log_map_server(
        f"{config.SYMBOLS['gear']} Adding Docker repository to Apt sources...",
        "info",
        logger_to_use,
    )
    try:
        arch_result = run_command(
            ["dpkg", "--print-architecture"],
            capture_output=True,
            check=True,
            current_logger=logger_to_use,
        )
        arch = arch_result.stdout.strip()

        codename_result = run_command(
            ["lsb_release", "-cs"],
            capture_output=True,
            check=True,
            current_logger=logger_to_use,
        )
        codename = codename_result.stdout.strip()
    except Exception as e: # pragma: no cover
        log_map_server(
            f"{config.SYMBOLS['error']} Could not determine system "
            f"architecture or codename for Docker setup: {e}",
            "error",
            logger_to_use,
        )
        raise

    docker_source_list_content = (
        f"deb [arch={arch} signed-by={key_dest_final}] "
        f"https://download.docker.com/linux/debian {codename} stable\n"
    )
    docker_sources_file = "/etc/apt/sources.list.d/docker.list"
    try:
        run_elevated_command(
            ["tee", docker_sources_file],
            cmd_input=docker_source_list_content,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Docker apt source configured: "
            f"{docker_sources_file}",
            "success",
            logger_to_use,
        )
    except Exception as e: # pragma: no cover
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to write Docker apt source "
            f"list: {e}",
            "error",
            logger_to_use,
        )
        raise

    log_map_server(
        f"{config.SYMBOLS['gear']} Updating apt package list for Docker...",
        "info",
        logger_to_use,
    )
    run_elevated_command(["apt", "update"], current_logger=logger_to_use)

    docker_packages_list = [
        "docker-ce",
        "docker-ce-cli",
        "containerd.io",
        "docker-buildx-plugin",
        "docker-compose-plugin",
    ]
    log_map_server(
        f"{config.SYMBOLS['package']} Installing Docker packages: "
        f"{', '.join(docker_packages_list)}...",
        "info",
        logger_to_use,
    )
    run_elevated_command(
        ["apt", "--yes", "install"] + docker_packages_list,
        current_logger=logger_to_use,
    )

    current_user_name = getpass.getuser()
    log_map_server(
        f"{config.SYMBOLS['gear']} Adding current user ({current_user_name}) "
        "to the 'docker' group...",
        "info",
        logger_to_use,
    )
    try:
        run_elevated_command(
            ["usermod", "-aG", "docker", current_user_name],
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} User {current_user_name} added to "
            "'docker' group.",
            "success",
            logger_to_use,
        )
        log_map_server(
            f"   {config.SYMBOLS['warning']} You MUST log out and log back "
            "in for this group change to take full effect for your current "
            "session.",
            "warning",
            logger_to_use,
        )
    except Exception as e: # pragma: no cover
        log_map_server(
            f"{config.SYMBOLS['warning']} Could not add user "
            f"{current_user_name} to docker group: {e}. Docker commands might "
            "require 'sudo' prefix from this user until re-login.",
            "warning",
            logger_to_use,
        )

    log_map_server(
        f"{config.SYMBOLS['gear']} Enabling and starting Docker services...", # Note: Original file had success here, but service management is usually later.
        "info",                                                              # The function in core_prerequisites only did install.
        logger_to_use,
    )
    # Enabling and starting services are usually part of a "service activation" phase,
    # not typically inside the "installer" part for just the package.
    # The original install_docker_engine in core_prerequisites.py did NOT start/enable the service.
    # Let's keep it that way for this installer function.
    # run_elevated_command(["systemctl", "enable", "docker.service"], current_logger=logger_to_use)
    # run_elevated_command(["systemctl", "enable", "containerd.service"], current_logger=logger_to_use)
    # run_elevated_command(["systemctl", "start", "docker.service"], current_logger=logger_to_use)

    log_map_server(
        f"{config.SYMBOLS['success']} Docker Engine packages installed. Service management (start/enable) should be handled by a subsequent configuration or service activation step.",
        "success",
        logger_to_use,
    )