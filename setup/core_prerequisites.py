# setup/core_prerequisites.py
# -*- coding: utf-8 -*-
"""
Functions for installing ALL core system prerequisites, including initial setup,
package installations, Docker, and Node.js.
"""

import getpass
import logging
from typing import (  # Added List, Tuple, Callable
    Callable,
    List,
    Optional,
    Tuple,
)

# check_package_installed is in common.command_utils and now takes app_settings
from common.command_utils import (
    check_package_installed,
    log_map_server,
    run_elevated_command,
)
from common.file_utils import backup_file

# installer functions for Docker and Node.js already accept app_settings
from installer.docker_installer import install_docker_engine
from installer.nodejs_installer import install_nodejs_lts
from setup import config as static_config  # For package lists, static paths
from setup.cli_handler import (
    cli_prompt_for_rerun,
)
from setup.config_models import AppSettings
from setup.step_executor import (
    execute_step,
)

module_logger = logging.getLogger(__name__)

# Define Task Tags as constants to be used internally and for import by tests
PREREQ_BOOT_VERBOSITY_TAG = "PREREQ_BOOT_VERBOSITY_TAG"
PREREQ_CORE_CONFLICTS_TAG = "PREREQ_CORE_CONFLICTS_TAG"
PREREQ_ESSENTIAL_UTILS_TAG = "PREREQ_ESSENTIAL_UTILS_TAG"
PREREQ_PYTHON_PACKAGES_TAG = "PREREQ_PYTHON_PACKAGES_TAG"
PREREQ_POSTGRES_PACKAGES_TAG = "PREREQ_POSTGRES_PACKAGES_TAG"
PREREQ_MAPPING_FONT_PACKAGES_TAG = "PREREQ_MAPPING_FONT_PACKAGES_TAG"
PREREQ_UNATTENDED_UPGRADES_TAG = "PREREQ_UNATTENDED_UPGRADES_TAG"
PREREQ_DOCKER_ENGINE_TAG = "PREREQ_DOCKER_ENGINE_TAG"
PREREQ_NODEJS_LTS_TAG = "PREREQ_NODEJS_LTS_TAG"


StepExecutorFuncCore = Callable[[AppSettings, Optional[logging.Logger]], None]


def boot_verbosity(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Improves boot verbosity and adds user to systemd-journal group."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('step', '➡️')} Improving boot verbosity & journal group...",
        "info",
        logger_to_use,
        app_settings,
    )

    grub_file = "/etc/default/grub"
    if backup_file(grub_file, app_settings, current_logger=logger_to_use):
        try:
            sed_expressions = [
                r"-e",
                r"/^GRUB_CMDLINE_LINUX_DEFAULT=/s/\bquiet\b//g",
                r"-e",
                r"/^GRUB_CMDLINE_LINUX_DEFAULT=/s/\bsplash\b//g",
                r"-e",
                r"/^GRUB_CMDLINE_LINUX_DEFAULT=/s/  +/ /g",
                r"-e",
                r'/^GRUB_CMDLINE_LINUX_DEFAULT=/s/" /"/g',
                r"-e",
                r'/^GRUB_CMDLINE_LINUX_DEFAULT=/s/ "/"/g',
            ]
            run_elevated_command(
                ["sed", "-i"] + sed_expressions + [grub_file],
                app_settings,
                current_logger=logger_to_use,
            )
            run_elevated_command(
                ["update-grub"], app_settings, current_logger=logger_to_use
            )
            run_elevated_command(
                ["update-initramfs", "-u"],
                app_settings,
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{symbols.get('success', '✅')} Boot verbosity improved.",
                "success",
                logger_to_use,
                app_settings,
            )
        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '❌')} Failed to update grub for boot verbosity: {e}",
                "error",
                logger_to_use,
                app_settings,
                exc_info=True,
            )

    current_user_name = getpass.getuser()
    log_map_server(
        f"{symbols.get('gear', '⚙️')} Adding user '{current_user_name}' to 'systemd-journal' group...",
        "info",
        logger_to_use,
        app_settings,
    )
    try:
        run_elevated_command(
            ["usermod", "-aG", "systemd-journal", current_user_name],
            app_settings,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} User {current_user_name} added to systemd-journal group.",
            "success",
            logger_to_use,
            app_settings,
        )
    except Exception as e:
        log_map_server(
            f"{symbols.get('warning', '!')} Could not add user {current_user_name} to systemd-journal: {e}. This may be non-critical.",
            "warning",
            logger_to_use,
            app_settings,
        )
    log_map_server(
        f"{symbols.get('info', 'ℹ️')} Boot verbosity and journal group steps completed.",
        "info",
        logger_to_use,
        app_settings,
    )


def core_conflict_removal(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Removes potentially conflicting system-installed Node.js packages."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('step', '➡️')} Removing conflicting system Node.js (if any)...",
        "info",
        logger_to_use,
        app_settings,
    )
    try:
        if check_package_installed(
            "nodejs", app_settings=app_settings, current_logger=logger_to_use
        ):
            log_map_server(
                f"{symbols.get('info', 'ℹ️')} System 'nodejs' package found. Attempting removal...",
                "info",
                logger_to_use,
                app_settings,
            )
            run_elevated_command(
                ["apt", "remove", "--purge", "--yes", "nodejs", "npm"],
                app_settings,
                current_logger=logger_to_use,
            )
            run_elevated_command(
                ["apt", "--purge", "--yes", "autoremove"],
                app_settings,
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{symbols.get('success', '✅')} System nodejs and npm removed.",
                "success",
                logger_to_use,
                app_settings,
            )
        else:
            log_map_server(
                f"{symbols.get('info', 'ℹ️')} System 'nodejs' not found via dpkg, skipping removal.",
                "info",
                logger_to_use,
                app_settings,
            )
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Error during core conflict removal: {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )


def install_essential_utilities(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('package', '📦')} System update and essential utilities install...",
        "info",
        logger_to_use,
        app_settings,
    )
    try:
        run_elevated_command(
            ["apt", "update"], app_settings, current_logger=logger_to_use
        )
        run_elevated_command(
            ["apt", "--yes", "upgrade"],
            app_settings,
            current_logger=logger_to_use,
        )

        essential_utils = list(set(static_config.CORE_PREREQ_PACKAGES))

        if essential_utils:
            log_map_server(
                f"{symbols.get('package', '📦')} Installing core prerequisites: {', '.join(essential_utils)}",
                "info",
                logger_to_use,
                app_settings,
            )
            run_elevated_command(
                ["apt", "--yes", "install"] + essential_utils,
                app_settings,
                current_logger=logger_to_use,
            )
        log_map_server(
            f"{symbols.get('success', '✅')} System updated and essential utilities/prerequisites ensured.",
            "success",
            logger_to_use,
            app_settings,
        )
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed during system update/essential util install: {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        raise


def install_python_system_packages(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    python_pkgs = static_config.PYTHON_SYSTEM_PACKAGES
    if not python_pkgs:
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} No Python system packages listed to install.",
            "info",
            logger_to_use,
            app_settings,
        )
        return
    log_map_server(
        f"{symbols.get('package', '📦')} Installing Python system packages: {', '.join(python_pkgs)}...",
        "info",
        logger_to_use,
        app_settings,
    )
    try:
        run_elevated_command(
            ["apt", "--yes", "install"] + python_pkgs,
            app_settings,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Python system packages installed.",
            "success",
            logger_to_use,
            app_settings,
        )
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to install Python system packages: {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        raise


def install_postgres_packages(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    pg_version = app_settings.pg.version
    pg_pkgs = static_config.POSTGRES_PACKAGES
    if not pg_pkgs:
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} No PostgreSQL packages listed.",
            "info",
            logger_to_use,
            app_settings,
        )
        return
    log_map_server(
        f"{symbols.get('package', '📦')} Installing PostgreSQL packages (for configured v{pg_version}): {', '.join(pg_pkgs)}...",
        "info",
        logger_to_use,
        app_settings,
    )
    try:
        run_elevated_command(
            ["apt", "--yes", "install"] + pg_pkgs,
            app_settings,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} PostgreSQL packages installed.",
            "success",
            logger_to_use,
            app_settings,
        )
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to install PostgreSQL packages: {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        raise


def install_mapping_and_font_packages(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    map_pkgs = static_config.MAPPING_PACKAGES
    font_pkgs = static_config.FONT_PACKAGES
    pkgs_to_install = map_pkgs + font_pkgs
    if not pkgs_to_install:
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} No mapping or font packages listed.",
            "info",
            logger_to_use,
            app_settings,
        )
        return
    log_map_server(
        f"{symbols.get('package', '📦')} Installing mapping and font packages...",
        "info",
        logger_to_use,
        app_settings,
    )
    try:
        if map_pkgs:
            log_map_server(
                f"  Mapping packages: {', '.join(map_pkgs)}",
                "debug",
                logger_to_use,
                app_settings,
            )
        if font_pkgs:
            log_map_server(
                f"  Font packages: {', '.join(font_pkgs)}",
                "debug",
                logger_to_use,
                app_settings,
            )
        run_elevated_command(
            ["apt", "--yes", "install"] + pkgs_to_install,
            app_settings,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Mapping and font packages installed.",
            "success",
            logger_to_use,
            app_settings,
        )
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to install mapping/font packages: {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        raise


def install_unattended_upgrades(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('package', '📦')} Installing unattended-upgrades...",
        "info",
        logger_to_use,
        app_settings,
    )
    try:
        run_elevated_command(
            ["apt", "--yes", "install", "unattended-upgrades"],
            app_settings,
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["dpkg-reconfigure", "--priority=low", "unattended-upgrades"],
            app_settings,
            cmd_input="yes\n",
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} unattended-upgrades installed & configured.",
            "success",
            logger_to_use,
            app_settings,
        )
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to install/configure unattended-upgrades: {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )


def core_prerequisites_group(
    app_cfg: AppSettings, current_logger: Optional[logging.Logger] = None
) -> bool:
    """Runs ALL core prerequisite installation steps, passing app_cfg."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"--- {app_cfg.symbols.get('info', 'ℹ️')} Starting Comprehensive Core Prerequisites Group ---",
        "info",
        logger_to_use,
        app_cfg,
    )
    overall_success = True

    prereq_steps_with_desc: List[Tuple[str, str, StepExecutorFuncCore]] = [
        (
            PREREQ_BOOT_VERBOSITY_TAG,
            "Improve Boot Verbosity & Journal Group",
            boot_verbosity,
        ),
        (
            PREREQ_CORE_CONFLICTS_TAG,
            "Remove Core Node.js Conflicts",
            core_conflict_removal,
        ),
        (
            PREREQ_ESSENTIAL_UTILS_TAG,
            "Install Essential Utilities & Update System",
            install_essential_utilities,
        ),
        (
            PREREQ_PYTHON_PACKAGES_TAG,
            "Install Python System Packages",
            install_python_system_packages,
        ),
        (
            PREREQ_POSTGRES_PACKAGES_TAG,
            "Install PostgreSQL Packages",
            install_postgres_packages,
        ),
        (
            PREREQ_MAPPING_FONT_PACKAGES_TAG,
            "Install Mapping & Font Packages",
            install_mapping_and_font_packages,
        ),
        (
            PREREQ_UNATTENDED_UPGRADES_TAG,
            "Install Unattended Upgrades",
            install_unattended_upgrades,
        ),
        (
            PREREQ_DOCKER_ENGINE_TAG,
            "Install Docker Engine",
            install_docker_engine,
        ),
        (
            PREREQ_NODEJS_LTS_TAG,
            "Install Node.js LTS",
            install_nodejs_lts,
        ),
    ]

    for tag, desc, step_func_ref in prereq_steps_with_desc:
        if not execute_step(
            tag,
            desc,
            step_func_ref,
            app_cfg,
            logger_to_use,
            lambda prompt, ac, cl_prompt: cli_prompt_for_rerun(
                prompt, app_settings=ac, current_logger_instance=cl_prompt
            ),
        ):
            overall_success = False
            log_map_server(
                f"{app_cfg.symbols.get('error', '❌')} Prerequisite step '{desc}' ({tag}) failed. Group aborted.",
                "error",
                logger_to_use,
                app_cfg,
            )
            break

    log_map_server(
        f"--- {app_cfg.symbols.get('info', 'ℹ️')} Core Prerequisites Group Finished (Success: {overall_success}) ---",
        "info" if overall_success else "error",
        logger_to_use,
        app_cfg,
    )
    return overall_success
