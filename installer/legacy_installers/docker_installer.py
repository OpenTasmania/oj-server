# ot-osm-osrm-server/installer/docker_installer.py
# -*- coding: utf-8 -*-
"""
Handles the installation of Docker Engine.
"""

import getpass
import logging
from typing import Optional

from common.command_utils import (
    log_map_server,
    run_command,
    run_elevated_command,
)
from common.debian.apt_manager import AptManager
from common.system_utils import get_debian_codename
from installer.config_models import AppSettings

module_logger = logging.getLogger(__name__)


def install_docker_engine(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Sets up Docker Engine and its associated components on a Debian-based Linux system
    using the official recommended method and modern apt sources.
    """
    logger_to_use = current_logger or module_logger
    symbols = app_settings.symbols
    docker_settings = app_settings.docker

    log_map_server(
        f"{symbols.get('step', '➡️')} Setting up Docker Engine...",
        "info",
        logger_to_use,
        app_settings,
    )

    apt_manager = AptManager(logger=logger_to_use)

    try:
        apt_manager.add_gpg_key_from_url(
            str(docker_settings.key_url),
            str(docker_settings.keyring_path),
            app_settings,
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
        raise

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
        )
        if not codename:
            raise EnvironmentError(
                "Could not determine Debian codename for Docker."
            )

        repo_details = {
            "Types": "deb",
            "URIs": str(docker_settings.repo_url),
            "Suites": codename,
            "Components": "stable",
            "Architectures": arch,
            "Signed-By": str(docker_settings.keyring_path),
        }

        apt_manager.add_repository(
            "docker", repo_details, app_settings, update_after=True
        )

        log_map_server(
            f"{symbols.get('success', '✅')} Docker apt source configured and updated.",
            "success",
            logger_to_use,
            app_settings,
        )
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to configure Docker apt source: {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        raise

    pkgs = docker_settings.packages
    log_map_server(
        f"{symbols.get('package', '📦')} Installing Docker packages: {', '.join(pkgs)}...",
        "info",
        logger_to_use,
        app_settings,
    )

    apt_manager.install(pkgs, app_settings, update_first=False)

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
