# modular/components/apache/apache_installer.py
# -*- coding: utf-8 -*-
"""
Apache installer module.

This module provides a self-contained installer for Apache web server.
"""

import logging
import os
from typing import List, Optional

from common.command_utils import (
    check_package_installed,
    elevated_command_exists,
    log_map_server,
    run_elevated_command,
)
from common.debian.apt_manager import AptManager
from common.file_utils import backup_file
from common.system_utils import get_current_script_hash, systemd_reload
from installer import config
from installer.base_component import BaseComponent
from installer.config_models import (
    VM_IP_OR_DOMAIN_DEFAULT,
    AppSettings,
)
from installer.registry import InstallerRegistry


@InstallerRegistry.register(
    name="apache",
    metadata={
        "dependencies": ["prerequisites"],  # Depends on core prerequisites
        "estimated_time": 60,  # Estimated installation time in seconds
        "required_resources": {
            "memory": 256,  # Required memory in MB
            "disk": 512,  # Required disk space in MB
            "cpu": 1,  # Required CPU cores
        },
        "description": "Apache web server with mod_tile for serving map tiles",
    },
)
class ApacheInstaller(BaseComponent):
    """
    Installer for Apache web server with mod_tile for serving map tiles.

    This installer ensures that Apache and related packages are installed
    and properly configured.
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
        Initialize the Apache installer.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)
        self.apt_manager = AptManager(logger=self.logger)

    def install(self) -> bool:
        """
        Install Apache and related packages.

        Returns:
            True if the installation was successful, False otherwise.
        """
        try:
            # Log the start of the installation
            log_map_server(
                f"{config.SYMBOLS['info']} Installing Apache and related packages...",
                "info",
                self.logger,
            )

            # Get the list of packages to install
            packages = self._get_apache_packages()

            if not packages:
                log_map_server(
                    f"{config.SYMBOLS['warning']} No Apache packages specified.",
                    "warning",
                    self.logger,
                )
                return False

            # Install the packages
            self.apt_manager.install(packages, self.app_settings)

            # Verify that all packages were installed
            if not self._verify_packages_installed(packages):
                log_map_server(
                    f"{config.SYMBOLS['error']} Failed to install all required Apache packages.",
                    "error",
                    self.logger,
                )
                return False

            log_map_server(
                f"{config.SYMBOLS['success']} Apache and related packages installed successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error installing Apache: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def uninstall(self) -> bool:
        """
        Uninstall Apache and related packages.

        Returns:
            True if the uninstallation was successful, False otherwise.
        """
        try:
            # Log the start of the uninstallation
            log_map_server(
                f"{config.SYMBOLS['info']} Uninstalling Apache and related packages...",
                "info",
                self.logger,
            )

            # Get the list of packages to uninstall
            packages = self._get_apache_packages()

            if not packages:
                log_map_server(
                    f"{config.SYMBOLS['warning']} No Apache packages specified.",
                    "warning",
                    self.logger,
                )
                return False

            # Uninstall the packages
            self.apt_manager.purge(packages, self.app_settings)

            # Clean up any remaining packages
            self.apt_manager.autoremove(
                purge=True, app_settings=self.app_settings
            )

            log_map_server(
                f"{config.SYMBOLS['success']} Apache and related packages uninstalled successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error uninstalling Apache: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def is_installed(self) -> bool:
        """
        Check if Apache is installed.

        Returns:
            True if Apache is installed, False otherwise.
        """
        packages = self._get_apache_packages()

        if not packages:
            log_map_server(
                f"{config.SYMBOLS['warning']} No Apache packages specified.",
                "warning",
                self.logger,
            )
            return False

        return self._verify_packages_installed(packages)

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

    def _get_apache_packages(self) -> List[str]:
        """
        Get the list of Apache packages to install.

        Returns:
            A list of package names.
        """
        # Based on the original apache_installer.py
        return ["apache2", "libapache2-mod-tile"]

    def _verify_packages_installed(self, packages: List[str]) -> bool:
        """
        Verify that all specified packages are installed.

        Args:
            packages: A list of package names to verify.

        Returns:
            True if all packages are installed, False otherwise.
        """
        all_installed = True

        for pkg in packages:
            if check_package_installed(
                pkg,
                app_settings=self.app_settings,
                current_logger=self.logger,
            ):
                log_map_server(
                    f"{config.SYMBOLS['success']} Package '{pkg}' is installed.",
                    "debug",
                    self.logger,
                )
            else:
                log_map_server(
                    f"{config.SYMBOLS['error']} Package '{pkg}' is NOT installed.",
                    "error",
                    self.logger,
                )
                all_installed = False

        return all_installed

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
                sed_cmd_ipv6, self.app_settings, current_logger=self.logger
            )

            log_map_server(
                f"{symbols.get('success', '')} Apache ports configured to listen on port {target_listen_port}",
                "success",
                self.logger,
                self.app_settings,
            )
        else:
            log_map_server(
                f"{symbols.get('warning', '')} Failed to backup Apache ports configuration file. Skipping port configuration.",
                "warning",
                self.logger,
                self.app_settings,
            )

    def _create_mod_tile_config(self) -> None:
        """
        Create the mod_tile configuration file.

        This method creates the mod_tile configuration file in the Apache
        conf-available directory.
        """
        symbols = self.app_settings.symbols

        log_map_server(
            f"{symbols.get('step', '')} Creating mod_tile configuration...",
            "info",
            self.logger,
            self.app_settings,
        )

        # Create the mod_tile configuration file
        mod_tile_conf_content = f"""# mod_tile configuration
# Generated by OSM-OSRM Server installer
# Script hash: {get_current_script_hash(config.OSM_PROJECT_ROOT, self.app_settings, self.logger)}

LoadModule tile_module /usr/lib/apache2/modules/mod_tile.so

ModTileRenderdSocketName /var/run/renderd/renderd.sock
ModTileRequestTimeout 0
ModTileMissingRequestTimeout 30
ModTileMaxLoadOld 16
ModTileMaxLoadMissing 50
ModTileVeryOldThreshold 31536000000000

# Tile cache configuration
ModTileCacheDurationMax 604800
ModTileCacheDurationDirty 900
ModTileCacheDurationMinimum 10800
ModTileCacheDurationMediumZoom 13 86400
ModTileCacheDurationLowZoom 9 518400
ModTileCacheLastModifiedFactor 0.20
"""

        # Write the configuration file
        with open("/tmp/mod_tile.conf", "w") as f:
            f.write(mod_tile_conf_content)

        # Move the file to the Apache conf-available directory
        run_elevated_command(
            ["mv", "/tmp/mod_tile.conf", self.MOD_TILE_CONF_AVAILABLE_PATH],
            self.app_settings,
            current_logger=self.logger,
        )

        log_map_server(
            f"{symbols.get('success', '')} mod_tile configuration created",
            "success",
            self.logger,
            self.app_settings,
        )

    def _create_apache_tile_site_config(self) -> None:
        """
        Create the Apache tile site configuration file.

        This method creates the Apache tile site configuration file in the
        sites-available directory.
        """
        symbols = self.app_settings.symbols
        domain = self.app_settings.vm_ip_or_domain or VM_IP_OR_DOMAIN_DEFAULT
        listen_port = self.app_settings.apache.listen_port

        log_map_server(
            f"{symbols.get('step', '')} Creating Apache tile site configuration...",
            "info",
            self.logger,
            self.app_settings,
        )

        # Create the Apache tile site configuration file
        tile_site_conf_content = f"""# Apache tile site configuration
# Generated by OSM-OSRM Server installer
# Script hash: {get_current_script_hash(config.OSM_PROJECT_ROOT, self.app_settings, self.logger)}

<VirtualHost *:{listen_port}>
    ServerName {domain}
    ServerAdmin webmaster@localhost
    DocumentRoot /var/www/html

    # Tile server configuration
    <Directory /var/www/html>
        Options Indexes FollowSymLinks
        AllowOverride None
        Require all granted
    </Directory>

    # Tile server configuration
    LoadTileConfigFile /etc/renderd.conf
    ModTileRenderdSocketName /var/run/renderd/renderd.sock
    ModTileRequestTimeout 0
    ModTileMissingRequestTimeout 30

    # Logging
    ErrorLog ${{APACHE_LOG_DIR}}/error.log
    CustomLog ${{APACHE_LOG_DIR}}/access.log combined
</VirtualHost>
"""

        # Write the configuration file
        with open("/tmp/001-tiles.conf", "w") as f:
            f.write(tile_site_conf_content)

        # Move the file to the Apache sites-available directory
        run_elevated_command(
            [
                "mv",
                "/tmp/001-tiles.conf",
                self.APACHE_TILES_SITE_CONF_AVAILABLE_PATH,
            ],
            self.app_settings,
            current_logger=self.logger,
        )

        log_map_server(
            f"{symbols.get('success', '')} Apache tile site configuration created",
            "success",
            self.logger,
            self.app_settings,
        )

    def _manage_apache_modules_and_sites(self) -> None:
        """
        Manage Apache modules and sites.

        This method enables the required Apache modules and sites, and disables
        the default site.
        """
        symbols = self.app_settings.symbols

        log_map_server(
            f"{symbols.get('step', '')} Managing Apache modules and sites...",
            "info",
            self.logger,
            self.app_settings,
        )

        # Check if a2enmod and a2ensite commands exist
        if not elevated_command_exists(
            "a2enmod", self.app_settings, current_logger=self.logger
        ):
            log_map_server(
                f"{symbols.get('critical', '')} a2enmod command not found. Please install Apache2 first.",
                "critical",
                self.logger,
                self.app_settings,
            )
            raise FileNotFoundError("a2enmod command not found")

        if not elevated_command_exists(
            "a2ensite", self.app_settings, current_logger=self.logger
        ):
            log_map_server(
                f"{symbols.get('critical', '')} a2ensite command not found. Please install Apache2 first.",
                "critical",
                self.logger,
                self.app_settings,
            )
            raise FileNotFoundError("a2ensite command not found")

        # Enable required modules
        run_elevated_command(
            ["a2enmod", "tile"],
            self.app_settings,
            current_logger=self.logger,
        )
        log_map_server(
            f"{symbols.get('success', '')} Enabled mod_tile module",
            "success",
            self.logger,
            self.app_settings,
        )

        # Enable mod_tile configuration
        run_elevated_command(
            ["a2enconf", "mod_tile"],
            self.app_settings,
            current_logger=self.logger,
        )
        log_map_server(
            f"{symbols.get('success', '')} Enabled mod_tile configuration",
            "success",
            self.logger,
            self.app_settings,
        )

        # Disable default site
        run_elevated_command(
            ["a2dissite", "000-default"],
            self.app_settings,
            current_logger=self.logger,
        )
        log_map_server(
            f"{symbols.get('success', '')} Disabled default Apache site",
            "success",
            self.logger,
            self.app_settings,
        )

        # Enable tile site
        tile_site_name = os.path.basename(
            self.APACHE_TILES_SITE_CONF_AVAILABLE_PATH
        ).replace(".conf", "")
        run_elevated_command(
            ["a2ensite", tile_site_name],
            self.app_settings,
            current_logger=self.logger,
        )
        log_map_server(
            f"{symbols.get('success', '')} Enabled Apache tile site",
            "success",
            self.logger,
            self.app_settings,
        )

    def _activate_apache_service(self) -> None:
        """
        Activate the Apache service.

        This method reloads the Apache service to apply the configuration changes.
        """
        symbols = self.app_settings.symbols

        log_map_server(
            f"{symbols.get('step', '')} Activating Apache service...",
            "info",
            self.logger,
            self.app_settings,
        )

        # Reload systemd to apply any changes
        systemd_reload(self.app_settings, current_logger=self.logger)

        # Reload Apache to apply configuration changes
        run_elevated_command(
            ["systemctl", "reload", "apache2"],
            self.app_settings,
            current_logger=self.logger,
        )
        log_map_server(
            f"{symbols.get('success', '')} Apache service reloaded",
            "success",
            self.logger,
            self.app_settings,
        )
