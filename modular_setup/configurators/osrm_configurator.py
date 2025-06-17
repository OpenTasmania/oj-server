"""
OSRM configurator module.

This module provides a self-contained configurator for OSRM services,
primarily setting up and activating systemd services for osrm-routed
for processed regions.
"""

import logging
from os import cpu_count, environ
from pathlib import Path
from subprocess import CalledProcessError
from typing import Optional

from common.command_utils import (
    log_map_server,
    run_command,
    run_elevated_command,
)
from common.system_utils import get_current_script_hash, systemd_reload
from modular_setup.base_configurator import BaseConfigurator
from modular_setup.registry import ConfiguratorRegistry
from setup import config as static_config
from setup.config_models import AppSettings


@ConfiguratorRegistry.register(
    name="osrm",
    metadata={
        "dependencies": ["postgres"],  # OSRM depends on PostgreSQL
        "description": "OSRM (Open Source Routing Machine) services configuration",
    },
)
class OsrmConfigurator(BaseConfigurator):
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

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)

    def configure(self) -> bool:
        """
        Configure OSRM services.

        This method configures the OSRM services based on the specified application
        settings and logged information. It handles configuration for all processed
        regions listed in the OSRM data directory, logging progress, warnings, and
        errors encountered during the process.

        Returns:
            True if the configuration was successful, False otherwise.
        """
        try:
            return self._configure_osrm_services()
        except Exception as e:
            self.logger.error(f"Error configuring OSRM: {str(e)}")
            return False

    def unconfigure(self) -> bool:
        """
        Unconfigure OSRM services.

        This method removes the OSRM services by disabling and stopping
        the systemd services for all processed regions.

        Returns:
            True if the unconfiguration was successful, False otherwise.
        """
        try:
            symbols = self.app_settings.symbols
            processed_dir = Path(self.app_settings.osrm_data.processed_dir)

            if not processed_dir.is_dir():
                log_map_server(
                    f"{symbols.get('warning', '')} Processed OSRM data directory not found at {processed_dir}. Nothing to unconfigure.",
                    "warning",
                    self.logger,
                    self.app_settings,
                )
                return True

            processed_regions = [
                d.name for d in processed_dir.iterdir() if d.is_dir()
            ]

            if not processed_regions:
                log_map_server(
                    f"{symbols.get('warning', '')} No processed OSRM regions found in {processed_dir}. No services to remove.",
                    "warning",
                    self.logger,
                    self.app_settings,
                )
                return True

            all_successful = True
            for region_name_key in processed_regions:
                service_name = f"osrm-routed-{region_name_key}.service"
                service_file_path = f"/etc/systemd/system/{service_name}"

                try:
                    log_map_server(
                        f"{symbols.get('step', '')} Stopping and disabling {service_name}...",
                        "info",
                        self.logger,
                        self.app_settings,
                    )

                    # Stop and disable the service
                    run_elevated_command(
                        ["systemctl", "stop", service_name],
                        self.app_settings,
                        current_logger=self.logger,
                        check=False,
                    )
                    run_elevated_command(
                        ["systemctl", "disable", service_name],
                        self.app_settings,
                        current_logger=self.logger,
                        check=False,
                    )

                    # Remove the service file
                    if Path(service_file_path).exists():
                        run_elevated_command(
                            ["rm", service_file_path],
                            self.app_settings,
                            current_logger=self.logger,
                        )

                    log_map_server(
                        f"{symbols.get('success', '')} {service_name} stopped, disabled, and removed.",
                        "success",
                        self.logger,
                        self.app_settings,
                    )
                except Exception as e:
                    log_map_server(
                        f"{symbols.get('error', '')} Error unconfiguring {service_name}: {str(e)}",
                        "error",
                        self.logger,
                        self.app_settings,
                    )
                    all_successful = False

            # Reload systemd to apply changes
            systemd_reload(self.app_settings, current_logger=self.logger)

            if all_successful:
                log_map_server(
                    f"{symbols.get('success', '')} All OSRM services unconfigured successfully.",
                    "success",
                    self.logger,
                    self.app_settings,
                )
            else:
                log_map_server(
                    f"{symbols.get('error', '')} Some OSRM services failed to unconfigure. Please check the logs.",
                    "error",
                    self.logger,
                    self.app_settings,
                )

            return all_successful
        except Exception as e:
            self.logger.error(f"Error unconfiguring OSRM: {str(e)}")
            return False

    def is_configured(self) -> bool:
        """
        Check if OSRM services are configured.

        This method checks if the OSRM services are properly configured
        by verifying that the systemd services for all processed regions
        are enabled and active.

        Returns:
            True if OSRM services are configured, False otherwise.
        """
        try:
            processed_dir = Path(self.app_settings.osrm_data.processed_dir)

            if not processed_dir.is_dir():
                return False

            processed_regions = [
                d.name for d in processed_dir.iterdir() if d.is_dir()
            ]

            if not processed_regions:
                return False

            for region_name_key in processed_regions:
                service_name = f"osrm-routed-{region_name_key}.service"

                # Check if the service is enabled
                result = run_elevated_command(
                    ["systemctl", "is-enabled", service_name],
                    self.app_settings,
                    capture_output=True,
                    check=False,
                    current_logger=self.logger,
                )
                if result.returncode != 0:
                    return False

                # Check if the service is active
                result = run_elevated_command(
                    ["systemctl", "is-active", service_name],
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
                f"Error checking if OSRM is configured: {str(e)}"
            )
            return False

    def _get_next_available_port(self) -> int:
        """
        Determine the next available port not currently in use within the region port map.

        Returns:
            The next available port number starting from the default host port.
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
        Create or update a systemd service file for an OSRM routed service for a particular region.

        Args:
            region_name_key: Unique key for the region, such as "Australia_Tasmania_Hobart".

        Raises:
            FileNotFoundError: If the required OSRM data file for the specified region is not found.
            KeyError: If a required placeholder key is missing in the systemd service template.
            Exception: For any other errors occurring while generating or writing the service file.
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

        osrm_data_cfg = self.app_settings.osrm_data
        osrm_service_cfg = self.app_settings.osrm_service

        service_name = f"osrm-routed-{region_name_key}.service"
        service_file_path = f"/etc/systemd/system/{service_name}"

        host_osrm_data_dir_for_this_region = (
            Path(osrm_data_cfg.processed_dir) / region_name_key
        )
        osrm_filename_stem_in_container = region_name_key

        log_map_server(
            f"{symbols.get('step', '')} Creating systemd service file for {service_name} at {service_file_path} from template...",
            "info",
            self.logger,
            self.app_settings,
        )

        expected_osrm_file_on_host = (
            host_osrm_data_dir_for_this_region
            / f"{osrm_filename_stem_in_container}.osrm"
        )
        if not expected_osrm_file_on_host.exists():
            log_map_server(
                f"{symbols.get('error', '')} OSRM data file {expected_osrm_file_on_host} not found. Cannot create service for {region_name_key}.",
                "error",
                self.logger,
                self.app_settings,
            )
            raise FileNotFoundError(
                f"OSRM data file {expected_osrm_file_on_host} missing for service {service_name}"
            )

        if region_name_key in osrm_service_cfg.region_port_map:
            host_port_for_this_region = osrm_service_cfg.region_port_map[
                region_name_key
            ]
            log_map_server(
                f"{symbols.get('info', '')} Using configured port {host_port_for_this_region} for region {region_name_key}",
                "info",
                self.logger,
                self.app_settings,
            )
        else:
            host_port_for_this_region = self._get_next_available_port()
            log_map_server(
                f"{symbols.get('info', '')} Auto-assigned port {host_port_for_this_region} for region {region_name_key}",
                "info",
                self.logger,
                self.app_settings,
            )

        osrm_service_cfg.region_port_map[region_name_key] = (
            host_port_for_this_region
        )

        systemd_template_str = osrm_service_cfg.systemd_template
        format_vars = {
            "script_hash": script_hash,
            "region_name": region_name_key,
            "container_runtime_command": self.app_settings.container_runtime_command,
            "host_port_for_region": host_port_for_this_region,
            "container_osrm_port": osrm_service_cfg.container_osrm_port,
            "host_osrm_data_dir_for_region": str(
                host_osrm_data_dir_for_this_region
            ),
            "osrm_image_tag": osrm_service_cfg.image_tag,
            "osrm_filename_in_container": f"{osrm_filename_stem_in_container}.osrm",
            "max_table_size_routed": osrm_data_cfg.max_table_size_routed,
            "extra_osrm_routed_args": osrm_service_cfg.extra_routed_args,
        }

        try:
            service_content_final = systemd_template_str.format(**format_vars)
            run_elevated_command(
                ["tee", service_file_path],
                self.app_settings,
                cmd_input=service_content_final,
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
                f"{symbols.get('error', '')} Missing placeholder key '{e_key}' for OSRM systemd template. Check config.yaml/models.",
                "error",
                self.logger,
                self.app_settings,
            )
            raise
        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '')} Failed to write {service_file_path}: {e}",
                "error",
                self.logger,
                self.app_settings,
                exc_info=True,
            )
            raise

    def _import_pbf_to_postgis_with_osm2pgsql(
        self, pbf_full_path: str
    ) -> bool:
        """
        Import a PBF (Protocolbuffer Binary Format) file into a PostGIS database using the osm2pgsql tool.

        Args:
            pbf_full_path: Full path to the PBF file to be imported.

        Returns:
            True if the import is successful, False otherwise.

        Raises:
            CalledProcessError: Raised when the osm2pgsql command returns a non-zero exit status.
            Exception: Raised for any other unexpected errors encountered during the import process.
        """
        symbols = self.app_settings.symbols
        postgis_cfg = self.app_settings.pg
        osm_data_cfg = self.app_settings.osrm_data

        log_map_server(
            f"{symbols.get('step', '')} Starting osm2pgsql import for {Path(pbf_full_path).name}...",
            "info",
            self.logger,
            self.app_settings,
        )

        if not Path(pbf_full_path).is_file():
            log_map_server(
                f"{symbols.get('error', '')} PBF file not found for osm2pgsql import: {pbf_full_path}",
                "error",
                self.logger,
                self.app_settings,
            )
            return False

        osm_carto_dir = (
            static_config.OSM_PROJECT_ROOT
            / "external"
            / "openstreetmap-carto"
        )
        # TODO:
        # Decide if we want openstreetmap-carto.lua or openstreetmap-carto-flex.lua or something else
        osm_carto_lua_script = osm_carto_dir / "openstreetmap-carto.lua"

        if not osm_carto_lua_script.is_file():
            log_map_server(
                f"{symbols.get('error', '')} OSM-Carto LUA script not found at {osm_carto_lua_script}. Cannot proceed.",
                "error",
                self.logger,
                self.app_settings,
            )
            return False

        env_vars = environ.copy()
        env_vars["PGPASSWORD"] = postgis_cfg.password

        osm2pgsql_cmd = [
            "osm2pgsql",
            "--create",
            "--database",
            str(postgis_cfg.database),
            "--user",
            str(postgis_cfg.user),
            "--host",
            str(postgis_cfg.host),
            "--port",
            str(postgis_cfg.port),
            "--slim",
            "--hstore",
            "--multi-geometry",
            f"--tag-transform-script={osm_carto_lua_script}",
            f"--style={osm_carto_lua_script}",
            "--output=flex",
            "-C",
            str(osm_data_cfg.osm2pgsql_cache_mb),
            f"--number-processes={str(cpu_count() or 1)}",
            pbf_full_path,
        ]

        log_map_server(
            f"osm2pgsql command: {' '.join(osm2pgsql_cmd)}",
            "info",
            self.logger,
            self.app_settings,
        )

        try:
            run_command(
                osm2pgsql_cmd,
                self.app_settings,
                current_logger=self.logger,
                check=True,
                env=env_vars,
            )
            log_map_server(
                f"{symbols.get('success', '')} osm2pgsql import for {Path(pbf_full_path).name} completed successfully.",
                "success",
                self.logger,
                self.app_settings,
            )
            return True
        except CalledProcessError as e:
            log_map_server(
                f"{symbols.get('critical', '')} osm2pgsql import FAILED with exit code {e.returncode}. Output: {e.stderr or e.stdout}",
                "critical",
                self.logger,
                self.app_settings,
            )
            return False
        except Exception as e:
            log_map_server(
                f"{symbols.get('critical', '')} Unexpected error during osm2pgsql import: {e}",
                "critical",
                self.logger,
                self.app_settings,
                exc_info=True,
            )
            return False

    def _activate_osrm_routed_service(self, region_name_key: str) -> None:
        """
        Activate and ensure the proper startup and status of an OSRM routed service for a specific region.

        Args:
            region_name_key: The key corresponding to the region-specific service name.

        Raises:
            CalledProcessError: Raised if the systemctl command indicates the service has failed to start.
            Exception: Raised for unexpected errors during service status verification.
        """
        symbols = self.app_settings.symbols
        service_name = f"osrm-routed-{region_name_key}.service"
        log_map_server(
            f"{symbols.get('step', '')} Activating {service_name}...",
            "info",
            self.logger,
            self.app_settings,
        )

        systemd_reload(self.app_settings, current_logger=self.logger)
        run_elevated_command(
            ["systemctl", "enable", service_name],
            self.app_settings,
            current_logger=self.logger,
        )
        run_elevated_command(
            ["systemctl", "restart", service_name],
            self.app_settings,
            current_logger=self.logger,
        )

        try:
            log_map_server(
                f"{symbols.get('info', '')} Checking status of {service_name}...",
                "info",
                self.logger,
                self.app_settings,
            )
            run_elevated_command(
                ["systemctl", "status", service_name, "--no-pager", "-l"],
                self.app_settings,
                current_logger=self.logger,
                check=True,
            )
            log_map_server(
                f"{symbols.get('success', '')} {service_name} is active.",
                "success",
                self.logger,
                self.app_settings,
            )
        except CalledProcessError:
            log_map_server(
                f"{symbols.get('critical', '')} {service_name} FAILED to start. Aborting OSRM configuration.",
                "critical",
                self.logger,
                self.app_settings,
            )
            raise
        except Exception as e:
            log_map_server(
                f"{symbols.get('critical', '')} Unexpected error while checking {service_name} status: {e}",
                "critical",
                self.logger,
                self.app_settings,
                exc_info=True,
            )
            raise

        log_map_server(
            f"{symbols.get('success', '')} {service_name} activation process completed.",
            "success",
            self.logger,
            self.app_settings,
        )

    def _configure_osrm_services(self) -> bool:
        """
        Configure the OSRM services based on the specified application settings.

        Returns:
            True if all OSRM services are successfully configured, otherwise False.
        """
        symbols = self.app_settings.symbols
        processed_dir = Path(self.app_settings.osrm_data.processed_dir)

        log_map_server(
            f"{symbols.get('step', '')} Starting OSRM service configuration...",
            "info",
            self.logger,
            self.app_settings,
        )

        if not processed_dir.is_dir():
            log_map_server(
                f"{symbols.get('warning', '')} Processed OSRM data directory not found at {processed_dir}. Nothing to configure.",
                "warning",
                self.logger,
                self.app_settings,
            )
            return True

        processed_regions = [
            d.name for d in processed_dir.iterdir() if d.is_dir()
        ]

        if not processed_regions:
            log_map_server(
                f"{symbols.get('warning', '')} No processed OSRM regions found in {processed_dir}. No services to create.",
                "warning",
                self.logger,
                self.app_settings,
            )
            return True

        all_successful = True
        for region_name_key in processed_regions:
            try:
                log_map_server(
                    f"--- Configuring OSRM service for region: {region_name_key} ---",
                    "info",
                    self.logger,
                    self.app_settings,
                )
                self._create_osrm_routed_service_file(region_name_key)
                self._activate_osrm_routed_service(region_name_key)
            except FileNotFoundError as e:
                log_map_server(
                    f"{symbols.get('error', '')} Skipping configuration for {region_name_key}: {e}",
                    "error",
                    self.logger,
                    self.app_settings,
                )
                all_successful = False
                continue
            except Exception as e:
                log_map_server(
                    f"{symbols.get('critical', '')} Unexpected error configuring {region_name_key}: {e}",
                    "critical",
                    self.logger,
                    self.app_settings,
                    exc_info=True,
                )
                all_successful = False

        if all_successful:
            log_map_server(
                f"{symbols.get('success', '')} All OSRM services configured successfully.",
                "success",
                self.logger,
                self.app_settings,
            )
        else:
            log_map_server(
                f"{symbols.get('error', '')} Some OSRM services failed to configure. Please check the logs.",
                "error",
                self.logger,
                self.app_settings,
            )

        return all_successful
