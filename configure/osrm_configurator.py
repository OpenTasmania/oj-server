# configure/osrm_configurator.py
# -*- coding: utf-8 -*-
"""
Handles configuration of OSRM services, primarily setting up and activating
systemd services for osrm-routed for processed regions.
"""
import logging
from pathlib import Path
from typing import Optional

from common.command_utils import log_map_server, run_elevated_command
from common.system_utils import systemd_reload
from setup import config  # For SYMBOLS
from setup.state_manager import get_current_script_hash

module_logger = logging.getLogger(__name__)

OSRM_BASE_PROCESSED_DIR = "/opt/osrm_processed_data"  # Must match data_processor
OSRM_DOCKER_IMAGE = "osrm/osrm-backend:latest"  # Must match data_processor


def create_osrm_routed_service_file(
        region_name: str,
        current_logger: Optional[logging.Logger] = None
) -> None:
    """Creates a systemd service file for osrm-routed for a specific region."""
    logger_to_use = current_logger if current_logger else module_logger
    script_hash = get_current_script_hash(logger_instance=logger_to_use) or "UNKNOWN_HASH"

    service_name = f"osrm-routed-{region_name}.service"
    service_file_path = f"/etc/systemd/system/{service_name}"

    # Path to the .osrm file on the host, which will be mounted into Docker
    host_osrm_file_path = Path(OSRM_BASE_PROCESSED_DIR) / region_name / f"{region_name}_processing.osrm"
    # Path to the .osrm file INSIDE the Docker container for osrm-routed
    container_osrm_file_path = f"/data/{region_name}.osrm"

    log_map_server(
        f"{config.SYMBOLS['step']} Creating systemd service file for {service_name} at {service_file_path}...", "info",
        logger_to_use)

    # Check if the actual .osrm data file exists on host
    if not host_osrm_file_path.exists():
        log_map_server(
            f"{config.SYMBOLS['error']} OSRM data file {host_osrm_file_path} not found. Cannot create service for {region_name}.",
            "error", logger_to_use)
        raise FileNotFoundError(f"OSRM data file {host_osrm_file_path} missing for service {service_name}")

    # Define port mapping (example, could be dynamic or configured)
    # This needs a strategy if multiple regions run simultaneously on same host.
    # For now, let's use a base port and increment or have a config map.
    # Simple approach: each region gets a different port if this function is called per region.
    # This is a placeholder; a robust port management strategy is needed for multiple regions.
    host_port = 5000  # Default OSRM port. For multiple regions, this must be unique.
    # Example: host_port = 5000 + hash(region_name) % 100 # or some other scheme

    service_content = f"""[Unit]
Description=OSRM Routed service for {region_name}
After=docker.service network-online.target
Wants=docker.service

[Service]
Restart=always
RestartSec=5
ExecStartPre=-/usr/bin/docker stop {service_name}
ExecStartPre=-/usr/bin/docker rm {service_name}
ExecStart=/usr/bin/docker run --rm --name {service_name} \\
    -p 127.0.0.1:{host_port}:5000 \\
    -v "{host_osrm_file_path.parent}":"/data":ro \\
    {OSRM_DOCKER_IMAGE} osrm-routed "{container_osrm_file_path}" --max-table-size 8000

ExecStop=/usr/bin/docker stop {service_name}

[Install]
WantedBy=multi-user.target
# File created by script V{script_hash} for region {region_name}
"""
    # Note on port: If multiple OSRM instances are to run, each needs a unique host port.
    # The -p 127.0.0.1:{host_port}:5000 binds only to localhost on the host.
    # Nginx would then proxy_pass to localhost:<host_port_for_region>.

    try:
        run_elevated_command(["tee", service_file_path], cmd_input=service_content, current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} Created/Updated {service_file_path}", "success", logger_to_use)
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['error']} Failed to write {service_file_path}: {e}", "error", logger_to_use)
        raise


def activate_osrm_routed_service(
        region_name: str,
        current_logger: Optional[logging.Logger] = None
) -> None:
    """Reloads systemd, enables and restarts the osrm-routed service for a region."""
    logger_to_use = current_logger if current_logger else module_logger
    service_name = f"osrm-routed-{region_name}.service"
    log_map_server(f"{config.SYMBOLS['step']} Activating {service_name}...", "info", logger_to_use)

    systemd_reload(current_logger=logger_to_use)  # Reload to pick up new/changed service file
    run_elevated_command(["systemctl", "enable", service_name], current_logger=logger_to_use)
    run_elevated_command(["systemctl", "restart", service_name], current_logger=logger_to_use)

    log_map_server(f"{config.SYMBOLS['info']} {service_name} status:", "info", logger_to_use)
    run_elevated_command(["systemctl", "status", service_name, "--no-pager", "-l"], current_logger=logger_to_use)
    log_map_server(f"{config.SYMBOLS['success']} {service_name} activated.", "success", logger_to_use)