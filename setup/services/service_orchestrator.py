# setup/services/service_orchestrator.py
"""
Orchestrates the setup of various map-related services.
Imports individual service setup functions and runs them as a group.
"""
import logging
from typing import Optional

from setup import config
from setup.command_utils import log_map_server
from setup.services.apache import apache_modtile_setup  # Assuming you create apache.py
from setup.services.carto import carto_setup  # Assuming you create carto.py
from setup.services.certbot import certbot_setup  # Assuming you create certbot.py
from setup.services.nginx import nginx_setup  # Assuming you create nginx.py
from setup.services.osrm import osm_osrm_server_setup  # Assuming you create osrm.py
from setup.services.pg_tileserv import pg_tileserv_setup  # Assuming you create pg_tileserv.py
from setup.services.postgres import postgres_setup
from setup.services.renderd import renderd_setup  # Assuming you create renderd.py
from setup.services.ufw import ufw_setup
from setup.ui import execute_step

module_logger = logging.getLogger(__name__)


def services_setup_group(
        current_logger: Optional[logging.Logger] = None,
) -> bool:
    """Runs all service setup steps in sequence."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"--- {config.SYMBOLS['info']} Starting Services Setup Group ---",
        "info",
        logger_to_use,
    )
    overall_success = True

    service_steps_to_run = [
        ("UFW_SETUP", "Setup UFW Firewall", ufw_setup),
        (
            "POSTGRES_SETUP",
            "Setup PostgreSQL Database & User",
            postgres_setup,
        ),
        ("PGTILESERV_SETUP", "Setup pg_tileserv", pg_tileserv_setup),
        ("CARTO_SETUP", "Setup CartoCSS Compiler & OSM Style", carto_setup),
        ("RENDERD_SETUP", "Setup Renderd for Raster Tiles", renderd_setup),
        (
            "OSM_OSRM_SERVER_SETUP",
            "Setup OSM Data & OSRM",
            osm_osrm_server_setup,
        ),
        ("APACHE_SETUP", "Setup Apache for mod_tile", apache_modtile_setup),
        ("NGINX_SETUP", "Setup Nginx Reverse Proxy", nginx_setup),
        (
            "CERTBOT_SETUP",
            "Setup Certbot for SSL (optional, requires FQDN)",
            certbot_setup,
        ),
    ]

    for tag, desc, func_ref in service_steps_to_run:
        # Pass logger_to_use to execute_step, which will then pass it to func_ref
        if not execute_step(
                tag, desc, func_ref, current_logger_instance=logger_to_use
        ):
            overall_success = False
            log_map_server(
                f"{config.SYMBOLS['error']} Step '{desc}' ({tag}) failed. Aborting services setup group.",
                "error",
                logger_to_use,
            )
            break  # Stop on first failure in the group

    log_map_server(
        f"--- {config.SYMBOLS['info']} Services Setup Group Finished (Overall Success: {overall_success}) ---",
        "info" if overall_success else "error",
        logger_to_use,
    )
    return overall_success
