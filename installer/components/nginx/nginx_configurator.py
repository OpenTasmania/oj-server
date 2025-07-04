"""
Nginx configurator module.

This module provides a self-contained configurator for Nginx.
"""

import logging
import os
import subprocess
from typing import Optional

from common.command_utils import (
    run_elevated_command,
)
from common.system_utils import get_current_script_hash, systemd_reload
from installer import config as static_config
from installer.base_component import BaseComponent
from installer.components.nginx.nginx_installer import NginxInstaller
from installer.config_models import (
    VM_IP_OR_DOMAIN_DEFAULT,
    AppSettings,
)
from installer.registry import ComponentRegistry


@ComponentRegistry.register(
    name="nginx",
    metadata={
        "dependencies": ["prerequisites"],
        "description": "Nginx web server and reverse proxy configuration",
    },
)
class NginxConfigurator(BaseComponent):
    """
    Configurator for Nginx web server and reverse proxy.
    """

    NGINX_SITES_AVAILABLE_DIR = "/etc/nginx/sites-available"
    NGINX_SITES_ENABLED_DIR = "/etc/nginx/sites-enabled"

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Nginx configurator.
        """
        super().__init__(app_settings, logger)
        self.installer = NginxInstaller(app_settings, self.logger)

    def install(self) -> bool:
        """
        Install Nginx by delegating to the NginxInstaller.
        """
        return self.installer.install()

    def uninstall(self) -> bool:
        """
        Uninstall Nginx by delegating to the NginxInstaller.
        """
        return self.installer.uninstall()

    def is_installed(self) -> bool:
        """
        Check if Nginx is installed by delegating to the NginxInstaller.
        """
        return self.installer.is_installed()

    def configure(self) -> bool:
        """
        Configure Nginx with the necessary settings.
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
        """
        try:
            proxy_conf_filename = self.app_settings.nginx.proxy_conf_name_base
            symlink_path = os.path.join(
                self.NGINX_SITES_ENABLED_DIR, proxy_conf_filename
            )
            if os.path.lexists(symlink_path):
                run_elevated_command(
                    ["rm", symlink_path],
                    self.app_settings,
                    current_logger=self.logger,
                )

            conf_path = os.path.join(
                self.NGINX_SITES_AVAILABLE_DIR, proxy_conf_filename
            )
            if os.path.exists(conf_path):
                run_elevated_command(
                    ["rm", conf_path],
                    self.app_settings,
                    current_logger=self.logger,
                )

            default_site_path = os.path.join(
                self.NGINX_SITES_AVAILABLE_DIR, "default"
            )
            if os.path.exists(default_site_path):
                default_symlink_path = os.path.join(
                    self.NGINX_SITES_ENABLED_DIR, "default"
                )
                run_elevated_command(
                    ["ln", "-sf", default_site_path, default_symlink_path],
                    self.app_settings,
                    current_logger=self.logger,
                )

            self._test_nginx_configuration()
            self._activate_nginx_service()
            return True
        except Exception as e:
            self.logger.error(f"Error unconfiguring Nginx: {str(e)}")
            return False

    def is_configured(self) -> bool:
        """
        Check if Nginx is configured as a reverse proxy.
        """
        try:
            proxy_conf_filename = self.app_settings.nginx.proxy_conf_name_base
            conf_path = os.path.join(
                self.NGINX_SITES_AVAILABLE_DIR, proxy_conf_filename
            )
            symlink_path = os.path.join(
                self.NGINX_SITES_ENABLED_DIR, proxy_conf_filename
            )

            service_active = (
                run_elevated_command(
                    ["systemctl", "is-active", "nginx.service"],
                    self.app_settings,
                    capture_output=True,
                    check=False,
                    current_logger=self.logger,
                ).returncode
                == 0
            )

            return (
                os.path.exists(conf_path)
                and os.path.islink(symlink_path)
                and service_active
            )
        except Exception as e:
            self.logger.error(f"Error checking Nginx configuration: {str(e)}")
            return False

    def _create_nginx_proxy_site_config(self) -> None:
        """
        Create the Nginx site configuration file for reverse proxying services.
        """
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

        server_name_val = self.app_settings.vm_ip_or_domain
        if server_name_val == VM_IP_OR_DOMAIN_DEFAULT:
            server_name_val = "_"

        nginx_template = self.app_settings.nginx.proxy_site_template
        format_vars = {
            "script_hash": script_hash,
            "server_name_nginx": server_name_val,
            "proxy_conf_filename_base": proxy_conf_filename,
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
        except KeyError as e_key:
            self.logger.error(
                f"Missing placeholder key '{e_key}' for Nginx proxy template."
            )
            raise

    def _manage_nginx_sites(self) -> None:
        """
        Enable the new Nginx proxy site and disable the default site.
        """
        proxy_conf_filename = self.app_settings.nginx.proxy_conf_name_base
        source_conf_path = os.path.join(
            self.NGINX_SITES_AVAILABLE_DIR, proxy_conf_filename
        )
        symlink_path = os.path.join(
            self.NGINX_SITES_ENABLED_DIR, proxy_conf_filename
        )

        if not os.path.exists(source_conf_path):
            raise FileNotFoundError(
                f"{source_conf_path} not found. Cannot enable."
            )

        run_elevated_command(
            ["ln", "-sf", source_conf_path, symlink_path],
            self.app_settings,
            current_logger=self.logger,
        )

        default_nginx_symlink = os.path.join(
            self.NGINX_SITES_ENABLED_DIR, "default"
        )
        if os.path.lexists(default_nginx_symlink):
            run_elevated_command(
                ["rm", default_nginx_symlink],
                self.app_settings,
                current_logger=self.logger,
            )

    def _test_nginx_configuration(self) -> None:
        """
        Test the Nginx configuration for syntax errors.
        """
        try:
            run_elevated_command(
                ["nginx", "-t"],
                self.app_settings,
                check=True,
                current_logger=self.logger,
            )
        except subprocess.CalledProcessError:
            self.logger.error("Nginx configuration test failed. Check logs.")
            raise

    def _activate_nginx_service(self) -> None:
        """
        Reload systemd, restart and enable the Nginx service.
        """
        systemd_reload(self.app_settings, self.logger)
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
        run_elevated_command(
            ["systemctl", "status", "nginx.service", "--no-pager", "-l"],
            self.app_settings,
            current_logger=self.logger,
        )
