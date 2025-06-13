# installer/renderd_installer.py
# -*- coding: utf-8 -*-
"""
Handles setup of Renderd: package checks, directory creation,
and systemd service file definition.
"""

import logging
from pathlib import Path
from typing import Optional

from common.command_utils import (
    check_package_installed,
    log_map_server,
    run_elevated_command,
)
from common.system_utils import get_current_script_hash
from setup import (
    config as static_config,  # For SCRIPT_VERSION via get_current_script_hash indirectly
)
from setup.config_models import AppSettings  # For type hinting

module_logger = logging.getLogger(__name__)

RENDERD_SYSTEM_USER = "www-data"
RENDERD_SYSTEM_GROUP = "www-data"
RENDERD_CONF_FILE_SYSTEM_PATH = "/etc/renderd.conf"


def ensure_renderd_packages_installed(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Ensures that required Renderd and Mapnik-related packages are installed and logs the
    status of these packages. If any package is missing, an error will be raised, as it
    indicates a critical issue with the system's prerequisite setup.

    Raises:
        EnvironmentError: If one or more essential Renderd/Mapnik packages are not installed.

    Args:
        app_settings (AppSettings): Application settings containing configurations such
            as logging and symbol mapping.
        current_logger (Optional[logging.Logger]): A logger instance to use for logging
            messages. If not provided, a default module-level logger will be used.

    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('info', 'ℹ️')} Checking Renderd package installation status...",
        "info",
        logger_to_use,
        app_settings,
    )

    packages_to_check = ["renderd", "mapnik-utils"]
    all_found = True
    for pkg in packages_to_check:
        if check_package_installed(
            pkg, app_settings=app_settings, current_logger=logger_to_use
        ):
            log_map_server(
                f"{symbols.get('success', '✅')} Package '{pkg}' is installed.",
                "debug",
                logger_to_use,
                app_settings,
            )
        else:
            log_map_server(
                f"{symbols.get('error', '❌')} Package '{pkg}' is NOT installed. "
                "This should have been handled by core prerequisite installation.",
                "error",
                logger_to_use,
                app_settings,
            )
            all_found = False
    if not all_found:
        raise EnvironmentError(
            "One or more essential Renderd/Mapnik packages are missing."
        )
    log_map_server(
        f"{symbols.get('success', '✅')} Renderd related packages confirmed.",
        "success",
        logger_to_use,
        app_settings,
    )


def create_renderd_directories(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Creates necessary directories for Renderd and sets their ownership and permissions.

    This function ensures that the required directories for Renderd exist, setting appropriate
    ownership and permissions. If a custom logger is provided, it is used for logging information.
    Otherwise, a module-level logger is employed. Additionally, it utilizes app-specific settings
    to manage directory paths and user/group ownership.

    Arguments:
        app_settings (AppSettings): The application settings object containing Renderd-specific
            configuration, including directory paths, user, and group information.
        current_logger (Optional[logging.Logger]): A custom logger to use for logging messages.
            Defaults to None, in which case the module-level logger is used.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('step', '➡️')} Creating directories for Renderd...",
        "info",
        logger_to_use,
        app_settings,
    )

    tile_cache_dir = str(
        app_settings.renderd.tile_cache_dir
    )  # Ensure string for commands
    renderd_run_dir = str(app_settings.renderd.run_dir)

    dirs_to_create_and_own = {
        tile_cache_dir: (RENDERD_SYSTEM_USER, RENDERD_SYSTEM_GROUP),
        renderd_run_dir: (RENDERD_SYSTEM_USER, RENDERD_SYSTEM_GROUP),
    }

    for dir_path, (owner, group) in dirs_to_create_and_own.items():
        run_elevated_command(
            ["mkdir", "-p", dir_path],
            app_settings,
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["chown", "-R", f"{owner}:{group}", dir_path],
            app_settings,
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["chmod", "-R", "u+rwX,g+rX,o+rX", dir_path],
            app_settings,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Directory '{dir_path}' created/permissions set for {owner}:{group}.",
            "success",
            logger_to_use,
            app_settings,
        )


def create_renderd_systemd_service_file(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Creates or updates a systemd service file for the renderd daemon.

    This function generates a systemd service file for the renderd application,
    which is responsible for rendering map tiles. It uses the provided application
    settings to create the content of the service file, specifically customizing
    paths and other necessary parameters. The generated file is then written to
    the appropriate location on the system using elevated privileges. Logging is
    performed for both success and failure cases to assist with debugging and
    confirm correct operation.

    Arguments:
        app_settings (AppSettings): The application settings containing configuration
            needed to create the service file.
        current_logger (Optional[logging.Logger], optional): A logger instance for
            logging during the operation. If not provided, a default module-level
            logger is used.

    Raises:
        Exception: Re-raises errors encountered during the creation or update
            of the service file after logging the failure.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    script_hash = (
        get_current_script_hash(
            project_root_dir=static_config.OSM_PROJECT_ROOT,
            app_settings=app_settings,
            logger_instance=logger_to_use,
        )
        or "UNKNOWN_HASH"
    )

    log_map_server(
        f"{symbols.get('step', '➡️')} Creating Renderd systemd service file...",
        "info",
        logger_to_use,
        app_settings,
    )

    renderd_service_path = "/etc/systemd/system/renderd.service"

    # TODO: Work out move to config.models and to the yaml config files
    renderd_service_content_template = f"""[Unit]
Description=Map tile rendering daemon (renderd)
Documentation=man:renderd(8)
After=network.target auditd.service postgresql.service

[Service]
User={RENDERD_SYSTEM_USER}
Group={RENDERD_SYSTEM_GROUP}
ExecStart=/usr/bin/renderd -f -c {{renderd_conf_file_system_path}}
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=renderd
# RuntimeDirectory={Path(app_settings.renderd.run_dir).name} # Systemd can manage this if desired
# RuntimeDirectoryMode=0755 

[Install]
WantedBy=multi-user.target
# File created by script V{{script_hash}}
"""
    # TODO: Configurable conf file
    # RENDERD_CONF_FILE_SYSTEM_PATH is the static path /etc/renderd.conf
    # where configure/renderd_configurator.py will write the actual config.
    # This path is hardcoded here as it's where systemd expects to find it based on common practice.
    # If this path itself became configurable via AppSettings, it would need to be passed here.
    final_service_content = renderd_service_content_template.format(
        renderd_conf_file_system_path=RENDERD_CONF_FILE_SYSTEM_PATH,
        script_hash=script_hash,
    )

    try:
        run_elevated_command(
            ["tee", renderd_service_path],
            app_settings,
            cmd_input=final_service_content,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Created/Updated {renderd_service_path}",
            "success",
            logger_to_use,
            app_settings,
        )
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to write {renderd_service_path}: {e}",
            "error",
            logger_to_use,
            app_settings,
        )
        raise
