"""
Renderd configurator module.

This module provides a self-contained configurator for Renderd,
including its .conf file and service activation.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from common.command_utils import (
    command_exists,
    run_command,
    run_elevated_command,
)
from common.system_utils import get_current_script_hash, systemd_reload
from installer import config as static_config
from installer.base_component import BaseComponent
from installer.components.renderd.renderd_installer import RenderdInstaller
from installer.config_models import (
    VM_IP_OR_DOMAIN_DEFAULT,
    AppSettings,
)
from installer.registry import ComponentRegistry


@ComponentRegistry.register(
    name="renderd",
    metadata={
        "dependencies": ["apache", "carto"],
        "description": "Renderd configuration and service activation",
    },
)
class RenderdConfigurator(BaseComponent):
    """
    Configurator for Renderd.

    This configurator ensures that Renderd is properly configured,
    including its .conf file and service activation.
    """

    RENDERD_CONF_FILE = "/etc/renderd.conf"
    RENDERD_SERVICE_FILE = "/etc/systemd/system/renderd.service"
    RENDERD_SYSTEM_GROUP = "www-data"

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Renderd configurator.
        """
        super().__init__(app_settings, logger)
        self.installer = RenderdInstaller(app_settings, self.logger)

    def install(self) -> bool:
        """Install Renderd packages and directories by delegating to the installer."""
        return self.installer.install()

    def uninstall(self) -> bool:
        """Uninstall Renderd packages and directories by delegating to the installer."""
        return self.installer.uninstall()

    def is_installed(self) -> bool:
        """Check if Renderd prerequisites are installed by delegating to the installer."""
        return self.installer.is_installed()

    def configure(self) -> bool:
        """
        Configure Renderd by creating config files and starting the service.
        """
        try:
            self._create_renderd_conf_file()
            self._create_renderd_systemd_service_file()
            self._activate_renderd_service()
            return True
        except Exception as e:
            self.logger.error(f"Error configuring Renderd: {str(e)}")
            return False

    def unconfigure(self) -> bool:
        """
        Unconfigure Renderd by stopping the service and removing config files.
        """
        try:
            run_elevated_command(
                ["systemctl", "stop", "renderd.service"],
                self.app_settings,
                check=False,
                current_logger=self.logger,
            )
            run_elevated_command(
                ["systemctl", "disable", "renderd.service"],
                self.app_settings,
                check=False,
                current_logger=self.logger,
            )

            for f in [self.RENDERD_CONF_FILE, self.RENDERD_SERVICE_FILE]:
                if os.path.exists(f):
                    run_elevated_command(
                        ["rm", f],
                        self.app_settings,
                        current_logger=self.logger,
                    )

            systemd_reload(self.app_settings, self.logger)
            return True
        except Exception as e:
            self.logger.error(f"Error unconfiguring Renderd: {str(e)}")
            return False

    def is_configured(self) -> bool:
        """
        Check if Renderd is configured and the service is running.
        """
        try:
            service_active = (
                run_elevated_command(
                    ["systemctl", "is-active", "renderd.service"],
                    self.app_settings,
                    check=False,
                    current_logger=self.logger,
                ).returncode
                == 0
            )
            return os.path.exists(self.RENDERD_CONF_FILE) and service_active
        except Exception as e:
            self.logger.error(
                f"Error checking Renderd configuration: {str(e)}"
            )
            return False

    def _get_mapnik_plugin_dir(self) -> str:
        """
        Determine the Mapnik plugins directory path.
        """
        # 1. Check for override
        override_dir = self.app_settings.renderd.mapnik_plugins_dir_override
        if override_dir and Path(override_dir).is_dir():
            return str(override_dir)

        # 2. Try mapnik-config
        # FIX: Correctly call command_exists with one argument
        if command_exists("mapnik-config"):
            try:
                res = run_command(
                    ["mapnik-config", "--input-plugins"],
                    self.app_settings,
                    capture_output=True,
                    current_logger=self.logger,
                )
                # FIX: Check type of stdout to satisfy type checker
                stdout_str = res.stdout
                if isinstance(stdout_str, str):
                    resolved_dir = stdout_str.strip()
                    if resolved_dir and Path(resolved_dir).is_dir():
                        return resolved_dir
            except Exception:
                pass  # Fall through to default

        # 3. Fallback to default
        return "/usr/lib/mapnik/3/input/"

    def _create_renderd_conf_file(self) -> None:
        """
        Create the renderd.conf file from a template.
        """
        script_hash = (
            get_current_script_hash(
                static_config.OSM_PROJECT_ROOT, self.app_settings, self.logger
            )
            or "UNKNOWN"
        )

        cpu_count = os.cpu_count() or 2
        num_threads = (
            int(cpu_count * self.app_settings.renderd.num_threads_multiplier)
            if self.app_settings.renderd.num_threads_multiplier > 0
            else 2
        )

        renderd_host = self.app_settings.vm_ip_or_domain
        if renderd_host == VM_IP_OR_DOMAIN_DEFAULT:
            renderd_host = "localhost"

        format_vars = {
            "renderd_conf_path": self.RENDERD_CONF_FILE,
            "script_hash": script_hash,
            "num_threads_renderd": str(num_threads),
            "renderd_tile_cache_dir": str(
                self.app_settings.renderd.tile_cache_dir
            ),
            "renderd_run_dir": str(self.app_settings.renderd.run_dir),
            "mapnik_plugins_dir": self._get_mapnik_plugin_dir(),
            "renderd_uri_path_segment": self.app_settings.renderd.uri_path_segment,
            "mapnik_xml_stylesheet_path": str(
                self.app_settings.renderd.mapnik_xml_stylesheet_path
            ),
            "renderd_host": renderd_host,
        }

        content = self.app_settings.renderd.renderd_conf_template.format(
            **format_vars
        )
        run_elevated_command(
            ["tee", self.RENDERD_CONF_FILE],
            self.app_settings,
            cmd_input=content,
            current_logger=self.logger,
        )
        run_elevated_command(
            [
                "chown",
                f"root:{self.RENDERD_SYSTEM_GROUP}",
                self.RENDERD_CONF_FILE,
            ],
            self.app_settings,
            current_logger=self.logger,
        )
        run_elevated_command(
            ["chmod", "640", self.RENDERD_CONF_FILE],
            self.app_settings,
            current_logger=self.logger,
        )

    def _create_renderd_systemd_service_file(self) -> None:
        """
        Create Renderd systemd service file.
        """
        service_content = f"""[Unit]
Description=Renderd - OSM tile rendering daemon
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User={self.RENDERD_SYSTEM_GROUP}
Group={self.RENDERD_SYSTEM_GROUP}
ExecStart=/usr/bin/renderd -f -c {self.RENDERD_CONF_FILE}
Restart=on-failure
RestartSec=5s
ProtectSystem=full
ProtectHome=true
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
"""
        run_elevated_command(
            ["tee", self.RENDERD_SERVICE_FILE],
            self.app_settings,
            cmd_input=service_content,
            current_logger=self.logger,
        )
        run_elevated_command(
            ["chmod", "644", self.RENDERD_SERVICE_FILE],
            self.app_settings,
            current_logger=self.logger,
        )

    def _activate_renderd_service(self) -> None:
        """
        Reload systemd, enable and restart the renderd service.
        """
        systemd_reload(self.app_settings, self.logger)
        run_elevated_command(
            ["systemctl", "enable", "renderd.service"],
            self.app_settings,
            current_logger=self.logger,
        )
        run_elevated_command(
            ["systemctl", "restart", "renderd.service"],
            self.app_settings,
            current_logger=self.logger,
        )
        run_elevated_command(
            ["systemctl", "status", "renderd.service", "--no-pager", "-l"],
            self.app_settings,
            current_logger=self.logger,
        )
