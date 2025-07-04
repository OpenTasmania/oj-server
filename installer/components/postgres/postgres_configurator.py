"""
PostgreSQL configurator module.

This module provides a self-contained configurator for PostgreSQL.
"""

import logging
import os
import shutil
import subprocess
from typing import Optional, Tuple

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
from installer import config as static_config
from installer.base_component import BaseComponent
from installer.config_models import AppSettings
from installer.registry import ComponentRegistry


@ComponentRegistry.register(
    name="postgres",
    metadata={
        "dependencies": [],  # PostgreSQL is a base component with no dependencies
        "description": "PostgreSQL database server configuration",
    },
)
class PostgresConfigurator(BaseComponent):
    """
    Configurator for PostgreSQL database server.

    This configurator ensures that PostgreSQL is properly configured with the
    necessary users, databases, extensions, permissions, and configuration files.
    """

    # Constants for PostgreSQL configuration
    PG_VERSION_DEFAULT = "17"
    PG_CONF_DIR_TEMPLATE = "/etc/postgresql/{version}/main"
    PG_CONF_FILE_TEMPLATE = os.path.join(
        PG_CONF_DIR_TEMPLATE, "postgresql.conf"
    )
    PG_HBA_FILE_TEMPLATE = os.path.join(PG_CONF_DIR_TEMPLATE, "pg_hba.conf")

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the PostgreSQL configurator.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)

    def install(self) -> bool:
        """
        This component is a configurator. The actual installation of PostgreSQL
        packages is assumed to be handled separately. This method is a placeholder
        to satisfy the BaseComponent interface.
        """
        self.logger.info(
            "PostgresConfigurator: Skipping installation phase. Configuration will be applied if the component is installed."
        )
        return True

    def uninstall(self) -> bool:
        """
        Uninstallation of PostgreSQL is not handled by this component
        to prevent accidental data loss. This should be done manually.
        """
        self.logger.warning(
            "PostgresConfigurator: Uninstallation is not supported to prevent data loss. Please uninstall PostgreSQL manually if required."
        )
        return True

    def is_installed(self) -> bool:
        """
        Check if PostgreSQL appears to be installed by checking for the psql executable.
        """
        # Using shutil.which to find the psql executable in the system's PATH.
        return shutil.which("psql") is not None

    def configure(self) -> bool:
        """
        Configure PostgreSQL with the necessary settings.

        This method performs the following configuration tasks:
        1. Creates a PostgreSQL user and database
        2. Enables PostgreSQL extensions
        3. Sets PostgreSQL permissions
        4. Customizes the PostgreSQL configuration file
        5. Customizes the PostgreSQL host-based authentication configuration file
        6. Restarts and enables the PostgreSQL service

        Returns:
            True if the configuration was successful, False otherwise.
        """
        try:
            self._check_pg_config_dir_exists()
            self._create_postgres_user_and_db()
            self._enable_postgres_extensions()
            self._set_postgres_permissions()
            self._customize_postgresql_conf()
            self._customize_pg_hba_conf()
            self._restart_and_enable_postgres_service()
            return True
        except Exception as e:
            self.logger.error(f"Error configuring PostgreSQL: {str(e)}")
            return False

    def unconfigure(self) -> bool:
        """
        Unconfigure PostgreSQL settings.

        This method is not fully implemented as unconfiguring PostgreSQL would
        involve removing databases and users, which could result in data loss.
        Instead, it logs a warning message.

        Returns:
            True to indicate the operation completed (though no changes were made).
        """
        self.logger.warning(
            "Unconfiguring PostgreSQL is not implemented to prevent data loss."
        )
        return True

    def is_configured(self) -> bool:
        """
        Check if PostgreSQL is configured.

        This method checks if the PostgreSQL configuration directory exists and
        if the database exists.

        Returns:
            True if PostgreSQL is configured, False otherwise.
        """
        try:
            self._check_pg_config_dir_exists()

            # Check if the database exists
            pg_database = self.app_settings.pg.database

            # Use shell=True to properly handle the pipe
            result = run_command(
                f"sudo -u postgres psql -lqt | grep -w {pg_database}",
                self.app_settings,
                capture_output=True,
                current_logger=self.logger,
                check=False,
                shell=True,
            )

            return result.returncode == 0
        except Exception as e:
            self.logger.error(
                f"Error checking if PostgreSQL is configured: {str(e)}"
            )
            return False

    def _get_pg_config_path_params(self) -> Tuple[str, str, str, str]:
        """
        Get PostgreSQL configuration path parameters.

        Returns:
            A tuple containing:
            - PostgreSQL version as a string.
            - PostgreSQL configuration directory path as a string.
            - PostgreSQL configuration file path as a string.
            - PostgreSQL HBA file path as a string.
        """
        pg_version = getattr(
            self.app_settings.pg, "version", self.PG_VERSION_DEFAULT
        )
        pg_conf_dir = self.PG_CONF_DIR_TEMPLATE.format(version=pg_version)
        pg_conf_file = self.PG_CONF_FILE_TEMPLATE.format(version=pg_version)
        pg_hba_file = self.PG_HBA_FILE_TEMPLATE.format(version=pg_version)
        return pg_version, pg_conf_dir, pg_conf_file, pg_hba_file

    def _check_pg_config_dir_exists(self) -> None:
        """
        Check if the PostgreSQL configuration directory exists.

        Raises:
            FileNotFoundError: If the PostgreSQL configuration directory does not exist.
        """
        pg_version, pg_conf_dir, _, _ = self._get_pg_config_path_params()
        symbols = self.app_settings.symbols

        if not os.path.isdir(pg_conf_dir):
            try:
                run_elevated_command(
                    ["test", "-d", pg_conf_dir],
                    self.app_settings,
                    check=True,
                    capture_output=True,
                    current_logger=self.logger,
                )
            except subprocess.CalledProcessError as e:
                log_map_server(
                    f"{symbols.get('error', '')} PostgreSQL config directory not found: {pg_conf_dir}. "
                    f"Is PostgreSQL v{pg_version} installed correctly?",
                    "error",
                    self.logger,
                    self.app_settings,
                )
                raise FileNotFoundError(
                    f"PostgreSQL config directory {pg_conf_dir} not found."
                ) from e

    def _create_postgres_user_and_db(self) -> None:
        """
        Create a PostgreSQL user and database.

        Raises:
            subprocess.CalledProcessError: If the PostgreSQL commands fail.
        """
        pg_user = self.app_settings.pg.user
        pg_password = self.app_settings.pg.password
        pg_database = self.app_settings.pg.database
        symbols = self.app_settings.symbols

        try:
            log_map_server(
                f"{symbols.get('gear', '')} Creating PostgreSQL user '{pg_user}'...",
                "info",
                self.logger,
                self.app_settings,
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
                self.app_settings,
                capture_output=True,
                current_logger=self.logger,
            )
            log_map_server(
                f"{symbols.get('success', '')} PostgreSQL user '{pg_user}' created.",
                "success",
                self.logger,
                self.app_settings,
            )
        except subprocess.CalledProcessError as e:
            if e.stderr and "already exists" in e.stderr.lower():
                log_map_server(
                    f"{symbols.get('info', '')} PostgreSQL user '{pg_user}' already exists. Attempting to update password.",
                    "info",
                    self.logger,
                    self.app_settings,
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
                    self.app_settings,
                    capture_output=True,
                    current_logger=self.logger,
                )
                log_map_server(
                    f"{symbols.get('success', '')} Password for PostgreSQL user '{pg_user}' updated.",
                    "success",
                    self.logger,
                    self.app_settings,
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
                    self.logger,
                    self.app_settings,
                )
                raise

        try:
            log_map_server(
                f"{symbols.get('gear', '')} Creating PostgreSQL database '{pg_database}'...",
                "info",
                self.logger,
                self.app_settings,
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
                self.app_settings,
                capture_output=True,
                current_logger=self.logger,
            )
            log_map_server(
                f"{symbols.get('success', '')} PostgreSQL database '{pg_database}' created.",
                "success",
                self.logger,
                self.app_settings,
            )
        except subprocess.CalledProcessError as e:
            if e.stderr and "already exists" in e.stderr.lower():
                log_map_server(
                    f"{symbols.get('info', '')} PostgreSQL database '{pg_database}' already exists.",
                    "info",
                    self.logger,
                    self.app_settings,
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
                    self.logger,
                    self.app_settings,
                )
                raise

    def _enable_postgres_extensions(self) -> None:
        """
        Enable PostgreSQL extensions.

        Raises:
            subprocess.CalledProcessError: If enabling any PostgreSQL extension fails.
        """
        pg_database = self.app_settings.pg.database
        symbols = self.app_settings.symbols
        extensions = ["postgis", "hstore"]

        for ext in extensions:
            log_map_server(
                f"{symbols.get('gear', '')} Ensuring PostgreSQL extension '{ext}' is available in database '{pg_database}'...",
                "info",
                self.logger,
                self.app_settings,
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
                    self.app_settings,
                    current_logger=self.logger,
                )
                log_map_server(
                    f"{symbols.get('success', '')} PostgreSQL extension '{ext}' ensured.",
                    "success",
                    self.logger,
                    self.app_settings,
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
                    self.logger,
                    self.app_settings,
                )
                raise

    def _set_postgres_permissions(self) -> None:
        """
        Set PostgreSQL permissions.

        Raises:
            subprocess.CalledProcessError: If setting permissions fails.
        """
        pg_user = self.app_settings.pg.user
        pg_database = self.app_settings.pg.database
        symbols = self.app_settings.symbols

        log_map_server(
            f"{symbols.get('gear', '')} Setting database permissions for user '{pg_user}' on database '{pg_database}'...",
            "info",
            self.logger,
            self.app_settings,
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
                    self.app_settings,
                    current_logger=self.logger,
                )
            log_map_server(
                f"{symbols.get('success', '')} Database permissions set for user '{pg_user}'.",
                "success",
                self.logger,
                self.app_settings,
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
                self.logger,
                self.app_settings,
            )
            raise

    def _customize_postgresql_conf(self) -> None:
        """
        Customize the PostgreSQL configuration file.

        Raises:
            KeyError: If required placeholders for the configuration template are missing.
            Exception: For any other errors encountered while updating the configuration file.
        """
        _, _, pg_conf_file, _ = self._get_pg_config_path_params()
        symbols = self.app_settings.symbols
        script_hash = (
            get_current_script_hash(
                project_root_dir=static_config.OSM_PROJECT_ROOT,
                app_settings=self.app_settings,
                logger_instance=self.logger,
            )
            or "UNKNOWN_HASH"
        )

        conf_additions_template = (
            self.app_settings.pg.postgresql_conf_additions_template
        )

        if backup_file(
            pg_conf_file, self.app_settings, current_logger=self.logger
        ):
            customisation_marker = (
                "# --- TRANSIT SERVER CUSTOMISATIONS - Appended by script V"
            )

            grep_result = run_elevated_command(
                ["grep", "-qF", customisation_marker, pg_conf_file],
                self.app_settings,
                check=False,
                capture_output=True,
                current_logger=self.logger,
            )

            if grep_result.returncode != 0:
                try:
                    content_to_append_final = conf_additions_template.format(
                        script_hash=script_hash
                    )
                    run_elevated_command(
                        ["tee", "-a", pg_conf_file],
                        self.app_settings,
                        cmd_input=content_to_append_final,
                        current_logger=self.logger,
                    )
                    log_map_server(
                        f"{symbols.get('success', '')} Appended custom settings to {pg_conf_file} from configuration template.",
                        "success",
                        self.logger,
                        self.app_settings,
                    )
                except KeyError as e_key:
                    log_map_server(
                        f"{symbols.get('error', '')} Missing placeholder key '{e_key}' for postgresql.conf template. Check config.yaml and config_models.py.",
                        "error",
                        self.logger,
                        self.app_settings,
                    )
                    raise
                except Exception as e:
                    log_map_server(
                        f"{symbols.get('error', '')} Error updating {pg_conf_file}: {e}",
                        "error",
                        self.logger,
                        self.app_settings,
                    )
                    raise
            else:
                log_map_server(
                    f"{symbols.get('info', '')} Customizations marker already found in {pg_conf_file}. Assuming settings are applied or managed manually.",
                    "info",
                    self.logger,
                    self.app_settings,
                )

    def _customize_pg_hba_conf(self) -> None:
        """
        Customize the PostgreSQL host-based authentication configuration file.

        Raises:
            ValueError: If the administrator group IP is invalid.
            KeyError: If the HBA template is missing a placeholder key.
            Exception: For general errors during the file update process.
        """
        _, _, _, pg_hba_file = self._get_pg_config_path_params()
        symbols = self.app_settings.symbols
        script_hash = (
            get_current_script_hash(
                project_root_dir=static_config.OSM_PROJECT_ROOT,
                app_settings=self.app_settings,
                logger_instance=self.logger,
            )
            or "UNKNOWN_HASH"
        )

        hba_template = self.app_settings.pg.hba_template
        format_vars = {
            "script_hash": script_hash,
            "pg_database": self.app_settings.pg.database,
            "pg_user": self.app_settings.pg.user,
            "admin_group_ip": self.app_settings.admin_group_ip,
        }

        if not validate_cidr(
            self.app_settings.admin_group_ip,
            self.app_settings,
            current_logger=self.logger,
        ):
            log_map_server(
                f"{symbols.get('error', '')} Invalid ADMIN_GROUP_IP '{self.app_settings.admin_group_ip}' for pg_hba.conf. Skipping HBA update.",
                "error",
                self.logger,
                self.app_settings,
            )
            raise ValueError(
                f"Invalid ADMIN_GROUP_IP '{self.app_settings.admin_group_ip}' for pg_hba.conf."
            )

        if backup_file(
            pg_hba_file, self.app_settings, current_logger=self.logger
        ):
            try:
                hba_content_final = hba_template.format(**format_vars)
                run_elevated_command(
                    ["tee", pg_hba_file],
                    self.app_settings,
                    cmd_input=hba_content_final,
                    current_logger=self.logger,
                )
                log_map_server(
                    f"{symbols.get('success', '')} Wrote pg_hba.conf using template from configuration.",
                    "success",
                    self.logger,
                    self.app_settings,
                )
            except KeyError as e_key:
                log_map_server(
                    f"{symbols.get('error', '')} Missing placeholder key '{e_key}' for HBA template. Check config.yaml and config_models.py.",
                    "error",
                    self.logger,
                    self.app_settings,
                )
                raise
            except Exception as e:
                log_map_server(
                    f"{symbols.get('error', '')} Error writing {pg_hba_file}: {e}",
                    "error",
                    self.logger,
                    self.app_settings,
                )
                raise

    def _restart_and_enable_postgres_service(self) -> None:
        """
        Restart and enable the PostgreSQL service.

        Raises:
            subprocess.CalledProcessError: If restarting or enabling the service fails.
        """
        pg_version, _, _, _ = self._get_pg_config_path_params()
        symbols = self.app_settings.symbols
        service_name = f"postgresql@{pg_version}-main"

        log_map_server(
            f"{symbols.get('gear', '')} Restarting PostgreSQL service...",
            "info",
            self.logger,
            self.app_settings,
        )
        try:
            run_elevated_command(
                ["systemctl", "restart", service_name],
                self.app_settings,
                current_logger=self.logger,
            )
            log_map_server(
                f"{symbols.get('success', '')} PostgreSQL service restarted.",
                "success",
                self.logger,
                self.app_settings,
            )
        except subprocess.CalledProcessError as e:
            err_msg = (
                e.stderr.strip()
                if e.stderr
                else "Unknown error restarting PostgreSQL service."
            )
            log_map_server(
                f"{symbols.get('error', '')} Failed to restart PostgreSQL service. Error: {err_msg}",
                "error",
                self.logger,
                self.app_settings,
            )
            raise

        log_map_server(
            f"{symbols.get('gear', '')} Enabling PostgreSQL service to start on boot...",
            "info",
            self.logger,
            self.app_settings,
        )
        try:
            run_elevated_command(
                ["systemctl", "enable", service_name],
                self.app_settings,
                current_logger=self.logger,
            )
            log_map_server(
                f"{symbols.get('success', '')} PostgreSQL service enabled to start on boot.",
                "success",
                self.logger,
                self.app_settings,
            )
        except subprocess.CalledProcessError as e:
            err_msg = (
                e.stderr.strip()
                if e.stderr
                else "Unknown error enabling PostgreSQL service."
            )
            log_map_server(
                f"{symbols.get('error', '')} Failed to enable PostgreSQL service. Error: {err_msg}",
                "error",
                self.logger,
                self.app_settings,
            )
            raise
