"""
Renderd configurator module.

This module provides a self-contained configurator for Renderd,
including its .conf file and service activation.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from common.command_utils import (
    command_exists,
    log_map_server,
    run_command,
    run_elevated_command,
)
from common.system_utils import get_current_script_hash, systemd_reload
from installer import config as static_config
from installer.base_component import BaseComponent
from installer.config_models import (
    VM_IP_OR_DOMAIN_DEFAULT,
    AppSettings,
)
from installer.registry import ComponentRegistry


@ComponentRegistry.register(
    name="renderd",
    metadata={
        "dependencies": [
            "carto"
        ],  # Renderd depends on Carto for the mapnik.xml file
        "description": "Renderd configuration and service activation",
    },
)
class RenderdConfigurator(BaseComponent):
    """
    Configurator for Renderd.

    This configurator ensures that Renderd is properly configured,
    including its .conf file and service activation.
    """

    # Constants for Renderd configuration
    RENDERD_CONF_FILE_SYSTEM_PATH = "/etc/renderd.conf"
    RENDERD_SYSTEM_GROUP = "www-data"  # Group for config file readability

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Renderd configurator.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)

    def configure(self) -> bool:
        """
        Configure Renderd.

        This method performs the following configuration tasks:
        1. Creates the renderd configuration file from a template
        2. Activates the renderd service

        Returns:
            True if the configuration was successful, False otherwise.
        """
        try:
            self._create_renderd_conf_file()
            self._activate_renderd_service()
            return True
        except Exception as e:
            self.logger.error(f"Error configuring Renderd: {str(e)}")
            return False

    def unconfigure(self) -> bool:
        """
        Unconfigure Renderd.

        This method performs the following unconfiguration tasks:
        1. Stops and disables the renderd service
        2. Removes the renderd configuration file

        Returns:
            True if the unconfiguration was successful, False otherwise.
        """
        try:
            symbols = self.app_settings.symbols

            # Stop and disable the service
            log_map_server(
                f"{symbols.get('step', '')} Stopping and disabling renderd service...",
                "info",
                self.logger,
                self.app_settings,
            )
            run_elevated_command(
                ["systemctl", "stop", "renderd.service"],
                self.app_settings,
                current_logger=self.logger,
                check=False,
            )
            run_elevated_command(
                ["systemctl", "disable", "renderd.service"],
                self.app_settings,
                current_logger=self.logger,
                check=False,
            )

            # Remove the configuration file
            if Path(self.RENDERD_CONF_FILE_SYSTEM_PATH).exists():
                run_elevated_command(
                    ["rm", self.RENDERD_CONF_FILE_SYSTEM_PATH],
                    self.app_settings,
                    current_logger=self.logger,
                )
                log_map_server(
                    f"{symbols.get('success', '')} Removed renderd configuration file.",
                    "success",
                    self.logger,
                    self.app_settings,
                )

            # Reload systemd to apply changes
            systemd_reload(self.app_settings, current_logger=self.logger)

            log_map_server(
                f"{symbols.get('success', '')} Renderd unconfigured successfully.",
                "success",
                self.logger,
                self.app_settings,
            )

            return True
        except Exception as e:
            self.logger.error(f"Error unconfiguring Renderd: {str(e)}")
            return False

    def is_configured(self) -> bool:
        """
        Check if Renderd is configured.

        This method checks if the renderd configuration file exists and
        the renderd service is enabled and active.

        Returns:
            True if Renderd is configured, False otherwise.
        """
        try:
            # Check if the configuration file exists
            if not Path(self.RENDERD_CONF_FILE_SYSTEM_PATH).exists():
                return False

            # Check if the service is enabled
            result = run_elevated_command(
                ["systemctl", "is-enabled", "renderd.service"],
                self.app_settings,
                capture_output=True,
                check=False,
                current_logger=self.logger,
            )
            if result.returncode != 0:
                return False

            # Check if the service is active
            result = run_elevated_command(
                ["systemctl", "is-active", "renderd.service"],
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
                f"Error checking if Renderd is configured: {str(e)}"
            )
            return False

    def _get_mapnik_plugin_dir(self) -> str:
        """
        Determine the Mapnik plugins directory path.

        Returns:
            The path to the Mapnik plugins directory.
        """
        symbols = self.app_settings.symbols

        # 1. Check for override path
        mapnik_plugins_dir_override_val = (
            self.app_settings.renderd.mapnik_plugins_dir_override
        )
        if mapnik_plugins_dir_override_val is not None:
            override_path_str = str(mapnik_plugins_dir_override_val)
            if Path(override_path_str).is_dir():
                log_map_server(
                    f"{symbols.get('info', '')} Using Mapnik plugins directory from override: {override_path_str}",
                    "info",
                    self.logger,
                    self.app_settings,
                )
                return override_path_str
            else:
                log_map_server(
                    f"{symbols.get('warning', '')} Override Mapnik plugins directory '{override_path_str}' not found or not a directory. Trying auto-detection.",
                    "warning",
                    self.logger,
                    self.app_settings,
                )

        # 2. Default logic if no valid override: Try mapnik-config
        default_debian_plugins_dir = (
            "/usr/lib/mapnik/input/"  # Generic for Mapnik 3.x/4.x
        )

        if command_exists("mapnik-config"):
            try:
                mapnik_config_res: subprocess.CompletedProcess = run_command(
                    ["mapnik-config", "--input-plugins"],
                    self.app_settings,
                    capture_output=True,
                    check=True,
                    current_logger=self.logger,
                )
                stdout_val: Optional[str] = mapnik_config_res.stdout
                if stdout_val is not None:
                    resolved_dir: str = stdout_val.strip()
                    if resolved_dir and Path(resolved_dir).is_dir():
                        log_map_server(
                            f"{symbols.get('info', '')} Determined Mapnik plugins directory via mapnik-config: {resolved_dir}",
                            "info",
                            self.logger,
                            self.app_settings,
                        )
                        return resolved_dir
                    else:
                        log_map_server(
                            f"{symbols.get('warning', '')} mapnik-config provided non-existent or empty directory path: '{resolved_dir}'. Trying default Debian path.",
                            "warning",
                            self.logger,
                            self.app_settings,
                        )
                else:  # stdout_val is None
                    log_map_server(
                        f"{symbols.get('warning', '')} mapnik-config command succeeded but produced no output. Trying default Debian path.",
                        "warning",
                        self.logger,
                        self.app_settings,
                    )
            except Exception as e_mapnik:
                log_map_server(
                    f"{symbols.get('warning', '')} mapnik-config failed or error during processing ({e_mapnik}). Trying default Debian path: {default_debian_plugins_dir}",
                    "warning",
                    self.logger,
                    self.app_settings,
                )

        # 3. Try default Debian path if mapnik-config failed or didn't yield a valid path
        if Path(default_debian_plugins_dir).is_dir():
            log_map_server(
                f"{symbols.get('info', '')} Using default Mapnik plugins directory: {default_debian_plugins_dir}",
                "info",
                self.logger,
                self.app_settings,
            )
            return default_debian_plugins_dir

        # 4. Fallback if everything else fails
        final_fallback_dir = (
            "/usr/lib/mapnik/input/"  # A common older default
        )
        log_map_server(
            f"{symbols.get('critical', '')} Mapnik plugins directory not found via override, mapnik-config, or common defaults. Fallback to: {final_fallback_dir}. Renderd may fail if this path is incorrect.",
            "critical",
            self.logger,
            self.app_settings,
        )
        return final_fallback_dir

    def _create_renderd_conf_file(self) -> None:
        """
        Create the renderd configuration file from a template.

        Raises:
            KeyError: If a required placeholder key is missing in the renderd template.
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

        log_map_server(
            f"{symbols.get('step', '')} Creating {self.RENDERD_CONF_FILE_SYSTEM_PATH} from template...",
            "info",
            self.logger,
            self.app_settings,
        )

        # Calculate num_threads for renderd
        num_threads_val = 0
        if self.app_settings.renderd.num_threads_multiplier > 0:
            cpu_c = os.cpu_count()
            if cpu_c:
                num_threads_val = int(
                    cpu_c * self.app_settings.renderd.num_threads_multiplier
                )
            else:  # Fallback if cpu_count() is None
                num_threads_val = int(
                    2 * self.app_settings.renderd.num_threads_multiplier
                )  # e.g. 2*2=4
            if num_threads_val == 0:
                num_threads_val = 2  # Ensure at least 2 if multiplier is very small leading to 0

        num_threads_renderd_str = (
            str(num_threads_val)
            if self.app_settings.renderd.num_threads_multiplier > 0
            else "0"
        )

        mapnik_plugins_dir_val = self._get_mapnik_plugin_dir()

        renderd_host_val = self.app_settings.vm_ip_or_domain
        if renderd_host_val == VM_IP_OR_DOMAIN_DEFAULT:
            renderd_host_val = "localhost"

        renderd_conf_template_str = (
            self.app_settings.renderd.renderd_conf_template
        )
        format_vars = {
            "renderd_conf_path": self.RENDERD_CONF_FILE_SYSTEM_PATH,
            "script_hash": script_hash,
            "num_threads_renderd": num_threads_renderd_str,
            "renderd_tile_cache_dir": str(
                self.app_settings.renderd.tile_cache_dir
            ),
            "renderd_run_dir": str(self.app_settings.renderd.run_dir),
            "mapnik_plugins_dir": mapnik_plugins_dir_val,
            "renderd_uri_path_segment": self.app_settings.renderd.uri_path_segment,
            "mapnik_xml_stylesheet_path": str(
                self.app_settings.renderd.mapnik_xml_stylesheet_path
            ),
            "renderd_host": renderd_host_val,
        }

        try:
            renderd_conf_content_final = renderd_conf_template_str.format(
                **format_vars
            )
            run_elevated_command(
                ["tee", self.RENDERD_CONF_FILE_SYSTEM_PATH],
                self.app_settings,
                cmd_input=renderd_conf_content_final,
                current_logger=self.logger,
            )
            # Config file should be readable by the renderd user (e.g., www-data)
            run_elevated_command(
                [
                    "chown",
                    f"root:{self.RENDERD_SYSTEM_GROUP}",
                    self.RENDERD_CONF_FILE_SYSTEM_PATH,
                ],
                self.app_settings,
                current_logger=self.logger,
            )
            run_elevated_command(
                ["chmod", "640", self.RENDERD_CONF_FILE_SYSTEM_PATH],
                self.app_settings,
                current_logger=self.logger,
            )
            log_map_server(
                f"{symbols.get('success', '')} Created/Updated and secured {self.RENDERD_CONF_FILE_SYSTEM_PATH}",
                "success",
                self.logger,
                self.app_settings,
            )
        except KeyError as e_key:
            log_map_server(
                f"{symbols.get('error', '')} Missing placeholder key '{e_key}' for renderd.conf template. Check config.yaml/models.",
                "error",
                self.logger,
                self.app_settings,
            )
            raise
        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '')} Failed to write or set permissions for {self.RENDERD_CONF_FILE_SYSTEM_PATH}: {e}",
                "error",
                self.logger,
                self.app_settings,
            )
            raise

    def _activate_renderd_service(self) -> None:
        """
        Reload systemd, enable and restart the renderd service.
        """
        symbols = self.app_settings.symbols
        log_map_server(
            f"{symbols.get('step', '')} Activating Renderd systemd service...",
            "info",
            self.logger,
            self.app_settings,
        )

        systemd_reload(self.app_settings, current_logger=self.logger)
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

        log_map_server(
            f"{symbols.get('info', '')} Renderd service status:",
            "info",
            self.logger,
            self.app_settings,
        )
        run_elevated_command(
            ["systemctl", "status", "renderd.service", "--no-pager", "-l"],
            self.app_settings,
            current_logger=self.logger,
        )
        log_map_server(
            f"{symbols.get('success', '')} Renderd service activated.",
            "success",
            self.logger,
            self.app_settings,
        )
