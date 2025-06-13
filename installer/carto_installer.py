# installer/carto_installer.py
# -*- coding: utf-8 -*-
"""
Handles installation of CartoCSS compiler (carto) and setup of the
OpenStreetMap-Carto stylesheet repository.
"""

import getpass
import grp
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from common.command_utils import (
    command_exists,
    log_map_server,
    run_command,
    run_elevated_command,
)

# Import static_config for OSM_PROJECT_ROOT and other true constants
from setup import config as static_config

# Import AppSettings for type hinting
from setup.config_models import AppSettings

module_logger = logging.getLogger(__name__)


OSM_CARTO_BASE_DIR = "/opt/openstreetmap-carto"


def install_carto_cli(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Installs the CartoCSS compiler (carto CLI) using npm and handles the required
    dependencies and processes to ensure successful installation. Logs the
    progress, success, or failure details.

    Args:
        app_settings (AppSettings): Configuration object containing application
            settings needed during the installation process.
        current_logger (Optional[logging.Logger], optional): Logger instance to be
            used for logging the operations. If not provided, the default module
            logger is used.

    Raises:
        EnvironmentError: Raised when npm (Node Package Manager) is not found in
            the system environment.
        Exception: Propagates any failure during the installation process and logs
            the issue for debugging/alerting purposes.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('step', '➡️')} Installing CartoCSS compiler (carto CLI)...",
        "info",
        logger_to_use,
        app_settings,
    )

    if not command_exists("npm"):
        log_map_server(
            f"{symbols.get('error', '❌')} NPM (Node Package Manager) not found. "
            "Node.js needs to be installed first. Skipping carto CLI install.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise EnvironmentError("NPM not found, cannot install carto CLI.")

    try:
        run_elevated_command(
            ["npm", "install", "-g", "carto"],
            app_settings,
            current_logger=logger_to_use,
        )
        carto_version_result = run_command(
            ["carto", "-v"],
            app_settings,
            capture_output=True,
            check=False,
            current_logger=logger_to_use,
        )
        carto_version = (
            carto_version_result.stdout.strip()
            if carto_version_result.returncode == 0
            and carto_version_result.stdout
            else "Not found or error determining version"
        )
        log_map_server(
            f"{symbols.get('success', '✅')} CartoCSS compiler 'carto' installed/updated. Version: {carto_version}",
            "success",
            logger_to_use,
            app_settings,
        )
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to install 'carto' via npm: {e}. Check npm/Node.js.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise


def setup_osm_carto_repository(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Sets up the OpenStreetMap-Carto repository by either cloning it from a remote
    repository or verifying the repository's existence at a predefined location.

    This function ensures that the OpenStreetMap-Carto repository is properly set
    up in the specified directory. If the directory does not exist, it clones
    the repository; otherwise, it logs that the directory already exists.

    Arguments:
        app_settings: AppSettings
            The application settings containing configurations used for the
            setup process.
        current_logger: Optional[logging.Logger]
            The logger to use for logging messages. If none is provided, a
            module-level default logger will be used.

    Returns:
        None
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('step', '➡️')} Setting up OpenStreetMap-Carto repository at {OSM_CARTO_BASE_DIR}...",
        "info",
        logger_to_use,
        app_settings,
    )

    dir_exists_check = run_elevated_command(
        ["test", "-d", OSM_CARTO_BASE_DIR],
        app_settings,
        check=False,
        capture_output=True,
        current_logger=logger_to_use,
    )
    if dir_exists_check.returncode != 0:
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Cloning OpenStreetMap-Carto repository...",
            "info",
            logger_to_use,
            app_settings,
        )
        run_elevated_command(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "https://github.com/gravitystorm/openstreetmap-carto.git",
                OSM_CARTO_BASE_DIR,
            ],
            app_settings,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Cloned OpenStreetMap-Carto to {OSM_CARTO_BASE_DIR}.",
            "success",
            logger_to_use,
            app_settings,
        )
    else:
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Directory {OSM_CARTO_BASE_DIR} already exists. To update, please do so manually.",
            "info",
            logger_to_use,
            app_settings,
        )


def prepare_carto_directory_for_processing(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Prepares the Carto directory for processing by temporarily changing its ownership
    to the current user and group to allow script execution.

    Parameters
    ----------
    app_settings : AppSettings
        The application settings that include configuration details such as symbols
        for logging and other application-specific preferences.
    current_logger : Optional[logging.Logger], optional
        A logger instance to be used for logging messages during the execution.
        If not provided, a default module logger will be used.

    Raises
    ------
    KeyError
        If the group ID cannot be resolved to a group name.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    current_user = getpass.getuser()
    try:
        current_group_info = grp.getgrgid(os.getgid())
        current_group_name = current_group_info.gr_name
    except KeyError:
        current_group_name = str(os.getgid())

    log_map_server(
        f"{symbols.get('info', 'ℹ️')} Temporarily changing ownership of {OSM_CARTO_BASE_DIR} "
        f"to {current_user}:{current_group_name} for script execution.",
        "info",
        logger_to_use,
        app_settings,
    )
    run_elevated_command(
        [
            "chown",
            "-R",
            f"{current_user}:{current_group_name}",
            OSM_CARTO_BASE_DIR,
        ],
        app_settings,
        current_logger=logger_to_use,
    )


def fetch_carto_external_data(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Fetches external data (shapefiles, etc.) for the OpenStreetMap-Carto style."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('step', '➡️')} Fetching external data for OpenStreetMap-Carto style...",
        "info",
        logger_to_use,
        app_settings,
    )

    original_cwd = os.getcwd()
    python_exe_path = sys.executable

    # OSM_PROJECT_ROOT comes from static_config
    custom_script_path = (
        static_config.OSM_PROJECT_ROOT
        / "external/openstreetmap-carto/scripts/get-external-data.py"
    )

    if custom_script_path.is_file():
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Using custom get-external-data.py: {custom_script_path}",
            "info",
            logger_to_use,
            app_settings,
        )
        script_to_run_cmd = [python_exe_path, str(custom_script_path)]
    else:
        log_map_server(
            f"{symbols.get('warning', '!')} Custom get-external-data.py: {custom_script_path} not found",
            "warning",
            logger_to_use,
            app_settings,
        )
        default_script_path = (
            Path(OSM_CARTO_BASE_DIR) / "scripts/get-external-data.py"
        )
        if default_script_path.is_file():
            log_map_server(
                f"{symbols.get('info', 'ℹ️')} Using default get-external-data.py from Carto repo: {default_script_path}",
                "info",
                logger_to_use,
                app_settings,
            )
            script_to_run_cmd = [python_exe_path, str(default_script_path)]
        else:
            log_map_server(
                f"{symbols.get('critical', '🔥')} No get-external-data.py script found. Shapefiles might be missing.",
                "critical",
                logger_to_use,
                app_settings,
            )
            raise FileNotFoundError(
                "get-external-data.py script not found at custom or default paths."
            )

    try:
        os.chdir(OSM_CARTO_BASE_DIR)
        if script_to_run_cmd:
            pg_credentials = [
                "--database",
                app_settings.pg.database,
                "--host",
                app_settings.pg.host,
                "--port",
                str(app_settings.pg.port),
                "--username",
                app_settings.pg.user,
                "--password",
                app_settings.pg.password,
            ]

            run_command(
                script_to_run_cmd + pg_credentials,
                app_settings,
                current_logger=logger_to_use,
                check=True,
            )
            log_map_server(
                f"{symbols.get('success', '✅')} External data fetching process completed.",
                "success",
                logger_to_use,
                app_settings,
            )
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Error during external data fetching for Carto: {e}",
            "error",
            logger_to_use,
            app_settings,
        )
        raise
    finally:
        os.chdir(original_cwd)
