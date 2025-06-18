"""
pg_tileserv configurator module.

This module provides a self-contained configurator for pg_tileserv,
including its config file and service activation.
"""

import logging
from pathlib import Path
from typing import Optional

from common.command_utils import log_map_server, run_elevated_command
from common.system_utils import get_current_script_hash, systemd_reload
from modular.base_configurator import BaseConfigurator
from modular.registry import ComponentRegistry
from setup import config as static_config
from setup.config_models import (
    PGPASSWORD_DEFAULT,
    AppSettings,
)


@ComponentRegistry.register(
    name="pg_tileserv",
    metadata={
        "dependencies": ["postgres"],  # pg_tileserv depends on PostgreSQL
        "description": "pg_tileserv configuration and service activation",
    },
)
class PgTileservConfigurator(BaseConfigurator):
    """
    Configurator for pg_tileserv.

    This configurator ensures that pg_tileserv is properly configured,
    including its config file and service activation.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the pg_tileserv configurator.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)

    def configure(self) -> bool:
        """
        Configure pg_tileserv.

        This method performs the following configuration tasks:
        1. Creates the pg_tileserv config.toml file and sets appropriate permissions
        2. Creates the systemd service file for pg_tileserv
        3. Activates the pg_tileserv service

        Returns:
            True if the configuration was successful, False otherwise.
        """
        try:
            self._create_pg_tileserv_config_file()
            self._create_pg_tileserv_systemd_service_file()
            self._activate_pg_tileserv_service()
            return True
        except Exception as e:
            self.logger.error(f"Error configuring pg_tileserv: {str(e)}")
            return False

    def unconfigure(self) -> bool:
        """
        Unconfigure pg_tileserv.

        This method performs the following unconfiguration tasks:
        1. Stops and disables the pg_tileserv service
        2. Removes the systemd service file
        3. Removes the pg_tileserv config file

        Returns:
            True if the unconfiguration was successful, False otherwise.
        """
        try:
            symbols = self.app_settings.symbols
            pg_tileserv_settings = self._get_pg_tileserv_settings()

            # Stop and disable the service
            log_map_server(
                f"{symbols.get('step', '')} Stopping and disabling pg_tileserv service...",
                "info",
                self.logger,
                self.app_settings,
            )
            run_elevated_command(
                ["systemctl", "stop", "pg_tileserv.service"],
                self.app_settings,
                current_logger=self.logger,
                check=False,
            )
            run_elevated_command(
                ["systemctl", "disable", "pg_tileserv.service"],
                self.app_settings,
                current_logger=self.logger,
                check=False,
            )

            # Remove the systemd service file
            service_file_path = "/etc/systemd/system/pg_tileserv.service"
            if Path(service_file_path).exists():
                run_elevated_command(
                    ["rm", service_file_path],
                    self.app_settings,
                    current_logger=self.logger,
                )
                log_map_server(
                    f"{symbols.get('success', '')} Removed pg_tileserv systemd service file.",
                    "success",
                    self.logger,
                    self.app_settings,
                )

            # Remove the config file
            config_dir = Path(pg_tileserv_settings.config_dir)
            config_file_path = (
                config_dir / pg_tileserv_settings.config_filename
            )
            if config_file_path.exists():
                run_elevated_command(
                    ["rm", str(config_file_path)],
                    self.app_settings,
                    current_logger=self.logger,
                )
                log_map_server(
                    f"{symbols.get('success', '')} Removed pg_tileserv config file.",
                    "success",
                    self.logger,
                    self.app_settings,
                )

            # Reload systemd to apply changes
            systemd_reload(self.app_settings, current_logger=self.logger)

            log_map_server(
                f"{symbols.get('success', '')} pg_tileserv unconfigured successfully.",
                "success",
                self.logger,
                self.app_settings,
            )

            return True
        except Exception as e:
            self.logger.error(f"Error unconfiguring pg_tileserv: {str(e)}")
            return False

    def is_configured(self) -> bool:
        """
        Check if pg_tileserv is configured.

        This method checks if the pg_tileserv config file exists, the systemd
        service file exists, and the service is enabled and active.

        Returns:
            True if pg_tileserv is configured, False otherwise.
        """
        try:
            pg_tileserv_settings = self._get_pg_tileserv_settings()

            # Check if the config file exists
            config_dir = Path(pg_tileserv_settings.config_dir)
            config_file_path = (
                config_dir / pg_tileserv_settings.config_filename
            )
            if not config_file_path.exists():
                return False

            # Check if the systemd service file exists
            service_file_path = "/etc/systemd/system/pg_tileserv.service"
            if not Path(service_file_path).exists():
                return False

            # Check if the service is enabled
            result = run_elevated_command(
                ["systemctl", "is-enabled", "pg_tileserv.service"],
                self.app_settings,
                capture_output=True,
                check=False,
                current_logger=self.logger,
            )
            if result.returncode != 0:
                return False

            # Check if the service is active
            result = run_elevated_command(
                ["systemctl", "is-active", "pg_tileserv.service"],
                self.app_settings,
                capture_output=True,
                check=False,
                current_logger=self.logger,
            )
            if result.returncode != 0:
                return False

            return True
        except Exception as e:
            self.logger.error(
                f"Error checking if pg_tileserv is configured: {str(e)}"
            )
            return False

    def _get_pg_tileserv_settings(self):
        """
        Get pg_tileserv settings from app_settings.

        Returns:
            The pg_tileserv settings section from app_settings.
        """
        return self.app_settings.pg_tileserv

    def _create_pg_tileserv_config_file(self) -> None:
        """
        Create the pg_tileserv config.toml file and set appropriate permissions.

        Raises:
            KeyError: If a required placeholder key is missing in the pg_tileserv template.
            Exception: For any other errors encountered during file creation or permission setting.
        """
        symbols = self.app_settings.symbols
        script_hash = (
            get_current_script_hash(
                project_root_dir=static_config.OSM_PROJECT_ROOT,
                app_settings=self.app_settings,
                logger_instance=self.logger,
            )
            or "UNKNOWN_HASH"
        )

        pg_tileserv_settings = self._get_pg_tileserv_settings()
        config_dir = Path(pg_tileserv_settings.config_dir)
        config_file_path = config_dir / pg_tileserv_settings.config_filename

        log_map_server(
            f"{symbols.get('step', '')} Creating pg_tileserv configuration file at {config_file_path} from template...",
            "info",
            self.logger,
            self.app_settings,
        )

        run_elevated_command(
            ["mkdir", "-p", str(config_dir)],
            self.app_settings,
            current_logger=self.logger,
        )

        # Construct DatabaseURL for the template
        db_url_for_config = (
            f"postgresql://{self.app_settings.pg.user}:{self.app_settings.pg.password}@"
            f"{self.app_settings.pg.host}:{self.app_settings.pg.port}/{self.app_settings.pg.database}"
        )
        # Check for default password usage
        if (
            self.app_settings.pg.password == PGPASSWORD_DEFAULT
            and not self.app_settings.dev_override_unsafe_password
        ):
            log_map_server(
                f"{symbols.get('warning', '')} Default PGPASSWORD used in pg_tileserv config.toml. "
                "Service may not connect if password is not updated in DB or if this is not a dev environment with override.",
                "warning",
                self.logger,
                self.app_settings,
            )
            db_url_for_config = (
                f"postgresql://{self.app_settings.pg.user}:{self.app_settings.pg.password}@"
                f"{self.app_settings.pg.host}:{self.app_settings.pg.port}/{self.app_settings.pg.database}"
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
                self.app_settings,
                cmd_input=pg_tileserv_config_content_final,
                current_logger=self.logger,
            )
            log_map_server(
                f"{symbols.get('success', '')} Created/Updated {config_file_path}",
                "success",
                self.logger,
                self.app_settings,
            )

            # Set ownership and permissions for config file
            system_user = pg_tileserv_settings.system_user
            run_elevated_command(
                [
                    "chown",
                    f"{system_user}:{system_user}",
                    str(config_file_path),
                ],
                self.app_settings,
                current_logger=self.logger,
            )
            run_elevated_command(
                ["chmod", "640", str(config_file_path)],
                self.app_settings,
                current_logger=self.logger,
            )  # Readable by owner and group
            log_map_server(
                f"{symbols.get('success', '')} Permissions set for {config_file_path}.",
                "success",
                self.logger,
                self.app_settings,
            )

        except KeyError as e_key:
            log_map_server(
                f"{symbols.get('error', '')} Missing placeholder key '{e_key}' for pg_tileserv config template. Check config.yaml/models.",
                "error",
                self.logger,
                self.app_settings,
            )
            raise
        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '')} Failed to write pg_tileserv config: {e}",
                "error",
                self.logger,
                self.app_settings,
                exc_info=True,
            )
            raise

    def _create_pg_tileserv_systemd_service_file(self) -> None:
        """
        Create the systemd service file for pg_tileserv.

        Raises:
            KeyError: If a required placeholder key is missing in the systemd template.
            Exception: For any other errors encountered during file creation or writing.
        """
        symbols = self.app_settings.symbols
        script_hash = (
            get_current_script_hash(
                project_root_dir=static_config.OSM_PROJECT_ROOT,
                app_settings=self.app_settings,
                logger_instance=self.logger,
            )
            or "UNKNOWN_HASH"
        )

        pg_tileserv_settings = self._get_pg_tileserv_settings()
        service_file_path = (
            "/etc/systemd/system/pg_tileserv.service"  # Standard system path
        )
        config_file_full_path = str(
            Path(pg_tileserv_settings.config_dir)
            / pg_tileserv_settings.config_filename
        )

        log_map_server(
            f"{symbols.get('step', '')} Creating pg_tileserv systemd service file at {service_file_path} from template...",
            "info",
            self.logger,
            self.app_settings,
        )
        systemd_template = pg_tileserv_settings.systemd_template
        db_url_for_config = (
            f"postgresql://{self.app_settings.pg.user}:{self.app_settings.pg.password}@"
            f"{self.app_settings.pg.host}:{self.app_settings.pg.port}/{self.app_settings.pg.database}"
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
                self.app_settings,
                cmd_input=pg_tileserv_service_content_final,
                current_logger=self.logger,
            )
            log_map_server(
                f"{symbols.get('success', '')} Created/Updated {service_file_path}",
                "success",
                self.logger,
                self.app_settings,
            )
        except KeyError as e_key:
            log_map_server(
                f"{symbols.get('error', '')} Missing placeholder key '{e_key}' for pg_tileserv systemd template. Check config.yaml/models.",
                "error",
                self.logger,
                self.app_settings,
            )
            raise
        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '')} Failed to write pg_tileserv systemd service file: {e}",
                "error",
                self.logger,
                self.app_settings,
            )
            raise

    def _activate_pg_tileserv_service(self) -> None:
        """
        Reload systemd, enable and restart the pg_tileserv service.
        """
        symbols = self.app_settings.symbols
        log_map_server(
            f"{symbols.get('step', '')} Activating pg_tileserv systemd service...",
            "info",
            self.logger,
            self.app_settings,
        )

        systemd_reload(self.app_settings, current_logger=self.logger)
        run_elevated_command(
            ["systemctl", "enable", "pg_tileserv.service"],
            self.app_settings,
            current_logger=self.logger,
        )
        run_elevated_command(
            ["systemctl", "restart", "pg_tileserv.service"],
            self.app_settings,
            current_logger=self.logger,
        )

        log_map_server(
            f"{symbols.get('info', '')} pg_tileserv service status:",
            "info",
            self.logger,
            self.app_settings,
        )
        run_elevated_command(
            [
                "systemctl",
                "status",
                "pg_tileserv.service",
                "--no-pager",
                "-l",
            ],
            self.app_settings,
            current_logger=self.logger,
        )
        log_map_server(
            f"{symbols.get('success', '')} pg_tileserv service activated.",
            "success",
            self.logger,
            self.app_settings,
        )
