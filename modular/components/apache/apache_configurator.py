"""
Apache configurator module.

This module provides a self-contained configurator for Apache.
"""

import logging
import os
from typing import Optional

from common.command_utils import (
    elevated_command_exists,
    log_map_server,
    run_elevated_command,
)
from common.file_utils import backup_file
from common.system_utils import get_current_script_hash, systemd_reload
from modular.base_configurator import BaseConfigurator
from modular.registry import ComponentRegistry
from setup import (
    config as static_config,
)
from setup.config_models import (
    VM_IP_OR_DOMAIN_DEFAULT,
    AppSettings,
)


@ComponentRegistry.register(
    name="apache",
    metadata={
        "dependencies": [],  # Apache is a base component with no dependencies
        "description": "Apache web server configuration with mod_tile",
    },
)
class ApacheConfigurator(BaseConfigurator):
    """
    Configurator for Apache web server with mod_tile.

    This configurator ensures that Apache is properly configured with the necessary
    ports, modules, and site configurations for serving map tiles.
    """

    # Standard Apache paths
    PORTS_CONF_PATH = "/etc/apache2/ports.conf"
    MOD_TILE_CONF_AVAILABLE_PATH = "/etc/apache2/conf-available/mod_tile.conf"
    APACHE_TILES_SITE_CONF_AVAILABLE_PATH = (
        "/etc/apache2/sites-available/001-tiles.conf"
    )

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Apache configurator.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)

    def configure(self) -> bool:
        """
        Configure Apache with the necessary settings.

        This method performs the following configuration tasks:
        1. Configures Apache ports
        2. Creates mod_tile configuration
        3. Creates Apache tile site configuration
        4. Manages Apache modules and sites
        5. Activates the Apache service

        Returns:
            True if the configuration was successful, False otherwise.
        """
        try:
            self._configure_apache_ports()
            self._create_mod_tile_config()
            self._create_apache_tile_site_config()
            self._manage_apache_modules_and_sites()
            self._activate_apache_service()
            return True
        except Exception as e:
            self.logger.error(f"Error configuring Apache: {str(e)}")
            return False

    def unconfigure(self) -> bool:
        """
        Unconfigure Apache settings.

        This method removes the custom Apache configurations and restores
        the default settings.

        Returns:
            True if the unconfiguration was successful, False otherwise.
        """
        try:
            symbols = self.app_settings.symbols

            # Disable the tile site
            tile_site_name = os.path.basename(
                self.APACHE_TILES_SITE_CONF_AVAILABLE_PATH
            ).replace(".conf", "")
            run_elevated_command(
                ["a2dissite", tile_site_name],
                self.app_settings,
                current_logger=self.logger,
            )
            log_map_server(
                f"{symbols.get('success', '')} Disabled Apache tile site",
                "success",
                self.logger,
                self.app_settings,
            )

            # Disable the mod_tile configuration
            run_elevated_command(
                ["a2disconf", "mod_tile"],
                self.app_settings,
                current_logger=self.logger,
            )
            log_map_server(
                f"{symbols.get('success', '')} Disabled mod_tile configuration",
                "success",
                self.logger,
                self.app_settings,
            )

            # Re-enable the default site if it exists
            default_site_path = (
                "/etc/apache2/sites-available/000-default.conf"
            )
            if os.path.exists(default_site_path):
                run_elevated_command(
                    ["a2ensite", "000-default"],
                    self.app_settings,
                    current_logger=self.logger,
                )
                log_map_server(
                    f"{symbols.get('success', '')} Re-enabled default Apache site",
                    "success",
                    self.logger,
                    self.app_settings,
                )

            # Restore the original ports.conf if a backup exists
            backup_path = f"{self.PORTS_CONF_PATH}.bak"
            if os.path.exists(backup_path):
                run_elevated_command(
                    ["cp", backup_path, self.PORTS_CONF_PATH],
                    self.app_settings,
                    current_logger=self.logger,
                )
                log_map_server(
                    f"{symbols.get('success', '')} Restored original Apache ports configuration",
                    "success",
                    self.logger,
                    self.app_settings,
                )

            # Restart Apache
            self._activate_apache_service()

            return True
        except Exception as e:
            self.logger.error(f"Error unconfiguring Apache: {str(e)}")
            return False

    def is_configured(self) -> bool:
        """
        Check if Apache is configured.

        This method checks if the Apache tile site configuration file exists and
        is enabled, and if the Apache service is active.

        Returns:
            True if Apache is configured, False otherwise.
        """
        try:
            # Check if the tile site configuration file exists
            if not os.path.exists(self.APACHE_TILES_SITE_CONF_AVAILABLE_PATH):
                return False

            # Check if the tile site is enabled
            tile_site_name = os.path.basename(
                self.APACHE_TILES_SITE_CONF_AVAILABLE_PATH
            ).replace(".conf", "")
            site_enabled_path = (
                f"/etc/apache2/sites-enabled/{tile_site_name}.conf"
            )
            if not os.path.exists(site_enabled_path) and not os.path.islink(
                site_enabled_path
            ):
                return False

            # Check if the mod_tile configuration is enabled
            mod_tile_enabled_path = "/etc/apache2/conf-enabled/mod_tile.conf"
            if not os.path.exists(
                mod_tile_enabled_path
            ) and not os.path.islink(mod_tile_enabled_path):
                return False

            # Check if the Apache service is active
            result = run_elevated_command(
                ["systemctl", "is-active", "apache2.service"],
                self.app_settings,
                capture_output=True,
                check=False,
                current_logger=self.logger,
            )

            return result.returncode == 0
        except Exception as e:
            self.logger.error(
                f"Error checking if Apache is configured: {str(e)}"
            )
            return False

    def _configure_apache_ports(self) -> None:
        """
        Configure Apache ports.

        Raises:
            FileNotFoundError: If the Apache ports configuration file cannot be found.
        """
        symbols = self.app_settings.symbols
        target_listen_port = self.app_settings.apache.listen_port

        log_map_server(
            f"{symbols.get('step', '')} Configuring Apache listening ports to {target_listen_port}...",
            "info",
            self.logger,
            self.app_settings,
        )

        if not os.path.exists(self.PORTS_CONF_PATH):
            try:
                run_elevated_command(
                    ["test", "-f", self.PORTS_CONF_PATH],
                    self.app_settings,
                    check=True,
                    capture_output=True,
                    current_logger=self.logger,
                )
            except Exception as e:
                log_map_server(
                    f"{symbols.get('critical', '')} Apache ports configuration file {self.PORTS_CONF_PATH} not found.",
                    "critical",
                    self.logger,
                    self.app_settings,
                )
                raise FileNotFoundError(
                    f"{self.PORTS_CONF_PATH} not found."
                ) from e

        if backup_file(
            self.PORTS_CONF_PATH,
            self.app_settings,
            current_logger=self.logger,
        ):
            # Replace "Listen 80" with "Listen <target_listen_port>"
            # And "Listen [::]:80" with "Listen [::]:<target_listen_port>"
            sed_cmd_ipv4 = [
                "sed",
                "-i.bak_ports_sed",
                f"s/^Listen 80$/Listen {target_listen_port}/",
                self.PORTS_CONF_PATH,
            ]
            sed_cmd_ipv6 = [
                "sed",
                "-i",
                f"s/^Listen \\[::\\]:80$/Listen [::]:{target_listen_port}/",
                self.PORTS_CONF_PATH,
            ]

            run_elevated_command(
                sed_cmd_ipv4, self.app_settings, current_logger=self.logger
            )
            run_elevated_command(
                sed_cmd_ipv6,
                self.app_settings,
                current_logger=self.logger,
                check=False,
            )  # Allow to fail if IPv6 line not present

            log_map_server(
                f"{symbols.get('success', '')} Apache configured to listen on port {target_listen_port} (original backed up).",
                "success",
                self.logger,
                self.app_settings,
            )

    def _create_mod_tile_config(self) -> None:
        """
        Create the mod_tile Apache configuration file.

        Raises:
            KeyError: If a required placeholder key is missing in the mod_tile.conf template.
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

        log_map_server(
            f"{symbols.get('step', '')} Creating mod_tile Apache configuration from template...",
            "info",
            self.logger,
            self.app_settings,
        )

        mod_tile_template = self.app_settings.apache.mod_tile_conf_template
        format_vars = {
            "script_hash": script_hash,
            "mod_tile_request_timeout": self.app_settings.apache.mod_tile_request_timeout,
            "mod_tile_missing_request_timeout": self.app_settings.apache.mod_tile_missing_request_timeout,
            "mod_tile_max_load_old": self.app_settings.apache.mod_tile_max_load_old,
            "mod_tile_max_load_missing": self.app_settings.apache.mod_tile_max_load_missing,
        }

        try:
            mod_tile_conf_content_final = mod_tile_template.format(
                **format_vars
            )
            run_elevated_command(
                ["tee", self.MOD_TILE_CONF_AVAILABLE_PATH],
                self.app_settings,
                cmd_input=mod_tile_conf_content_final,
                current_logger=self.logger,
            )
            log_map_server(
                f"{symbols.get('success', '')} Created/Updated {self.MOD_TILE_CONF_AVAILABLE_PATH}",
                "success",
                self.logger,
                self.app_settings,
            )
        except KeyError as e_key:
            log_map_server(
                f"{symbols.get('error', '')} Missing placeholder key '{e_key}' for mod_tile.conf template. Check config.yaml/models.",
                "error",
                self.logger,
                self.app_settings,
            )
            raise
        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '')} Failed to write {self.MOD_TILE_CONF_AVAILABLE_PATH}: {e}",
                "error",
                self.logger,
                self.app_settings,
            )
            raise

    def _create_apache_tile_site_config(self) -> None:
        """
        Create the Apache site configuration file for serving map tiles.

        Raises:
            KeyError: If a required placeholder key is missing in the Apache tile site template.
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

        log_map_server(
            f"{symbols.get('step', '')} Creating Apache tile serving site configuration from template...",
            "info",
            self.logger,
            self.app_settings,
        )

        # Determine ServerName and ServerAdmin for the template
        server_name_val = self.app_settings.vm_ip_or_domain
        if server_name_val == VM_IP_OR_DOMAIN_DEFAULT:
            server_name_val = (
                "tiles.localhost"  # Default if using placeholder domain
            )

        admin_email_val = f"webmaster@{self.app_settings.vm_ip_or_domain}"
        if self.app_settings.vm_ip_or_domain == VM_IP_OR_DOMAIN_DEFAULT:
            admin_email_val = "webmaster@localhost"

        tile_site_template = self.app_settings.apache.tile_site_template
        format_vars = {
            "script_hash": script_hash,
            "apache_listen_port": self.app_settings.apache.listen_port,
            "server_name_apache": server_name_val,
            "admin_email_apache": admin_email_val,
        }

        try:
            apache_tiles_site_content_final = tile_site_template.format(
                **format_vars
            )
            run_elevated_command(
                ["tee", self.APACHE_TILES_SITE_CONF_AVAILABLE_PATH],
                self.app_settings,
                cmd_input=apache_tiles_site_content_final,
                current_logger=self.logger,
            )
            log_map_server(
                f"{symbols.get('success', '')} Created/Updated {self.APACHE_TILES_SITE_CONF_AVAILABLE_PATH}",
                "success",
                self.logger,
                self.app_settings,
            )
        except KeyError as e_key:
            log_map_server(
                f"{symbols.get('error', '')} Missing placeholder key '{e_key}' for Apache tile site template. Check config.yaml/models.",
                "error",
                self.logger,
                self.app_settings,
            )
            raise
        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '')} Failed to write {self.APACHE_TILES_SITE_CONF_AVAILABLE_PATH}: {e}",
                "error",
                self.logger,
                self.app_settings,
            )
            raise

    def _manage_apache_modules_and_sites(self) -> None:
        """
        Enable necessary Apache configurations, modules, and sites for tile serving.
        """
        symbols = self.app_settings.symbols
        log_map_server(
            f"{symbols.get('step', '')} Enabling Apache modules and site configurations...",
            "info",
            self.logger,
            self.app_settings,
        )

        run_elevated_command(
            ["a2enconf", "mod_tile"],
            self.app_settings,
            current_logger=self.logger,
        )
        for mod in ["expires", "headers"]:  # These module names are static
            run_elevated_command(
                ["a2enmod", mod],
                self.app_settings,
                current_logger=self.logger,
            )

        tile_site_name = os.path.basename(
            self.APACHE_TILES_SITE_CONF_AVAILABLE_PATH
        ).replace(".conf", "")
        run_elevated_command(
            ["a2ensite", tile_site_name],
            self.app_settings,
            current_logger=self.logger,
        )

        default_site_enabled_path = (
            "/etc/apache2/sites-enabled/000-default.conf"
        )
        if elevated_command_exists(
            f"test -L {default_site_enabled_path}",
            self.app_settings,
            current_logger=self.logger,
        ):
            log_map_server(
                f"{symbols.get('info', '')} Disabling default Apache site (000-default)...",
                "info",
                self.logger,
                self.app_settings,
            )
            run_elevated_command(
                ["a2dissite", "000-default"],
                self.app_settings,
                current_logger=self.logger,
            )
        else:
            log_map_server(
                f"{symbols.get('info', '')} Default Apache site not enabled or not found. Skipping disable.",
                "info",
                self.logger,
                self.app_settings,
            )
        log_map_server(
            f"{symbols.get('success', '')} Apache modules and sites configured.",
            "success",
            self.logger,
            self.app_settings,
        )

    def _activate_apache_service(self) -> None:
        """
        Reload systemd, restart and enable the Apache service.
        """
        symbols = self.app_settings.symbols
        log_map_server(
            f"{symbols.get('step', '')} Activating Apache service...",
            "info",
            self.logger,
            self.app_settings,
        )

        systemd_reload(self.app_settings, current_logger=self.logger)
        run_elevated_command(
            ["systemctl", "restart", "apache2.service"],
            self.app_settings,
            current_logger=self.logger,
        )
        run_elevated_command(
            ["systemctl", "enable", "apache2.service"],
            self.app_settings,
            current_logger=self.logger,
        )

        log_map_server(
            f"{symbols.get('info', '')} Apache service status:",
            "info",
            self.logger,
            self.app_settings,
        )
        run_elevated_command(
            ["systemctl", "status", "apache2.service", "--no-pager", "-l"],
            self.app_settings,
            current_logger=self.logger,
        )
        log_map_server(
            f"{symbols.get('success', '')} Apache service activated.",
            "success",
            self.logger,
            self.app_settings,
        )
