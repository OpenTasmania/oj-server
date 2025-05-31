# setup/core_setup.py
# -*- coding: utf-8 -*-
"""
Functions for core system setup tasks.

This module includes functions for improving boot verbosity, removing
conflicting packages (like system Node.js), installing essential system
packages, Docker, and Node.js LTS from NodeSource. It also defines
group functions to orchestrate these core setup steps.
"""

import getpass  # For user-related operations
import logging
import os
import tempfile
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

module_logger = logging.getLogger(__name__)


def boot_verbosity(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Improve boot verbosity by modifying GRUB configuration and add user to
    systemd-journal group. Also performs a system update and installs
    essential utilities.

    Args:
        current_logger: Optional logger instance to use.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Improving boot verbosity & core utils...",
        "info",
        logger_to_use,
    )

    grub_file = "/etc/default/grub"
    if backup_file(grub_file, current_logger=logger_to_use):
        try:
            # SED expressions to remove 'quiet' and 'splash' from GRUB config.
            sed_expressions = [
                r"-e",
                r"/^GRUB_CMDLINE_LINUX_DEFAULT=/s/\bquiet\b//g",
                r"-e",
                r"/^GRUB_CMDLINE_LINUX_DEFAULT=/s/\bsplash\b//g",
                r"-e",
                r"/^GRUB_CMDLINE_LINUX_DEFAULT=/s/  +/ /g",  # Compact spaces
                r"-e",
                r'/^GRUB_CMDLINE_LINUX_DEFAULT=/s/" /"/g',  # Trim leading space in value
                r"-e",
                r'/^GRUB_CMDLINE_LINUX_DEFAULT=/s/ "/"/g',  # Trim trailing space in value
            ]
            run_elevated_command(
                ["sed", "-i"] + sed_expressions + [grub_file],
                current_logger=logger_to_use,
            )
            run_elevated_command(
                ["update-grub"], current_logger=logger_to_use
            )
            run_elevated_command(
                ["update-initramfs", "-u"], current_logger=logger_to_use
            )
            log_map_server(
                f"{config.SYMBOLS['success']} Boot verbosity improved.",
                "success",
                logger_to_use,
            )
        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to update grub for boot "
                f"verbosity: {e}",
                "error",
                logger_to_use,
            )
            # Non-critical, so we don't re-raise here.

    current_user_name = getpass.getuser()
    log_map_server(
        f"{config.SYMBOLS['gear']} Adding user '{current_user_name}' to "
        "'systemd-journal' group...",
        "info",
        logger_to_use,
    )
    try:
        run_elevated_command(
            [
                "usermod",
                "--append",
                "--group",
                "systemd-journal",
                current_user_name,
            ],
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} User {current_user_name} added to "
            "systemd-journal group.",
            "success",
            logger_to_use,
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['warning']} Could not add user "
            f"{current_user_name} to systemd-journal group: {e}. This may "
            "be non-critical.",
            "warning",
            logger_to_use,
        )

    log_map_server(
        f"{config.SYMBOLS['package']} System update and essential utilities "
        "install...",
        "info",
        logger_to_use,
    )
    try:
        run_elevated_command(["apt", "update"], current_logger=logger_to_use)
        run_elevated_command(
            ["apt", "--yes", "upgrade"], current_logger=logger_to_use
        )
        essential_utils = [
            "curl",
            "wget",
            "bash",
            "btop",
            "screen",
            "ca-certificates",
            "lsb-release",
            "gnupg",
        ]
        run_elevated_command(
            ["apt", "--yes", "install"] + essential_utils,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} System updated and essential "
            "utilities ensured.",
            "success",
            logger_to_use,
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed during system update/essential "
            f"util install: {e}",
            "error",
            logger_to_use,
        )
        raise  # This is more critical for subsequent steps.


def core_conflict_removal(
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Remove potentially conflicting system-installed Node.js packages.

    This is done to ensure that the Node.js version managed by NodeSource
    (or another method) is used without conflicts.

    Args:
        current_logger: Optional logger instance to use.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Removing conflicting system Node.js "
        "(if any)...",
        "info",
        logger_to_use,
    )
    try:
        # Check if 'nodejs' package is installed.
        result = run_command(
            ["dpkg", "-s", "nodejs"],
            check=False,  # Don't raise error if package not found.
            capture_output=True,
            current_logger=logger_to_use,
        )
        if result.returncode == 0:  # Package is installed.
            log_map_server(
                f"{config.SYMBOLS['info']} System 'nodejs' package found. "
                "Attempting removal...",
                "info",
                logger_to_use,
            )
            run_elevated_command(
                ["apt", "remove", "--purge", "--yes", "nodejs", "npm"],
                current_logger=logger_to_use,
            )
            run_elevated_command(
                ["apt", "--purge", "--yes", "autoremove"],
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{config.SYMBOLS['success']} System nodejs and npm removed.",
                "success",
                logger_to_use,
            )
        else:
            log_map_server(
                f"{config.SYMBOLS['info']} System 'nodejs' not found via dpkg, "
                "skipping removal.",
                "info",
                logger_to_use,
            )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Error during core conflict removal: {e}",
            "error",
            logger_to_use,
        )
        # Depending on severity, you might re-raise or just log.
        # For this step, it's often okay if it fails (e.g., package was already gone).


def core_install(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Install core system packages required for the map server.

    This includes prerequisites, Python, PostgreSQL, mapping tools, and fonts.

    Args:
        current_logger: Optional logger instance to use.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Installing core system packages...",
        "info",
        logger_to_use,
    )
    try:
        run_elevated_command(["apt", "update"], current_logger=logger_to_use)

        package_categories = {
            "prerequisite system utilities": config.CORE_PREREQ_PACKAGES,
            "Python system packages": config.PYTHON_SYSTEM_PACKAGES,
            "PostgreSQL system packages": config.POSTGRES_PACKAGES,
            "mapping system packages": config.MAPPING_PACKAGES,
            "font system packages": config.FONT_PACKAGES,
        }

        for category, packages in package_categories.items():
            if packages:  # Only attempt install if list is not empty
                log_map_server(
                    f"{config.SYMBOLS['package']} Installing {category}...",
                    "info",
                    logger_to_use,
                )
                run_elevated_command(
                    ["apt", "--yes", "install"] + packages,
                    current_logger=logger_to_use,
                )

        log_map_server(
            f"{config.SYMBOLS['package']} Installing unattended-upgrades...",
            "info",
            logger_to_use,
        )
        run_elevated_command(
            ["apt", "--yes", "install", "unattended-upgrades"],
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Core system packages installation "
            "process completed.",
            "success",
            logger_to_use,
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Error during core package "
            f"installation: {e}",
            "error",
            logger_to_use,
        )
        raise  # Package installation is critical.


def docker_install(current_logger: Optional[logging.Logger] = None) -> None:
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
    key_dest_tmp = ""  # Path for temporary GPG key download.

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
        # Create a temporary file for the GPG key.
        with tempfile.NamedTemporaryFile(
            delete=False, prefix="dockerkey_", suffix=".asc"
        ) as temp_f:
            key_dest_tmp = temp_f.name
        # Download the key.
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
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to download or install Docker "
            f"GPG key: {e}",
            "error",
            logger_to_use,
        )
        if key_dest_tmp and os.path.exists(key_dest_tmp):
            os.unlink(key_dest_tmp)  # Clean up temporary file.
        raise  # GPG key setup is critical for repository trust.
    finally:
        if key_dest_tmp and os.path.exists(key_dest_tmp):
            os.unlink(key_dest_tmp)

    log_map_server(
        f"{config.SYMBOLS['gear']} Adding Docker repository to Apt sources...",
        "info",
        logger_to_use,
    )
    try:
        # Determine system architecture and Debian codename.
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
    except Exception as e:
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
    except Exception as e:
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
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['warning']} Could not add user "
            f"{current_user_name} to docker group: {e}. Docker commands might "
            "require 'sudo' prefix from this user until re-login.",
            "warning",
            logger_to_use,
        )

    log_map_server(
        f"{config.SYMBOLS['gear']} Enabling and starting Docker services...",
        "info",
        logger_to_use,
    )
    run_elevated_command(
        ["systemctl", "enable", "docker.service"],
        current_logger=logger_to_use,
    )
    run_elevated_command(
        ["systemctl", "enable", "containerd.service"],
        current_logger=logger_to_use,
    )
    run_elevated_command(
        ["systemctl", "start", "docker.service"], current_logger=logger_to_use
    )
    log_map_server(
        f"{config.SYMBOLS['success']} Docker setup complete.",
        "success",
        logger_to_use,
    )


def node_js_lts_install(
    current_logger: Optional[logging.Logger] = None,
) -> None:
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
        nodesource_setup_url = "https://deb.nodesource.com/setup_lts.x"
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
            ["bash", "-"],  # Execute script content passed via stdin.
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

        # Verify installation by checking versions.
        node_version = (
            run_command(
                ["node", "--version"],
                capture_output=True,
                check=False,
                current_logger=logger_to_use,
            ).stdout.strip()
            or "Not detected"
        )
        npm_version = (
            run_command(
                ["npm", "--version"],
                capture_output=True,
                check=False,
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
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to install Node.js LTS: {e}",
            "error",
            logger_to_use,
        )
        raise  # Node.js might be critical for Carto or other tools.


def core_conflict_removal_group(current_logger: logging.Logger) -> bool:
    """
    Execute the core conflict removal step as a group.

    Args:
        current_logger: The logger instance to use.

    Returns:
        True if the step succeeds, False otherwise.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"--- {config.SYMBOLS['info']} Starting Core Conflict Removal Group "
        "---",
        "info",
        logger_to_use,
    )
    success = execute_step(
        step_tag="CORE_CONFLICTS",
        step_description="Remove Core Conflicts (e.g. system node)",
        step_function=core_conflict_removal,
        current_logger_instance=logger_to_use,
        prompt_user_for_rerun=cli_prompt_for_rerun,
    )
    log_map_server(
        f"--- {config.SYMBOLS['info']} Core Conflict Removal Group Finished "
        f"(Success: {success}) ---",
        "info" if success else "error",
        logger_to_use,
    )
    return success


def prereqs_install_group(current_logger: logging.Logger) -> bool:
    """
    Execute all prerequisite installation steps as a group.

    This includes boot verbosity changes, core package installation,
    Docker installation, and Node.js installation.

    Args:
        current_logger: The logger instance to use.

    Returns:
        True if all steps in the group succeed, False otherwise.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"--- {config.SYMBOLS['info']} Starting Prerequisites Installation "
        "Group ---",
        "info",
        logger_to_use,
    )

    overall_success = True
    steps_in_group = [
        (
            "BOOT_VERBOSITY",
            "Improve Boot Verbosity & Core Utils",
            boot_verbosity,
        ),
        ("CORE_INSTALL", "Install Core System Packages", core_install),
        ("DOCKER_INSTALL", "Install Docker Engine", docker_install),
        (
            "NODEJS_INSTALL",
            "Install Node.js (LTS from NodeSource)",
            node_js_lts_install,
        ),
    ]

    for tag, desc, func in steps_in_group:
        if not execute_step(
            step_tag=tag,
            step_description=desc,
            step_function=func,
            current_logger_instance=logger_to_use,
            prompt_user_for_rerun=cli_prompt_for_rerun,
        ):
            overall_success = False
            log_map_server(
                f"{config.SYMBOLS['error']} Step '{desc}' failed in "
                "Prerequisites group.",
                "error",
                logger_to_use,
            )
            break  # Stop on first failure within the group.

    log_map_server(
        f"--- {config.SYMBOLS['info']} Prerequisites Installation Group "
        f"Finished (Overall Success: {overall_success}) ---",
        "info" if overall_success else "error",
        logger_to_use,
    )
    return overall_success
