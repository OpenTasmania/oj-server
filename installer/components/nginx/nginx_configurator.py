"""
Nginx configurator module.

This module provides a self-contained configurator for Nginx.
"""

import logging
import os
import subprocess
from typing import Optional

from common.command_utils import (
    log_map_server,
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
    name="nginx",
    metadata={
        "dependencies": [],  # Nginx is a base component with no dependencies
        "description": "Nginx web server and reverse proxy configuration",
    },
)
class NginxConfigurator(BaseComponent):
    """
    Configurator for Nginx web server and reverse proxy.

    This configurator ensures that Nginx is properly configured as a reverse proxy
    for map services, with the necessary site configurations and service settings.
    """

    # Standard Nginx paths
    NGINX_SITES_AVAILABLE_DIR = "/etc/nginx/sites-available"
    NGINX_SITES_ENABLED_DIR = "/etc/nginx/sites-enabled"

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Nginx configurator.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)

    def configure(self) -> bool:
        """
        Configure Nginx with the necessary settings.

        This method performs the following configuration tasks:
        1. Creates the Nginx proxy site configuration file
        2. Enables the new site and disables the default site
        3. Tests the Nginx configuration for syntax errors
        4. Activates the Nginx service

        Returns:
            True if the configuration was successful, False otherwise.
        """
        try:
            self._create_nginx_proxy_site_config()
            self._manage_nginx_sites()
            self._test_nginx_configuration()
            self._activate_nginx_service()
            return True
        except Exception as e:
            self.logger.error(f"Error configuring Nginx: {str(e)}")
            return False

    def unconfigure(self) -> bool:
        """
        Unconfigure Nginx settings.

        This method removes the custom Nginx site configuration and restores
        the default site.

        Returns:
            True if the unconfiguration was successful, False otherwise.
        """
        try:
            proxy_conf_filename = self.app_settings.nginx.proxy_conf_name_base
            symbols = self.app_settings.symbols

            # Remove the enabled site symlink
            symlink_path = os.path.join(
                self.NGINX_SITES_ENABLED_DIR, proxy_conf_filename
            )
            if os.path.exists(symlink_path) or os.path.islink(symlink_path):
                run_elevated_command(
                    ["rm", symlink_path],
                    self.app_settings,
                    current_logger=self.logger,
                )
                log_map_server(
                    f"{symbols.get('success', '')} Removed Nginx site symlink: {symlink_path}",
                    "success",
                    self.logger,
                    self.app_settings,
                )

            # Remove the site configuration file
            conf_path = os.path.join(
                self.NGINX_SITES_AVAILABLE_DIR, proxy_conf_filename
            )
            if os.path.exists(conf_path):
                run_elevated_command(
                    ["rm", conf_path],
                    self.app_settings,
                    current_logger=self.logger,
                )
                log_map_server(
                    f"{symbols.get('success', '')} Removed Nginx site configuration: {conf_path}",
                    "success",
                    self.logger,
                    self.app_settings,
                )

            # Re-enable the default site if it exists
            default_site_path = os.path.join(
                self.NGINX_SITES_AVAILABLE_DIR, "default"
            )
            default_symlink_path = os.path.join(
                self.NGINX_SITES_ENABLED_DIR, "default"
            )
            if os.path.exists(default_site_path) and not os.path.exists(
                default_symlink_path
            ):
                run_elevated_command(
                    ["ln", "-sf", default_site_path, default_symlink_path],
                    self.app_settings,
                    current_logger=self.logger,
                )
                log_map_server(
                    f"{symbols.get('success', '')} Re-enabled default Nginx site",
                    "success",
                    self.logger,
                    self.app_settings,
                )

            # Test and restart Nginx
            self._test_nginx_configuration()
            self._activate_nginx_service()

            return True
        except Exception as e:
            self.logger.error(f"Error unconfiguring Nginx: {str(e)}")
            return False

    def is_configured(self) -> bool:
        """
        Check if Nginx is configured.

        This method checks if the Nginx proxy site configuration file exists and
        is enabled, and if the Nginx service is active.

        Returns:
            True if Nginx is configured, False otherwise.
        """
        try:
            proxy_conf_filename = self.app_settings.nginx.proxy_conf_name_base

            # Check if the site configuration file exists
            conf_path = os.path.join(
                self.NGINX_SITES_AVAILABLE_DIR, proxy_conf_filename
            )
            if not os.path.exists(conf_path):
                return False

            # Check if the site is enabled
            symlink_path = os.path.join(
                self.NGINX_SITES_ENABLED_DIR, proxy_conf_filename
            )
            if not os.path.exists(symlink_path) and not os.path.islink(
                symlink_path
            ):
                return False

            # Check if the Nginx service is active
            result = run_elevated_command(
                ["systemctl", "is-active", "nginx.service"],
                self.app_settings,
                capture_output=True,
                check=False,
                current_logger=self.logger,
            )

            return result.returncode == 0
        except Exception as e:
            self.logger.error(
                f"Error checking if Nginx is configured: {str(e)}"
            )
            return False

    def _create_nginx_proxy_site_config(self) -> None:
        """
        Create the Nginx site configuration file for reverse proxying services.

        Raises:
            KeyError: If a required placeholder key is missing in the Nginx template.
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

        proxy_conf_filename = self.app_settings.nginx.proxy_conf_name_base

        nginx_conf_path = os.path.join(
            self.NGINX_SITES_AVAILABLE_DIR, proxy_conf_filename
        )
        log_map_server(
            f"{symbols.get('step', '')} Creating Nginx site configuration: {nginx_conf_path} from template...",
            "info",
            self.logger,
            self.app_settings,
        )

        server_name_val = self.app_settings.vm_ip_or_domain
        if server_name_val == VM_IP_OR_DOMAIN_DEFAULT:
            server_name_val = "_"  # Catch-all if default example.com is used

        nginx_template = self.app_settings.nginx.proxy_site_template
        format_vars = {
            "script_hash": script_hash,
            "server_name_nginx": server_name_val,
            "proxy_conf_filename_base": proxy_conf_filename,  # For log file names
            "pg_tileserv_port": self.app_settings.pg_tileserv.http_port,
            "apache_port": self.app_settings.apache.listen_port,
            "osrm_port_car": self.app_settings.osrm_service.car_profile_default_host_port,
            "website_root_dir": self.app_settings.webapp.root_dir,
        }

        try:
            nginx_conf_content_final = nginx_template.format(**format_vars)
            run_elevated_command(
                ["tee", nginx_conf_path],
                self.app_settings,
                cmd_input=nginx_conf_content_final,
                current_logger=self.logger,
            )
            log_map_server(
                f"{symbols.get('success', '')} Created Nginx site configuration: {nginx_conf_path}",
                "success",
                self.logger,
                self.app_settings,
            )
        except KeyError as e_key:
            log_map_server(
                f"{symbols.get('error', '')} Missing placeholder key '{e_key}' for Nginx proxy template. Check config.yaml/models.",
                "error",
                self.logger,
                self.app_settings,
            )
            raise
        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '')} Failed to write Nginx site configuration {nginx_conf_path}: {e}",
                "error",
                self.logger,
                self.app_settings,
            )
            raise

    def _manage_nginx_sites(self) -> None:
        """
        Enable the new Nginx proxy site and disable the default site.

        Raises:
            FileNotFoundError: If the source Nginx site configuration file does not exist.
            Exception: For any other errors encountered during the symbolic link creation
                or default site removal process.
        """
        symbols = self.app_settings.symbols
        proxy_conf_filename = self.app_settings.nginx.proxy_conf_name_base

        log_map_server(
            f"{symbols.get('step', '')} Managing Nginx sites (enabling {proxy_conf_filename}, disabling default)...",
            "info",
            self.logger,
            self.app_settings,
        )

        source_conf_path = os.path.join(
            self.NGINX_SITES_AVAILABLE_DIR, proxy_conf_filename
        )
        symlink_path = os.path.join(
            self.NGINX_SITES_ENABLED_DIR, proxy_conf_filename
        )

        if not os.path.exists(source_conf_path):
            try:
                run_elevated_command(
                    ["test", "-f", source_conf_path],
                    self.app_settings,
                    check=True,
                    current_logger=self.logger,
                )
            except Exception as e:
                log_map_server(
                    f"{symbols.get('error', '')} Nginx site file {source_conf_path} does not exist. Cannot enable.",
                    "error",
                    self.logger,
                    self.app_settings,
                )
                raise FileNotFoundError(
                    f"{source_conf_path} not found."
                ) from e

        run_elevated_command(
            ["ln", "-sf", source_conf_path, symlink_path],
            self.app_settings,
            current_logger=self.logger,
        )
        log_map_server(
            f"{symbols.get('success', '')} Enabled Nginx site '{proxy_conf_filename}'.",
            "success",
            self.logger,
            self.app_settings,
        )

        default_nginx_symlink = os.path.join(
            self.NGINX_SITES_ENABLED_DIR, "default"
        )
        try:
            test_command = [
                "test",
                "-L",
                default_nginx_symlink,
                "-o",
                "-f",
                default_nginx_symlink,
            ]
            result = run_elevated_command(
                test_command,
                self.app_settings,
                check=False,
                current_logger=self.logger,
            )
            if result:
                run_elevated_command(
                    ["rm", default_nginx_symlink],
                    self.app_settings,
                    current_logger=self.logger,
                )
                log_map_server(
                    f"{symbols.get('info', '')} Disabled default Nginx site ({default_nginx_symlink}).",
                    "info",
                    self.logger,
                    self.app_settings,
                )
            else:
                log_map_server(
                    f"{symbols.get('info', '')} Default Nginx site not enabled or symlink not found ({default_nginx_symlink}). Skipping disable.",
                    "info",
                    self.logger,
                    self.app_settings,
                )
        except Exception as e:
            log_map_server(
                f"{symbols.get('warning', '')} Could not disable default Nginx site (error: {e}). This might be okay.",
                "warning",
                self.logger,
                self.app_settings,
            )
            raise

    def _test_nginx_configuration(self) -> None:
        """
        Test the Nginx configuration for syntax errors.

        Raises:
            subprocess.CalledProcessError: If the Nginx configuration test fails, indicating
                syntax errors or other configuration issues.
        """
        symbols = self.app_settings.symbols
        log_map_server(
            f"{symbols.get('step', '')} Testing Nginx configuration (nginx -t)...",
            "info",
            self.logger,
            self.app_settings,
        )
        try:
            run_elevated_command(
                ["nginx", "-t"],
                self.app_settings,
                current_logger=self.logger,
                check=True,
            )
            log_map_server(
                f"{symbols.get('success', '')} Nginx configuration test successful.",
                "success",
                self.logger,
                self.app_settings,
            )
        except subprocess.CalledProcessError:
            # Error already logged by run_elevated_command
            raise  # Propagate failure, this is critical

    def _activate_nginx_service(self) -> None:
        """
        Reload systemd, restart and enable the Nginx service.

        Raises:
            subprocess.CalledProcessError: If restarting or enabling the service fails.
        """
        symbols = self.app_settings.symbols
        log_map_server(
            f"{symbols.get('step', '')} Activating Nginx service...",
            "info",
            self.logger,
            self.app_settings,
        )

        systemd_reload(self.app_settings, current_logger=self.logger)
        run_elevated_command(
            ["systemctl", "restart", "nginx.service"],
            self.app_settings,
            current_logger=self.logger,
        )
        run_elevated_command(
            ["systemctl", "enable", "nginx.service"],
            self.app_settings,
            current_logger=self.logger,
        )

        log_map_server(
            f"{symbols.get('info', '')} Nginx service status:",
            "info",
            self.logger,
            self.app_settings,
        )
        run_elevated_command(
            ["systemctl", "status", "nginx.service", "--no-pager", "-l"],
            self.app_settings,
            current_logger=self.logger,
        )
        log_map_server(
            f"{symbols.get('success', '')} Nginx service activated.",
            "success",
            self.logger,
            self.app_settings,
        )

    def install(self) -> bool:
        """
        Install Nginx.

        This is a placeholder implementation. In a real implementation, this method
        would install Nginx.

        Returns:
            True if the installation was successful, False otherwise.
        """
        # This is a placeholder implementation
        return True

    def uninstall(self) -> bool:
        """
        Uninstall Nginx.

        This is a placeholder implementation. In a real implementation, this method
        would uninstall Nginx.

        Returns:
            True if the uninstallation was successful, False otherwise.
        """
        # This is a placeholder implementation
        return True

    def is_installed(self) -> bool:
        """
        Check if Nginx is installed.

        This is a placeholder implementation. In a real implementation, this method
        would check if Nginx is installed.

        Returns:
            True if Nginx is installed, False otherwise.
        """
        # This is a placeholder implementation
        return True
