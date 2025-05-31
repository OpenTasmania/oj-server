# setup/main_installer.py
# -*- coding: utf-8 -*-
"""
Main entry point and orchestrator for the Map Server Setup script.
Handles argument parsing, logging setup, and calls a sequence of setup steps
from various modules within the 'setup' package following a refactored
setup and configure phase approach.
"""

import argparse
import logging
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

# --- Common module imports ---
from common.command_utils import log_map_server
from common.pgpass_utils import setup_pgpass
from common.system_utils import systemd_reload

# --- Setup phase module imports ---
from setup import config
from setup.cli_handler import cli_prompt_for_rerun, view_configuration
from setup.state_manager import get_current_script_hash

from actions.ufw_setup_actions import enable_ufw_service
from installer.postgres_installer import ensure_postgres_packages_are_installed
from installer.carto_installer import (
    install_carto_cli, setup_osm_carto_repository,
    prepare_carto_directory_for_processing, fetch_carto_external_data
)
from installer.renderd_installer import (
    ensure_renderd_packages_installed, create_renderd_directories,
    create_renderd_systemd_service_file
)
from installer.nginx_installer import ensure_nginx_package_installed
from installer.pg_tileserv_installer import (
    download_and_install_pg_tileserv_binary, create_pg_tileserv_system_user,
    setup_pg_tileserv_binary_permissions, create_pg_tileserv_systemd_service_file
)
from installer.osrm_installer import (
    ensure_osrm_dependencies, setup_osrm_data_directories,
    download_base_pbf, prepare_region_boundaries
)
from installer.apache_installer import ensure_apache_packages_installed
from installer.certbot_installer import install_certbot_packages
from actions.website_content_deployer import deploy_test_website_content

# --- Configure phase module imports ---
from configure.ufw_configurator import apply_ufw_rules
from configure.postgres_configurator import (
    create_postgres_user_and_db, enable_postgres_extensions,
    set_postgres_permissions, customize_postgresql_conf,
    customize_pg_hba_conf, restart_and_enable_postgres_service
)
from configure.carto_configurator import (
    compile_osm_carto_stylesheet, deploy_mapnik_stylesheet,
    finalize_carto_directory_processing, update_font_cache
)
from configure.renderd_configurator import (
    create_renderd_conf_file, activate_renderd_service
)
from configure.nginx_configurator import (
    create_nginx_proxy_site_config, manage_nginx_sites,
    test_nginx_configuration, activate_nginx_service
)
from configure.pg_tileserv_configurator import (
    create_pg_tileserv_config_file, activate_pg_tileserv_service
)
from configure.osrm_configurator import (
    create_osrm_routed_service_file, activate_osrm_routed_service
)
from configure.apache_configurator import (
    configure_apache_ports, create_mod_tile_config, create_apache_tile_site_config,
    manage_apache_modules_and_sites, activate_apache_service
)
from configure.certbot_configurator import run_certbot_nginx

# --- Data processing, state, execution tools ---
from setup.gtfs_environment_setup import setup_gtfs_logging_and_env_vars
from dataproc.gtfs_processor_runner import run_gtfs_etl_pipeline_and_verify
from configure.gtfs_automation_configurator import configure_gtfs_update_cronjob
from dataproc.raster_processor import raster_tile_prerender
from dataproc.osrm_data_processor import (  # OSRM data processing steps
    extract_regional_pbfs_with_osmium,
    build_osrm_graphs_for_region
)

from setup.state_manager import (
    clear_state_file, initialize_state_system, view_completed_steps,
)
from setup.step_executor import execute_step

# Core setup (prerequisites)
from setup.core_setup import (
    boot_verbosity, core_conflict_removal, core_conflict_removal_group,
    core_install, docker_install, node_js_lts_install, prereqs_install_group,
)

logger = logging.getLogger(__name__)

INSTALLATION_GROUPS_ORDER: List[Dict[str, Any]] = [
    {"name": "Core Conflict Removal", "steps": ["CORE_CONFLICTS"]},
    {"name": "Prerequisites", "steps": ["BOOT_VERBOSITY", "CORE_INSTALL", "DOCKER_INSTALL", "NODEJS_INSTALL"]},
    {"name": "Firewall Service (UFW)", "steps": ["CONFIG_UFW_RULES", "SETUP_UFW_ENABLE_SERVICE"]},
    {"name": "Database Service (PostgreSQL)", "steps": [
        "SETUP_POSTGRES_PKG_CHECK", "CONFIG_POSTGRES_USER_DB", "CONFIG_POSTGRES_EXTENSIONS",
        "CONFIG_POSTGRES_PERMISSIONS", "CONFIG_POSTGRESQL_CONF", "CONFIG_PG_HBA_CONF",
        "SERVICE_POSTGRES_RESTART_ENABLE"
    ]},
    {"name": "pg_tileserv Service", "steps": [
        "SETUP_PGTS_DOWNLOAD_BINARY", "SETUP_PGTS_CREATE_USER", "SETUP_PGTS_BINARY_PERMS",
        "SETUP_PGTS_SYSTEMD_FILE", "CONFIG_PGTS_CONFIG_FILE", "SERVICE_PGTS_ACTIVATE"
    ]},
    {"name": "Carto Service", "steps": [
        "SETUP_CARTO_CLI", "SETUP_CARTO_REPO", "SETUP_CARTO_PREPARE_DIR", "SETUP_CARTO_FETCH_DATA",
        "CONFIG_CARTO_COMPILE", "CONFIG_CARTO_DEPLOY_XML", "CONFIG_CARTO_FINALIZE_DIR", "CONFIG_SYSTEM_FONT_CACHE"
    ]},
    {"name": "Renderd Service", "steps": [
        "SETUP_RENDERD_PKG_CHECK", "SETUP_RENDERD_DIRS", "SETUP_RENDERD_SYSTEMD_FILE",
        "CONFIG_RENDERD_CONF_FILE", "SERVICE_RENDERD_ACTIVATE"
    ]},
    {"name": "OSRM Service & Data Processing", "steps": [
        "SETUP_OSRM_DEPS", "SETUP_OSRM_DIRS", "SETUP_OSRM_DOWNLOAD_PBF", "SETUP_OSRM_REGION_BOUNDARIES",
        "DATAPROC_OSMIUM_EXTRACT_REGIONS", "DATAPROC_OSRM_BUILD_GRAPHS_ALL_REGIONS",
        "SETUP_OSRM_SYSTEMD_SERVICES_ALL_REGIONS", "CONFIG_OSRM_ACTIVATE_SERVICES_ALL_REGIONS"
    ]},
    {"name": "Apache Service", "steps": [
        "SETUP_APACHE_PKG_CHECK", "CONFIG_APACHE_PORTS", "CONFIG_APACHE_MOD_TILE_CONF",
        "CONFIG_APACHE_TILE_SITE_CONF", "CONFIG_APACHE_MODULES_SITES", "SERVICE_APACHE_ACTIVATE"
    ]},
    {"name": "Nginx Service", "steps": [
        "SETUP_NGINX_PKG_CHECK", "CONFIG_NGINX_PROXY_SITE", "CONFIG_NGINX_MANAGE_SITES",
        "CONFIG_NGINX_TEST_CONFIG", "SERVICE_NGINX_ACTIVATE"
    ]},
    {"name": "Certbot Service", "steps": ["SETUP_CERTBOT_PACKAGES", "CONFIG_CERTBOT_RUN"]},
    {"name": "Application Content", "steps": ["WEBSITE_CONTENT_DEPLOY"]},
    {"name": "GTFS Data Pipeline", "steps": ["SETUP_GTFS_ENV", "DATAPROC_GTFS_ETL", "CONFIG_GTFS_CRON"]},
    {"name": "Raster Tile Pre-rendering", "steps": ["RASTER_PREP"]},
    {"name": "Systemd Reload", "steps": ["SYSTEMD_RELOAD_TASK"]},
]

task_execution_details_lookup: Dict[str, Tuple[str, int]] = {}
for group_idx, group_info in enumerate(INSTALLATION_GROUPS_ORDER):
    group_name = group_info["name"]
    for step_idx, task_tag in enumerate(group_info["steps"]):
        task_execution_details_lookup[task_tag] = (group_name, step_idx + 1)

task_execution_details_lookup["UFW_FULL_SETUP"] = ("Firewall Service (UFW)", 0)
task_execution_details_lookup["POSTGRES_FULL_SETUP"] = ("Database Service (PostgreSQL)", 0)
task_execution_details_lookup["CARTO_FULL_SETUP"] = ("Carto Service", 0)
task_execution_details_lookup["RENDERD_FULL_SETUP"] = ("Renderd Service", 0)
task_execution_details_lookup["NGINX_FULL_SETUP"] = ("Nginx Service", 0)
task_execution_details_lookup["PGTILESERV_FULL_SETUP"] = ("pg_tileserv Service", 0)
task_execution_details_lookup["OSRM_FULL_SETUP"] = ("OSRM Service & Data Processing", 0)
task_execution_details_lookup["APACHE_FULL_SETUP"] = ("Apache Service", 0)
task_execution_details_lookup["CERTBOT_FULL_SETUP"] = ("Certbot Service", 0)
task_execution_details_lookup["GTFS_FULL_SETUP"] = ("GTFS Data Pipeline", 0)

group_order_lookup: Dict[str, int] = {
    group_info["name"]: index
    for index, group_info in enumerate(INSTALLATION_GROUPS_ORDER)
}


def get_dynamic_help(base_help: str, task_tag: str) -> str:
    details = task_execution_details_lookup.get(task_tag)
    if details and details[1] > 0:
        return f"{base_help} (Part of: '{details[0]}', Sub-step: {details[1]})"
    elif details and details[1] == 0:
        return f"{base_help} (Orchestrates: '{details[0]}')"
    return base_help


def setup_main_logging() -> None:
    level_str = os.environ.get("LOGLEVEL", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)
    if not isinstance(level, int):
        print(f"Warning: Invalid LOGLEVEL string '{level_str}'. Defaulting to INFO.", file=sys.stderr)
        level = logging.INFO
    log_prefix_for_formatter = config.LOG_PREFIX
    log_formatter = logging.Formatter(
        f"{log_prefix_for_formatter} %(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root_logger_instance = logging.getLogger()
    for handler in root_logger_instance.handlers[:]: root_logger_instance.removeHandler(handler)
    for handler in logger.handlers[:]: logger.removeHandler(handler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)
    logger.setLevel(level)
    logger.propagate = False


# --- Orchestrator sequences for REFACTORED services ---
def ufw_full_setup_sequence(current_logger: Optional[logging.Logger] = None) -> None:
    logger_to_use = current_logger if current_logger else logger
    log_map_server(f"--- {config.SYMBOLS['step']} Starting UFW Full Setup & Config Sequence ---", "info", logger_to_use)
    if not execute_step("CONFIG_UFW_RULES", "Configure UFW Rules", apply_ufw_rules, logger_to_use,
                        cli_prompt_for_rerun):
        raise RuntimeError("UFW rule configuration failed.")
    if not execute_step("SETUP_UFW_ENABLE_SERVICE", "Enable UFW Service", enable_ufw_service, logger_to_use,
                        cli_prompt_for_rerun):
        raise RuntimeError("UFW service enabling failed.")
    log_map_server(f"--- {config.SYMBOLS['success']} UFW Full Setup & Config Sequence Completed ---", "success",
                   logger_to_use)


def postgres_full_setup_sequence(current_logger: Optional[logging.Logger] = None) -> None:
    logger_to_use = current_logger if current_logger else logger
    log_map_server(f"--- {config.SYMBOLS['step']} Starting PostgreSQL Full Setup & Config Sequence ---", "info",
                   logger_to_use)
    pg_steps_to_execute = [
        ("SETUP_POSTGRES_PKG_CHECK", "Check PostgreSQL Package Installation", ensure_postgres_packages_are_installed),
        ("CONFIG_POSTGRES_USER_DB", "Create PostgreSQL User and Database", create_postgres_user_and_db),
        ("CONFIG_POSTGRES_EXTENSIONS", "Enable PostgreSQL Extensions", enable_postgres_extensions),
        ("CONFIG_POSTGRES_PERMISSIONS", "Set PostgreSQL Database Permissions", set_postgres_permissions),
        ("CONFIG_POSTGRESQL_CONF", "Customize postgresql.conf", customize_postgresql_conf),
        ("CONFIG_PG_HBA_CONF", "Customize pg_hba.conf", customize_pg_hba_conf),
        ("SERVICE_POSTGRES_RESTART_ENABLE", "Restart & Enable PostgreSQL Service", restart_and_enable_postgres_service),
    ]
    for tag, description, func_ref in pg_steps_to_execute:
        if not execute_step(tag, description, func_ref, logger_to_use, cli_prompt_for_rerun):
            raise RuntimeError(f"PostgreSQL setup step '{description}' ({tag}) failed.")
    log_map_server(f"--- {config.SYMBOLS['success']} PostgreSQL Full Setup & Config Sequence Completed ---", "success",
                   logger_to_use)


def carto_full_setup_sequence(current_logger: Optional[logging.Logger] = None) -> None:
    logger_to_use = current_logger if current_logger else logger
    log_map_server(f"--- {config.SYMBOLS['step']} Starting Carto Full Setup & Config Sequence ---", "info",
                   logger_to_use)
    compiled_xml_path_holder = {"path": None}
    carto_steps = [
        ("SETUP_CARTO_CLI", "Install Carto CSS Compiler", install_carto_cli),
        ("SETUP_CARTO_REPO", "Setup OSM-Carto Repository", setup_osm_carto_repository),
        ("SETUP_CARTO_PREPARE_DIR", "Prepare Carto Directory", prepare_carto_directory_for_processing),
        ("SETUP_CARTO_FETCH_DATA", "Fetch External Data for Carto", fetch_carto_external_data),
        ("CONFIG_CARTO_COMPILE", "Compile OSM Carto Stylesheet",
         lambda cl: compiled_xml_path_holder.update({"path": compile_osm_carto_stylesheet(cl)})),
        ("CONFIG_CARTO_DEPLOY_XML", "Deploy Mapnik Stylesheet",
         lambda cl: deploy_mapnik_stylesheet(compiled_xml_path_holder["path"], cl) if compiled_xml_path_holder[
             "path"] else (_ for _ in ()).throw(RuntimeError("Compiled XML path not set"))),
        ("CONFIG_CARTO_FINALIZE_DIR", "Finalize Carto Directory", finalize_carto_directory_processing),
        ("CONFIG_SYSTEM_FONT_CACHE", "Update System Font Cache", update_font_cache),
    ]
    try:
        for tag, description, func_ref in carto_steps:
            if not execute_step(tag, description, func_ref, logger_to_use, cli_prompt_for_rerun):
                raise RuntimeError(f"Carto setup step '{description}' ({tag}) failed.")
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['error']} Error in Carto sequence: {e}. Attempting to finalize directory.",
                       "error", logger_to_use)
        try:
            finalize_carto_directory_processing(logger_to_use)
        except Exception as e_finalize:
            log_map_server(
                f"{config.SYMBOLS['error']} Error during Carto directory finalization after failure: {e_finalize}",
                "error", logger_to_use)
        raise
    log_map_server(f"--- {config.SYMBOLS['success']} Carto Full Setup & Config Sequence Completed ---", "success",
                   logger_to_use)


def renderd_full_setup_sequence(current_logger: Optional[logging.Logger] = None) -> None:
    logger_to_use = current_logger if current_logger else logger
    log_map_server(f"--- {config.SYMBOLS['step']} Starting Renderd Full Setup & Config Sequence ---", "info",
                   logger_to_use)
    setup_steps = [
        ("SETUP_RENDERD_PKG_CHECK", "Check Renderd Package Installation", ensure_renderd_packages_installed),
        ("SETUP_RENDERD_DIRS", "Create Renderd Directories", create_renderd_directories),
        ("SETUP_RENDERD_SYSTEMD_FILE", "Create Renderd Systemd Service File", create_renderd_systemd_service_file),
    ]
    config_steps = [
        ("CONFIG_RENDERD_CONF_FILE", "Create renderd.conf File", create_renderd_conf_file),
        ("SERVICE_RENDERD_ACTIVATE", "Activate Renderd Service", activate_renderd_service),
    ]
    for tag, description, func_ref in setup_steps:
        if not execute_step(tag, description, func_ref, logger_to_use, cli_prompt_for_rerun):
            raise RuntimeError(f"Renderd setup step '{description}' ({tag}) failed.")
    for tag, description, func_ref in config_steps:
        if not execute_step(tag, description, func_ref, logger_to_use, cli_prompt_for_rerun):
            raise RuntimeError(f"Renderd configuration step '{description}' ({tag}) failed.")
    log_map_server(f"--- {config.SYMBOLS['success']} Renderd Full Setup & Config Sequence Completed ---", "success",
                   logger_to_use)


def nginx_full_setup_sequence(current_logger: Optional[logging.Logger] = None) -> None:
    logger_to_use = current_logger if current_logger else logger
    log_map_server(f"--- {config.SYMBOLS['step']} Starting Nginx Full Setup & Config Sequence ---", "info",
                   logger_to_use)
    nginx_steps = [
        ("SETUP_NGINX_PKG_CHECK", "Check Nginx Package Installation", ensure_nginx_package_installed),
        ("CONFIG_NGINX_PROXY_SITE", "Create Nginx Proxy Site Configuration", create_nginx_proxy_site_config),
        ("CONFIG_NGINX_MANAGE_SITES", "Enable Proxy Site & Disable Default", manage_nginx_sites),
        ("CONFIG_NGINX_TEST_CONFIG", "Test Nginx Configuration", test_nginx_configuration),
        ("SERVICE_NGINX_ACTIVATE", "Activate Nginx Service", activate_nginx_service),
    ]
    for tag, description, func_ref in nginx_steps:
        if not execute_step(tag, description, func_ref, logger_to_use, cli_prompt_for_rerun):
            raise RuntimeError(f"Nginx setup step '{description}' ({tag}) failed.")
    log_map_server(f"--- {config.SYMBOLS['success']} Nginx Full Setup & Config Sequence Completed ---", "success",
                   logger_to_use)


def pg_tileserv_full_setup_sequence(current_logger: Optional[logging.Logger] = None) -> None:
    logger_to_use = current_logger if current_logger else logger
    log_map_server(f"--- {config.SYMBOLS['step']} Starting pg_tileserv Full Setup & Config Sequence ---", "info",
                   logger_to_use)
    setup_steps = [
        ("SETUP_PGTS_DOWNLOAD_BINARY", "Download & Install pg_tileserv Binary",
         download_and_install_pg_tileserv_binary),
        ("SETUP_PGTS_CREATE_USER", "Create pg_tileserv System User", create_pg_tileserv_system_user),
        ("SETUP_PGTS_BINARY_PERMS", "Set pg_tileserv Binary Permissions", setup_pg_tileserv_binary_permissions),
        ("SETUP_PGTS_SYSTEMD_FILE", "Create pg_tileserv Systemd Service File", create_pg_tileserv_systemd_service_file),
    ]
    config_steps = [
        ("CONFIG_PGTS_CONFIG_FILE", "Create pg_tileserv config.toml", create_pg_tileserv_config_file),
        ("SERVICE_PGTS_ACTIVATE", "Activate pg_tileserv Service", activate_pg_tileserv_service),
    ]
    for tag, description, func_ref in setup_steps:
        if not execute_step(tag, description, func_ref, logger_to_use, cli_prompt_for_rerun):
            raise RuntimeError(f"pg_tileserv setup step '{description}' ({tag}) failed.")
    for tag, description, func_ref in config_steps:
        if not execute_step(tag, description, func_ref, logger_to_use, cli_prompt_for_rerun):
            raise RuntimeError(f"pg_tileserv configuration step '{description}' ({tag}) failed.")
    log_map_server(f"--- {config.SYMBOLS['success']} pg_tileserv Full Setup & Config Sequence Completed ---", "success",
                   logger_to_use)


def osrm_full_setup_sequence(current_logger: Optional[logging.Logger] = None) -> None:
    logger_to_use = current_logger if current_logger else logger
    log_map_server(f"--- {config.SYMBOLS['step']} Starting OSRM Full Setup, Processing & Config Sequence ---", "info",
                   logger_to_use)
    base_pbf_path_holder = {"path": None}
    regional_pbf_paths_holder = {"paths_map": {}}
    processed_regions_holder = {"names": []}

    infra_steps = [
        ("SETUP_OSRM_DEPS", "Ensure OSRM Dependencies", ensure_osrm_dependencies),
        ("SETUP_OSRM_DIRS", "Setup OSRM Data Directories", setup_osrm_data_directories),
        ("SETUP_OSRM_DOWNLOAD_PBF", "Download Base PBF for OSRM",
         lambda cl: base_pbf_path_holder.update({"path": download_base_pbf(cl)})),
        ("SETUP_OSRM_REGION_BOUNDARIES", "Prepare Region Boundary Files", prepare_region_boundaries),
    ]
    log_map_server("--- Phase: OSRM Infrastructure & Base Data ---", "info", logger_to_use)
    for tag, desc, func in infra_steps:
        if not execute_step(tag, desc, func, logger_to_use, cli_prompt_for_rerun): raise RuntimeError(
            f"OSRM infra step '{desc}' failed.")

    base_pbf_path = base_pbf_path_holder["path"]
    if not base_pbf_path: raise RuntimeError("Base PBF path not set for OSRM.")

    log_map_server("--- Phase: OSRM Regional PBF Extraction (Osmium) ---", "info", logger_to_use)
    if not execute_step("DATAPROC_OSMIUM_EXTRACT_REGIONS", "Extract Regional PBFs (Osmium)",
                        lambda cl: regional_pbf_paths_holder.update(
                                {"paths_map": extract_regional_pbfs_with_osmium(base_pbf_path, cl)}), logger_to_use,
                        cli_prompt_for_rerun):
        raise RuntimeError("Osmium regional PBF extraction failed.")

    regional_pbf_map = regional_pbf_paths_holder["paths_map"]
    if not regional_pbf_map: log_map_server(f"{config.SYMBOLS['warning']} No regional PBFs for OSRM graph building.",
                                            "warning", logger_to_use); return

    log_map_server("--- Phase: OSRM Graph Building (Docker) ---", "info", logger_to_use)
    for region_name, regional_pbf_path in regional_pbf_map.items():
        if not execute_step(f"DATAPROC_OSRM_BUILD_GRAPH_{region_name.upper()}", f"Build OSRM Graphs for {region_name}",
                            lambda cl, rn=region_name, rpp=regional_pbf_path: build_osrm_graphs_for_region(rn, rpp, cl),
                            logger_to_use, cli_prompt_for_rerun):
            log_map_server(f"{config.SYMBOLS['error']} Failed to build OSRM graphs for {region_name}.", "error",
                           logger_to_use)
        else:
            processed_regions_holder["names"].append(region_name)

    successfully_processed_regions = processed_regions_holder["names"]
    if not successfully_processed_regions: log_map_server(
        f"{config.SYMBOLS['warning']} No OSRM graphs successfully built.", "warning", logger_to_use); return

    log_map_server("--- Phase: OSRM Service Configuration & Activation ---", "info", logger_to_use)
    for region_name in successfully_processed_regions:
        if not execute_step(f"SETUP_OSRM_SYSTEMD_SERVICE_{region_name.upper()}",
                            f"Create OSRM Systemd Service for {region_name}",
                            lambda cl, rn=region_name: create_osrm_routed_service_file(rn, cl), logger_to_use,
                            cli_prompt_for_rerun):
            log_map_server(f"{config.SYMBOLS['error']} Failed to create OSRM systemd service for {region_name}.",
                           "error", logger_to_use);
            continue
        if not execute_step(f"CONFIG_OSRM_ACTIVATE_SERVICE_{region_name.upper()}",
                            f"Activate OSRM Service for {region_name}",
                            lambda cl, rn=region_name: activate_osrm_routed_service(rn, cl), logger_to_use,
                            cli_prompt_for_rerun):
            log_map_server(f"{config.SYMBOLS['error']} Failed to activate OSRM service for {region_name}.", "error",
                           logger_to_use)
    log_map_server(f"--- {config.SYMBOLS['success']} OSRM Full Setup, Processing & Config Sequence Completed ---",
                   "success", logger_to_use)


def apache_full_setup_sequence(current_logger: Optional[logging.Logger] = None) -> None:
    logger_to_use = current_logger if current_logger else logger
    log_map_server(f"--- {config.SYMBOLS['step']} Starting Apache & mod_tile Full Setup & Config Sequence ---", "info",
                   logger_to_use)
    apache_steps = [
        ("SETUP_APACHE_PKG_CHECK", "Check Apache Package Installation", ensure_apache_packages_installed),
        ("CONFIG_APACHE_PORTS", "Configure Apache Listening Ports", configure_apache_ports),
        ("CONFIG_APACHE_MOD_TILE_CONF", "Create mod_tile Apache Configuration", create_mod_tile_config),
        ("CONFIG_APACHE_TILE_SITE_CONF", "Create Apache Tile Serving Site", create_apache_tile_site_config),
        ("CONFIG_APACHE_MODULES_SITES", "Enable Apache Modules and Sites", manage_apache_modules_and_sites),
        ("SERVICE_APACHE_ACTIVATE", "Activate Apache Service", activate_apache_service),
    ]
    for tag, description, func_ref in apache_steps:
        if not execute_step(tag, description, func_ref, logger_to_use, cli_prompt_for_rerun):
            raise RuntimeError(f"Apache setup step '{description}' ({tag}) failed.")
    log_map_server(f"--- {config.SYMBOLS['success']} Apache & mod_tile Full Setup & Config Sequence Completed ---",
                   "success", logger_to_use)


def certbot_full_setup_sequence(current_logger: Optional[logging.Logger] = None) -> None:
    logger_to_use = current_logger if current_logger else logger
    log_map_server(f"--- {config.SYMBOLS['step']} Starting Certbot Full Setup & Config Sequence ---", "info",
                   logger_to_use)
    certbot_steps = [
        ("SETUP_CERTBOT_PACKAGES", "Install Certbot Packages", install_certbot_packages),
        ("CONFIG_CERTBOT_RUN", "Run Certbot for Nginx SSL/TLS Certificates", run_certbot_nginx),
    ]
    for tag, description, func_ref in certbot_steps:
        if not execute_step(tag, description, func_ref, logger_to_use, cli_prompt_for_rerun):
            log_map_server(
                f"{config.SYMBOLS['warning']} Certbot step '{description}' ({tag}) did not complete successfully. SSL may not be configured.",
                "warning", logger_to_use)
            break
    log_map_server(f"--- {config.SYMBOLS['success']} Certbot Full Setup & Config Sequence Attempted ---", "success",
                   logger_to_use)


def gtfs_full_setup_sequence(current_logger: Optional[logging.Logger] = None) -> None:
    logger_to_use = current_logger if current_logger else logger
    log_map_server(f"--- {config.SYMBOLS['step']} Starting GTFS Full Setup, Processing & Automation ---", "info",
                   logger_to_use)
    gtfs_steps = [
        ("SETUP_GTFS_ENV", "Setup GTFS Environment", setup_gtfs_logging_and_env_vars),
        ("DATAPROC_GTFS_ETL", "Run GTFS ETL Pipeline & Verify", run_gtfs_etl_pipeline_and_verify),
        ("CONFIG_GTFS_CRON", "Configure GTFS Update Cron Job", configure_gtfs_update_cronjob),
    ]
    for tag, description, func_ref in gtfs_steps:
        if not execute_step(tag, description, func_ref, logger_to_use, cli_prompt_for_rerun):
            raise RuntimeError(f"GTFS step '{description}' ({tag}) failed.")
    log_map_server(f"--- {config.SYMBOLS['success']} GTFS Full Setup, Processing & Automation Completed ---", "success",
                   logger_to_use)


def systemd_reload_step_group(current_logger_instance: Optional[logging.Logger] = None) -> bool:
    logger_to_use = current_logger_instance if current_logger_instance else logger
    return execute_step("SYSTEMD_RELOAD_MAIN", "Reload Systemd Daemon (Group Action)",
                        lambda lp: systemd_reload(current_logger=lp), logger_to_use, cli_prompt_for_rerun)


def main_map_server_entry(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Map Server Installer Script. Automates installation and configuration.",
        epilog="Example: python3 ./setup/main_installer.py --full -v mymap.example.com",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter, add_help=False,
    )
    # ... (Argparse setup as before, ensure all flags match defined_tasks_map keys) ...
    parser.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS,
                        help="Show this help message and exit.")
    parser.add_argument("--full", action="store_true", help="Run full installation process (all groups in sequence).")
    parser.add_argument("--view-config", action="store_true", help="View current configuration settings and exit.")
    parser.add_argument("--view-state", action="store_true",
                        help="View completed installation steps from state file and exit.")
    parser.add_argument("--clear-state", action="store_true", help="Clear all progress state from state file and exit.")

    config_group = parser.add_argument_group("Configuration Overrides")
    config_group.add_argument("-a", "--admin-group-ip", default=config.ADMIN_GROUP_IP_DEFAULT,
                              help="Admin group IP range (CIDR) for firewall and DB access.")
    config_group.add_argument("-f", "--gtfs-feed-url", default=config.GTFS_FEED_URL_DEFAULT,
                              help="URL of the GTFS feed to download and process.")
    config_group.add_argument("-v", "--vm-ip-or-domain", default=config.VM_IP_OR_DOMAIN_DEFAULT,
                              help="Public IP address or Fully Qualified Domain Name (FQDN) of this server.")
    config_group.add_argument("-b", "--pg-tileserv-binary-location", default=config.PG_TILESERV_BINARY_LOCATION_DEFAULT,
                              help="URL for the pg_tileserv binary if not installed via apt.")
    config_group.add_argument("-l", "--log-prefix", default=config.LOG_PREFIX_DEFAULT,
                              help="Prefix for log messages from this script.")

    pg_group = parser.add_argument_group("PostgreSQL Connection Overrides")
    pg_group.add_argument("-H", "--pghost", default=config.PGHOST_DEFAULT, help="PostgreSQL host.")
    pg_group.add_argument("-P", "--pgport", default=config.PGPORT_DEFAULT, help="PostgreSQL port.")
    pg_group.add_argument("-D", "--pgdatabase", default=config.PGDATABASE_DEFAULT, help="PostgreSQL database name.")
    pg_group.add_argument("-U", "--pguser", default=config.PGUSER_DEFAULT, help="PostgreSQL username.")
    pg_group.add_argument("-W", "--pgpassword", default=config.PGPASSWORD_DEFAULT,
                          help="PostgreSQL password. IMPORTANT: Change this default for security!")

    task_group = parser.add_argument_group("Individual Task Flags")
    # These flags now point to the _full_setup_sequence orchestrators for refactored services
    task_flags_definitions: List[Tuple[str, str, str]] = [
        ("boot-verbosity", "BOOT_VERBOSITY", "Run boot verbosity setup only."),
        ("core-conflicts", "CORE_CONFLICTS", "Run core conflict removal only."),
        ("core-install", "CORE_INSTALL", "Run core package installation only."),
        ("docker-install", "DOCKER_INSTALL", "Run Docker installation only."),
        ("nodejs-install", "NODEJS_INSTALL", "Run Node.js installation only."),
        ("ufw", "UFW_FULL_SETUP", "Run UFW full setup and configuration."),
        ("postgres", "POSTGRES_FULL_SETUP", "Run PostgreSQL full setup and configuration."),
        ("carto", "CARTO_FULL_SETUP", "Run Carto full setup and configuration."),
        ("renderd", "RENDERD_FULL_SETUP", "Run Renderd full setup and configuration."),
        ("nginx", "NGINX_FULL_SETUP", "Run Nginx full setup and configuration."),
        ("pgtileserv", "PGTILESERV_FULL_SETUP", "Run pg_tileserv full setup and configuration."),
        ("osrm", "OSRM_FULL_SETUP", "Run OSRM full setup, data processing & service activation."),
        ("apache", "APACHE_FULL_SETUP", "Run Apache & mod_tile full setup and configuration."),
        ("certbot", "CERTBOT_FULL_SETUP", "Run Certbot full setup and configuration."),
        ("gtfs-prep", "GTFS_FULL_SETUP", "Run GTFS full setup, data processing, and automation."),
        ("raster-prep", "RASTER_PREP", "Run raster tile pre-rendering only."),
        ("website-setup", "WEBSITE_SETUP", "Deploy test website content."),
        ("task-systemd-reload", "SYSTEMD_RELOAD_TASK", "Run systemd reload as a single task."),
    ]
    for flag_name, task_tag, base_desc in task_flags_definitions:
        task_group.add_argument(f"--{flag_name}", action="store_true", dest=flag_name.replace("-", "_"),
                                help=get_dynamic_help(base_desc, task_tag))

    group_task_flags = parser.add_argument_group("Group Task Flags")
    group_task_flags.add_argument("--conflicts-removed", dest="conflicts_removed_flag", action="store_true",
                                  help="Run core conflict removal group only.")
    group_task_flags.add_argument("--prereqs", action="store_true", help="Run prerequisites installation group only.")
    group_task_flags.add_argument("--services", action="store_true",
                                  help="Run setup for ALL services (using new sequences).")
    group_task_flags.add_argument("--data", action="store_true", help="Run all data preparation and processing tasks.")
    group_task_flags.add_argument("--systemd-reload", dest="group_systemd_reload_flag", action="store_true",
                                  help="Run systemd reload (as a group action).")

    dev_group = parser.add_argument_group("Developer and Advanced Options")
    dev_group.add_argument("--dev-override-unsafe-password", "--im-a-developer-get-me-out-of-here", action="store_true",
                           dest="dev_override_unsafe_password",
                           help="DEV FLAG: Allow using default PGPASSWORD for .pgpass. USE WITH CAUTION.")

    # --- Argument Parsing and Config Update ---
    try:
        if args is None and ("-h" in sys.argv or "--help" in sys.argv): parser.print_help(sys.stderr); return 0
        parsed_args = parser.parse_args(args)
    except SystemExit as e:
        return e.code

    config.ADMIN_GROUP_IP = parsed_args.admin_group_ip;
    config.GTFS_FEED_URL = parsed_args.gtfs_feed_url
    config.VM_IP_OR_DOMAIN = parsed_args.vm_ip_or_domain;
    config.PG_TILESERV_BINARY_LOCATION = parsed_args.pg_tileserv_binary_location
    config.LOG_PREFIX = parsed_args.log_prefix;
    config.PGHOST = parsed_args.pghost;
    config.PGPORT = parsed_args.pgport
    config.PGDATABASE = parsed_args.pgdatabase;
    config.PGUSER = parsed_args.pguser;
    config.PGPASSWORD = parsed_args.pgpassword
    config.DEV_OVERRIDE_UNSAFE_PASSWORD = parsed_args.dev_override_unsafe_password

    setup_main_logging()
    log_map_server(
        f"{config.SYMBOLS['sparkles']} Starting Map Server Setup (v {config.SCRIPT_VERSION}) SCRIPT_HASH: {get_current_script_hash(logger) or 'N/A'} ...",
        current_logger=logger)

    # ... (PGPASSWORD warning, root check as before) ...
    if (
            config.PGPASSWORD == config.PGPASSWORD_DEFAULT and not parsed_args.view_config and not config.DEV_OVERRIDE_UNSAFE_PASSWORD):
        log_map_server(f"{config.SYMBOLS['warning']} WARNING: Using default PostgreSQL password. This is INSECURE.",
                       "warning", current_logger=logger)
    if os.geteuid() != 0:  # Simplified root check message
        log_map_server(f"{config.SYMBOLS['info']} Script not run as root. 'sudo' will be used for elevated commands.",
                       "info", current_logger=logger)
    else:
        log_map_server(f"{config.SYMBOLS['info']} Script is running as root.", "info", current_logger=logger)

    initialize_state_system(current_logger=logger)
    setup_pgpass(pg_host=config.PGHOST, pg_port=config.PGPORT, pg_database=config.PGDATABASE, pg_user=config.PGUSER,
                 pg_password=config.PGPASSWORD, pg_password_default=config.PGPASSWORD_DEFAULT,
                 allow_default_for_dev=config.DEV_OVERRIDE_UNSAFE_PASSWORD, current_logger=logger)

    if parsed_args.view_config: view_configuration(current_logger=logger); return 0
    if parsed_args.view_state:
        completed_steps_list = view_completed_steps(current_logger=logger)
        if completed_steps_list:
            log_map_server(f"{config.SYMBOLS['info']} Completed steps:", "info", current_logger=logger)
            for s_idx, s_item in enumerate(completed_steps_list): print(f"  {s_idx + 1}. {s_item}")
        else:
            log_map_server(f"{config.SYMBOLS['info']} No steps marked as completed.", "info", current_logger=logger)
        return 0
    if parsed_args.clear_state:
        if cli_prompt_for_rerun(f"Are you sure you want to clear state from {config.STATE_FILE_PATH}?"):
            clear_state_file(current_logger=logger)
        else:
            log_map_server(f"{config.SYMBOLS['info']} State clearing cancelled.", "info", current_logger=logger)
        return 0

    # --- Task Definitions (Map argparse dest to Tag, Description, Function) ---
    defined_tasks_map: Dict[str, Tuple[str, str, Callable]] = {
        "boot_verbosity": ("BOOT_VERBOSITY", "Improve Boot Verbosity & Core Utils", boot_verbosity),
        "core_conflicts": ("CORE_CONFLICTS", "Remove Core Conflicts", core_conflict_removal),
        "core_install": ("CORE_INSTALL", "Install Core System Packages", core_install),
        "docker_install": ("DOCKER_INSTALL", "Install Docker Engine", docker_install),
        "nodejs_install": ("NODEJS_INSTALL", "Install Node.js LTS", node_js_lts_install),
        "ufw": ("UFW_FULL_SETUP", "Run UFW full setup", ufw_full_setup_sequence),
        "postgres": ("POSTGRES_FULL_SETUP", "Run PostgreSQL full setup", postgres_full_setup_sequence),
        "carto": ("CARTO_FULL_SETUP", "Run Carto full setup", carto_full_setup_sequence),
        "renderd": ("RENDERD_FULL_SETUP", "Run Renderd full setup", renderd_full_setup_sequence),
        "nginx": ("NGINX_FULL_SETUP", "Run Nginx full setup", nginx_full_setup_sequence),
        "pgtileserv": ("PGTILESERV_FULL_SETUP", "Run pg_tileserv full setup", pg_tileserv_full_setup_sequence),
        "osrm": ("OSRM_FULL_SETUP", "Run OSRM full setup & data processing", osrm_full_setup_sequence),
        "apache": ("APACHE_FULL_SETUP", "Run Apache & mod_tile full setup", apache_full_setup_sequence),
        "certbot": ("CERTBOT_FULL_SETUP", "Run Certbot full setup", certbot_full_setup_sequence),
        "gtfs_prep": ("GTFS_FULL_SETUP", "Run GTFS full pipeline", gtfs_full_setup_sequence),
        "raster_prep": ("RASTER_PREP", "Pre-render Raster Tiles", raster_tile_prerender),
        "website_setup": ("WEBSITE_SETUP", "Deploy Test Website Content", deploy_test_website_content),
        "task_systemd_reload": ("SYSTEMD_RELOAD_TASK", "Reload Systemd Daemon (Task)",
                                lambda cl: systemd_reload(current_logger=cl)),
    }

    overall_success = True
    action_taken = False

    tasks_to_run_from_flags: List[Dict[str, Any]] = []
    for arg_dest_name_key in defined_tasks_map.keys():
        if getattr(parsed_args, arg_dest_name_key.replace("-", "_"), False):
            action_taken = True
            tag, desc, func_ref = defined_tasks_map[arg_dest_name_key]
            tasks_to_run_from_flags.append({"tag": tag, "desc": desc, "func": func_ref})

    if tasks_to_run_from_flags:
        log_map_server(f"{config.SYMBOLS['rocket']}====== Running Specified Individual Task(s) ======",
                       current_logger=logger)
        if len(tasks_to_run_from_flags) > 1:
            def get_sort_key(task_item_dict: Dict[str, Any]) -> Tuple[int, int]:
                tag_for_sort = task_item_dict["tag"]
                # Determine primary sort tag (e.g. first sub-step of a sequence)
                sort_key_tag_map = {
                    "UFW_FULL_SETUP": "CONFIG_UFW_RULES", "POSTGRES_FULL_SETUP": "SETUP_POSTGRES_PKG_CHECK",
                    "CARTO_FULL_SETUP": "SETUP_CARTO_CLI", "RENDERD_FULL_SETUP": "SETUP_RENDERD_PKG_CHECK",
                    "NGINX_FULL_SETUP": "SETUP_NGINX_PKG_CHECK", "PGTILESERV_FULL_SETUP": "SETUP_PGTS_DOWNLOAD_BINARY",
                    "OSRM_FULL_SETUP": "SETUP_OSRM_DEPS", "APACHE_FULL_SETUP": "SETUP_APACHE_PKG_CHECK",
                    "CERTBOT_FULL_SETUP": "SETUP_CERTBOT_PACKAGES", "GTFS_FULL_SETUP": "SETUP_GTFS_ENV",
                }
                effective_sort_tag = sort_key_tag_map.get(tag_for_sort, tag_for_sort)
                details = task_execution_details_lookup.get(effective_sort_tag)
                if details:
                    group_name, step_in_group = details
                    return (group_order_lookup.get(group_name, float('inf')), step_in_group)
                return (float('inf'), float('inf'))

            tasks_to_run_from_flags.sort(key=get_sort_key)

        for task_info in tasks_to_run_from_flags:
            if not overall_success:
                log_map_server(
                    f"{config.SYMBOLS['warning']} Skipping task '{task_info['desc']}' due to previous failure.",
                    "warning", logger);
                continue
            if not execute_step(task_info["tag"], task_info["desc"], task_info["func"], logger, cli_prompt_for_rerun):
                overall_success = False

    elif parsed_args.full:
        action_taken = True
        log_map_server(f"{config.SYMBOLS['rocket']}====== Starting Full Installation Process ======",
                       current_logger=logger)

        all_setup_and_config_phases = [
            ("CORE_CONFLICT_REMOVAL_GROUP", "Core Conflict Removal Group", core_conflict_removal_group),
            ("PREREQUISITES_GROUP", "Prerequisites Installation Group", prereqs_install_group),
            ("UFW_FULL_SETUP", "Full UFW Setup & Configuration", ufw_full_setup_sequence),
            ("POSTGRES_FULL_SETUP", "Full PostgreSQL Setup & Configuration", postgres_full_setup_sequence),
            ("PGTILESERV_FULL_SETUP", "Full pg_tileserv Setup & Configuration", pg_tileserv_full_setup_sequence),
            ("CARTO_FULL_SETUP", "Full Carto Setup & Configuration", carto_full_setup_sequence),
            ("RENDERD_FULL_SETUP", "Full Renderd Setup & Configuration", renderd_full_setup_sequence),
            ("OSRM_FULL_SETUP", "Full OSRM Setup, Data Processing & Service Activation", osrm_full_setup_sequence),
            ("APACHE_FULL_SETUP", "Full Apache & mod_tile Setup & Configuration", apache_full_setup_sequence),
            ("NGINX_FULL_SETUP", "Full Nginx Setup & Configuration", nginx_full_setup_sequence),
            ("CERTBOT_FULL_SETUP", "Full Certbot Setup & Configuration", certbot_full_setup_sequence),
            ("WEBSITE_SETUP", "Deploy Test Website Content", deploy_test_website_content),  # Direct function call
            ("SYSTEMD_RELOAD_GROUP", "Systemd Reload After All Services", systemd_reload_step_group),
            ("GTFS_FULL_SETUP", "Full GTFS Data Pipeline Setup", gtfs_full_setup_sequence),
            ("RASTER_PREP", "Raster Tile Pre-rendering", raster_tile_prerender),  # Direct function call
        ]

        for tag, desc, phase_func_ref in all_setup_and_config_phases:
            if not overall_success:
                log_map_server(f"{config.SYMBOLS['warning']} Skipping '{desc}' due to previous failure.", "warning",
                               logger);
                continue
            log_map_server(f"--- {config.SYMBOLS['info']} Executing: {desc} ({tag}) ---", "info", logger)

            current_phase_success = True
            if "GROUP" in tag:  # Group orchestrators return bool
                if not phase_func_ref(logger): current_phase_success = False
            else:  # For X_full_setup_sequence or single functions
                if not execute_step(tag, desc, phase_func_ref, logger, cli_prompt_for_rerun):
                    current_phase_success = False

            if not current_phase_success:
                overall_success = False
                log_map_server(f"{config.SYMBOLS['error']} Phase/Task '{desc}' failed.", "error", logger);
                break

    elif parsed_args.conflicts_removed_flag:
        action_taken = True;
        overall_success = core_conflict_removal_group(logger)
    elif parsed_args.prereqs:
        action_taken = True;
        overall_success = prereqs_install_group(logger)
    elif parsed_args.services:
        action_taken = True
        log_map_server(f"{config.SYMBOLS['rocket']}====== Running All Service Setups & Configurations ======",
                       current_logger=logger)
        all_service_related_sequences = [
            ("UFW_FULL_SETUP", "Full UFW Setup", ufw_full_setup_sequence),
            ("POSTGRES_FULL_SETUP", "Full PostgreSQL Setup", postgres_full_setup_sequence),
            ("PGTILESERV_FULL_SETUP", "Full pg_tileserv Setup", pg_tileserv_full_setup_sequence),
            ("CARTO_FULL_SETUP", "Full Carto Setup", carto_full_setup_sequence),
            ("RENDERD_FULL_SETUP", "Full Renderd Setup", renderd_full_setup_sequence),
            ("OSRM_FULL_SETUP", "Full OSRM Setup", osrm_full_setup_sequence),
            ("APACHE_FULL_SETUP", "Full Apache Setup", apache_full_setup_sequence),
            ("NGINX_FULL_SETUP", "Full Nginx Setup", nginx_full_setup_sequence),
            ("CERTBOT_FULL_SETUP", "Full Certbot Setup", certbot_full_setup_sequence),
            ("WEBSITE_SETUP", "Deploy Test Website Content", deploy_test_website_content),
        ]
        for tag, desc, func in all_service_related_sequences:
            if not overall_success: break
            if not execute_step(tag, desc, func, logger, cli_prompt_for_rerun):
                overall_success = False
        if overall_success: overall_success = systemd_reload_step_group(logger)

    elif parsed_args.data:
        action_taken = True
        log_map_server(f"{config.SYMBOLS['rocket']}====== Running Data Tasks ======", current_logger=logger)
        data_tasks_for_group_flag = [
            ("GTFS_FULL_SETUP", "Full GTFS Pipeline Setup", gtfs_full_setup_sequence),
            ("RASTER_PREP", "Raster Tile Pre-rendering", raster_tile_prerender),
        ]
        for tag, desc, func in data_tasks_for_group_flag:
            if not overall_success: break
            if not execute_step(tag, desc, func, logger, cli_prompt_for_rerun):
                overall_success = False

    elif parsed_args.group_systemd_reload_flag:
        action_taken = True;
        overall_success = systemd_reload_step_group(logger)

    if not action_taken:
        log_map_server(f"{config.SYMBOLS['info']} No installation action specified. Displaying help.", "info",
                       current_logger=logger)
        parser.print_help(file=sys.stderr)
        return 2

    if not overall_success:
        log_map_server(f"{config.SYMBOLS['critical']} One or more steps failed.", "critical", current_logger=logger)
        return 1
    else:
        log_map_server(f"{config.SYMBOLS['sparkles']} All requested operations completed successfully.", "success",
                       current_logger=logger)
        return 0


if __name__ == "__main__":
    sys.exit(main_map_server_entry())