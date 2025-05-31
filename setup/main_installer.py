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
from common.command_utils import check_package_installed, log_map_server
from common.pgpass_utils import setup_pgpass
from common.system_utils import systemd_reload

# --- Setup phase module imports ---
from setup import config
from setup.cli_handler import cli_prompt_for_rerun, view_configuration
from setup.ufw_setup_actions import enable_ufw_service
from setup.postgres_installer import ensure_postgres_packages_are_installed
from setup.state_manager import get_current_script_hash

# --- Configure phase module imports ---
from configure.ufw_configurator import apply_ufw_rules
from configure.postgres_configurator import (
    create_postgres_user_and_db,
    enable_postgres_extensions,
    set_postgres_permissions,
    customize_postgresql_conf,
    customize_pg_hba_conf,
    restart_and_enable_postgres_service
)

# --- Data processing, state, execution tools ---
from setup.data_processing import data_prep_group, gtfs_data_prep, raster_tile_prerender
from setup.state_manager import (
    clear_state_file,
    initialize_state_system,
    view_completed_steps,
)
from setup.step_executor import execute_step

# Old service imports (to be phased out or refactored as new setup/configure modules are made)
from setup.core_setup import (
    boot_verbosity,
    core_conflict_removal,
    core_conflict_removal_group,
    core_install,
    docker_install,
    node_js_lts_install,
    prereqs_install_group,
)
from setup.services.apache import apache_modtile_setup
from setup.services.carto import carto_setup
from setup.services.certbot import certbot_setup
from setup.services.nginx import nginx_setup
from setup.services.osrm import osm_osrm_server_setup
from setup.services.pg_tileserv import pg_tileserv_setup
# Original setup.services.postgres.postgres_setup is no longer directly used for the --postgres flag
from setup.services.renderd import renderd_setup
from setup.services.website import website_setup
# services_setup_group will orchestrate UNREFACTORED services.
from setup.services.service_orchestrator import services_setup_group

logger = logging.getLogger(__name__)  # Main installer logger

# Defines the conceptual order and grouping of installation tasks.
INSTALLATION_GROUPS_ORDER: List[Dict[str, Any]] = [
    {"name": "Core Conflict Removal", "steps": ["CORE_CONFLICTS"]},
    {
        "name": "Prerequisites",
        "steps": [
            "BOOT_VERBOSITY", "CORE_INSTALL", "DOCKER_INSTALL", "NODEJS_INSTALL",
        ],
    },
    {
        "name": "Services (Legacy Orchestration for Unrefactored)",
        "steps": [
            "PGTILESERV_SETUP", "CARTO_SETUP", "RENDERD_SETUP",
            "OSM_OSRM_SERVER_SETUP", "APACHE_SETUP", "NGINX_SETUP",
            "CERTBOT_SETUP", "WEBSITE_SETUP",
        ],
    },
    {"name": "Systemd Reload", "steps": ["SYSTEMD_RELOAD_TASK"]},
    {"name": "Data Preparation", "steps": ["GTFS_PREP", "RASTER_PREP"]},
]

task_execution_details_lookup: Dict[str, Tuple[str, int]] = {}
for group_info in INSTALLATION_GROUPS_ORDER:
    group_name = group_info["name"]
    for i, task_tag in enumerate(group_info["steps"]):
        task_execution_details_lookup[task_tag] = (group_name, i + 1)
task_execution_details_lookup["UFW_FULL_SETUP"] = ("Firewall Service", 1)
task_execution_details_lookup["POSTGRES_FULL_SETUP"] = ("Database Service", 1)

group_order_lookup: Dict[str, int] = {
    group_info["name"]: index
    for index, group_info in enumerate(INSTALLATION_GROUPS_ORDER)
}
group_order_lookup["Firewall Service"] = group_order_lookup["Prerequisites"] + 1
group_order_lookup["Database Service"] = group_order_lookup["Prerequisites"] + 2


def get_dynamic_help(base_help: str, task_tag: str) -> str:
    details = task_execution_details_lookup.get(task_tag)
    if details:
        return f"{base_help} (Conceptual Group: '{details[0]}', Step: {details[1]})"
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


def ufw_full_setup_sequence(current_logger: Optional[logging.Logger] = None) -> None:
    """Orchestrates the new UFW setup (activation) and configuration (rules) sequence."""
    logger_to_use = current_logger if current_logger else logger  # Corrected: use 'logger'
    log_map_server(f"--- {config.SYMBOLS['step']} Starting UFW Full Setup & Config Sequence ---", "info", logger_to_use)

    if not execute_step(
            step_tag="CONFIG_UFW_RULES",
            step_description="Configure UFW Rules",
            step_function=apply_ufw_rules,
            current_logger_instance=logger_to_use,
            prompt_user_for_rerun=cli_prompt_for_rerun,
    ):
        raise RuntimeError("UFW rule configuration failed.")

    if not execute_step(
            step_tag="SETUP_UFW_ENABLE_SERVICE",
            step_description="Enable UFW Service",
            step_function=enable_ufw_service,
            current_logger_instance=logger_to_use,
            prompt_user_for_rerun=cli_prompt_for_rerun,
    ):
        raise RuntimeError("UFW service enabling failed.")

    log_map_server(f"--- {config.SYMBOLS['success']} UFW Full Setup & Config Sequence Completed ---", "success",
                   logger_to_use)


def postgres_full_setup_sequence(current_logger: Optional[logging.Logger] = None) -> None:
    """Orchestrates the new PostgreSQL setup and configuration sequence."""
    logger_to_use = current_logger if current_logger else logger  # Corrected: use 'logger'
    log_map_server(f"--- {config.SYMBOLS['step']} Starting PostgreSQL Full Setup & Config Sequence ---", "info",
                   logger_to_use)

    pg_steps_to_execute = [
        ("SETUP_POSTGRES_PKG_CHECK", "Check PostgreSQL Package Installation", ensure_postgres_packages_are_installed),
        ("CONFIG_POSTGRES_USER_DB", "Create PostgreSQL User and Database", create_postgres_user_and_db),
        ("CONFIG_POSTGRES_EXTENSIONS", "Enable PostgreSQL Extensions (PostGIS, Hstore)", enable_postgres_extensions),
        ("CONFIG_POSTGRES_PERMISSIONS", "Set PostgreSQL Database Permissions", set_postgres_permissions),
        ("CONFIG_POSTGRESQL_CONF", "Customize postgresql.conf", customize_postgresql_conf),
        ("CONFIG_PG_HBA_CONF", "Customize pg_hba.conf", customize_pg_hba_conf),
        ("SERVICE_POSTGRES_RESTART_ENABLE", "Restart and Enable PostgreSQL Service",
         restart_and_enable_postgres_service),
    ]

    for tag, description, func_ref in pg_steps_to_execute:
        if not execute_step(
                step_tag=tag,
                step_description=description,
                step_function=func_ref,
                current_logger_instance=logger_to_use,
                prompt_user_for_rerun=cli_prompt_for_rerun,
        ):
            raise RuntimeError(f"PostgreSQL setup step '{description}' ({tag}) failed.")

    log_map_server(f"--- {config.SYMBOLS['success']} PostgreSQL Full Setup & Config Sequence Completed ---", "success",
                   logger_to_use)


def systemd_reload_step_group(current_logger_instance: logging.Logger) -> bool:
    """Wrapper for systemd_reload as a group step."""
    return execute_step(
        step_tag="SYSTEMD_RELOAD_MAIN",
        step_description="Reload Systemd Daemon (Group Action)",
        step_function=lambda logger_param: systemd_reload(current_logger=logger_param),
        current_logger_instance=current_logger_instance,
        prompt_user_for_rerun=cli_prompt_for_rerun,
    )


def main_map_server_entry(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Map Server Installer Script. Automates installation and configuration.",
        epilog="Example: python3 ./setup/main_installer.py --full -v mymap.example.com",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=False,
    )
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
    task_flags_definitions: List[Tuple[str, str, str]] = [
        ("boot-verbosity", "BOOT_VERBOSITY", "Run boot verbosity setup only."),
        ("core-conflicts", "CORE_CONFLICTS", "Run core conflict removal only."),
        ("core-install", "CORE_INSTALL", "Run core package installation only."),
        ("docker-install", "DOCKER_INSTALL", "Run Docker installation only."),
        ("nodejs-install", "NODEJS_INSTALL", "Run Node.js installation only."),
        ("ufw", "UFW_FULL_SETUP", "Run UFW full setup (rules and enable)."),
        ("postgres", "POSTGRES_FULL_SETUP", "Run PostgreSQL full setup & configuration."),
        ("pgtileserv", "PGTILESERV_SETUP", "Run pg_tileserv setup only (Old Style)."),
        ("carto", "CARTO_SETUP", "Run CartoCSS & OSM Style setup only (Old Style)."),
        ("renderd", "RENDERD_SETUP", "Run Renderd setup only (Old Style)."),
        ("osrm", "OSM_OSRM_SERVER_SETUP", "Run OSM Data & OSRM setup only (Old Style)."),
        ("apache", "APACHE_SETUP", "Run Apache for mod_tile setup only (Old Style)."),
        ("nginx", "NGINX_SETUP", "Run Nginx reverse proxy setup only (Old Style)."),
        ("certbot", "CERTBOT_SETUP", "Run Certbot SSL setup only (Old Style)."),
        ("gtfs-prep", "GTFS_PREP", "Run GTFS data preparation only."),
        ("raster-prep", "RASTER_PREP", "Run raster tile pre-rendering only."),
        ("website-setup", "WEBSITE_SETUP", "Run website setup only."),
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
                                  help="Run (mostly unrefactored) services setup group.")
    group_task_flags.add_argument("--data", action="store_true", help="Run data preparation group only.")
    group_task_flags.add_argument("--systemd-reload", dest="group_systemd_reload_flag", action="store_true",
                                  help="Run systemd reload (as a group action after service changes).")

    dev_group = parser.add_argument_group("Developer and Advanced Options")
    dev_group.add_argument("--dev-override-unsafe-password", "--im-a-developer-get-me-out-of-here", action="store_true",
                           dest="dev_override_unsafe_password",
                           help="DEV FLAG: Allow using default PGPASSWORD for .pgpass and suppress related warnings. USE WITH CAUTION.")

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
        f"{config.SYMBOLS['sparkles']} Starting Map Server Setup (Script Version: {config.SCRIPT_VERSION})...",
        current_logger=logger)
    current_hash = get_current_script_hash(logger_instance=logger)
    log_map_server(f"Current SCRIPT_HASH: {current_hash or 'Could not determine'}", "info", current_logger=logger)

    if (
            config.PGPASSWORD == config.PGPASSWORD_DEFAULT and not parsed_args.view_config and not config.DEV_OVERRIDE_UNSAFE_PASSWORD):
        log_map_server(f"{config.SYMBOLS['warning']} WARNING: Using default PostgreSQL password. This is INSECURE.",
                       "warning", current_logger=logger)
    elif (config.DEV_OVERRIDE_UNSAFE_PASSWORD and config.PGPASSWORD == config.PGPASSWORD_DEFAULT):
        log_map_server(f"{config.SYMBOLS['warning']} DEV OVERRIDE: Using default PostgreSQL password.", "warning",
                       current_logger=logger)
    if os.geteuid() != 0:
        all_system_pkgs = (
                    config.CORE_PREREQ_PACKAGES + config.PYTHON_SYSTEM_PACKAGES + config.POSTGRES_PACKAGES + config.MAPPING_PACKAGES + config.FONT_PACKAGES)
        if any(not check_package_installed(p, current_logger=logger) for p in all_system_pkgs):
            log_map_server(
                f"{config.SYMBOLS['info']} Script not run as root & system packages may need installing. 'sudo' will be used.",
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

    defined_tasks_map: Dict[str, Tuple[str, str, Callable]] = {
        "boot_verbosity": ("BOOT_VERBOSITY", "Improve Boot Verbosity & Core Utils", boot_verbosity),
        "core_conflicts": ("CORE_CONFLICTS", "Remove Core Conflicts", core_conflict_removal),
        "core_install": ("CORE_INSTALL", "Install Core System Packages", core_install),
        "docker_install": ("DOCKER_INSTALL", "Install Docker Engine", docker_install),
        "nodejs_install": ("NODEJS_INSTALL", "Install Node.js LTS", node_js_lts_install),
        "ufw": ("UFW_FULL_SETUP", "Run UFW full setup (rules and enable)", ufw_full_setup_sequence),
        "postgres": ("POSTGRES_FULL_SETUP", "Run PostgreSQL full setup & configuration", postgres_full_setup_sequence),
        "pgtileserv": ("PGTILESERV_SETUP", "Setup pg_tileserv (Old)", pg_tileserv_setup),
        "carto": ("CARTO_SETUP", "Setup CartoCSS & OSM Style (Old)", carto_setup),
        "renderd": ("RENDERD_SETUP", "Setup Renderd (Old)", renderd_setup),
        "osrm": ("OSM_OSRM_SERVER_SETUP", "Setup OSM Data & OSRM (Old)", osm_osrm_server_setup),
        "apache": ("APACHE_SETUP", "Setup Apache for mod_tile (Old)", apache_modtile_setup),
        "nginx": ("NGINX_SETUP", "Setup Nginx Reverse Proxy (Old)", nginx_setup),
        "certbot": ("CERTBOT_SETUP", "Setup Certbot for SSL (Old)", certbot_setup),
        "gtfs_prep": ("GTFS_PREP", "Prepare GTFS Data", gtfs_data_prep),
        "raster_prep": ("RASTER_PREP", "Pre-render Raster Tiles", raster_tile_prerender),
        "website_setup": ("WEBSITE_SETUP", "Setup Test Website", website_setup),
        "task_systemd_reload": ("SYSTEMD_RELOAD_TASK", "Reload Systemd Daemon (Task)", systemd_reload),
    }

    overall_success = True
    action_taken = False
    ran_individual_tasks = False

    tasks_to_run_from_flags: List[Dict[str, Any]] = []
    for arg_dest_name in defined_tasks_map.keys():
        if getattr(parsed_args, arg_dest_name, False):
            ran_individual_tasks = True
            tag, desc, func_ref = defined_tasks_map[arg_dest_name]
            tasks_to_run_from_flags.append({"tag": tag, "desc": desc, "func": func_ref})

    if ran_individual_tasks:
        action_taken = True
        log_map_server(f"{config.SYMBOLS['rocket']}====== Running Specified Individual Task(s) ======",
                       current_logger=logger)
        # Add sorting logic here if execution order of mixed individual flags matters
        # For now, assume tasks from flags are independent enough or user specifies one by one.
        # If sorting is needed: tasks_to_run_from_flags.sort(key=get_sort_key_for_overall_task)
        for task_info in tasks_to_run_from_flags:
            if not overall_success:
                log_map_server(
                    f"{config.SYMBOLS['warning']} Skipping task '{task_info['desc']}' due to previous failure.",
                    "warning", logger)
                continue

            step_success = execute_step(
                task_info["tag"],
                task_info["desc"],
                task_info["func"],
                logger,
                prompt_user_for_rerun=cli_prompt_for_rerun,
            )
            if not step_success:
                overall_success = False

    elif parsed_args.full:
        action_taken = True
        log_map_server(f"{config.SYMBOLS['rocket']}====== Starting Full Installation Process ======",
                       current_logger=logger)

        # This sequence needs to be carefully defined with new and old orchestrators
        # during the transition.
        full_install_sequence = [
            ("CORE_CONFLICT_REMOVAL_GROUP", "Core Conflict Removal Group", core_conflict_removal_group),
            ("PREREQUISITES_GROUP", "Prerequisites Installation Group", prereqs_install_group),
            ("UFW_FULL_SETUP", "Full UFW Setup & Configuration", ufw_full_setup_sequence),
            ("POSTGRES_FULL_SETUP", "Full PostgreSQL Setup & Configuration", postgres_full_setup_sequence),
            # services_setup_group will run *remaining* unrefactored services.
            # It needs to be intelligent enough not to re-run UFW/Postgres, or be passed skips.
            ("SERVICES_GROUP_REMAINING", "Setup Remaining Services", services_setup_group),
            # services_setup_group needs to be adapted
            ("SYSTEMD_RELOAD_GROUP", "Systemd Reload Group", systemd_reload_step_group),
            ("DATA_PREP_GROUP", "Data Preparation Group", data_prep_group),
        ]

        for tag, desc, func_or_group_func in full_install_sequence:
            if not overall_success:
                log_map_server(f"{config.SYMBOLS['warning']} Skipping '{desc}' due to previous failure.", "warning",
                               logger)
                continue

            log_map_server(f"--- {config.SYMBOLS['info']} Executing: {desc} ({tag}) ---", "info", logger)

            # Group functions like prereqs_install_group usually return bool.
            # Overall sequence functions (like ufw_full_setup_sequence) use execute_step internally
            # and will raise on failure, so they should be wrapped by execute_step here for consistent
            # overall state marking and error handling for the *entire* sequence.
            if "GROUP" in tag:
                if not func_or_group_func(logger):
                    overall_success = False
            else:  # For overall sequences like UFW_FULL_SETUP, POSTGRES_FULL_SETUP
                if not execute_step(tag, desc, func_or_group_func, logger, cli_prompt_for_rerun):
                    overall_success = False

            if not overall_success:
                log_map_server(f"{config.SYMBOLS['error']} Phase/Group '{desc}' failed.", "error", logger)
                break

    elif parsed_args.conflicts_removed_flag:
        action_taken = True;
        overall_success = core_conflict_removal_group(logger)
    elif parsed_args.prereqs:
        action_taken = True;
        overall_success = prereqs_install_group(logger)
    elif parsed_args.services:
        action_taken = True
        # This will run the OLD services_setup_group. UFW and Postgres might be
        # re-configured if their old setup functions are still in services_setup_group.
        # This highlights the need to refactor services_setup_group itself.
        log_map_server(
            f"{config.SYMBOLS['warning']} Running --services will use the old service orchestrator. UFW and Postgres might be re-actioned by their old setup functions if not removed from that group.",
            "warning", logger)
        overall_success = services_setup_group(logger)
        if overall_success: overall_success = systemd_reload_step_group(logger)
    elif parsed_args.data:
        action_taken = True;
        overall_success = data_prep_group(logger)
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