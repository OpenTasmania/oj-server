"""
OSRM configurator module.

This module provides a self-contained configurator for OSRM services,
primarily setting up and activating systemd services for osrm-routed
for processed regions.
"""

import logging
from pathlib import Path
from typing import Optional

from common.command_utils import (
    run_elevated_command,
)
from common.system_utils import get_current_script_hash, systemd_reload
from installer import config as static_config
from installer.base_component import BaseComponent
from installer.components.osrm.osrm_installer import OsrmInstaller
from installer.config_models import AppSettings
from installer.registry import ComponentRegistry


@ComponentRegistry.register(
    name="osrm",
    metadata={
        "dependencies": [
            "prerequisites",
            "docker",
            "data_processing",
            "postgres",
        ],
        "description": "OSRM (Open Source Routing Machine) services configuration",
    },
)
class OsrmConfigurator(BaseComponent):
    """
    Configurator for OSRM services.

    This configurator ensures that OSRM services are properly configured,
    including setting up and activating systemd services for osrm-routed
    for processed regions.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the OSRM configurator.
        """
        super().__init__(app_settings, logger)
        self.installer = OsrmInstaller(app_settings, self.logger)

    def install(self) -> bool:
        """
        Install OSRM data by delegating to the OsrmInstaller.
        """
        return self.installer.install()

    def uninstall(self) -> bool:
        """
        Uninstall OSRM data by delegating to the OsrmInstaller.
        """
        return self.installer.uninstall()

    def is_installed(self) -> bool:
        """
        Check if OSRM data is installed by delegating to the OsrmInstaller.
        """
        return self.installer.is_installed()

    def configure(self) -> bool:
        """
        Configure OSRM services for all processed regions.
        """
        try:
            return self._configure_osrm_services()
        except Exception as e:
            self.logger.error(f"Error configuring OSRM: {str(e)}")
            return False

    def unconfigure(self) -> bool:
        """
        Unconfigure OSRM services by stopping and removing them.
        """
        try:
            processed_dir = Path(self.app_settings.osrm_data.processed_dir)
            if not processed_dir.is_dir():
                return True

            all_successful = True
            for region_dir in processed_dir.iterdir():
                if not region_dir.is_dir():
                    continue
                service_name = f"osrm-routed-{region_dir.name}.service"
                try:
                    run_elevated_command(
                        ["systemctl", "stop", service_name],
                        self.app_settings,
                        check=False,
                    )
                    run_elevated_command(
                        ["systemctl", "disable", service_name],
                        self.app_settings,
                        check=False,
                    )
                    service_file = Path(f"/etc/systemd/system/{service_name}")
                    if service_file.exists():
                        run_elevated_command(
                            ["rm", str(service_file)], self.app_settings
                        )
                except Exception as e:
                    self.logger.error(
                        f"Error unconfiguring {service_name}: {e}"
                    )
                    all_successful = False

            systemd_reload(self.app_settings, self.logger)
            return all_successful
        except Exception as e:
            self.logger.error(f"Error unconfiguring OSRM: {str(e)}")
            return False

    def is_configured(self) -> bool:
        """
        Check if OSRM services for all processed regions are configured and active.
        """
        try:
            processed_dir = Path(self.app_settings.osrm_data.processed_dir)
            if not processed_dir.is_dir():
                return False

            processed_regions = [
                d for d in processed_dir.iterdir() if d.is_dir()
            ]
            if not processed_regions:
                return False

            for region_dir in processed_regions:
                service_name = f"osrm-routed-{region_dir.name}.service"
                is_active = (
                    run_elevated_command(
                        ["systemctl", "is-active", service_name],
                        self.app_settings,
                        check=False,
                    ).returncode
                    == 0
                )
                is_enabled = (
                    run_elevated_command(
                        ["systemctl", "is-enabled", service_name],
                        self.app_settings,
                        check=False,
                    ).returncode
                    == 0
                )
                if not (is_active and is_enabled):
                    return False
            return True
        except Exception as e:
            self.logger.error(f"Error checking OSRM configuration: {str(e)}")
            return False

    def _get_next_available_port(self) -> int:
        """
        Determine the next available port for an OSRM service.
        """
        osrm_service_cfg = self.app_settings.osrm_service
        base_port = osrm_service_cfg.car_profile_default_host_port
        used_ports = set(osrm_service_cfg.region_port_map.values())
        next_port = base_port
        while next_port in used_ports:
            next_port += 1
        return next_port

    def _create_osrm_routed_service_file(self, region_name_key: str) -> None:
        """
        Create a systemd service file for a specific OSRM region.
        """
        script_hash = (
            get_current_script_hash(
                static_config.OSM_PROJECT_ROOT, self.app_settings, self.logger
            )
            or "UNKNOWN_HASH"
        )

        osrm_data_cfg = self.app_settings.osrm_data
        osrm_service_cfg = self.app_settings.osrm_service
        service_name = f"osrm-routed-{region_name_key}.service"
        service_file_path = f"/etc/systemd/system/{service_name}"
        host_osrm_data_dir = (
            Path(osrm_data_cfg.processed_dir) / region_name_key
        )

        expected_osrm_file = host_osrm_data_dir / f"{region_name_key}.osrm"
        if not expected_osrm_file.exists():
            raise FileNotFoundError(
                f"OSRM data file {expected_osrm_file} missing for service."
            )

        port = osrm_service_cfg.region_port_map.get(
            region_name_key, self._get_next_available_port()
        )
        osrm_service_cfg.region_port_map[region_name_key] = port

        format_vars = {
            "script_hash": script_hash,
            "region_name": region_name_key,
            "container_runtime_command": self.app_settings.container_runtime_command,
            "host_port_for_region": port,
            "container_osrm_port": osrm_service_cfg.container_osrm_port,
            "host_osrm_data_dir_for_region": str(host_osrm_data_dir),
            "osrm_image_tag": osrm_service_cfg.image_tag,
            "osrm_filename_in_container": f"{region_name_key}.osrm",
            "max_table_size_routed": osrm_data_cfg.max_table_size_routed,
            "extra_osrm_routed_args": osrm_service_cfg.extra_routed_args,
        }

        service_content = osrm_service_cfg.systemd_template.format(
            **format_vars
        )
        run_elevated_command(
            ["tee", service_file_path],
            self.app_settings,
            cmd_input=service_content,
        )

    def _activate_osrm_routed_service(self, region_name_key: str) -> None:
        """
        Enable, start, and check the status of a specific OSRM service.
        """
        service_name = f"osrm-routed-{region_name_key}.service"
        systemd_reload(self.app_settings, self.logger)
        run_elevated_command(
            ["systemctl", "enable", service_name], self.app_settings
        )
        run_elevated_command(
            ["systemctl", "restart", service_name], self.app_settings
        )
        run_elevated_command(
            ["systemctl", "status", service_name, "--no-pager", "-l"],
            self.app_settings,
            check=True,
        )

    def _configure_osrm_services(self) -> bool:
        """
        Iterate through processed regions and configure a service for each.
        """
        processed_dir = Path(self.app_settings.osrm_data.processed_dir)
        if not processed_dir.is_dir():
            return True

        all_successful = True
        for region_dir in processed_dir.iterdir():
            if not region_dir.is_dir():
                continue
            try:
                self._create_osrm_routed_service_file(region_dir.name)
                self._activate_osrm_routed_service(region_dir.name)
            except Exception as e:
                self.logger.error(
                    f"Failed to configure OSRM service for {region_dir.name}: {e}"
                )
                all_successful = False
        return all_successful
