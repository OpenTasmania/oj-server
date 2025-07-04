"""
pg_tileserv configurator module.

This module provides a self-contained configurator for pg_tileserv,
including its config file and service activation.
"""

import logging
from pathlib import Path
from typing import Optional

from common.command_utils import run_elevated_command
from common.system_utils import get_current_script_hash, systemd_reload
from installer import config as static_config
from installer.base_component import BaseComponent
from installer.components.pg_tileserv.pg_tileserv_installer import (
    PgTileservInstaller,
)
from installer.config_models import (
    PGPASSWORD_DEFAULT,
    AppSettings,
)
from installer.registry import ComponentRegistry


@ComponentRegistry.register(
    name="pg_tileserv",
    metadata={
        "dependencies": ["postgres"],
        "description": "pg_tileserv configuration and service activation",
    },
)
class PgTileservConfigurator(BaseComponent):
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
        """
        super().__init__(app_settings, logger)
        self.installer = PgTileservInstaller(app_settings, self.logger)

    def install(self) -> bool:
        """
        Install pg_tileserv by delegating to the installer.
        """
        return self.installer.install()

    def uninstall(self) -> bool:
        """
        Uninstall pg_tileserv by delegating to the installer.
        """
        return self.installer.uninstall()

    def is_installed(self) -> bool:
        """
        Check if pg_tileserv is installed by delegating to the installer.
        """
        return self.installer.is_installed()

    def configure(self) -> bool:
        """
        Configure pg_tileserv service and config file.
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
        Unconfigure pg_tileserv service and config file.
        """
        try:
            run_elevated_command(
                ["systemctl", "stop", "pg_tileserv.service"],
                self.app_settings,
                check=False,
            )
            run_elevated_command(
                ["systemctl", "disable", "pg_tileserv.service"],
                self.app_settings,
                check=False,
            )

            service_file_path = Path(
                "/etc/systemd/system/pg_tileserv.service"
            )
            if service_file_path.exists():
                run_elevated_command(
                    ["rm", str(service_file_path)], self.app_settings
                )

            cfg = self.app_settings.pg_tileserv
            config_file_path = Path(cfg.config_dir) / cfg.config_filename
            if config_file_path.exists():
                run_elevated_command(
                    ["rm", str(config_file_path)], self.app_settings
                )

            systemd_reload(self.app_settings, self.logger)
            return True
        except Exception as e:
            self.logger.error(f"Error unconfiguring pg_tileserv: {str(e)}")
            return False

    def is_configured(self) -> bool:
        """
        Check if pg_tileserv is configured and running.
        """
        try:
            cfg = self.app_settings.pg_tileserv
            config_file_path = Path(cfg.config_dir) / cfg.config_filename
            service_file_path = Path(
                "/etc/systemd/system/pg_tileserv.service"
            )

            service_active = (
                run_elevated_command(
                    ["systemctl", "is-active", "pg_tileserv.service"],
                    self.app_settings,
                    check=False,
                ).returncode
                == 0
            )

            return (
                config_file_path.exists()
                and service_file_path.exists()
                and service_active
            )
        except Exception as e:
            self.logger.error(
                f"Error checking pg_tileserv configuration: {str(e)}"
            )
            return False

    def _create_pg_tileserv_config_file(self) -> None:
        """
        Create the pg_tileserv config.toml file and set permissions.
        """
        script_hash = (
            get_current_script_hash(
                static_config.OSM_PROJECT_ROOT, self.app_settings, self.logger
            )
            or "UNKNOWN_HASH"
        )

        cfg = self.app_settings.pg_tileserv
        config_dir = Path(cfg.config_dir)
        config_file_path = config_dir / cfg.config_filename
        run_elevated_command(
            ["mkdir", "-p", str(config_dir)], self.app_settings
        )

        db_url = (
            f"postgresql://{self.app_settings.pg.user}:{self.app_settings.pg.password}@"
            f"{self.app_settings.pg.host}:{self.app_settings.pg.port}/{self.app_settings.pg.database}"
        )
        if (
            self.app_settings.pg.password == PGPASSWORD_DEFAULT
            and not self.app_settings.dev_override_unsafe_password
        ):
            self.logger.warning(
                "Default PGPASSWORD used in pg_tileserv config."
            )

        format_vars = {
            "script_hash": script_hash,
            "pg_tileserv_http_host": cfg.http_host,
            "pg_tileserv_http_port": cfg.http_port,
            "db_url_for_pg_tileserv": db_url,
            "pg_tileserv_default_max_features": cfg.default_max_features,
            "pg_tileserv_publish_schemas": cfg.publish_schemas,
            "pg_tileserv_uri_prefix": cfg.uri_prefix,
            "pg_tileserv_development_mode_bool": str(
                cfg.development_mode
            ).lower(),
            "pg_tileserv_allow_function_sources_bool": str(
                cfg.allow_function_sources
            ).lower(),
        }

        config_content = cfg.config_template.format(**format_vars)
        run_elevated_command(
            ["tee", str(config_file_path)],
            self.app_settings,
            cmd_input=config_content,
        )
        run_elevated_command(
            [
                "chown",
                f"{cfg.system_user}:{cfg.system_user}",
                str(config_file_path),
            ],
            self.app_settings,
        )
        run_elevated_command(
            ["chmod", "640", str(config_file_path)], self.app_settings
        )

    def _create_pg_tileserv_systemd_service_file(self) -> None:
        """
        Create the systemd service file for pg_tileserv.
        """
        script_hash = (
            get_current_script_hash(
                static_config.OSM_PROJECT_ROOT, self.app_settings, self.logger
            )
            or "UNKNOWN_HASH"
        )

        cfg = self.app_settings.pg_tileserv
        service_file_path = "/etc/systemd/system/pg_tileserv.service"
        config_file_full_path = str(
            Path(cfg.config_dir) / cfg.config_filename
        )
        db_url = (
            f"postgresql://{self.app_settings.pg.user}:{self.app_settings.pg.password}@"
            f"{self.app_settings.pg.host}:{self.app_settings.pg.port}/{self.app_settings.pg.database}"
        )

        format_vars = {
            "script_hash": script_hash,
            "pg_tileserv_system_user": cfg.system_user,
            "pg_tileserv_system_group": cfg.system_user,
            "pg_tileserv_binary_path": str(cfg.binary_install_path),
            "pg_tileserv_config_file_path_systemd": config_file_full_path,
            "pg_tileserv_systemd_environment": db_url,
        }

        service_content = cfg.systemd_template.format(**format_vars)
        run_elevated_command(
            ["tee", service_file_path],
            self.app_settings,
            cmd_input=service_content,
        )

    def _activate_pg_tileserv_service(self) -> None:
        """
        Reload systemd, enable and restart the pg_tileserv service.
        """
        systemd_reload(self.app_settings, self.logger)
        run_elevated_command(
            ["systemctl", "enable", "pg_tileserv.service"], self.app_settings
        )
        run_elevated_command(
            ["systemctl", "restart", "pg_tileserv.service"], self.app_settings
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
        )
