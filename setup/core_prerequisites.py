# setup/core_prerequisites.py
# -*- coding: utf-8 -*-
"""
Functions for installing ALL core system prerequisites, including initial setup,
package installations, Docker, and Node.js.
"""

import getpass
import logging
import os  # For os.unlink, os.environ
import tempfile
from typing import (
    Callable,
    List,
    Optional,
    Tuple,
)

from common.command_utils import (
    check_package_installed,
    log_map_server,
    run_elevated_command,
)
from common.constants_loader import get_constant
from common.file_utils import backup_file
from installer.docker_installer import install_docker_engine
from installer.nodejs_installer import install_nodejs_lts
from setup import config as static_config
from setup.cli_handler import (
    cli_prompt_for_rerun,
)
from setup.config_models import AppSettings
from setup.step_executor import (
    execute_step,
)

module_logger = logging.getLogger(__name__)

PREREQ_BOOT_VERBOSITY_TAG = "PREREQ_BOOT_VERBOSITY_TAG"
PREREQ_CORE_CONFLICTS_TAG = "PREREQ_CORE_CONFLICTS_TAG"
PREREQ_ESSENTIAL_UTILS_TAG = "PREREQ_ESSENTIAL_UTILS_TAG"
PREREQ_PYTHON_PACKAGES_TAG = "PREREQ_PYTHON_PACKAGES_TAG"
PREREQ_POSTGRES_PACKAGES_TAG = "PREREQ_POSTGRES_PACKAGES_TAG"
PREREQ_MAPPING_FONT_PACKAGES_TAG = "PREREQ_MAPPING_FONT_PACKAGES_TAG"
PREREQ_UNATTENDED_UPGRADES_TAG = "PREREQ_UNATTENDED_UPGRADES_TAG"
# PREREQ_TZDATA_TAG is removed as tzdata is handled by install_essential_utilities
PREREQ_DOCKER_ENGINE_TAG = "PREREQ_DOCKER_ENGINE_TAG"
PREREQ_NODEJS_LTS_TAG = "PREREQ_NODEJS_LTS_TAG"

StepExecutorFuncCore = Callable[[AppSettings, Optional[logging.Logger]], None]


def apply_preseed_and_install_package(
    package_name: str,
    app_settings: AppSettings,
    current_logger: Optional[logging.Logger] = None,
    run_dpkg_reconfigure: bool = False,
) -> None:
    """
    Applies preseed configurations for a package and then installs it.

    If preseed data is found in app_settings.package_preseeding_values,
    it's loaded via debconf-set-selections before installing the package
    non-interactively.

    Args:
        package_name: The name of the Debian package to install.
        app_settings: The application settings object.
        current_logger: Optional logger instance.
        run_dpkg_reconfigure: If True, runs 'dpkg-reconfigure --frontend=noninteractive'
                              on the package after installation.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    preseed_data = app_settings.package_preseeding_values.get(package_name)
    temp_preseed_file: Optional[str] = None
    original_debian_frontend = os.environ.get("DEBIAN_FRONTEND")

    try:
        os.environ["DEBIAN_FRONTEND"] = "noninteractive"

        if preseed_data and isinstance(preseed_data, dict):
            log_map_server(
                f"{symbols.get('info', 'ℹ️')} Preseeding configuration for package '{package_name}'...",
                "info",
                logger_to_use,
                app_settings,
            )
            preseed_content = "\n".join([
                f"{package_name} {key} {value}"
                for key, value in preseed_data.items()
            ])
            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".preseed"
            ) as tmp_file:
                tmp_file.write(preseed_content)
                temp_preseed_file = tmp_file.name

            log_map_server(
                f"Temporary preseed file for {package_name} created at {temp_preseed_file} with content:\n{preseed_content}",
                "debug",
                logger_to_use,
                app_settings,
            )

            run_elevated_command(
                ["debconf-set-selections", temp_preseed_file],
                app_settings,
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{symbols.get('success', '✅')} Preseed values loaded for '{package_name}'.",
                "info",
                logger_to_use,
                app_settings,
            )
        else:
            log_map_server(
                f"{symbols.get('info', 'ℹ️')} No preseed data found in config for '{package_name}'. Proceeding with standard install.",
                "info",
                logger_to_use,
                app_settings,
            )

        log_map_server(
            f"{symbols.get('package', '📦')} Installing package '{package_name}'...",
            "info",
            logger_to_use,
            app_settings,
        )
        run_elevated_command(
            ["apt-get", "install", "-yq", package_name],
            app_settings,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Package '{package_name}' installed successfully.",
            "success",
            logger_to_use,
            app_settings,
        )

        if run_dpkg_reconfigure:
            log_map_server(
                f"{symbols.get('gear', '⚙️')} Running dpkg-reconfigure for '{package_name}'...",
                "info",
                logger_to_use,
                app_settings,
            )
            run_elevated_command(
                [
                    "dpkg-reconfigure",
                    "--frontend=noninteractive",
                    package_name,
                ],
                app_settings,
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{symbols.get('success', '✅')} dpkg-reconfigure completed for '{package_name}'.",
                "success",
                logger_to_use,
                app_settings,
            )

    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed during installation/configuration of package '{package_name}': {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        raise
    finally:
        if temp_preseed_file and os.path.exists(temp_preseed_file):
            try:
                os.unlink(temp_preseed_file)
                log_map_server(
                    f"Temporary preseed file {temp_preseed_file} deleted.",
                    "debug",
                    logger_to_use,
                    app_settings,
                )
            except OSError as e_unlink:  # pragma: no cover
                log_map_server(
                    f"{symbols.get('warning', '!')} Could not delete temporary preseed file {temp_preseed_file}: {e_unlink}",
                    "warning",
                    logger_to_use,
                    app_settings,
                )
        # Restore DEBIAN_FRONTEND
        if original_debian_frontend is None:
            if "DEBIAN_FRONTEND" in os.environ:
                del os.environ["DEBIAN_FRONTEND"]
        else:
            os.environ["DEBIAN_FRONTEND"] = original_debian_frontend


def boot_verbosity(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Improves the boot verbosity of the system by modifying GRUB configuration, updating
    the bootloader, and ensuring the user is added to the 'systemd-journal' group for
    journal access. This function involves making changes to system-level files and
    configurations, and hence requires elevated privileges.

    Args:
        app_settings (AppSettings): Configuration settings object containing details
        such as logging preferences and file paths.

        current_logger (Optional[logging.Logger]): Logger instance to be used for
        logging messages. If not provided, a module-level logger will be used.

    Raises:
        Exception: If an error occurs during the GRUB file update, running associated
        elevated commands, or adding the user to the 'systemd-journal' group. Errors
        will be logged with appropriate severity.
    """
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
        except Exception as e:  # pragma: no cover
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
    except Exception as e:  # pragma: no cover
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
    """
    Removes conflicting system-installed Node.js and npm packages, if any, using elevated
    commands to ensure compatibility with custom tools or applications.

    This function interacts with the system's environment and package configuration,
    modifying the `DEBIAN_FRONTEND` to run apt in a non-interactive manner. If
    conflicting system packages are detected, it performs their removal along with
    dependent configurations. Logs the entire process using the provided or default logger.

    Args:
        app_settings (AppSettings): Contains application configuration values required for
            operations such as symbols for logging, and other related settings.
        current_logger (Optional[logging.Logger]): A logger instance to record messages;
            if not provided, a default module-level logger is utilized.

    Raises:
        Exception: Any exceptions raised during execution will be logged and re-raised.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('step', '➡️')} Removing conflicting system Node.js (if any)...",
        "info",
        logger_to_use,
        app_settings,
    )
    original_debian_frontend = os.environ.get("DEBIAN_FRONTEND")
    try:
        os.environ["DEBIAN_FRONTEND"] = "noninteractive"
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
                ["apt-get", "remove", "--purge", "-yq", "nodejs", "npm"],
                app_settings,
                current_logger=logger_to_use,
            )
            run_elevated_command(
                ["apt-get", "--purge", "-yq", "autoremove"],
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
    except Exception as e:  # pragma: no cover
        log_map_server(
            f"{symbols.get('error', '❌')} Error during core conflict removal: {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
    finally:
        if original_debian_frontend is None:
            if "DEBIAN_FRONTEND" in os.environ:
                del os.environ["DEBIAN_FRONTEND"]
        else:
            os.environ["DEBIAN_FRONTEND"] = original_debian_frontend


def install_essential_utilities(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Installs essential utilities and updates the system for the provided application settings.

    This function performs a system update and ensures that a predefined set of
    essential utilities are installed on the system. It logs progress and errors
    using the specified logger or the default module logger. The function also
    handles the 'DEBIAN_FRONTEND' environment variable to suppress prompts during
    package installation.

    Parameters:
        app_settings (AppSettings): The application's settings object containing
            configuration details and logging preferences.
        current_logger (Optional[logging.Logger]): A custom logger to use for logging
            progress and errors. If not provided, the module's default logger will
            be used.

    Raises:
        Exception: If any error occurs during the system update or essential utility
            installation.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('package', '📦')} System update and essential utilities install...",
        "info",
        logger_to_use,
        app_settings,
    )
    original_debian_frontend = os.environ.get("DEBIAN_FRONTEND")
    try:
        os.environ["DEBIAN_FRONTEND"] = "noninteractive"
        run_elevated_command(
            ["apt-get", "update", "-yq"],
            app_settings,
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["apt-get", "-yq", "upgrade"],
            app_settings,
            current_logger=logger_to_use,
        )

        essential_utils = list(
            set(
                get_constant(
                    "packages.core_prereq", static_config.CORE_PREREQ_PACKAGES
                )
            )
        )
        if not essential_utils:  # pragma: no cover
            log_map_server(
                f"{symbols.get('info', 'ℹ️')} No essential utility packages listed to install.",
                "info",
                logger_to_use,
                app_settings,
            )
        else:
            log_map_server(
                f"{symbols.get('package', '📦')} Processing essential utility packages: {', '.join(essential_utils)}",
                "info",
                logger_to_use,
                app_settings,
            )
            for pkg_name in essential_utils:
                needs_reconfigure = pkg_name == "tzdata"
                apply_preseed_and_install_package(
                    pkg_name,
                    app_settings,
                    logger_to_use,
                    run_dpkg_reconfigure=needs_reconfigure,
                )

        log_map_server(
            f"{symbols.get('success', '✅')} System updated and essential utilities/prerequisites ensured.",
            "success",
            logger_to_use,
            app_settings,
        )
    except Exception as e:  # pragma: no cover
        log_map_server(
            f"{symbols.get('error', '❌')} Failed during system update/essential util install: {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        raise
    finally:
        if original_debian_frontend is None:
            if "DEBIAN_FRONTEND" in os.environ:
                del os.environ["DEBIAN_FRONTEND"]
        else:
            os.environ["DEBIAN_FRONTEND"] = original_debian_frontend


def _install_package_list(
    package_list: List[str],
    list_description: str,
    app_settings: AppSettings,
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Installs a list of packages with optional logging and app-specific configurations.

    The function handles the installation of system packages provided in the package list,
    utilizing app-specific settings and logging mechanisms. When no packages are specified,
    a corresponding log message is generated. This function also ensures informative logging
    of the installation process, success, and errors that might occur during execution.

    Parameters:
    package_list: List[str]
        A list of package names to be installed.
    list_description: str
        A brief description of the package list (e.g., "system", "application") used in log messages.
    app_settings: AppSettings
        Application settings providing configurations such as symbols and other utilities.
    current_logger: Optional[logging.Logger]
        A logger instance to be used for logging messages. Defaults to module_logger if not provided.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols

    if not package_list:
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} No {list_description} packages listed to install.",
            "info",
            logger_to_use,
            app_settings,
        )
        return

    log_map_server(
        f"{symbols.get('package', '📦')} Installing {list_description} packages: {', '.join(package_list)}...",
        "info",
        logger_to_use,
        app_settings,
    )
    try:
        for pkg_name in package_list:
            apply_preseed_and_install_package(
                pkg_name,
                app_settings,
                logger_to_use,
                run_dpkg_reconfigure=False,
            )
        log_map_server(
            f"{symbols.get('success', '✅')} {list_description} packages installed.",
            "success",
            logger_to_use,
            app_settings,
        )
    except Exception as e:  # pragma: no cover
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to install {list_description} packages: {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        raise


def install_python_system_packages(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Installs required Python system packages based on application settings.

    This function handles the installation of Python system packages by retrieving
    a predefined list of package names and invoking an internal utility function
    to manage the installation process. It operates using the application's
    configuration and an optional logger for reporting progress and potential issues.

    Parameters:
    app_settings : AppSettings
        The application settings object that provides necessary configurations
        for the installation process.
    current_logger : Optional[logging.Logger]
        An optional logger instance for logging installation progress or issues.
    """
    _install_package_list(
        get_constant(
            "packages.python_system", static_config.PYTHON_SYSTEM_PACKAGES
        ),
        "Python system",
        app_settings,
        current_logger,
    )


def install_postgres_packages(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Install PostgreSQL-related packages based on the provided application settings.

    This function is responsible for installing a predefined list of PostgreSQL-related
    packages. It uses a helper function to perform the actual installation process.
    The installation operation takes into consideration application settings and an
    optional logger instance for logging purposes.

    Parameters:
        app_settings (AppSettings): The application settings object that contains
            configuration details used for installing PostgreSQL packages.
        current_logger (Optional[logging.Logger]): An optional logger instance
            that may be used to log information about the installation process.

    Returns:
        None
    """
    _install_package_list(
        get_constant("packages.postgres", static_config.POSTGRES_PACKAGES),
        "PostgreSQL",
        app_settings,
        current_logger,
    )


def install_mapping_and_font_packages(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Install required mapping and font packages.

    This function retrieves a combined list of mapping and font package names
    and passes it to the `_install_package_list` function for installation.
    It utilizes configuration constants and logs the process using the
    provided logger.

    Arguments:
        app_settings (AppSettings): Configuration settings required for installing packages.
        current_logger (Optional[logging.Logger]): Logger instance for logging details
            about the installation process. If None, no logging occurs.

    Returns:
        None
    """
    combined_list = get_constant(
        "packages.mapping", static_config.MAPPING_PACKAGES
    ) + get_constant("packages.font", static_config.FONT_PACKAGES)
    _install_package_list(
        combined_list, "mapping and font", app_settings, current_logger
    )


def install_unattended_upgrades(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Installs and configures the 'unattended-upgrades' package using provided application
    settings and logger. Ensures preseed configuration is applied and package is
    reconfigured if required.

    Parameters
    ----------
    app_settings : AppSettings
        Configuration settings required for installing and configuring the package.
    current_logger : Optional[logging.Logger], optional
        A logger instance to be used for logging messages. If not provided, the
        module-level logger will be used.

    Raises
    ------
    Exception
        Propagates any exceptions encountered during the installation or configuration
        process after logging the error details.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    package_name = "unattended-upgrades"

    log_map_server(
        f"{symbols.get('package', '📦')} Installing and configuring '{package_name}' with preseeding...",
        "info",
        logger_to_use,
        app_settings,
    )
    try:
        apply_preseed_and_install_package(
            package_name,
            app_settings,
            logger_to_use,
            run_dpkg_reconfigure=True,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} '{package_name}' installed & configured.",
            "success",
            logger_to_use,
            app_settings,
        )
    except Exception as e:  # pragma: no cover
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to install/configure '{package_name}': {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        raise


def core_prerequisites_group(
    app_cfg: AppSettings, current_logger: Optional[logging.Logger] = None
) -> bool:
    """
    Executes a comprehensive sequence of core prerequisite steps for system preparation.

    The function runs a defined set of prerequisite steps in sequence, each with its
    own description and functionality. These steps include tasks such as improving
    boot verbosity, resolving conflicts, installing essential utilities, configuring
    packages, and setting up services like Docker and Node.js LTS. If any of the steps
    fail, execution halts, and the failure is logged. The function also communicates
    progress and results using the provided or a default logger.

    Parameters:
    app_cfg (AppSettings): Configuration settings for the application.
    current_logger (Optional[logging.Logger]): Logger instance to be used
        for logging messages. Defaults to None, in which case a module-level
        logger is used.

    Returns:
    bool: True if all steps in the group are completed successfully, otherwise False.

    Raises:
    None
    """
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
            "Install Essential Utilities & Update System (includes dynamic tzdata handling)",
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
            "Install Unattended Upgrades (with preseeding)",
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
            overall_success = False  # pragma: no cover
            log_map_server(
                f"{app_cfg.symbols.get('error', '❌')} Prerequisite step '{desc}' ({tag}) failed. Group aborted.",
                "error",
                logger_to_use,
                app_cfg,
            )  # pragma: no cover
            break  # pragma: no cover

    log_map_server(
        f"--- {app_cfg.symbols.get('info', 'ℹ️')} Core Prerequisites Group Finished (Success: {overall_success}) ---",
        "info" if overall_success else "error",
        logger_to_use,
        app_cfg,
    )
    return overall_success
