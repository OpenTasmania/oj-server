# installer/main_installer.py
# -*- coding: utf-8 -*-
"""
Main entry point and orchestrator for the Map Server Setup script.
"""

import argparse
import logging
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple
from pathlib import Path

# Import AppSettings for type hinting
from setup.config_models import (
    AppSettings,
    ADMIN_GROUP_IP_DEFAULT, GTFS_FEED_URL_DEFAULT, VM_IP_OR_DOMAIN_DEFAULT,
    PG_TILESERV_BINARY_LOCATION_DEFAULT, LOG_PREFIX_DEFAULT,
    PGHOST_DEFAULT, PGPORT_DEFAULT, PGDATABASE_DEFAULT, PGUSER_DEFAULT,
    PGPASSWORD_DEFAULT,  # For argparse help and setup_pgpass
    CONTAINER_RUNTIME_COMMAND_DEFAULT, OSRM_IMAGE_TAG_DEFAULT  # For argparse help
)
from setup.config_loader import load_app_settings

from actions.website_setup_actions import deploy_test_website_content
# from actions.ufw_setup_actions import enable_ufw_service # Moved to configure.ufw_configurator
from common.command_utils import log_map_server  # Will use APP_CONFIG passed to it
from common.pgpass_utils import setup_pgpass
from common.system_utils import systemd_reload
from common.core_utils import setup_logging as common_setup_logging

from configure.apache_configurator import configure_apache_ports, create_mod_tile_config, \
    create_apache_tile_site_config, manage_apache_modules_and_sites, activate_apache_service
from configure.carto_configurator import compile_osm_carto_stylesheet, deploy_mapnik_stylesheet, \
    finalize_carto_directory_processing, update_font_cache
from configure.certbot_configurator import run_certbot_nginx
from configure.nginx_configurator import create_nginx_proxy_site_config, manage_nginx_sites, test_nginx_configuration, \
    activate_nginx_service
from configure.osrm_configurator import create_osrm_routed_service_file, activate_osrm_routed_service
from configure.pg_tileserv_configurator import create_pg_tileserv_config_file, activate_pg_tileserv_service
from configure.postgres_configurator import create_postgres_user_and_db, enable_postgres_extensions, \
    set_postgres_permissions, customize_postgresql_conf, customize_pg_hba_conf, restart_and_enable_postgres_service
from configure.renderd_configurator import create_renderd_conf_file, activate_renderd_service
from configure.ufw_configurator import apply_ufw_rules, activate_ufw_service  # activate_ufw_service moved here

from dataproc.osrm_data_processor import extract_regional_pbfs_with_osmium, build_osrm_graphs_for_region
from dataproc.raster_processor import raster_tile_prerender

from installer.apache_installer import ensure_apache_packages_installed
from installer.carto_installer import install_carto_cli, setup_osm_carto_repository, \
    prepare_carto_directory_for_processing, fetch_carto_external_data
from installer.certbot_installer import install_certbot_packages
from installer.nginx_installer import ensure_nginx_package_installed
from installer.osrm_installer import ensure_osrm_dependencies, setup_osrm_data_directories, download_base_pbf, \
    prepare_region_boundaries
from installer.pg_tileserv_installer import download_and_install_pg_tileserv_binary, create_pg_tileserv_system_user, \
    setup_pg_tileserv_binary_permissions, create_pg_tileserv_systemd_service_file
from installer.postgres_installer import ensure_postgres_packages_are_installed
from installer.renderd_installer import ensure_renderd_packages_installed, create_renderd_directories, \
    create_renderd_systemd_service_file
from installer.docker_installer import install_docker_engine
from installer.nodejs_installer import install_nodejs_lts
from installer.ufw_installer import ensure_ufw_package_installed  # New UFW installer

from setup import config as static_config  # For truly static constants
from setup.cli_handler import cli_prompt_for_rerun, view_configuration
from setup.core_prerequisites import core_prerequisites_group, boot_verbosity as prereq_boot_verbosity, \
    core_conflict_removal
from setup.state_manager import clear_state_file, initialize_state_system, view_completed_steps, get_current_script_hash
from setup.step_executor import execute_step
from processors.gtfs.orchestrator import process_and_setup_gtfs

logger = logging.getLogger(__name__)
APP_CONFIG: Optional[AppSettings] = None

GTFS_PROCESS_AND_SETUP_TAG = "GTFS_PROCESS_AND_SETUP"
ALL_CORE_PREREQUISITES_GROUP_TAG = "ALL_CORE_PREREQUISITES_GROUP"
UFW_PACKAGE_CHECK_TAG = "SETUP_UFW_PKG_CHECK"  # New tag for UFW installer check

INSTALLATION_GROUPS_ORDER: List[Dict[str, Any]] = [
    {"name": "Comprehensive Prerequisites", "steps": [ALL_CORE_PREREQUISITES_GROUP_TAG]},
    # Updated UFW Group
    {"name": "Firewall Service (UFW)", "steps": [
        UFW_PACKAGE_CHECK_TAG,  # Add installer check
        "CONFIG_UFW_RULES",
        "SERVICE_UFW_ACTIVATE"  # Renamed from SETUP_UFW_ENABLE_SERVICE
    ]},
    {"name": "Database Service (PostgreSQL)", "steps": [
        "SETUP_POSTGRES_PKG_CHECK", "CONFIG_POSTGRES_USER_DB", "CONFIG_POSTGRES_EXTENSIONS",
        "CONFIG_POSTGRES_PERMISSIONS", "CONFIG_POSTGRESQL_CONF", "CONFIG_PG_HBA_CONF",
        "SERVICE_POSTGRES_RESTART_ENABLE"
    ]},
    # ... (rest of INSTALLATION_GROUPS_ORDER as before) ...
    {"name": "pg_tileserv Service",
     "steps": ["SETUP_PGTS_DOWNLOAD_BINARY", "SETUP_PGTS_CREATE_USER", "SETUP_PGTS_BINARY_PERMS",
               "SETUP_PGTS_SYSTEMD_FILE", "CONFIG_PGTS_CONFIG_FILE", "SERVICE_PGTS_ACTIVATE"]},
    {"name": "Carto Service",
     "steps": ["SETUP_CARTO_CLI", "SETUP_CARTO_REPO", "SETUP_CARTO_PREPARE_DIR", "SETUP_CARTO_FETCH_DATA",
               "CONFIG_CARTO_COMPILE", "CONFIG_CARTO_DEPLOY_XML", "CONFIG_CARTO_FINALIZE_DIR",
               "CONFIG_SYSTEM_FONT_CACHE"]},
    {"name": "Renderd Service", "steps": ["SETUP_RENDERD_PKG_CHECK", "SETUP_RENDERD_DIRS", "SETUP_RENDERD_SYSTEMD_FILE",
                                          "CONFIG_RENDERD_CONF_FILE", "SERVICE_RENDERD_ACTIVATE"]},
    {"name": "OSRM Service & Data Processing",
     "steps": ["SETUP_OSRM_DEPS", "SETUP_OSRM_DIRS", "SETUP_OSRM_DOWNLOAD_PBF", "SETUP_OSRM_REGION_BOUNDARIES",
               "DATAPROC_OSMIUM_EXTRACT_REGIONS", "DATAPROC_OSRM_BUILD_GRAPHS_ALL_REGIONS",
               "SETUP_OSRM_SYSTEMD_SERVICES_ALL_REGIONS", "CONFIG_OSRM_ACTIVATE_SERVICES_ALL_REGIONS"]},
    {"name": "Apache Service", "steps": ["SETUP_APACHE_PKG_CHECK", "CONFIG_APACHE_PORTS", "CONFIG_APACHE_MOD_TILE_CONF",
                                         "CONFIG_APACHE_TILE_SITE_CONF", "CONFIG_APACHE_MODULES_SITES",
                                         "SERVICE_APACHE_ACTIVATE"]},
    {"name": "Nginx Service", "steps": ["SETUP_NGINX_PKG_CHECK", "CONFIG_NGINX_PROXY_SITE", "CONFIG_NGINX_MANAGE_SITES",
                                        "CONFIG_NGINX_TEST_CONFIG", "SERVICE_NGINX_ACTIVATE"]},
    {"name": "Certbot Service", "steps": ["SETUP_CERTBOT_PACKAGES", "CONFIG_CERTBOT_RUN"]},
    {"name": "Application Content", "steps": ["WEBSITE_CONTENT_DEPLOY"]},
    {"name": "GTFS Data Pipeline", "steps": [GTFS_PROCESS_AND_SETUP_TAG]},
    {"name": "Raster Tile Pre-rendering", "steps": ["RASTER_PREP"]},
    {"name": "Systemd Reload", "steps": ["SYSTEMD_RELOAD_TASK"]},
]

task_execution_details_lookup: Dict[str, Tuple[str, int]] = {}  # Populate as before
for group_idx, group_info in enumerate(INSTALLATION_GROUPS_ORDER):
    group_name = group_info["name"]
    for step_idx, task_tag in enumerate(group_info["steps"]):
        task_execution_details_lookup[task_tag] = (group_name, step_idx + 1)
# Add orchestrator group tags
task_execution_details_lookup[ALL_CORE_PREREQUISITES_GROUP_TAG] = ("Comprehensive Prerequisites", 0)
task_execution_details_lookup["UFW_FULL_SETUP"] = ("Firewall Service (UFW)", 0)
task_execution_details_lookup["POSTGRES_FULL_SETUP"] = ("Database Service (PostgreSQL)", 0)
task_execution_details_lookup["CARTO_FULL_SETUP"] = ("Carto Service", 0)
task_execution_details_lookup["RENDERD_FULL_SETUP"] = ("Renderd Service", 0)
task_execution_details_lookup["NGINX_FULL_SETUP"] = ("Nginx Service", 0)
task_execution_details_lookup["PGTILESERV_FULL_SETUP"] = ("pg_tileserv Service", 0)
task_execution_details_lookup["OSRM_FULL_SETUP"] = ("OSRM Service & Data Processing", 0)
task_execution_details_lookup["APACHE_FULL_SETUP"] = ("Apache Service", 0)
task_execution_details_lookup["CERTBOT_FULL_SETUP"] = ("Certbot Service", 0)

group_order_lookup: Dict[str, int] = {  # Populate as before
    group_info["name"]: index for index, group_info in enumerate(INSTALLATION_GROUPS_ORDER)
}


def get_dynamic_help(base_help: str, task_tag: str) -> str:  # No changes needed here
    details = task_execution_details_lookup.get(task_tag)
    if details and details[1] > 0:
        return f"{base_help} (Part of: '{details[0]}', Sub-step: {details[1]})"
    elif details and details[1] == 0:
        return f"{base_help} (Orchestrates: '{details[0]}')"
    return f"{base_help} (Standalone or specific task)"


# --- Orchestrator sequences ---
def ufw_full_setup_sequence(app_cfg: AppSettings,
                            current_logger: Optional[logging.Logger] = None) -> None:  # Takes app_cfg
    logger_to_use = current_logger if current_logger else logger
    log_map_server(f"--- {app_cfg.symbols.get('step', '')} Starting UFW Full Setup & Config Sequence ---", "info",
                   logger_to_use, app_cfg)
    # Step 1: Ensure package is installed
    if not execute_step(UFW_PACKAGE_CHECK_TAG, "Check UFW Package Installation",
                        lambda acl, cl: ensure_ufw_package_installed(acl, cl),  # Lambda to match execute_step
                        app_cfg, logger_to_use,  # Pass app_cfg to execute_step for the lambda
                        lambda prompt: cli_prompt_for_rerun(prompt, app_settings=app_cfg)):
        raise RuntimeError("UFW package check/installation failed.")
    # Step 2: Configure rules
    if not execute_step("CONFIG_UFW_RULES", "Configure UFW Rules",
                        lambda acl, cl: apply_ufw_rules(acl, cl),
                        app_cfg, logger_to_use,
                        lambda prompt: cli_prompt_for_rerun(prompt, app_settings=app_cfg)):
        raise RuntimeError("UFW rule configuration failed.")
    # Step 3: Activate service
    if not execute_step("SERVICE_UFW_ACTIVATE", "Activate UFW Service",  # Renamed task tag
                        lambda acl, cl: activate_ufw_service(acl, cl),
                        app_cfg, logger_to_use,
                        lambda prompt: cli_prompt_for_rerun(prompt, app_settings=app_cfg)):
        raise RuntimeError("UFW service activation failed.")
    log_map_server(f"--- {app_cfg.symbols.get('success', '')} UFW Full Setup & Config Sequence Completed ---",
                   "success", logger_to_use, app_cfg)


def postgres_full_setup_sequence(app_cfg: AppSettings,
                                 current_logger: Optional[logging.Logger] = None) -> None:  # Takes app_cfg
    logger_to_use = current_logger if current_logger else logger
    log_map_server(f"--- {app_cfg.symbols.get('step', '')} Starting PostgreSQL Full Setup & Config Sequence ---",
                   "info", logger_to_use, app_cfg)
    pg_steps_to_execute = [
        ("SETUP_POSTGRES_PKG_CHECK", "Check PostgreSQL Package Installation", ensure_postgres_packages_are_installed),
        ("CONFIG_POSTGRES_USER_DB", "Create PostgreSQL User and Database", create_postgres_user_and_db),
        ("CONFIG_POSTGRES_EXTENSIONS", "Enable PostgreSQL Extensions", enable_postgres_extensions),
        ("CONFIG_POSTGRES_PERMISSIONS", "Set PostgreSQL Database Permissions", set_postgres_permissions),
        ("CONFIG_POSTGRESQL_CONF", "Customize postgresql.conf", customize_postgresql_conf),
        ("CONFIG_PG_HBA_CONF", "Customize pg_hba.conf", customize_pg_hba_conf),
        ("SERVICE_POSTGRES_RESTART_ENABLE", "Restart & Enable PostgreSQL Service", restart_and_enable_postgres_service),
    ]
    for tag, description, step_func_ref in pg_steps_to_execute:
        if not execute_step(tag, description,
                            lambda acl, cl: step_func_ref(acl, cl),  # Lambda to pass app_cfg and logger
                            app_cfg, logger_to_use,  # Pass app_cfg to execute_step for the lambda
                            lambda prompt: cli_prompt_for_rerun(prompt, app_settings=app_cfg)):
            raise RuntimeError(f"PostgreSQL setup step '{description}' ({tag}) failed.")
    log_map_server(f"--- {app_cfg.symbols.get('success', '')} PostgreSQL Full Setup & Config Sequence Completed ---",
                   "success", logger_to_use, app_cfg)


# (Update other *_full_setup_sequence functions similarly to accept app_cfg
#  and pass it to execute_step and underlying step functions via lambdas)

def carto_full_setup_sequence(app_cfg: AppSettings, current_logger: Optional[logging.Logger] = None) -> None:
    logger_to_use = current_logger if current_logger else logger
    log_map_server(f"--- {app_cfg.symbols.get('step', '')} Starting Carto Full Setup & Config Sequence ---", "info",
                   logger_to_use, app_cfg)
    compiled_xml_path_holder = {"path": None}
    carto_steps = [
        ("SETUP_CARTO_CLI", "Install Carto CSS Compiler", install_carto_cli),
        ("SETUP_CARTO_REPO", "Setup OSM-Carto Repository", setup_osm_carto_repository),
        ("SETUP_CARTO_PREPARE_DIR", "Prepare Carto Directory", prepare_carto_directory_for_processing),
        ("SETUP_CARTO_FETCH_DATA", "Fetch External Data for Carto", fetch_carto_external_data),
        ("CONFIG_CARTO_COMPILE", "Compile OSM Carto Stylesheet",
         lambda acl, cl: compiled_xml_path_holder.update({"path": compile_osm_carto_stylesheet(acl, cl)})),
        ("CONFIG_CARTO_DEPLOY_XML", "Deploy Mapnik Stylesheet",
         lambda acl, cl: deploy_mapnik_stylesheet(compiled_xml_path_holder["path"], acl, cl) if
         compiled_xml_path_holder["path"] else (_ for _ in ()).throw(RuntimeError("Compiled XML path not set"))),
        ("CONFIG_CARTO_FINALIZE_DIR", "Finalize Carto Directory", finalize_carto_directory_processing),
        ("CONFIG_SYSTEM_FONT_CACHE", "Update System Font Cache", update_font_cache),
    ]
    try:
        for tag, description, step_func_or_lambda in carto_steps:
            if not execute_step(tag, description,
                                (lambda acl, cl: step_func_or_lambda(acl, cl)) if not isinstance(step_func_or_lambda,
                                                                                                 str) and callable(
                                    step_func_or_lambda) and not (hasattr(step_func_or_lambda,
                                                                          '__name__') and step_func_or_lambda.__name__ == '<lambda>') else step_func_or_lambda,
                                # Bit complex, needs simpler lambda defs
                                app_cfg, logger_to_use,
                                lambda prompt: cli_prompt_for_rerun(prompt, app_settings=app_cfg)):
                raise RuntimeError(f"Carto setup step '{description}' ({tag}) failed.")
    # ... (rest of carto_full_setup_sequence with APP_CONFIG passed where needed)
    except Exception as e:
        log_map_server(f"{app_cfg.symbols.get('error', '')} Error in Carto sequence: {e}. Attempting to finalize.",
                       "error", logger_to_use, app_cfg)
        try:
            finalize_carto_directory_processing(app_cfg, logger_to_use)
        except Exception as e_finalize:
            log_map_server(
                f"{app_cfg.symbols.get('error', '')} Error during Carto directory finalization: {e_finalize}", "error",
                logger_to_use, app_cfg)
        raise
    log_map_server(f"--- {app_cfg.symbols.get('success', '')} Carto Full Setup & Config Sequence Completed ---",
                   "success", logger_to_use, app_cfg)


def systemd_reload_step_group(app_cfg: AppSettings, current_logger_instance: Optional[logging.Logger] = None) -> bool:
    logger_to_use = current_logger_instance if current_logger_instance else logger
    return execute_step("SYSTEMD_RELOAD_MAIN", "Reload Systemd Daemon (Group Action)",
                        lambda acl, cl: systemd_reload(acl, cl),  # systemd_reload needs app_cfg
                        app_cfg, logger_to_use,  # Pass app_cfg to execute_step for the lambda
                        lambda prompt: cli_prompt_for_rerun(prompt, app_settings=app_cfg))


def run_full_gtfs_module_wrapper(app_cfg: AppSettings, calling_logger: Optional[logging.Logger]):
    # This function now receives app_cfg
    db_params_dict = {
        "PGHOST": app_cfg.pg.host, "PGPORT": str(app_cfg.pg.port),
        "PGDATABASE": app_cfg.pg.database, "PGUSER": app_cfg.pg.user,
        "PGPASSWORD": app_cfg.pg.password
    }
    default_gtfs_app_log = "/var/log/gtfs_processor_app.log"
    default_cron_output_log = "/var/log/gtfs_cron_output.log"
    project_root_path = Path(static_config.OSM_PROJECT_ROOT)

    process_and_setup_gtfs(
        gtfs_feed_url=str(app_cfg.gtfs_feed_url), db_params=db_params_dict,
        project_root=project_root_path, gtfs_app_log_file=default_gtfs_app_log,
        cron_run_user=app_cfg.pg.user, cron_job_output_log_file=default_cron_output_log,
        orchestrator_logger=calling_logger
    )


# Modify execute_step to handle the new signature for step_function
# This change should ideally be in setup/step_executor.py
# For now, assume the lambdas handle the adaptation.
# If execute_step is changed:
# def execute_step(step_tag, step_desc, step_function: Callable[[AppSettings, Logger], None], app_cfg, logger, prompt_func)
# then lambdas become: lambda ac, cl: actual_step_func(ac, cl)


def main_map_server_entry(args: Optional[List[str]] = None) -> int:
    global APP_CONFIG

    parser = argparse.ArgumentParser(
        description="Map Server Installer Script...",
        # ... (argparse setup as in previous response, using _DEFAULT constants for help text)
        epilog="Example: python3 ./installer/main_installer.py --full -v mymap.example.com",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter, add_help=False,
    )
    parser.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS,
                        help="Show this help message and exit.")
    parser.add_argument("--full", action="store_true", help="Run full installation process.")
    parser.add_argument("--view-config", action="store_true", help="View current configuration settings and exit.")
    parser.add_argument("--view-state", action="store_true", help="View completed installation steps and exit.")
    parser.add_argument("--clear-state", action="store_true", help="Clear all progress state and exit.")
    parser.add_argument("--config-file", default="config.yaml",
                        help="Path to YAML configuration file (default: config.yaml).")

    config_group = parser.add_argument_group("Configuration Overrides (CLI > YAML > ENV > Defaults)")
    config_group.add_argument("-a", "--admin-group-ip", default=None,
                              help=f"Admin IP range (CIDR). Default: {ADMIN_GROUP_IP_DEFAULT}")
    config_group.add_argument("-f", "--gtfs-feed-url", default=None,
                              help=f"GTFS feed URL. Default: {GTFS_FEED_URL_DEFAULT}")
    config_group.add_argument("-v", "--vm-ip-or-domain", default=None,
                              help=f"Public IP or FQDN. Default: {VM_IP_OR_DOMAIN_DEFAULT}")
    config_group.add_argument("-b", "--pg-tileserv-binary-location", default=None,
                              help=f"pg_tileserv URL. Default: {PG_TILESERV_BINARY_LOCATION_DEFAULT}")
    config_group.add_argument("-l", "--log-prefix", default=None, help=f"Log prefix. Default: {LOG_PREFIX_DEFAULT}")
    config_group.add_argument("--container-runtime-command", default=None,
                              help=f"Container runtime. Default: {CONTAINER_RUNTIME_COMMAND_DEFAULT}")
    config_group.add_argument("--osrm-image-tag", default=None,
                              help=f"OSRM Docker image. Default: {OSRM_IMAGE_TAG_DEFAULT}")

    pg_group = parser.add_argument_group("PostgreSQL Connection Overrides")
    pg_group.add_argument("-H", "--pghost", default=None, help=f"Host. Default: {PGHOST_DEFAULT}")
    pg_group.add_argument("-P", "--pgport", default=None, type=int, help=f"Port. Default: {PGPORT_DEFAULT}")
    pg_group.add_argument("-D", "--pgdatabase", default=None, help=f"Database. Default: {PGDATABASE_DEFAULT}")
    pg_group.add_argument("-U", "--pguser", default=None, help=f"User. Default: {PGUSER_DEFAULT}")
    pg_group.add_argument("-W", "--pgpassword", default=None, help="Password. Default: [sensitive]")

    task_flags_definitions: List[Tuple[str, str, str]] = [
        ("boot_verbosity", "PREREQ_BOOT_VERBOSITY_TAG", "Run boot verbosity setup."),
        ("core_conflicts", "PREREQ_CORE_CONFLICTS_TAG", "Run core conflict removal."),
        # This needs to match the import name `core_conflict_removal` now
        ("docker_install", "PREREQ_DOCKER_ENGINE_TAG", "Run Docker installation."),
        ("nodejs_install", "PREREQ_NODEJS_LTS_TAG", "Run Node.js installation."),
        ("ufw", "UFW_FULL_SETUP", "Run UFW setup."),
        ("postgres", "POSTGRES_FULL_SETUP", "Run PostgreSQL setup."),
        ("carto", "CARTO_FULL_SETUP", "Run Carto setup."),
        ("renderd", "RENDERD_FULL_SETUP", "Run Renderd setup."),
        ("nginx", "NGINX_FULL_SETUP", "Run Nginx setup."),
        ("pgtileserv", "PGTILESERV_FULL_SETUP", "Run pg_tileserv setup."),
        ("osrm", "OSRM_FULL_SETUP", "Run OSRM setup & data processing."),
        ("apache", "APACHE_FULL_SETUP", "Run Apache & mod_tile setup."),
        ("certbot", "CERTBOT_FULL_SETUP", "Run Certbot setup."),
        ("gtfs_prep", GTFS_PROCESS_AND_SETUP_TAG, "Run Full GTFS Pipeline."),
        ("raster_prep", "RASTER_PREP", "Run raster tile pre-rendering."),
        ("website_setup", "WEBSITE_CONTENT_DEPLOY", "Deploy test website."),
        ("task_systemd_reload", "SYSTEMD_RELOAD_TASK", "Run systemd reload task."),
    ]
    task_group = parser.add_argument_group("Individual Task Flags")
    for flag_name, task_tag, base_desc in task_flags_definitions:
        # Ensure dest matches the key in defined_tasks_map if that's how it's looked up
        task_group.add_argument(f"--{flag_name.replace('_', '-')}", action="store_true", dest=flag_name,
                                help=get_dynamic_help(base_desc, task_tag))

    group_task_flags = parser.add_argument_group("Group Task Flags")
    group_task_flags.add_argument("--prereqs", dest="run_all_core_prerequisites", action="store_true",
                                  help="Run comprehensive prerequisites group.")
    group_task_flags.add_argument("--services", action="store_true", help="Run setup for ALL services.")
    group_task_flags.add_argument("--data", action="store_true", help="Run all data preparation and processing tasks.")
    group_task_flags.add_argument("--systemd-reload", dest="group_systemd_reload_flag", action="store_true",
                                  help="Run systemd reload (as a group action).")

    dev_group = parser.add_argument_group("Developer and Advanced Options")
    dev_group.add_argument("--dev-override-unsafe-password", action="store_true", dest="dev_override_unsafe_password",
                           help="DEV FLAG: Allow using default PGPASSWORD.")

    parsed_args = parser.parse_args(args if args is not None else sys.argv[1:])
    APP_CONFIG = load_app_settings(parsed_args, parsed_args.config_file)

    common_setup_logging(log_level=logging.INFO, log_to_console=True, log_prefix=APP_CONFIG.log_prefix)

    log_map_server(
        f"{APP_CONFIG.symbols.get('sparkles', '')} Starting Map Server Setup (v {static_config.SCRIPT_VERSION}) SCRIPT_HASH: {get_current_script_hash(project_root_dir=static_config.OSM_PROJECT_ROOT, app_settings=APP_CONFIG, logger_instance=logger) or 'N/A'} ...",
        current_logger=logger, app_settings=APP_CONFIG)

    # ... (Password warning, root check, initialize_state_system, setup_pgpass (already updated)) ...
    if (
            APP_CONFIG.pg.password == PGPASSWORD_DEFAULT and not parsed_args.view_config and not APP_CONFIG.dev_override_unsafe_password):
        log_map_server(
            f"{APP_CONFIG.symbols.get('warning', '')} WARNING: Using default PostgreSQL password. This is INSECURE.",
            "warning", logger, APP_CONFIG)
    if os.geteuid() != 0:
        log_map_server(f"{APP_CONFIG.symbols.get('info', '')} Script not run as root. 'sudo' will be used.", "info",
                       logger, APP_CONFIG)
    else:
        log_map_server(f"{APP_CONFIG.symbols.get('info', '')} Script is running as root.", "info", logger, APP_CONFIG)

    initialize_state_system(app_settings=APP_CONFIG, current_logger=logger)  # Pass app_settings
    setup_pgpass(app_settings=APP_CONFIG, current_logger=logger)  # Already updated

    if parsed_args.view_config:
        view_configuration(app_config=APP_CONFIG, current_logger=logger)
        return 0
    if parsed_args.view_state:
        completed_steps_list = view_completed_steps(app_settings=APP_CONFIG, current_logger=logger)
        log_map_server(
            f"{APP_CONFIG.symbols.get('info', '')} Displaying completed steps from {static_config.STATE_FILE_PATH}:",
            "info", logger, APP_CONFIG)
        if completed_steps_list:
            [print(f"  {s_idx + 1}. {s_item}") for s_idx, s_item in enumerate(completed_steps_list)]
        else:
            log_map_server(f"{APP_CONFIG.symbols.get('info', '')} No steps marked as completed.", "info", logger,
                           APP_CONFIG)
        return 0
    if parsed_args.clear_state:
        if cli_prompt_for_rerun(f"Are you sure you want to clear state from {static_config.STATE_FILE_PATH}?",
                                app_settings=APP_CONFIG, current_logger_instance=logger):
            current_hash = get_current_script_hash(project_root_dir=static_config.OSM_PROJECT_ROOT,
                                                   app_settings=APP_CONFIG, logger_instance=logger)
            clear_state_file(app_settings=APP_CONFIG, current_logger=logger, script_hash_to_write=current_hash)
        else:
            log_map_server(f"{APP_CONFIG.symbols.get('info', '')} State clearing cancelled.", "info", logger,
                           APP_CONFIG)
        return 0

    # --- Task Definitions now pass APP_CONFIG via lambdas ---
    # execute_step itself is NOT YET refactored to take APP_CONFIG.
    # The lambdas bridge this by capturing APP_CONFIG from main_map_server_entry's scope.
    # The target functions (e.g., prereq_boot_verbosity) MUST be refactored to accept (app_settings, logger).
    defined_tasks_map: Dict[str, Tuple[str, str, Callable[[Optional[logging.Logger]], None]]] = {
        "boot_verbosity": ("PREREQ_BOOT_VERBOSITY_TAG", "Improve Boot Verbosity",
                           lambda cl: prereq_boot_verbosity(APP_CONFIG, cl)),
        "core_conflicts": ("PREREQ_CORE_CONFLICTS_TAG", "Remove Core Conflicts",
                           lambda cl: core_conflict_removal(APP_CONFIG, cl)),
        # core_conflict_removal was the corrected name
        "docker_install": ("PREREQ_DOCKER_ENGINE_TAG", "Install Docker Engine",
                           lambda cl: install_docker_engine(APP_CONFIG, cl)),
        "nodejs_install": ("PREREQ_NODEJS_LTS_TAG", "Install Node.js LTS",
                           lambda cl: install_nodejs_lts(APP_CONFIG, cl)),
        "run_all_core_prerequisites": (ALL_CORE_PREREQUISITES_GROUP_TAG, "Run Comprehensive Prerequisites Group",
                                       lambda cl: core_prerequisites_group(APP_CONFIG, cl)),

        "ufw": ("UFW_FULL_SETUP", "Run UFW full setup",
                lambda cl: ufw_full_setup_sequence(APP_CONFIG, cl)),
        "postgres": ("POSTGRES_FULL_SETUP", "Run PostgreSQL full setup",
                     lambda cl: postgres_full_setup_sequence(APP_CONFIG, cl)),  # This sequence was updated
        "carto": ("CARTO_FULL_SETUP", "Run Carto full setup",
                  lambda cl: carto_full_setup_sequence(APP_CONFIG, cl)),
        "renderd": ("RENDERD_FULL_SETUP", "Run Renderd full setup",
                    lambda cl: renderd_full_setup_sequence(APP_CONFIG, cl)),
        "nginx": ("NGINX_FULL_SETUP", "Run Nginx full setup",
                  lambda cl: nginx_full_setup_sequence(APP_CONFIG, cl)),
        "pgtileserv": ("PGTILESERV_FULL_SETUP", "Run pg_tileserv full setup",
                       lambda cl: pg_tileserv_full_setup_sequence(APP_CONFIG, cl)),
        "osrm": ("OSRM_FULL_SETUP", "Run OSRM full setup & data processing",
                 lambda cl: osrm_full_setup_sequence(APP_CONFIG, cl)),
        "apache": ("APACHE_FULL_SETUP", "Run Apache & mod_tile full setup",
                   lambda cl: apache_full_setup_sequence(APP_CONFIG, cl)),
        "certbot": ("CERTBOT_FULL_SETUP", "Run Certbot full setup",
                    lambda cl: certbot_full_setup_sequence(APP_CONFIG, cl)),

        "gtfs_prep": (GTFS_PROCESS_AND_SETUP_TAG, "Run Full GTFS Setup and Automation",
                      lambda cl: run_full_gtfs_module_wrapper(APP_CONFIG, cl)),

        "raster_prep": ("RASTER_PREP", "Pre-render Raster Tiles",
                        lambda cl: raster_tile_prerender(APP_CONFIG, cl)),
        "website_setup": ("WEBSITE_CONTENT_DEPLOY", "Deploy Test Website Content",
                          lambda cl: deploy_test_website_content(APP_CONFIG, cl)),
        "task_systemd_reload": ("SYSTEMD_RELOAD_TASK", "Reload Systemd Daemon (Task)",
                                lambda cl: systemd_reload(APP_CONFIG, cl)),
    }

    overall_success = True
    action_taken = False
    tasks_to_run_from_flags: List[Dict[str, Any]] = []

    for task_map_key in defined_tasks_map.keys():
        # getattr uses the dest name, which is flag_name.replace('-', '_') from task_flags_definitions
        # or the specific dest for group flags like 'run_all_core_prerequisites'
        if getattr(parsed_args, task_map_key, False):
            action_taken = True
            tag, desc, func_lambda = defined_tasks_map[task_map_key]
            tasks_to_run_from_flags.append({"tag": tag, "desc": desc, "func": func_lambda})

    # Ensure group flags like --prereqs are correctly added if their dest differs
    # Example: parsed_args.run_all_core_prerequisites is the dest for --prereqs
    if parsed_args.run_all_core_prerequisites and not any(
            t['tag'] == ALL_CORE_PREREQUISITES_GROUP_TAG for t in tasks_to_run_from_flags):
        action_taken = True
        tag, desc, func_lambda = defined_tasks_map["run_all_core_prerequisites"]
        tasks_to_run_from_flags.insert(0, {"tag": tag, "desc": desc, "func": func_lambda})

    if tasks_to_run_from_flags:
        log_map_server(
            f"{APP_CONFIG.symbols.get('rocket', '')}====== Running Specified Individual Task(s)/Group(s) ======",
            "info", logger, APP_CONFIG)
        for task_info in tasks_to_run_from_flags:
            if not overall_success:
                log_map_server(
                    f"{APP_CONFIG.symbols.get('warning', '')} Skipping task '{task_info['desc']}' due to previous failure.",
                    "warning", logger, APP_CONFIG)
                continue
            if not execute_step(task_info["tag"], task_info["desc"],
                                task_info["func"],  # This is the lambda (Logger) -> None
                                logger,  # Logger for execute_step itself
                                lambda prompt: cli_prompt_for_rerun(prompt, app_settings=APP_CONFIG,
                                                                    current_logger_instance=logger)):
                overall_success = False
    elif parsed_args.full:
        action_taken = True
        log_map_server(f"{APP_CONFIG.symbols.get('rocket', '')}====== Starting Full Installation Process ======",
                       "info", logger, APP_CONFIG)
        all_setup_and_config_phases = [
            (ALL_CORE_PREREQUISITES_GROUP_TAG, "Comprehensive Core Prerequisites",
             lambda cl: core_prerequisites_group(APP_CONFIG, cl)),
            ("UFW_FULL_SETUP", "Full UFW Setup & Configuration", lambda cl: ufw_full_setup_sequence(APP_CONFIG, cl)),
            ("POSTGRES_FULL_SETUP", "Full PostgreSQL Setup & Configuration",
             lambda cl: postgres_full_setup_sequence(APP_CONFIG, cl)),
            ("PGTILESERV_FULL_SETUP", "Full pg_tileserv Setup & Configuration",
             lambda cl: pg_tileserv_full_setup_sequence(APP_CONFIG, cl)),
            ("CARTO_FULL_SETUP", "Full Carto Setup & Configuration",
             lambda cl: carto_full_setup_sequence(APP_CONFIG, cl)),
            ("RENDERD_FULL_SETUP", "Full Renderd Setup & Configuration",
             lambda cl: renderd_full_setup_sequence(APP_CONFIG, cl)),
            ("OSRM_FULL_SETUP", "Full OSRM Setup, Data Processing & Service Activation",
             lambda cl: osrm_full_setup_sequence(APP_CONFIG, cl)),
            ("APACHE_FULL_SETUP", "Full Apache & mod_tile Setup & Configuration",
             lambda cl: apache_full_setup_sequence(APP_CONFIG, cl)),
            ("NGINX_FULL_SETUP", "Full Nginx Setup & Configuration",
             lambda cl: nginx_full_setup_sequence(APP_CONFIG, cl)),
            ("CERTBOT_FULL_SETUP", "Full Certbot Setup & Configuration",
             lambda cl: certbot_full_setup_sequence(APP_CONFIG, cl)),
            ("WEBSITE_CONTENT_DEPLOY", "Deploy Test Website Content",
             lambda cl: deploy_test_website_content(APP_CONFIG, cl)),
            (GTFS_PROCESS_AND_SETUP_TAG, "Full GTFS Data Pipeline Setup",
             lambda cl: run_full_gtfs_module_wrapper(APP_CONFIG, cl)),
            ("RASTER_PREP", "Raster Tile Pre-rendering", lambda cl: raster_tile_prerender(APP_CONFIG, cl)),
            ("SYSTEMD_RELOAD_GROUP", "Systemd Reload After All Services",
             lambda cl: systemd_reload_step_group(APP_CONFIG, cl)),
        ]
        for tag, desc, phase_func_ref_lambda in all_setup_and_config_phases:
            if not overall_success:
                log_map_server(f"{APP_CONFIG.symbols.get('warning', '')} Skipping '{desc}' due to previous failure.",
                               "warning", logger, APP_CONFIG)
                continue
            log_map_server(f"--- {APP_CONFIG.symbols.get('info', '')} Executing: {desc} ({tag}) ---", "info", logger,
                           APP_CONFIG)
            if not execute_step(tag, desc, phase_func_ref_lambda, logger,
                                lambda prompt: cli_prompt_for_rerun(prompt, app_settings=APP_CONFIG,
                                                                    current_logger_instance=logger)):
                overall_success = False
                log_map_server(f"{APP_CONFIG.symbols.get('error', '')} Phase/Task '{desc}' failed.", "error", logger,
                               APP_CONFIG)
                break
    # ... (rest of group flag handling like --services, --data as in previous response, ensuring lambdas are used correctly) ...
    elif parsed_args.services:
        action_taken = True
        log_map_server(
            f"{APP_CONFIG.symbols.get('rocket', '')}====== Running All Service Setups & Configurations ======", "info",
            logger, APP_CONFIG)
        all_service_related_sequences_keys = ["ufw", "postgres", "pgtileserv", "carto", "renderd", "osrm", "apache",
                                              "nginx", "certbot",
                                              "website_setup"]  # Must match keys in defined_tasks_map
        for task_key in all_service_related_sequences_keys:
            if not overall_success: break
            tag, desc, func_lambda = defined_tasks_map[task_key]
            if not execute_step(tag, desc, func_lambda, logger,
                                lambda prompt: cli_prompt_for_rerun(prompt, app_settings=APP_CONFIG,
                                                                    current_logger_instance=logger)): overall_success = False
        if overall_success:
            overall_success = systemd_reload_step_group(APP_CONFIG, logger)


    elif parsed_args.data:
        action_taken = True
        log_map_server(f"{APP_CONFIG.symbols.get('rocket', '')}====== Running Data Tasks ======", "info", logger,
                       APP_CONFIG)
        data_tasks_keys = ["gtfs_prep", "raster_prep"]
        for task_key in data_tasks_keys:
            if not overall_success: break
            tag, desc, func_lambda = defined_tasks_map[task_key]
            if not execute_step(tag, desc, func_lambda, logger,
                                lambda prompt: cli_prompt_for_rerun(prompt, app_settings=APP_CONFIG,
                                                                    current_logger_instance=logger)): overall_success = False

    elif parsed_args.group_systemd_reload_flag:
        action_taken = True
        overall_success = systemd_reload_step_group(APP_CONFIG, logger)  # Pass APP_CONFIG

    if not action_taken and not (parsed_args.view_config or parsed_args.view_state or parsed_args.clear_state):
        log_map_server(f"{APP_CONFIG.symbols.get('info', '')} No installation action specified. Displaying help.",
                       "info", logger, APP_CONFIG)
        parser.print_help(file=sys.stderr)
        return 2
    if not overall_success:
        log_map_server(f"{APP_CONFIG.symbols.get('critical', '')} One or more steps failed.", "critical", logger,
                       APP_CONFIG)
        return 1
    else:
        if action_taken:
            log_map_server(f"{APP_CONFIG.symbols.get('sparkles', '')} All requested operations completed successfully.",
                           "success", logger, APP_CONFIG)
        elif parsed_args.view_config or parsed_args.view_state or parsed_args.clear_state:
            log_map_server(f"{APP_CONFIG.symbols.get('sparkles', '')} View/Clear operation completed successfully.",
                           "success", logger, APP_CONFIG)  # Ensure this path also logs with APP_CONFIG
        return 0


if __name__ == "__main__":
    sys.exit(main_map_server_entry())