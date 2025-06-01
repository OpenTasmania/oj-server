# configure/postgres_configurator.py
# -*- coding: utf-8 -*-
"""
Handles configuration of PostgreSQL, including users, databases, extensions,
permissions, and server configuration files.
"""
import logging
import os
import subprocess
from typing import Optional

from common.command_utils import (
    log_map_server,
    run_command,
    run_elevated_command,
)
from common.file_utils import backup_file
from common.network_utils import validate_cidr
from setup import config as static_config
from setup.config_models import AppSettings
from common.system_utils import get_current_script_hash

module_logger = logging.getLogger(__name__)

PG_VERSION_DEFAULT = "17"
PG_CONF_DIR_TEMPLATE = "/etc/postgresql/{version}/main"
PG_CONF_FILE_TEMPLATE = os.path.join(PG_CONF_DIR_TEMPLATE, "postgresql.conf")
PG_HBA_FILE_TEMPLATE = os.path.join(PG_CONF_DIR_TEMPLATE, "pg_hba.conf")


def _get_pg_config_path_params(
        app_settings: AppSettings,
) -> tuple[str, str, str, str]:
    pg_version = getattr(app_settings.pg, "version", PG_VERSION_DEFAULT)
    pg_conf_dir = PG_CONF_DIR_TEMPLATE.format(version=pg_version)
    pg_conf_file = PG_CONF_FILE_TEMPLATE.format(version=pg_version)
    pg_hba_file = PG_HBA_FILE_TEMPLATE.format(version=pg_version)
    return pg_version, pg_conf_dir, pg_conf_file, pg_hba_file


def _check_pg_config_dir_exists(
        app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    pg_version, pg_conf_dir, _, _ = _get_pg_config_path_params(app_settings)
    symbols = app_settings.symbols
    if not os.path.isdir(pg_conf_dir):
        try:
            run_elevated_command(
                ["test", "-d", pg_conf_dir],
                check=True,
                capture_output=True,
                current_logger=logger_to_use,
            )
        except subprocess.CalledProcessError as e:
            log_map_server(
                f"{symbols.get('error', '')} PostgreSQL config directory not found: {pg_conf_dir}. "
                f"Is PostgreSQL v{pg_version} installed?",
                "error",
                logger_to_use,
            )
            raise FileNotFoundError(
                f"PostgreSQL config directory {pg_conf_dir} not found."
            ) from e


# ... create_postgres_user_and_db, enable_postgres_extensions, set_postgres_permissions ...
# (These functions remain as refactored in the previous step, using app_settings)


def create_postgres_user_and_db(
        app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Creates the PostgreSQL user and database if they don't exist."""
    logger_to_use = current_logger if current_logger else module_logger
    _check_pg_config_dir_exists(app_settings, logger_to_use)

    pg_user = app_settings.pg.user
    pg_password = app_settings.pg.password
    pg_database = app_settings.pg.database
    symbols = app_settings.symbols

    # Create PostgreSQL user
    try:
        log_map_server(
            f"{symbols.get('gear', '')} Creating PostgreSQL user '{pg_user}'...",
            "info",
            logger_to_use,
        )
        run_command(
            [
                "sudo",
                "-u",
                "postgres",
                "psql",
                "-c",
                f"CREATE USER {pg_user} WITH PASSWORD '{pg_password}';",
            ],
            capture_output=True,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '')} PostgreSQL user '{pg_user}' created.",
            "success",
            logger_to_use,
        )
    except subprocess.CalledProcessError as e:
        if e.stderr and "already exists" in e.stderr.lower():
            log_map_server(
                f"{symbols.get('info', '')} PostgreSQL user '{pg_user}' already exists. Attempting to update password.",
                "info",
                logger_to_use,
            )
            run_command(
                [
                    "sudo",
                    "-u",
                    "postgres",
                    "psql",
                    "-c",
                    f"ALTER USER {pg_user} WITH PASSWORD '{pg_password}';",
                ],
                capture_output=True,
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{symbols.get('success', '')} Password for PostgreSQL user '{pg_user}' updated.",
                "success",
                logger_to_use,
            )
        else:
            err_msg = (
                e.stderr.strip()
                if e.stderr
                else "Unknown psql error during user creation."
            )
            log_map_server(
                f"{symbols.get('error', '')} Failed to create/alter PostgreSQL user '{pg_user}'. Error: {err_msg}",
                "error",
                logger_to_use,
            )
            raise

    # Create PostgreSQL database
    try:
        log_map_server(
            f"{symbols.get('gear', '')} Creating PostgreSQL database '{pg_database}'...",
            "info",
            logger_to_use,
        )
        run_command(
            [
                "sudo",
                "-u",
                "postgres",
                "psql",
                "-c",
                f"CREATE DATABASE {pg_database} WITH OWNER {pg_user} ENCODING 'UTF8' LC_COLLATE='en_AU.UTF-8' LC_CTYPE='en_AU.UTF-8' TEMPLATE template0;",
            ],
            capture_output=True,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '')} PostgreSQL database '{pg_database}' created.",
            "success",
            logger_to_use,
        )
    except subprocess.CalledProcessError as e:
        if e.stderr and "already exists" in e.stderr.lower():
            log_map_server(
                f"{symbols.get('info', '')} PostgreSQL database '{pg_database}' already exists.",
                "info",
                logger_to_use,
            )
        else:
            err_msg = (
                e.stderr.strip()
                if e.stderr
                else "Unknown psql error during database creation."
            )
            log_map_server(
                f"{symbols.get('error', '')} Failed to create PostgreSQL database '{pg_database}'. Error: {err_msg}",
                "error",
                logger_to_use,
            )
            raise


def enable_postgres_extensions(
        app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Ensures necessary PostgreSQL extensions (PostGIS, Hstore) are enabled."""
    logger_to_use = current_logger if current_logger else module_logger
    _check_pg_config_dir_exists(app_settings, logger_to_use)

    pg_database = app_settings.pg.database
    symbols = app_settings.symbols
    extensions = ["postgis", "hstore"]

    for ext in extensions:
        log_map_server(
            f"{symbols.get('gear', '')} Ensuring PostgreSQL extension '{ext}' is available in database '{pg_database}'...",
            "info",
            logger_to_use,
        )
        try:
            run_command(
                [
                    "sudo",
                    "-u",
                    "postgres",
                    "psql",
                    "-d",
                    pg_database,
                    "-c",
                    f"CREATE EXTENSION IF NOT EXISTS {ext};",
                ],
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{symbols.get('success', '')} PostgreSQL extension '{ext}' ensured.",
                "success",
                logger_to_use,
            )
        except subprocess.CalledProcessError as e:
            err_msg = (
                e.stderr.strip()
                if e.stderr
                else f"Unknown psql error enabling extension {ext}."
            )
            log_map_server(
                f"{symbols.get('error', '')} Failed to enable PostgreSQL extension '{ext}'. Error: {err_msg}",
                "error",
                logger_to_use,
            )
            raise


def set_postgres_permissions(
        app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """Sets database permissions for the application user."""
    logger_to_use = current_logger if current_logger else module_logger
    _check_pg_config_dir_exists(app_settings, logger_to_use)

    pg_user = app_settings.pg.user
    pg_database = app_settings.pg.database
    symbols = app_settings.symbols

    log_map_server(
        f"{symbols.get('gear', '')} Setting database permissions for user '{pg_user}' on database '{pg_database}'...",
        "info",
        logger_to_use,
    )
    db_permission_commands = [
        f"ALTER SCHEMA public OWNER TO {pg_user};",
        f"GRANT ALL ON SCHEMA public TO {pg_user};",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {pg_user};",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {pg_user};",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO {pg_user};",
    ]
    try:
        for cmd_sql in db_permission_commands:
            run_command(
                [
                    "sudo",
                    "-u",
                    "postgres",
                    "psql",
                    "-d",
                    pg_database,
                    "-c",
                    cmd_sql,
                ],
                current_logger=logger_to_use,
            )
        log_map_server(
            f"{symbols.get('success', '')} Database permissions set for user '{pg_user}'.",
            "success",
            logger_to_use,
        )
    except subprocess.CalledProcessError as e:
        err_msg = (
            e.stderr.strip()
            if e.stderr
            else "Unknown psql error setting permissions."
        )
        log_map_server(
            f"{symbols.get('error', '')} Failed to set PostgreSQL permissions. Error: {err_msg}",
            "error",
            logger_to_use,
        )
        raise


def customize_postgresql_conf(
        app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    _check_pg_config_dir_exists(app_settings, logger_to_use)

    _, _, pg_conf_file, _ = _get_pg_config_path_params(app_settings)
    symbols = app_settings.symbols
    script_hash = (
            get_current_script_hash(
                project_root_dir=static_config.OSM_PROJECT_ROOT,
                logger_instance=logger_to_use,
            )
            or "UNKNOWN_HASH"
    )

    # Get the postgresql.conf additions template from AppSettings
    conf_additions_template = (
        app_settings.pg.postgresql_conf_additions_template
    )

    if backup_file(pg_conf_file, current_logger=logger_to_use):
        # Marker for idempotency, ensure it matches the one in the template from config_models/config.yaml
        customisation_marker = (
            "# --- TRANSIT SERVER CUSTOMISATIONS - Appended by script V"
        )

        grep_result = run_elevated_command(
            ["grep", "-qF", customisation_marker, pg_conf_file],
            check=False,
            capture_output=True,
            current_logger=logger_to_use,
        )

        if (
                grep_result.returncode != 0
        ):  # Marker not found, append the settings
            try:
                # Format the template with current script_hash
                # Add other placeholders here if the template uses them (e.g., {shared_buffers_value})
                content_to_append_final = conf_additions_template.format(
                    script_hash=script_hash
                )

                run_elevated_command(
                    ["tee", "-a", pg_conf_file],
                    cmd_input=content_to_append_final,
                    current_logger=logger_to_use,
                )
                log_map_server(
                    f"{symbols.get('success', '')} Appended custom settings to {pg_conf_file} from configuration template.",
                    "success",
                    logger_to_use,
                )
            except KeyError as e_key:
                log_map_server(
                    f"{symbols.get('error', '')} Missing placeholder key '{e_key}' for postgresql.conf template. Check config.yaml and config_models.py.",
                    "error",
                    logger_to_use,
                )
                raise
            except Exception as e:
                log_map_server(
                    f"{symbols.get('error', '')} Error updating {pg_conf_file}: {e}",
                    "error",
                    logger_to_use,
                )
                raise
        else:
            log_map_server(
                f"{symbols.get('info', '')} Customizations marker already found in {pg_conf_file}. Assuming settings are applied or managed manually.",
                "info",
                logger_to_use,
            )


def customize_pg_hba_conf(
        app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    _check_pg_config_dir_exists(app_settings, logger_to_use)

    _, _, _, pg_hba_file = _get_pg_config_path_params(app_settings)
    symbols = app_settings.symbols
    script_hash = (
            get_current_script_hash(
                project_root_dir=static_config.OSM_PROJECT_ROOT,
                logger_instance=logger_to_use,
            )
            or "UNKNOWN_HASH"
    )

    hba_template = app_settings.pg.hba_template
    format_vars = {
        "script_hash": script_hash,
        "pg_database": app_settings.pg.database,
        "pg_user": app_settings.pg.user,
        "admin_group_ip": app_settings.admin_group_ip,
    }

    if not validate_cidr(
            app_settings.admin_group_ip, current_logger=logger_to_use
    ):
        log_map_server(
            f"{symbols.get('error', '')} Invalid ADMIN_GROUP_IP '{app_settings.admin_group_ip}' for pg_hba.conf. Skipping HBA update.",
            "error",
            logger_to_use,
        )
        raise ValueError(
            f"Invalid ADMIN_GROUP_IP '{app_settings.admin_group_ip}' for pg_hba.conf."
        )

    if backup_file(pg_hba_file, current_logger=logger_to_use):
        try:
            hba_content_final = hba_template.format(**format_vars)
            run_elevated_command(
                ["tee", pg_hba_file],
                cmd_input=hba_content_final,
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{symbols.get('success', '')} Wrote pg_hba.conf using template from configuration.",
                "success",
                logger_to_use,
            )
        except KeyError as e_key:
            log_map_server(
                f"{symbols.get('error', '')} Missing placeholder key '{e_key}' for HBA template. Check config.yaml and config_models.py.",
                "error",
                logger_to_use,
            )
            raise
        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '')} Error writing {pg_hba_file}: {e}",
                "error",
                logger_to_use,
            )
            raise


def restart_and_enable_postgres_service(
        app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('gear', '')} Restarting and enabling PostgreSQL service...",
        "info",
        logger_to_use,
    )
    try:
        run_elevated_command(
            ["systemctl", "restart", "postgresql"],
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["systemctl", "enable", "postgresql"],
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('info', '')} PostgreSQL service status:",
            "info",
            logger_to_use,
        )
        run_elevated_command(
            ["systemctl", "status", "postgresql", "--no-pager", "-l"],
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '')} PostgreSQL service restarted and enabled.",
            "success",
            logger_to_use,
        )
    except subprocess.CalledProcessError as e:
        log_map_server(
            f"{symbols.get('error', '')} Failed to restart/enable PostgreSQL service. Error: {e.stderr or e.stdout}",
            "error",
            logger_to_use,
        )
        raise
