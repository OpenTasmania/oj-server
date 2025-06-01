# installer/docker_installer.py
# -*- coding: utf-8 -*-
"""
Handles the installation of Docker Engine.
"""
import getpass
import logging
import os
import tempfile
from typing import Optional

from common.command_utils import (
    log_map_server,
    run_command,
    run_elevated_command,
)
from common.system_utils import (
    get_debian_codename,  # Ensure this is refactored
)
from setup.config_models import AppSettings

module_logger = logging.getLogger(__name__)


def install_docker_engine(
        app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('step', '➡️')} Setting up Docker Engine...",
        "info",
        logger_to_use,
        app_settings,
    )

    key_dest_final = "/etc/apt/keyrings/docker.asc"
    key_url = "https://download.docker.com/linux/debian/gpg"
    key_dest_tmp = ""

    try:
        run_elevated_command(
            ["install", "-m", "0755", "-d", os.path.dirname(key_dest_final)],
            app_settings,
            current_logger=logger_to_use,
        )
        with tempfile.NamedTemporaryFile(
                delete=False, prefix="dockerkey_", suffix=".asc"
        ) as temp_f:
            key_dest_tmp = temp_f.name
        run_command(
            ["curl", "-fsSL", key_url, "-o", key_dest_tmp],
            app_settings,
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["cp", key_dest_tmp, key_dest_final],
            app_settings,
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["chmod", "a+r", key_dest_final],
            app_settings,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Docker GPG key installed.",
            "success",
            logger_to_use,
            app_settings,
        )
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to download/install Docker GPG key: {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        if key_dest_tmp and os.path.exists(key_dest_tmp):
            os.unlink(key_dest_tmp)
        raise
    finally:
        if key_dest_tmp and os.path.exists(key_dest_tmp):
            os.unlink(key_dest_tmp)

    try:
        arch_result = run_command(
            ["dpkg", "--print-architecture"],
            app_settings,
            capture_output=True,
            check=True,
            current_logger=logger_to_use,
        )
        arch = arch_result.stdout.strip()
        codename = get_debian_codename(
            app_settings, current_logger=logger_to_use
        )  # Pass app_settings
        if not codename:
            raise EnvironmentError(
                "Could not determine Debian codename for Docker."
            )
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Could not get system arch/codename for Docker: {e}",
            "error",
            logger_to_use,
            app_settings,
        )
        raise

    docker_source_list = f"deb [arch={arch} signed-by={key_dest_final}] https://download.docker.com/linux/debian {codename} stable\n"
    docker_sources_file = "/etc/apt/sources.list.d/docker.list"
    try:
        run_elevated_command(
            ["tee", docker_sources_file],
            app_settings,
            cmd_input=docker_source_list,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Docker apt source configured: {docker_sources_file}",
            "success",
            logger_to_use,
            app_settings,
        )
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to write Docker apt source: {e}",
            "error",
            logger_to_use,
            app_settings,
        )
        raise

    run_elevated_command(
        ["apt", "update"], app_settings, current_logger=logger_to_use
    )
    pkgs = [
        "docker-ce",
        "docker-ce-cli",
        "containerd.io",
        "docker-buildx-plugin",
        "docker-compose-plugin",
    ]
    log_map_server(
        f"{symbols.get('package', '📦')} Installing Docker packages: {', '.join(pkgs)}...",
        "info",
        logger_to_use,
        app_settings,
    )
    run_elevated_command(
        ["apt", "--yes", "install"] + pkgs,
        app_settings,
        current_logger=logger_to_use,
    )

    user = getpass.getuser()
    log_map_server(
        f"{symbols.get('gear', '⚙️')} Adding user {user} to 'docker' group...",
        "info",
        logger_to_use,
        app_settings,
    )
    try:
        run_elevated_command(
            ["usermod", "-aG", "docker", user],
            app_settings,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} User {user} added to 'docker' group.",
            "success",
            logger_to_use,
            app_settings,
        )
        log_map_server(
            f"   {symbols.get('warning', '!')} Log out and back in for this change to take full effect.",
            "warning",
            logger_to_use,
            app_settings,
        )
    except Exception as e:
        log_map_server(
            f"{symbols.get('warning', '!')} Could not add user {user} to docker group: {e}.",
            "warning",
            logger_to_use,
            app_settings,
        )
    log_map_server(
        f"{symbols.get('success', '✅')} Docker Engine packages installed.",
        "success",
        logger_to_use,
        app_settings,
    )
