# installer/docker_installer.py
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
from common.system_utils import (
    get_debian_codename,
)
from setup.config_models import AppSettings

module_logger = logging.getLogger(__name__)


def install_docker_engine(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Sets up Docker Engine and its associated components on a Debian-based Linux system.

    This function configures the system to enable Docker installation by performing
    the following:
    - Downloads and installs the GPG key for Docker from Docker's official source.
    - Configures the Docker apt source for the appropriate system architecture and
      Debian codename.
    - Updates the package index and installs required Docker packages including
      `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`, and
      `docker-compose-plugin`.
    - Adds the current user to the 'docker' group for Docker CLI access without
      needing elevated privileges.

    Exception handling is provided for every critical step, logging errors as they
    occur to assist debugging and provide feedback to the user.

    Parameters:
        app_settings (AppSettings): An object containing application-level
            configuration, including logging and system-level utilities.
        current_logger (Optional[logging.Logger]): An optional logger instance. If
            not provided, a module-level logger is used.

    Raises:
        Exception: Raised for failures in any intermediate steps needed to configure
            and install Docker Engine. This includes missing system configurations
            or execution errors during critical commands.

    Returns:
        None
    """
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

    # Initialize AptManager
    apt_manager = AptManager(logger=logger_to_use)

    try:
        # Use AptManager to add GPG key
        apt_manager.add_gpg_key_from_url(key_url, key_dest_final)

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

    docker_source_list = f"deb [arch={arch} signed-by={key_dest_final}] https://download.docker.com/linux/debian {codename} stable"
    try:
        # Use AptManager to add repository
        apt_manager.add_repository(docker_source_list, update_after=True)

        log_map_server(
            f"{symbols.get('success', '✅')} Docker apt source configured and updated",
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
        )
        raise

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

    # Use AptManager to install packages
    # Note: We set update_first=False because we already updated when adding the repository
    apt_manager.install(pkgs, update_first=False)

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
