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
from common.system_utils import (
    get_current_script_hash,
)
from setup import (
    config as static_config,
)
from setup.config_models import AppSettings

# TODO:
#  Configure postgresql to be friendlier to OpenStreetMap imports and stuff
#  See ../../../docs/postgis_thoughts.md

module_logger = logging.getLogger(__name__)

# TODO:
#  This should come from AppSettings to be more dynamic
PG_VERSION_DEFAULT = "17"
PG_CONF_DIR_TEMPLATE = "/etc/postgresql/{version}/main"
PG_CONF_FILE_TEMPLATE = os.path.join(PG_CONF_DIR_TEMPLATE, "postgresql.conf")
PG_HBA_FILE_TEMPLATE = os.path.join(PG_CONF_DIR_TEMPLATE, "pg_hba.conf")


def _get_pg_config_path_params(
    app_settings: AppSettings,
) -> tuple[str, str, str, str]:
    """
    Retrieves PostgreSQL configuration path parameters such as version, config
    directory, config file, and HBA file paths based on provided application
    settings.

    Parameters:
        app_settings (AppSettings): The application settings object containing
            configuration details for PostgreSQL. The `pg` property of this
            object should provide the version information if available.

    Returns:
        tuple[str, str, str, str]: Returns a tuple containing:
            - PostgreSQL version as a string.
            - PostgreSQL configuration directory path as a string.
            - PostgreSQL configuration file path as a string.
            - PostgreSQL HBA file path as a string.
    """
    pg_version = getattr(app_settings.pg, "version", PG_VERSION_DEFAULT)
    pg_conf_dir = PG_CONF_DIR_TEMPLATE.format(version=pg_version)
    pg_conf_file = PG_CONF_FILE_TEMPLATE.format(version=pg_version)
    pg_hba_file = PG_HBA_FILE_TEMPLATE.format(version=pg_version)
    return pg_version, pg_conf_dir, pg_conf_file, pg_hba_file


def _check_pg_config_dir_exists(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Checks the existence of the PostgreSQL configuration directory.

    This function determines whether the PostgreSQL configuration directory exists
    on the filesystem. If the directory is not directly accessible due to insufficient
    user permissions, it attempts an elevated command to verify its existence. If the
    directory is still not found after the elevated check, logs an error message
    through the provided or default logger, including a descriptive error message
    about the PostgreSQL version and configuration directory path. Finally, if the
    directory cannot be confirmed, a FileNotFoundError is raised.

    Parameters:
        app_settings (AppSettings): The settings object containing application
            configurations, including PostgreSQL paths and symbols.
        current_logger (Optional[logging.Logger]): Optional logger to use for logging
            messages. If not provided, a module-level logger will be used.

    Raises:
        FileNotFoundError: If the PostgreSQL configuration directory does not exist
            or cannot be verified after an elevated command check.
    """
    logger_to_use = current_logger if current_logger else module_logger
    pg_version, pg_conf_dir, _, _ = _get_pg_config_path_params(app_settings)
    symbols = app_settings.symbols
    if not os.path.isdir(pg_conf_dir):
        try:
            run_elevated_command(
                ["test", "-d", pg_conf_dir],
                app_settings,
                check=True,
                capture_output=True,
                current_logger=logger_to_use,
            )
        except subprocess.CalledProcessError as e:
            log_map_server(
                f"{symbols.get('error', '')} PostgreSQL config directory not found: {pg_conf_dir}. "
                f"Is PostgreSQL v{pg_version} installed correctly?",
                "error",
                logger_to_use,
                app_settings,
            )
            raise FileNotFoundError(
                f"PostgreSQL config directory {pg_conf_dir} not found."
            ) from e


def create_postgres_user_and_db(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Creates a PostgreSQL user and database based on the provided application settings.

    This function ensures that a PostgreSQL user is created or updated with the specified
    credentials and then attempts to create a PostgreSQL database assigned to this user.

    Parameters:
    app_settings: AppSettings
        The application settings containing PostgreSQL configuration (user, password, and
        database) as well as other relevant settings.
    current_logger: Optional[logging.Logger]
        The logger instance to use for logging. If not provided, a module-level logger is
        used.

    Raises:
    subprocess.CalledProcessError
        If the underlying PostgreSQL commands fail to execute properly for reasons other
        than the user or database already existing.
    """
    logger_to_use = current_logger if current_logger else module_logger
    _check_pg_config_dir_exists(app_settings, logger_to_use)

    pg_user = app_settings.pg.user
    pg_password = app_settings.pg.password
    pg_database = app_settings.pg.database
    symbols = app_settings.symbols

    try:
        log_map_server(
            f"{symbols.get('gear', '')} Creating PostgreSQL user '{pg_user}'...",
            "info",
            logger_to_use,
            app_settings,
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
            app_settings,
            capture_output=True,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '')} PostgreSQL user '{pg_user}' created.",
            "success",
            logger_to_use,
            app_settings,
        )
    except subprocess.CalledProcessError as e:
        if e.stderr and "already exists" in e.stderr.lower():
            log_map_server(
                f"{symbols.get('info', '')} PostgreSQL user '{pg_user}' already exists. Attempting to update password.",
                "info",
                logger_to_use,
                app_settings,
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
                app_settings,
                capture_output=True,
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{symbols.get('success', '')} Password for PostgreSQL user '{pg_user}' updated.",
                "success",
                logger_to_use,
                app_settings,
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
                app_settings,
            )
            raise

    try:
        log_map_server(
            f"{symbols.get('gear', '')} Creating PostgreSQL database '{pg_database}'...",
            "info",
            logger_to_use,
            app_settings,
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
            app_settings,
            capture_output=True,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '')} PostgreSQL database '{pg_database}' created.",
            "success",
            logger_to_use,
            app_settings,
        )
    except subprocess.CalledProcessError as e:
        if e.stderr and "already exists" in e.stderr.lower():
            log_map_server(
                f"{symbols.get('info', '')} PostgreSQL database '{pg_database}' already exists.",
                "info",
                logger_to_use,
                app_settings,
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
                app_settings,
            )
            raise


def enable_postgres_extensions(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Ensures that specific PostgreSQL extensions are enabled in the configured database.
    This function checks the presence of the required database configuration
    directory and enables the specified PostgreSQL extensions ('postgis', 'hstore')
    in the target database.

    Parameters:
        app_settings (AppSettings): The application settings object containing
            the database configuration and symbols for logging purposes.
        current_logger (Optional[logging.Logger]): A logger instance for logging
            messages. Defaults to None, in which case the module-level logger
            will be used.

    Raises:
        subprocess.CalledProcessError: Raised if enabling any PostgreSQL extension
            fails during the execution of the respective SQL commands via `psql`.
    """
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
            app_settings,
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
                app_settings,
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{symbols.get('success', '')} PostgreSQL extension '{ext}' ensured.",
                "success",
                logger_to_use,
                app_settings,
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
                app_settings,
            )
            raise


def set_postgres_permissions(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Sets the required PostgreSQL permissions for a specified user on a given database.

    This function ensures that a PostgreSQL user has the necessary permissions on the database, such as ownership of the
    schema and access to tables, sequences, and functions. The function executes SQL commands to set these permissions
    while logging the operation's progress and results. Optionally, a custom logger can be provided for logging.

    Parameters:
        app_settings (AppSettings): The configuration settings for the application, including database credentials
                                    and other operational settings.
        current_logger (Optional[logging.Logger]): A custom logger to use for logging messages. If not provided,
                                                   a default module logger is used.

    Raises:
        subprocess.CalledProcessError: If the execution of any SQL command to set permissions fails.
    """
    logger_to_use = current_logger if current_logger else module_logger
    _check_pg_config_dir_exists(app_settings, logger_to_use)

    pg_user = app_settings.pg.user
    pg_database = app_settings.pg.database
    symbols = app_settings.symbols

    log_map_server(
        f"{symbols.get('gear', '')} Setting database permissions for user '{pg_user}' on database '{pg_database}'...",
        "info",
        logger_to_use,
        app_settings,
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
                app_settings,
                current_logger=logger_to_use,
            )
        log_map_server(
            f"{symbols.get('success', '')} Database permissions set for user '{pg_user}'.",
            "success",
            logger_to_use,
            app_settings,
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
            app_settings,
        )
        raise


def customize_postgresql_conf(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Customizes the postgresql.conf file using settings and templates provided by the application.
    This function appends application-specific configuration to the PostgreSQL configuration file
    (postgresql.conf) if not already present. It uses a template for the additional configuration,
    verifies the existence of required directories/paths, backs up the configuration file, and logs
    its operations and outcomes.

    Parameters:
        app_settings (AppSettings): A settings instance that contains application-specific
            configurations, symbols, and file paths.
        current_logger (Optional[logging.Logger]): An optional logger instance. If not provided,
            a default module-wide logger will be used instead.

    Raises:
        KeyError: Raised if required placeholders for the configuration template are missing.
        Exception: Raised for any other errors encountered while updating the configuration file.
    """
    logger_to_use = current_logger if current_logger else module_logger
    _check_pg_config_dir_exists(app_settings, logger_to_use)

    _, _, pg_conf_file, _ = _get_pg_config_path_params(app_settings)
    symbols = app_settings.symbols
    script_hash = (
        get_current_script_hash(
            project_root_dir=static_config.OSM_PROJECT_ROOT,
            app_settings=app_settings,
            logger_instance=logger_to_use,
        )
        or "UNKNOWN_HASH"
    )

    conf_additions_template = (
        app_settings.pg.postgresql_conf_additions_template
    )

    if backup_file(pg_conf_file, app_settings, current_logger=logger_to_use):
        customisation_marker = (
            "# --- TRANSIT SERVER CUSTOMISATIONS - Appended by script V"
        )

        grep_result = run_elevated_command(
            ["grep", "-qF", customisation_marker, pg_conf_file],
            app_settings,
            check=False,
            capture_output=True,
            current_logger=logger_to_use,
        )

        if grep_result.returncode != 0:
            try:
                content_to_append_final = conf_additions_template.format(
                    script_hash=script_hash
                )
                run_elevated_command(
                    ["tee", "-a", pg_conf_file],
                    app_settings,
                    cmd_input=content_to_append_final,
                    current_logger=logger_to_use,
                )
                log_map_server(
                    f"{symbols.get('success', '')} Appended custom settings to {pg_conf_file} from configuration template.",
                    "success",
                    logger_to_use,
                    app_settings,
                )
            except KeyError as e_key:
                log_map_server(
                    f"{symbols.get('error', '')} Missing placeholder key '{e_key}' for postgresql.conf template. Check config.yaml and config_models.py.",
                    "error",
                    logger_to_use,
                    app_settings,
                )
                raise
            except Exception as e:
                log_map_server(
                    f"{symbols.get('error', '')} Error updating {pg_conf_file}: {e}",
                    "error",
                    logger_to_use,
                    app_settings,
                )
                raise
        else:
            log_map_server(
                f"{symbols.get('info', '')} Customizations marker already found in {pg_conf_file}. Assuming settings are applied or managed manually.",
                "info",
                logger_to_use,
                app_settings,
            )


def customize_pg_hba_conf(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Updates the PostgreSQL host-based authentication (HBA) configuration file using a
    template defined in application settings. This function verifies prerequisites, validates
    input parameters, backs up the current configuration file, and writes the updated file
    content based on provided settings. Logging is performed at various steps of the process
    to aid in debugging and feedback.

    Parameters:
        app_settings (AppSettings): The application settings object containing the configuration
            required for updating pg_hba.conf. This includes database credentials, template
            definitions, IP address configurations, and other relevant parameters.
        current_logger (Optional[logging.Logger]): An optional logger instance to record
            process details. Defaults to the module-level logger when not provided.

    Raises:
        ValueError: If the administrator group IP specified in the configuration is invalid
            for the CIDR standard.
        KeyError: If the HBA template is missing a placeholder key defined in the configuration.
        Exception: For general errors that occur during the file update process.
    """
    logger_to_use = current_logger if current_logger else module_logger
    _check_pg_config_dir_exists(app_settings, logger_to_use)

    _, _, _, pg_hba_file = _get_pg_config_path_params(app_settings)
    symbols = app_settings.symbols
    script_hash = (
        get_current_script_hash(
            project_root_dir=static_config.OSM_PROJECT_ROOT,
            app_settings=app_settings,
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
        app_settings.admin_group_ip,
        app_settings,
        current_logger=logger_to_use,
    ):
        log_map_server(
            f"{symbols.get('error', '')} Invalid ADMIN_GROUP_IP '{app_settings.admin_group_ip}' for pg_hba.conf. Skipping HBA update.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise ValueError(
            f"Invalid ADMIN_GROUP_IP '{app_settings.admin_group_ip}' for pg_hba.conf."
        )

    if backup_file(pg_hba_file, app_settings, current_logger=logger_to_use):
        try:
            hba_content_final = hba_template.format(**format_vars)
            run_elevated_command(
                ["tee", pg_hba_file],
                app_settings,
                cmd_input=hba_content_final,
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{symbols.get('success', '')} Wrote pg_hba.conf using template from configuration.",
                "success",
                logger_to_use,
                app_settings,
            )
        except KeyError as e_key:
            log_map_server(
                f"{symbols.get('error', '')} Missing placeholder key '{e_key}' for HBA template. Check config.yaml and config_models.py.",
                "error",
                logger_to_use,
                app_settings,
            )
            raise
        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '')} Error writing {pg_hba_file}: {e}",
                "error",
                logger_to_use,
                app_settings,
            )
            raise


def restart_and_enable_postgres_service(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Restart and enable the PostgreSQL service on the system.

    This function ensures that the PostgreSQL service is restarted and enabled
    to start automatically on system boot. It logs each operation's progress
    and status to the provided logger or the default module logger. In the
    event of a failure, logs an error message and raises the exception.

    Parameters:
    app_settings (AppSettings): The application settings object which contains
        the necessary configuration and symbols for logging.
    current_logger (Optional[logging.Logger]): Logger to use for logging
        activity. If none is provided, the function uses the default module
        logger.

    Raises:
    subprocess.CalledProcessError: If a subprocess command to restart, enable,
        or check the status of the PostgreSQL service fails.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('gear', '')} Restarting and enabling PostgreSQL service...",
        "info",
        logger_to_use,
        app_settings,
    )
    try:
        run_elevated_command(
            ["systemctl", "restart", "postgresql"],
            app_settings,
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["systemctl", "enable", "postgresql"],
            app_settings,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('info', '')} PostgreSQL service status:",
            "info",
            logger_to_use,
            app_settings,
        )
        run_elevated_command(
            ["systemctl", "status", "postgresql", "--no-pager", "-l"],
            app_settings,
            current_logger=logger_to_use,
            check=False,
        )
        log_map_server(
            f"{symbols.get('success', '')} PostgreSQL service restarted and enabled.",
            "success",
            logger_to_use,
            app_settings,
        )
    except subprocess.CalledProcessError as e:
        log_map_server(
            f"{symbols.get('error', '')} Failed to restart/enable PostgreSQL service. Error: {e.stderr or e.stdout}",
            "error",
            logger_to_use,
            app_settings,
        )
        raise
