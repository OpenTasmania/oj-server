# installer/renderd_installer.py
# -*- coding: utf-8 -*-
"""
Handles setup of Renderd: package checks, directory creation,
and systemd service file definition.
"""
import logging
from typing import Optional

from common.command_utils import (
    check_package_installed,
    log_map_server,
    run_elevated_command,
)
from setup import (
    config as static_config,  # For SCRIPT_VERSION via get_current_script_hash indirectly
)
from setup.config_models import AppSettings  # For type hinting
from setup.state_manager import get_current_script_hash

module_logger = logging.getLogger(__name__)

# RENDERD_USER and RENDERD_GROUP are system-level, usually static
RENDERD_SYSTEM_USER = (
    "www-data"  # User renderd runs as (often www-data for Apache integration)
)
RENDERD_SYSTEM_GROUP = "www-data"
# RENDERD_CONF_PATH is where the config file will be, path from static_config or hardcoded
# The actual path for renderd.conf is defined in configure/renderd_configurator.py
# and the service file needs to point to it.
# For the service file template, we can use a placeholder if this path becomes configurable.
RENDERD_CONF_FILE_SYSTEM_PATH = (
    "/etc/renderd.conf"  # Standard path for renderd.conf
)


def ensure_renderd_packages_installed(
        app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Confirms Renderd and mapnik-utils packages are installed."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('info', 'ℹ️')} Checking Renderd package installation status...",
        "info",
        logger_to_use,
        app_settings,
    )

    # These package names are fairly static
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
    """Creates necessary directories for Renderd and sets permissions, using paths from app_settings."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('step', '➡️')} Creating directories for Renderd...",
        "info",
        logger_to_use,
        app_settings,
    )

    # Get paths from app_settings.renderd
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
    """Creates the systemd service file for Renderd."""
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

    renderd_service_path = (
        "/etc/systemd/system/renderd.service"  # Standard system path
    )

    # Template for systemd service file. Could also be moved to config_models.py for full configuration.
    # For now, key parameters are substituted.
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
