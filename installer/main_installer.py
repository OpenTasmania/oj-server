# installer/main_installer.py
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

from actions.website_setup_actions import deploy_test_website_content
from actions.ufw_setup_actions import enable_ufw_service
# --- Common module imports ---
from common.command_utils import log_map_server
from common.pgpass_utils import setup_pgpass
from common.system_utils import systemd_reload
from common.core_utils import setup_logging as common_setup_logging

# --- Configuration and Installer imports ---
from configure.apache_configurator import (
    configure_apache_ports, create_mod_tile_config, create_apache_tile_site_config,
    manage_apache_modules_and_sites, activate_apache_service
)
from configure.carto_configurator import (
    compile_osm_carto_stylesheet, deploy_mapnik_stylesheet,
    finalize_carto_directory_processing, update_font_cache
)
from configure.certbot_configurator import run_certbot_nginx
from configure.gtfs_automation_configurator import configure_gtfs_update_cronjob
from configure.nginx_configurator import (
    create_nginx_proxy_site_config, manage_nginx_sites,
    test_nginx_configuration, activate_nginx_service
)
from configure.osrm_configurator import (
    create_osrm_routed_service_file, activate_osrm_routed_service
)
from configure.pg_tileserv_configurator import (
    create_pg_tileserv_config_file, activate_pg_tileserv_service
)
from configure.postgres_configurator import (
    create_postgres_user_and_db, enable_postgres_extensions,
    set_postgres_permissions, customize_postgresql_conf,
    customize_pg_hba_conf, restart_and_enable_postgres_service
)
from configure.renderd_configurator import (
    create_renderd_conf_file, activate_renderd_service
)
from configure.ufw_configurator import apply_ufw_rules

# --- Data Processing imports ---
from dataproc.gtfs_processor_runner import run_gtfs_etl_pipeline_and_verify
from dataproc.osrm_data_processor import (
    extract_regional_pbfs_with_osmium,
    build_osrm_graphs_for_region
)
from dataproc.raster_processor import raster_tile_prerender

# --- Installer component imports ---
from installer.apache_installer import ensure_apache_packages_installed
from installer.carto_installer import (
    install_carto_cli, setup_osm_carto_repository,
    prepare_carto_directory_for_processing, fetch_carto_external_data
)
from installer.certbot_installer import install_certbot_packages
from installer.nginx_installer import ensure_nginx_package_installed
from installer.osrm_installer import (
    ensure_osrm_dependencies, setup_osrm_data_directories,
    download_base_pbf, prepare_region_boundaries
)
from installer.pg_tileserv_installer import (
    download_and_install_pg_tileserv_binary, create_pg_tileserv_system_user,
    setup_pg_tileserv_binary_permissions, create_pg_tileserv_systemd_service_file
)
from installer.postgres_installer import ensure_postgres_packages_are_installed
from installer.renderd_installer import (
    ensure_renderd_packages_installed, create_renderd_directories,
    create_renderd_systemd_service_file
)
# Import new dedicated installers for Docker and Node.js
from installer.docker_installer import install_docker_engine
from installer.nodejs_installer import install_nodejs_lts

# --- Setup phase module imports ---
from setup import config
from setup.cli_handler import cli_prompt_for_rerun, view_configuration

# Import the comprehensive prerequisite group and specific prerequisite functions
from setup.core_prerequisites import (
    core_prerequisites_group,
    boot_verbosity as prereq_boot_verbosity,  # Alias to avoid conflict if needed
    core_conflict_removal as prereq_core_conflict_removal  # Alias
)
# core_setup.py is now much leaner or potentially removed if all its functions are relocated.

from setup.gtfs_environment_setup import setup_gtfs_logging_and_env_vars
from setup.state_manager import (
    clear_state_file, initialize_state_system, view_completed_steps,
    get_current_script_hash
)
from setup.step_executor import execute_step

logger = logging.getLogger(__name__)

# Updated INSTALLATION_GROUPS_ORDER
ALL_CORE_PREREQUISITES_GROUP_TAG = "ALL_CORE_PREREQUISITES_GROUP"  # Define a tag for the group

INSTALLATION_GROUPS_ORDER: List[Dict[str, Any]] = [
    # "Core Conflict Removal" and "Prerequisites" are now handled by core_prerequisites_group
    {"name": "Comprehensive Prerequisites", "steps": [ALL_CORE_PREREQUISITES_GROUP_TAG]},
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

# task_execution_details_lookup needs to be updated for the new structure
task_execution_details_lookup: Dict[str, Tuple[str, int]] = {}
for group_idx, group_info in enumerate(INSTALLATION_GROUPS_ORDER):
    group_name = group_info["name"]
    for step_idx, task_tag in enumerate(group_info["steps"]):
        task_execution_details_lookup[task_tag] = (group_name, step_idx + 1)

# Add entries for individual flags that might be run standalone and map to core_prerequisites functions
# These tags should match what's used in defined_tasks_map
task_execution_details_lookup["PREREQ_BOOT_VERBOSITY_TAG"] = ("Comprehensive Prerequisites", 1)  # Example sub-step
task_execution_details_lookup["PREREQ_CORE_CONFLICTS_TAG"] = ("Comprehensive Prerequisites", 2)  # Example sub-step
task_execution_details_lookup["PREREQ_DOCKER_ENGINE_TAG"] = ("Comprehensive Prerequisites",
                                                             8)  # Example sub-step (order might vary)
task_execution_details_lookup["PREREQ_NODEJS_LTS_TAG"] = ("Comprehensive Prerequisites", 9)  # Example sub-step

# Add entries for service groups (as before)
task_execution_details_lookup["UFW_FULL_SETUP"] = ("Firewall Service (UFW)", 0)
# ... (other service group lookups remain similar)
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
    if details and details[1] > 0:  # Indicates a sub-step of a group
        return f"{base_help} (Part of: '{details[0]}', Sub-step: {details[1]})"
    elif details and details[1] == 0:  # Indicates a full group orchestrator
        return f"{base_help} (Orchestrates: '{details[0]}')"
    # Fallback for tasks not explicitly in a group's "steps" list but runnable standalone
    return f"{base_help} (Standalone or specific task)"


# --- Orchestrator sequences for services (ufw_full_setup_sequence, etc.) remain unchanged ---
# ...

def main_map_server_entry(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Map Server Installer Script. Automates installation and configuration.",
        epilog="Example: python3 ./installer/main_installer.py --full -v mymap.example.com",  # Corrected path
        formatter_class=argparse.ArgumentDefaultsHelpFormatter, add_help=False,
    )
    # ... (standard help, --full, --view-config, --view-state, --clear-state args as before) ...
    parser.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS,
                        help="Show this help message and exit.")
    parser.add_argument("--full", action="store_true", help="Run full installation process (all groups in sequence).")
    parser.add_argument("--view-config", action="store_true", help="View current configuration settings and exit.")
    parser.add_argument("--view-state", action="store_true",
                        help="View completed installation steps from state file and exit.")
    parser.add_argument("--clear-state", action="store_true", help="Clear all progress state from state file and exit.")

    config_group = parser.add_argument_group("Configuration Overrides")
    # ... (config_group args as before, using config defaults) ...
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
    # ... (pg_group args as before, using config defaults) ...
    pg_group.add_argument("-H", "--pghost", default=config.PGHOST_DEFAULT, help="PostgreSQL host.")
    pg_group.add_argument("-P", "--pgport", default=config.PGPORT_DEFAULT, help="PostgreSQL port.")
    pg_group.add_argument("-D", "--pgdatabase", default=config.PGDATABASE_DEFAULT, help="PostgreSQL database name.")
    pg_group.add_argument("-U", "--pguser", default=config.PGUSER_DEFAULT, help="PostgreSQL username.")
    pg_group.add_argument("-W", "--pgpassword", default=config.PGPASSWORD_DEFAULT,
                          help="PostgreSQL password. IMPORTANT: Change this default for security!")

    task_group = parser.add_argument_group("Individual Task Flags")
    # Updated task flags definitions
    # Tags should be unique and match keys in defined_tasks_map
    task_flags_definitions: List[Tuple[str, str, str]] = [
        ("boot-verbosity", "PREREQ_BOOT_VERBOSITY_TAG", "Run boot verbosity setup only."),
        ("core-conflicts", "PREREQ_CORE_CONFLICTS_TAG", "Run core conflict removal only."),
        # ("core-install" flag removed as its logic is now part of the comprehensive prereq group)
        ("docker-install", "PREREQ_DOCKER_ENGINE_TAG", "Run Docker installation only."),
        ("nodejs-install", "PREREQ_NODEJS_LTS_TAG", "Run Node.js installation only."),
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
        ("website-setup", "WEBSITE_CONTENT_DEPLOY", "Deploy test website content."),
        ("task-systemd-reload", "SYSTEMD_RELOAD_TASK", "Run systemd reload as a single task."),
    ]
    for flag_name, task_tag, base_desc in task_flags_definitions:
        task_group.add_argument(f"--{flag_name}", action="store_true", dest=flag_name.replace("-", "_"),
                                help=get_dynamic_help(base_desc, task_tag))

    group_task_flags = parser.add_argument_group("Group Task Flags")
    # --conflicts-removed now points to the specific function via defined_tasks_map
    group_task_flags.add_argument("--conflicts-removed", dest="core_conflicts", action="store_true",
                                  # Use dest matching a task_flag_definition
                                  help="Run core conflict removal step only.")
    # --prereqs now points to the comprehensive group via defined_tasks_map
    group_task_flags.add_argument("--prereqs", dest="run_all_core_prerequisites", action="store_true",
                                  help="Run comprehensive prerequisites installation group.")
    group_task_flags.add_argument("--services", action="store_true", help="Run setup for ALL services.")
    group_task_flags.add_argument("--data", action="store_true", help="Run all data preparation and processing tasks.")
    group_task_flags.add_argument("--systemd-reload", dest="group_systemd_reload_flag", action="store_true",
                                  help="Run systemd reload (as a group action).")

    dev_group = parser.add_argument_group("Developer and Advanced Options")
    # ... (dev_group args as before) ...
    dev_group.add_argument("--dev-override-unsafe-password", "--im-a-developer-get-me-out-of-here", action="store_true",
                           dest="dev_override_unsafe_password",
                           help="DEV FLAG: Allow using default PGPASSWORD for .pgpass. USE WITH CAUTION.")

    # --- Argument Parsing and Config Update ---
    # ... (same as before) ...
    try:
        if args is None and ("-h" in sys.argv or "--help" in sys.argv):  # pragma: no cover
            parser.print_help(sys.stderr);
            return 0
        parsed_args = parser.parse_args(args)
    except SystemExit as e:  # pragma: no cover
        return e.code

    config.ADMIN_GROUP_IP = parsed_args.admin_group_ip
    config.GTFS_FEED_URL = parsed_args.gtfs_feed_url
    config.VM_IP_OR_DOMAIN = parsed_args.vm_ip_or_domain
    config.PG_TILESERV_BINARY_LOCATION = parsed_args.pg_tileserv_binary_location
    config.LOG_PREFIX = parsed_args.log_prefix
    config.PGHOST = parsed_args.pghost
    config.PGPORT = parsed_args.pgport
    config.PGDATABASE = parsed_args.pgdatabase
    config.PGUSER = parsed_args.pguser
    config.PGPASSWORD = parsed_args.pgpassword
    config.DEV_OVERRIDE_UNSAFE_PASSWORD = parsed_args.dev_override_unsafe_password

    # Centralized logging setup call (as refactored previously)
    level_str_main = os.environ.get("LOGLEVEL", "INFO").upper()
    log_level_main = getattr(logging, level_str_main, logging.INFO)
    if not isinstance(log_level_main, int):  # pragma: no cover
        print(f"Warning: Invalid LOGLEVEL string '{level_str_main}'. Defaulting to INFO.", file=sys.stderr)
        log_level_main = logging.INFO
    common_setup_logging(log_level=log_level_main, log_to_console=True, log_prefix=config.LOG_PREFIX)

    log_map_server(
        f"{config.SYMBOLS['sparkles']} Starting Map Server Setup (v {config.SCRIPT_VERSION}) SCRIPT_HASH: {get_current_script_hash(logger) or 'N/A'} ...",
        current_logger=logger)

    # ... (PGPASSWORD warning, root check, initialize_state_system, setup_pgpass as before) ...
    if (
            config.PGPASSWORD == config.PGPASSWORD_DEFAULT and not parsed_args.view_config and not config.DEV_OVERRIDE_UNSAFE_PASSWORD):  # pragma: no cover
        log_map_server(f"{config.SYMBOLS['warning']} WARNING: Using default PostgreSQL password. This is INSECURE.",
                       "warning", current_logger=logger)
    if os.geteuid() != 0:  # pragma: no cover
        log_map_server(f"{config.SYMBOLS['info']} Script not run as root. 'sudo' will be used for elevated commands.",
                       "info", current_logger=logger)
    else:
        log_map_server(f"{config.SYMBOLS['info']} Script is running as root.", "info", current_logger=logger)
    initialize_state_system(current_logger=logger)
    setup_pgpass(pg_host=config.PGHOST, pg_port=config.PGPORT, pg_database=config.PGDATABASE, pg_user=config.PGUSER,
                 pg_password=config.PGPASSWORD, pg_password_default=config.PGPASSWORD_DEFAULT,
                 allow_default_for_dev=config.DEV_OVERRIDE_UNSAFE_PASSWORD, current_logger=logger)
    if parsed_args.view_config: view_configuration(current_logger=logger); return 0
    if parsed_args.view_state:  # pragma: no cover
        completed_steps_list = view_completed_steps(current_logger=logger)
        if completed_steps_list:
            log_map_server(f"{config.SYMBOLS['info']} Completed steps:", "info", current_logger=logger); [
                print(f"  {s_idx + 1}. {s_item}") for s_idx, s_item in enumerate(completed_steps_list)]
        else:
            log_map_server(f"{config.SYMBOLS['info']} No steps marked as completed.", "info", current_logger=logger)
        return 0
    if parsed_args.clear_state:  # pragma: no cover
        if cli_prompt_for_rerun(f"Are you sure you want to clear state from {config.STATE_FILE_PATH}?"):
            clear_state_file(current_logger=logger)
        else:
            log_map_server(f"{config.SYMBOLS['info']} State clearing cancelled.", "info", current_logger=logger)
        return 0

    # --- Updated Task Definitions ---
    defined_tasks_map: Dict[str, Tuple[str, str, Callable]] = {
        # Individual prerequisite tasks now point to their new homes
        "boot_verbosity": ("PREREQ_BOOT_VERBOSITY_TAG", "Improve Boot Verbosity", prereq_boot_verbosity),
        "core_conflicts": ("PREREQ_CORE_CONFLICTS_TAG", "Remove Core Conflicts", prereq_core_conflict_removal),
        "docker_install": ("PREREQ_DOCKER_ENGINE_TAG", "Install Docker Engine", install_docker_engine),
        "nodejs_install": ("PREREQ_NODEJS_LTS_TAG", "Install Node.js LTS", install_nodejs_lts),

        # Orchestrator for the comprehensive prerequisite group (for --prereqs flag)
        "run_all_core_prerequisites": (ALL_CORE_PREREQUISITES_GROUP_TAG, "Run Comprehensive Prerequisites Group",
                                       core_prerequisites_group),

        # Service setup sequences (remain as before)
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
        "website_setup": ("WEBSITE_CONTENT_DEPLOY", "Deploy Test Website Content", deploy_test_website_content),
        "task_systemd_reload": ("SYSTEMD_RELOAD_TASK", "Reload Systemd Daemon (Task)",
                                lambda cl: systemd_reload(current_logger=cl)),
    }

    overall_success = True
    action_taken = False

    tasks_to_run_from_flags: List[Dict[str, Any]] = []
    # Check flags corresponding to keys in defined_tasks_map
    # Note: This includes the dest for --prereqs ("run_all_core_prerequisites")
    # and --conflicts-removed (which is now "core_conflicts" via its dest)
    for arg_dest_name_key in defined_tasks_map.keys():
        # Map argparse dest (e.g., parsed_args.boot_verbosity) to defined_tasks_map key (e.g., "boot_verbosity")
        # For group flags, the dest in argparse should match a key here.
        # Example: --prereqs has dest="run_all_core_prerequisites"
        if getattr(parsed_args, arg_dest_name_key, False):
            action_taken = True
            tag, desc, func_ref = defined_tasks_map[arg_dest_name_key]
            tasks_to_run_from_flags.append({"tag": tag, "desc": desc, "func": func_ref})

    # ... (rest of task execution logic, e.g., sorting tasks_to_run_from_flags, then executing) ...
    if tasks_to_run_from_flags:
        log_map_server(f"{config.SYMBOLS['rocket']}====== Running Specified Individual Task(s)/Group(s) ======", "info",
                       current_logger=logger)
        # Sorting logic for tasks_to_run_from_flags (as before, if needed, ensuring tags are in task_execution_details_lookup)
        # ...
        for task_info in tasks_to_run_from_flags:
            if not overall_success:  # pragma: no cover
                log_map_server(
                    f"{config.SYMBOLS['warning']} Skipping task '{task_info['desc']}' due to previous failure.",
                    "warning", logger);
                continue
            if not execute_step(task_info["tag"], task_info["desc"], task_info["func"], logger, cli_prompt_for_rerun):
                overall_success = False  # pragma: no cover

    elif parsed_args.full:  # pragma: no cover
        action_taken = True
        log_map_server(f"{config.SYMBOLS['rocket']}====== Starting Full Installation Process ======", "info",
                       current_logger=logger)
        # Updated all_setup_and_config_phases to use the new comprehensive prerequisite group tag
        all_setup_and_config_phases = [
            (ALL_CORE_PREREQUISITES_GROUP_TAG, "Comprehensive Core Prerequisites", core_prerequisites_group),
            ("UFW_FULL_SETUP", "Full UFW Setup & Configuration", ufw_full_setup_sequence),
            ("POSTGRES_FULL_SETUP", "Full PostgreSQL Setup & Configuration", postgres_full_setup_sequence),
            ("PGTILESERV_FULL_SETUP", "Full pg_tileserv Setup & Configuration", pg_tileserv_full_setup_sequence),
            ("CARTO_FULL_SETUP", "Full Carto Setup & Configuration", carto_full_setup_sequence),
            ("RENDERD_FULL_SETUP", "Full Renderd Setup & Configuration", renderd_full_setup_sequence),
            ("OSRM_FULL_SETUP", "Full OSRM Setup, Data Processing & Service Activation", osrm_full_setup_sequence),
            ("APACHE_FULL_SETUP", "Full Apache & mod_tile Setup & Configuration", apache_full_setup_sequence),
            ("NGINX_FULL_SETUP", "Full Nginx Setup & Configuration", nginx_full_setup_sequence),
            ("CERTBOT_FULL_SETUP", "Full Certbot Setup & Configuration", certbot_full_setup_sequence),
            ("WEBSITE_CONTENT_DEPLOY", "Deploy Test Website Content", deploy_test_website_content),
            ("SYSTEMD_RELOAD_GROUP", "Systemd Reload After All Services", systemd_reload_step_group),
            # Assuming this is a callable group function
            ("GTFS_FULL_SETUP", "Full GTFS Data Pipeline Setup", gtfs_full_setup_sequence),
            ("RASTER_PREP", "Raster Tile Pre-rendering", raster_tile_prerender),
        ]
        for tag, desc, phase_func_ref in all_setup_and_config_phases:
            if not overall_success: log_map_server(
                f"{config.SYMBOLS['warning']} Skipping '{desc}' due to previous failure.", "warning", logger); continue
            log_map_server(f"--- {config.SYMBOLS['info']} Executing: {desc} ({tag}) ---", "info", logger)
            current_phase_success = True
            # Check if it's a group function that returns bool or a step to be run via execute_step
            # Assuming group functions like core_prerequisites_group and systemd_reload_step_group are called directly.
            if tag == ALL_CORE_PREREQUISITES_GROUP_TAG or "GROUP" in tag.upper():  # Heuristic for group orchestrators
                if not phase_func_ref(logger): current_phase_success = False
            else:  # Standard step
                if not execute_step(tag, desc, phase_func_ref, logger,
                                    cli_prompt_for_rerun): current_phase_success = False
            if not current_phase_success: overall_success = False; log_map_server(
                f"{config.SYMBOLS['error']} Phase/Task '{desc}' failed.", "error", logger); break

    # Individual group flags like --services, --data, --systemd-reload are processed here
    # These might also need adjustment if their constituent steps have changed or moved.
    # For example, if --prereqs is now handled by defined_tasks_map key "run_all_core_prerequisites",
    # the explicit elif for parsed_args.prereqs might not be needed if tasks_to_run_from_flags handles it.
    # However, keeping them for clarity if they represent distinct user intentions for grouped actions.

    elif parsed_args.services:  # pragma: no cover
        action_taken = True;
        log_map_server(f"{config.SYMBOLS['rocket']}====== Running All Service Setups & Configurations ======", "info",
                       current_logger=logger)
        all_service_related_sequences = [
            ("UFW_FULL_SETUP", "Full UFW Setup", ufw_full_setup_sequence),
            ("POSTGRES_FULL_SETUP", "Full PostgreSQL Setup", postgres_full_setup_sequence),
            # ... (other services)
            ("WEBSITE_CONTENT_DEPLOY", "Deploy Test Website Content", deploy_test_website_content),
        ]
        for tag, desc, func in all_service_related_sequences:
            if not overall_success: break
            if not execute_step(tag, desc, func, logger, cli_prompt_for_rerun): overall_success = False
        if overall_success: overall_success = systemd_reload_step_group(logger)

    elif parsed_args.data:  # pragma: no cover
        action_taken = True;
        log_map_server(f"{config.SYMBOLS['rocket']}====== Running Data Tasks ======", "info", current_logger=logger)
        data_tasks_for_group_flag = [
            ("GTFS_FULL_SETUP", "Full GTFS Pipeline Setup", gtfs_full_setup_sequence),
            ("RASTER_PREP", "Raster Tile Pre-rendering", raster_tile_prerender),
        ]
        for tag, desc, func in data_tasks_for_group_flag:
            if not overall_success: break
            if not execute_step(tag, desc, func, logger, cli_prompt_for_rerun): overall_success = False

    elif parsed_args.group_systemd_reload_flag:  # pragma: no cover
        action_taken = True
        overall_success = systemd_reload_step_group(logger)

    if not action_taken and not (
            parsed_args.view_config or parsed_args.view_state or parsed_args.clear_state):  # pragma: no cover
        log_map_server(f"{config.SYMBOLS['info']} No installation action specified. Displaying help.", "info",
                       current_logger=logger)
        parser.print_help(file=sys.stderr)
        return 2

    if not overall_success:  # pragma: no cover
        log_map_server(f"{config.SYMBOLS['critical']} One or more steps failed.", "critical", current_logger=logger)
        return 1
    else:
        # Ensure a message is logged if only view/clear state was done and was successful
        if action_taken or parsed_args.view_config or parsed_args.view_state or parsed_args.clear_state:
            log_map_server(f"{config.SYMBOLS['sparkles']} All requested operations completed successfully.", "success",
                           current_logger=logger)
        return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main_map_server_entry())