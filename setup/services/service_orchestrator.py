# setup/services/service_orchestrator.py
# -*- coding: utf-8 -*-
"""
Orchestrates the setup of various map-related services.

This module imports individual service setup functions from their respective
modules (e.g., ufw, postgres, nginx) and runs them in a predefined sequence
as a group. It uses the `execute_step` utility to manage the execution
and state of each service setup step.
"""

import logging
from typing import Any, Callable, List, Optional, Tuple

from setup import config
from setup.cli_handler import cli_prompt_for_rerun
from configure.command_utils import log_map_server
from setup.services.apache import apache_modtile_setup
from setup.services.carto import carto_setup
from setup.services.certbot import certbot_setup
from setup.services.nginx import nginx_setup
from setup.services.osrm import osm_osrm_server_setup
from setup.services.pg_tileserv import pg_tileserv_setup
from setup.services.postgres import postgres_setup
from setup.services.renderd import renderd_setup
from setup.services.website import website_setup
from setup.services.ufw import ufw_setup
from setup.step_executor import execute_step

module_logger = logging.getLogger(__name__)


def services_setup_group(
    current_logger: Optional[logging.Logger] = None,
) -> bool:
    """
    Run all service setup steps in a predefined sequence.

    Each service setup is treated as a step, managed by `execute_step`.
    If any step fails, the orchestration for this group is aborted.

    Args:
        current_logger: Optional logger instance to use. If None,
                        the module's default logger is used.

    Returns:
        True if all service setup steps in the group complete successfully,
        False otherwise.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"--- {config.SYMBOLS['info']} Starting Services Setup Group ---",
        "info",
        logger_to_use,
    )
    overall_success = True

    # Define the sequence of service setup steps.
    # Each tuple: (step_tag, description, function_reference)
    service_steps_to_run: List[
        Tuple[str, str, Callable[[Optional[logging.Logger]], Any]]
    ] = [
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
        (
            "WEBSITE_SETUP",
            "Setup website",
            website_setup,
        ),
    ]

    for tag, desc, func_ref in service_steps_to_run:
        # Pass logger_to_use to execute_step, which will then pass it
        # to the individual service setup function (func_ref).
        if not execute_step(
            step_tag=tag,
            step_description=desc,
            step_function=func_ref,
            current_logger_instance=logger_to_use,
            prompt_user_for_rerun=cli_prompt_for_rerun,
        ):
            overall_success = False
            log_map_server(
                f"{config.SYMBOLS['error']} Step '{desc}' ({tag}) failed. "
                "Aborting services setup group.",
                "error",
                logger_to_use,
            )
            break  # Stop on first failure in the group.

    log_map_server(
        f"--- {config.SYMBOLS['info']} Services Setup Group Finished "
        f"(Overall Success: {overall_success}) ---",
        "info" if overall_success else "error",
        logger_to_use,
    )
    return overall_success
