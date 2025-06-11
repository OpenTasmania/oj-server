# configure/pg_tileserv_configurator.py
# -*- coding: utf-8 -*-
"""
Handles configuration of pg_tileserv, including its config file,
and service activation.
"""

import logging
from pathlib import Path  # Added Path
from typing import Optional

from common.command_utils import log_map_server, run_elevated_command
from common.system_utils import get_current_script_hash, systemd_reload
from installer.pg_tileserv_installer import module_logger
from setup import config as static_config
from setup.config_models import (  # For type hinting and default comparison
    PGPASSWORD_DEFAULT,
    AppSettings,
)

# PG_TILESERV_CONFIG_DIR and PG_TILESERV_CONFIG_FILE are now sourced from app_settings.pg_tileserv
# PGTILESERV_SYSTEM_USER is also from app_settings.pg_tileserv


def get_pg_tileserv_settings(app_settings: AppSettings):
    """
    Common function to retrieve pg_tileserv settings from app_settings.

    Args:
        app_settings: The application settings object

    Returns:
        The pg_tileserv settings from app_settings
    """
    return app_settings.pg_tileserv


def create_pg_tileserv_config_file(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Creates the pg_tileserv config.toml file using template from app_settings and sets its permissions."""
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

    pg_tileserv_settings = get_pg_tileserv_settings(app_settings)
    config_dir = Path(pg_tileserv_settings.config_dir)
    config_file_path = config_dir / pg_tileserv_settings.config_filename

    log_map_server(
        f"{symbols.get('step', '➡️')} Creating pg_tileserv configuration file at {config_file_path} from template...",
        "info",
        logger_to_use,
        app_settings,
    )

    run_elevated_command(
        ["mkdir", "-p", str(config_dir)],
        app_settings,
        current_logger=logger_to_use,
    )

    # Construct DatabaseURL for the template
    db_url_for_config = (
        f"postgresql://{app_settings.pg.user}:{app_settings.pg.password}@"
        f"{app_settings.pg.host}:{app_settings.pg.port}/{app_settings.pg.database}"
    )
    # Check for default password usage
    if (
        app_settings.pg.password == PGPASSWORD_DEFAULT
        and not app_settings.dev_override_unsafe_password
    ):
        log_map_server(
            f"{symbols.get('warning', '!')} Default PGPASSWORD used in pg_tileserv config.toml. "
            "Service may not connect if password is not updated in DB or if this is not a dev environment with override.",
            "warning",
            logger_to_use,
            app_settings,
        )
        db_url_for_config = (
            f"postgresql://{app_settings.pg.user}:{app_settings.pg.password}@"
            f"{app_settings.pg.host}:{app_settings.pg.port}/{app_settings.pg.database}"
        )

    config_template_str = pg_tileserv_settings.config_template
    format_vars = {
        "script_hash": script_hash,
        "pg_tileserv_http_host": pg_tileserv_settings.http_host,
        "pg_tileserv_http_port": pg_tileserv_settings.http_port,
        "db_url_for_pg_tileserv": db_url_for_config,
        "pg_tileserv_default_max_features": pg_tileserv_settings.default_max_features,
        "pg_tileserv_publish_schemas": pg_tileserv_settings.publish_schemas,
        "pg_tileserv_uri_prefix": pg_tileserv_settings.uri_prefix,
        "pg_tileserv_development_mode_bool": str(
            pg_tileserv_settings.development_mode
        ).lower(),  # bool to "true"/"false"
        "pg_tileserv_allow_function_sources_bool": str(
            pg_tileserv_settings.allow_function_sources
        ).lower(),
        # bool to "true"/"false"
    }

    try:
        pg_tileserv_config_content_final = config_template_str.format(
            **format_vars
        )
        run_elevated_command(
            ["tee", str(config_file_path)],
            app_settings,
            cmd_input=pg_tileserv_config_content_final,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Created/Updated {config_file_path}",
            "success",
            logger_to_use,
            app_settings,
        )

        # Set ownership and permissions for config file
        system_user = pg_tileserv_settings.system_user
        run_elevated_command(
            ["chown", f"{system_user}:{system_user}", str(config_file_path)],
            app_settings,
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["chmod", "640", str(config_file_path)],
            app_settings,
            current_logger=logger_to_use,
        )  # Readable by owner and group
        log_map_server(
            f"{symbols.get('success', '✅')} Permissions set for {config_file_path}.",
            "success",
            logger_to_use,
            app_settings,
        )

    except KeyError as e_key:
        log_map_server(
            f"{symbols.get('error', '❌')} Missing placeholder key '{e_key}' for pg_tileserv config template. Check config.yaml/models.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to write pg_tileserv config: {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        raise


def activate_pg_tileserv_service(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Reloads systemd, enables and restarts the pg_tileserv service."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('step', '➡️')} Activating pg_tileserv systemd service...",
        "info",
        logger_to_use,
        app_settings,
    )

    systemd_reload(app_settings, current_logger=logger_to_use)
    run_elevated_command(
        ["systemctl", "enable", "pg_tileserv.service"],
        app_settings,
        current_logger=logger_to_use,
    )
    run_elevated_command(
        ["systemctl", "restart", "pg_tileserv.service"],
        app_settings,
        current_logger=logger_to_use,
    )

    log_map_server(
        f"{symbols.get('info', 'ℹ️')} pg_tileserv service status:",
        "info",
        logger_to_use,
        app_settings,
    )
    run_elevated_command(
        ["systemctl", "status", "pg_tileserv.service", "--no-pager", "-l"],
        app_settings,
        current_logger=logger_to_use,
    )
    log_map_server(
        f"{symbols.get('success', '✅')} pg_tileserv service activated.",
        "success",
        logger_to_use,
        app_settings,
    )


def create_pg_tileserv_systemd_service_file(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Creates the systemd service file for pg_tileserv using template from app_settings."""
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

    pg_tileserv_settings = get_pg_tileserv_settings(app_settings)
    service_file_path = (
        "/etc/systemd/system/pg_tileserv.service"  # Standard system path
    )
    config_file_full_path = str(
        Path(pg_tileserv_settings.config_dir)
        / pg_tileserv_settings.config_filename
    )

    log_map_server(
        f"{symbols.get('step', '➡️')} Creating pg_tileserv systemd service file at {service_file_path} from template...",
        "info",
        logger_to_use,
        app_settings,
    )
    systemd_template = pg_tileserv_settings.systemd_template
    db_url_for_config = (
        f"postgresql://{app_settings.pg.user}:{app_settings.pg.password}@"
        f"{app_settings.pg.host}:{app_settings.pg.port}/{app_settings.pg.database}"
    )
    format_vars = {
        "script_hash": script_hash,
        "pg_tileserv_system_user": pg_tileserv_settings.system_user,
        "pg_tileserv_system_group": pg_tileserv_settings.system_user,  # Assumes group is same as user
        "pg_tileserv_binary_path": str(
            pg_tileserv_settings.binary_install_path
        ),
        "pg_tileserv_config_file_path_systemd": config_file_full_path,
        "pg_tileserv_systemd_environment": db_url_for_config,
    }

    try:
        pg_tileserv_service_content_final = systemd_template.format(
            **format_vars
        )
        run_elevated_command(
            ["tee", service_file_path],
            app_settings,
            cmd_input=pg_tileserv_service_content_final,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Created/Updated {service_file_path}",
            "success",
            logger_to_use,
            app_settings,
        )
    except KeyError as e_key:
        log_map_server(
            f"{symbols.get('error', '❌')} Missing placeholder key '{e_key}' for pg_tileserv systemd template. Check config.yaml/models.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to write pg_tileserv systemd service file: {e}",
            "error",
            logger_to_use,
            app_settings,
        )
        raise
