# setup/main_installer.py
"""
Main entry point and orchestrator for the Map Server Setup script.

Handles argument parsing, logging setup, and calls a sequence of setup steps
from various modules within the 'setup' package. It allows for full
installations, group-based installations, or running individual setup tasks.
State management is used to track completed steps and allow for reruns.
"""

import argparse
import logging
import os
import sys
from typing import List, Dict, Tuple, Callable, Any, Optional

from setup import config
from setup.cli_handler import cli_prompt_for_rerun, view_configuration
from setup.command_utils import log_map_server, check_package_installed
from setup.core_setup import (
    boot_verbosity,
    core_conflict_removal,
    core_install,
    docker_install,
    node_js_lts_install,
    core_conflict_removal_group,
    prereqs_install_group
)
from setup.data_processing import (
    gtfs_data_prep,
    raster_tile_prep,
    website_prep,
    data_prep_group
)
from setup.helpers import setup_pgpass, systemd_reload
from setup.services.apache import apache_modtile_setup
from setup.services.carto import carto_setup
from setup.services.certbot import certbot_setup
from setup.services.nginx import nginx_setup
from setup.services.osrm import osm_osrm_server_setup
from setup.services.pg_tileserv import pg_tileserv_setup
from setup.services.postgres import postgres_setup
from setup.services.renderd import renderd_setup
# Assuming services_setup_group is the primary orchestrator for services.
from setup.services.service_orchestrator import services_setup_group
from setup.services.ufw import ufw_setup
from setup.state_manager import (
    initialize_state_system,
    view_completed_steps,
    clear_state_file,
    get_current_script_hash
)
from setup.step_executor import execute_step

logger = logging.getLogger(__name__)

# Defines the order and grouping of installation tasks.
INSTALLATION_GROUPS_ORDER: List[Dict[str, Any]] = [
    {
        "name": "Core Conflict Removal",
        "steps": ["CORE_CONFLICTS"]
    },
    {
        "name": "Prerequisites",
        "steps": [
            "BOOT_VERBOSITY", "CORE_INSTALL", "DOCKER_INSTALL",
            "NODEJS_INSTALL"
        ]
    },
    {
        "name": "Services",
        "steps": [
            "UFW_SETUP", "POSTGRES_SETUP", "PGTILESERV_SETUP", "CARTO_SETUP",
            "RENDERD_SETUP", "OSM_OSRM_SERVER_SETUP", "APACHE_SETUP",
            "NGINX_SETUP", "CERTBOT_SETUP"
        ]
    },
    {
        "name": "Systemd Reload", # For actions after service file changes.
        "steps": ["SYSTEMD_RELOAD_TASK"]
    },
    {
        "name": "Data Preparation",
        "steps": ["GTFS_PREP", "RASTER_PREP", "WEBSITE_PREP"]
    }
]

# Lookup for task execution details (group name, step number within group).
task_execution_details_lookup: Dict[str, Tuple[str, int]] = {}
for group_info in INSTALLATION_GROUPS_ORDER:
    group_name = group_info["name"]
    for i, task_tag in enumerate(group_info["steps"]):
        task_execution_details_lookup[task_tag] = (group_name, i + 1)

# Lookup for the order of groups.
group_order_lookup: Dict[str, int] = {
    group_info["name"]: index
    for index, group_info in enumerate(INSTALLATION_GROUPS_ORDER)
}


def get_dynamic_help(base_help: str, task_tag: str) -> str:
    """
    Generate dynamic help text for argparse arguments, including group and step.

    Args:
        base_help: The base help string for the argument.
        task_tag: The unique tag of the task.

    Returns:
        A formatted help string including group and step number if found.
    """
    details = task_execution_details_lookup.get(task_tag)
    if details:
        return f"{base_help} (Group: '{details[0]}', Step: {details[1]})"
    return base_help


def setup_main_logging() -> None:
    """
    Configure the main logging setup for the application.

    Sets logging level based on LOGLEVEL environment variable (default INFO).
    Uses a custom format including the LOG_PREFIX from config.
    """
    level_str = os.environ.get("LOGLEVEL", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)

    if not isinstance(level, int):
        print(
            f"Warning: Invalid LOGLEVEL string '{level_str}'. Defaulting to INFO.",
            file=sys.stderr
        )
        level = logging.INFO

    log_prefix_for_formatter = config.LOG_PREFIX
    log_formatter = logging.Formatter(
        f"{log_prefix_for_formatter} %(asctime)s - [%(levelname)s] - "
        f"%(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Clear existing handlers from the root logger and our specific logger
    # to prevent duplicate messages if this function is called multiple times
    # or if external libraries also configure logging.
    root_logger_instance = logging.getLogger()
    for handler in root_logger_instance.handlers[:]:
        root_logger_instance.removeHandler(handler)
    for handler in logger.handlers[:]: # `logger` is the module logger here
        logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)
    logger.setLevel(level)
    logger.propagate = False # Avoid messages being passed to root logger if setup elsewhere.


def systemd_reload_step_group(
    current_logger_instance: logging.Logger
) -> bool:
    """
    Execute the systemd daemon reload as a distinct step group.

    Args:
        current_logger_instance: The logger to use for this operation.

    Returns:
        True if the systemd reload was successful, False otherwise.
    """
    return execute_step(
        step_tag="SYSTEMD_RELOAD_MAIN",
        step_description="Reload Systemd Daemon (Group Action)",
        step_function=lambda logger_param: systemd_reload(
            current_logger=logger_param
        ),
        current_logger_instance=current_logger_instance,
        prompt_user_for_rerun=cli_prompt_for_rerun
    )


def main_map_server_entry(args: Optional[List[str]] = None) -> int:
    """
    Main entry point for the map server installation script.

    Parses command-line arguments, sets up configuration and logging,
    and orchestrates the execution of setup steps or groups.

    Args:
        args: Optional list of command-line arguments (for testing or embedding).
              If None, `sys.argv[1:]` is used.

    Returns:
        0 on successful completion of all requested tasks.
        1 if any step fails.
        2 if no installation action was specified (e.g., only help shown).
        Other non-zero codes for argparse errors.
    """
    parser = argparse.ArgumentParser(
        description="Map Server Installer Script. Automates installation "
                    "and configuration of a full map server stack.",
        epilog="Example: python3 ./setup/main_installer.py --full "
               "-v mymap.example.com",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=False, # Custom help handling for dynamic task info.
    )
    # Main operations and info
    parser.add_argument(
        "-h", "--help", action="help", default=argparse.SUPPRESS,
        help="Show this help message and exit.",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="Run full installation process (all groups in sequence)."
    )
    parser.add_argument(
        "--view-config", action="store_true",
        help="View current configuration settings and exit."
    )
    parser.add_argument(
        "--view-state", action="store_true",
        help="View completed installation steps from state file and exit."
    )
    parser.add_argument(
        "--clear-state", action="store_true",
        help="Clear all progress state from state file and exit."
    )

    # Configuration overrides
    config_group = parser.add_argument_group('Configuration Overrides')
    config_group.add_argument(
        "-a", "--admin-group-ip", default=config.ADMIN_GROUP_IP_DEFAULT,
        help="Admin group IP range (CIDR) for firewall and DB access."
    )
    config_group.add_argument(
        "-f", "--gtfs-feed-url", default=config.GTFS_FEED_URL_DEFAULT,
        help="URL of the GTFS feed to download and process."
    )
    config_group.add_argument(
        "-v", "--vm-ip-or-domain", default=config.VM_IP_OR_DOMAIN_DEFAULT,
        help="Public IP address or Fully Qualified Domain Name (FQDN) of this server."
    )
    config_group.add_argument(
        "-b", "--pg-tileserv-binary-location",
        default=config.PG_TILESERV_BINARY_LOCATION_DEFAULT,
        help="URL for the pg_tileserv binary if not installed via apt."
    )
    config_group.add_argument(
        "-l", "--log-prefix", default=config.LOG_PREFIX_DEFAULT,
        help="Prefix for log messages from this script."
    )
    # PostgreSQL connection parameters
    pg_group = parser.add_argument_group('PostgreSQL Connection Overrides')
    pg_group.add_argument(
        "-H", "--pghost", default=config.PGHOST_DEFAULT,
        help="PostgreSQL host."
    )
    pg_group.add_argument(
        "-P", "--pgport", default=config.PGPORT_DEFAULT,
        help="PostgreSQL port."
    )
    pg_group.add_argument(
        "-D", "--pgdatabase", default=config.PGDATABASE_DEFAULT,
        help="PostgreSQL database name."
    )
    pg_group.add_argument(
        "-U", "--pguser", default=config.PGUSER_DEFAULT,
        help="PostgreSQL username."
    )
    pg_group.add_argument(
        "-W", "--pgpassword", default=config.PGPASSWORD_DEFAULT,
        help="PostgreSQL password. IMPORTANT: Change this default for security!"
    )

    # Individual Task Flags
    task_group = parser.add_argument_group('Individual Task Flags')
    task_flags_definitions: List[Tuple[str, str, str]] = [
        ('boot-verbosity', "BOOT_VERBOSITY", "Run boot verbosity setup only."),
        ('core-conflicts', "CORE_CONFLICTS", "Run core conflict removal only."),
        ('core-install', "CORE_INSTALL", "Run core package installation only."),
        ('docker-install', "DOCKER_INSTALL", "Run Docker installation only."),
        ('nodejs-install', "NODEJS_INSTALL", "Run Node.js installation only."),
        ('ufw', "UFW_SETUP", "Run UFW setup only."),
        ('postgres', "POSTGRES_SETUP", "Run PostgreSQL setup only."),
        ('pgtileserv', "PGTILESERV_SETUP", "Run pg_tileserv setup only."),
        ('carto', "CARTO_SETUP", "Run CartoCSS & OSM Style setup only."),
        ('renderd', "RENDERD_SETUP", "Run Renderd setup only."),
        ('osrm', "OSM_OSRM_SERVER_SETUP", "Run OSM Data & OSRM setup only."),
        ('apache', "APACHE_SETUP", "Run Apache for mod_tile setup only."),
        ('nginx', "NGINX_SETUP", "Run Nginx reverse proxy setup only."),
        ('certbot', "CERTBOT_SETUP", "Run Certbot SSL setup only."),
        ('gtfs-prep', "GTFS_PREP", "Run GTFS data preparation only."),
        ('raster-prep', "RASTER_PREP", "Run raster tile pre-rendering only."),
        ('website-prep', "WEBSITE_PREP", "Run test website preparation only."),
        ('task-systemd-reload', "SYSTEMD_RELOAD_TASK", "Run systemd reload as a single task."),
    ]
    for flag_name, task_tag, base_desc in task_flags_definitions:
        task_group.add_argument(
            f"--{flag_name}", action="store_true", dest=flag_name.replace('-', '_'),
            help=get_dynamic_help(base_desc, task_tag)
        )

    # Group Task Flags
    group_task_flags = parser.add_argument_group('Group Task Flags')
    group_task_flags.add_argument(
        "--conflicts-removed", dest="conflicts_removed_flag", action="store_true",
        help="Run core conflict removal group only."
    )
    group_task_flags.add_argument(
        "--prereqs", action="store_true",
        help="Run prerequisites installation group only."
    )
    group_task_flags.add_argument(
        "--services", action="store_true",
        help="Run services setup group only."
    )
    group_task_flags.add_argument(
        "--data", action="store_true",
        help="Run data preparation group only."
    )
    group_task_flags.add_argument(
        "--systemd-reload", dest="group_systemd_reload_flag", action="store_true",
        help="Run systemd reload (as a group action after service changes)."
    )

    # Developer/Advanced Options
    dev_group = parser.add_argument_group('Developer and Advanced Options')
    dev_group.add_argument(
        "--dev-override-unsafe-password", "--im-a-developer-get-me-out-of-here",
        action="store_true", dest="dev_override_unsafe_password",
        help="DEV FLAG: Allow using default PGPASSWORD for .pgpass and "
             "suppress related warnings. USE WITH CAUTION."
    )

    try:
        # Handle custom help display before parsing if -h or --help is present
        if args is None and ("-h" in sys.argv or "--help" in sys.argv):
            parser.print_help(sys.stderr)
            return 0
        parsed_args = parser.parse_args(args)
    except SystemExit as e:
        # Argparse raises SystemExit on --help or errors.
        # Return code 0 for --help, non-zero for errors.
        return e.code

    # Update config module with parsed arguments
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

    setup_main_logging() # Setup logging after config is updated.

    log_map_server(
        f"{config.SYMBOLS['sparkles']} Starting Map Server Setup "
        f"(Script Version: {config.SCRIPT_VERSION})...",
        current_logger=logger
    )
    current_hash = get_current_script_hash(logger_instance=logger)
    log_map_server(
        f"Current SCRIPT_HASH: {current_hash or 'Could not determine'}",
        "info", current_logger=logger
    )

    if (config.PGPASSWORD == config.PGPASSWORD_DEFAULT and
            not parsed_args.view_config and
            not config.DEV_OVERRIDE_UNSAFE_PASSWORD):
        log_map_server(
            f"{config.SYMBOLS['warning']} WARNING: Using default PostgreSQL "
            "password. This is INSECURE.", "warning", current_logger=logger
        )
        log_map_server(
            "   Provide a password via -W option or use "
            "--dev-override-unsafe-password (at your own risk) to use "
            "the default for .pgpass.", "warning", current_logger=logger
        )
    elif (config.DEV_OVERRIDE_UNSAFE_PASSWORD and
          config.PGPASSWORD == config.PGPASSWORD_DEFAULT):
        log_map_server(
            f"{config.SYMBOLS['warning']} DEV OVERRIDE: Using default "
            "PostgreSQL password for .pgpass setup due to "
            "--dev-override-unsafe-password flag.", "warning",
            current_logger=logger
        )

    # Check for root privileges if system packages might need installation.
    if os.geteuid() != 0:
        all_system_pkgs = (
            config.CORE_PREREQ_PACKAGES + config.PYTHON_SYSTEM_PACKAGES +
            config.POSTGRES_PACKAGES + config.MAPPING_PACKAGES +
            config.FONT_PACKAGES
        )
        if any(not check_package_installed(p, current_logger=logger)
               for p in all_system_pkgs):
            log_map_server(
                f"{config.SYMBOLS['info']} Script not run as root & system "
                "packages may need installing. 'sudo' will be used for "
                "elevated commands.", "info", current_logger=logger
            )
    else:
        log_map_server(
            f"{config.SYMBOLS['info']} Script is running as root.", "info",
            current_logger=logger
        )

    initialize_state_system(current_logger=logger)
    setup_pgpass(
        pg_host=config.PGHOST, pg_port=config.PGPORT,
        pg_database=config.PGDATABASE, pg_user=config.PGUSER,
        pg_password=config.PGPASSWORD,
        pg_password_default=config.PGPASSWORD_DEFAULT,
        allow_default_for_dev=config.DEV_OVERRIDE_UNSAFE_PASSWORD,
        current_logger=logger
    )

    # Handle informational/utility flags first.
    if parsed_args.view_config:
        view_configuration(current_logger=logger)
        return 0
    if parsed_args.view_state:
        completed_steps_list = view_completed_steps(current_logger=logger)
        if completed_steps_list:
            log_map_server(
                f"{config.SYMBOLS['info']} Completed steps recorded in state file:",
                "info", current_logger=logger
            )
            for s_idx, s_item in enumerate(completed_steps_list):
                print(f"  {s_idx + 1}. {s_item}")
        else:
            log_map_server(
                f"{config.SYMBOLS['info']} No steps marked as completed in "
                "state file.", "info", current_logger=logger
            )
        return 0
    if parsed_args.clear_state:
        try:
            confirm_clear = input(
                f"{config.SYMBOLS['warning']} Are you sure you want to clear "
                f"all progress state from {config.STATE_FILE_PATH}? (yes/NO): "
            ).strip().lower()
        except EOFError:
            confirm_clear = "no" # Default to no if non-interactive
            log_map_server(
                f"{config.SYMBOLS['warning']} No user input (EOF), defaulting "
                "to 'NO' for clearing state.", "warning", current_logger=logger
            )
        if confirm_clear == "yes":
            clear_state_file(current_logger=logger)
        else:
            log_map_server(
                f"{config.SYMBOLS['info']} State clearing cancelled.", "info",
                current_logger=logger
            )
        return 0

    # Define all individual tasks and their corresponding functions.
    # (flag_attr_name, task_tag, description, function_reference)
    defined_tasks_map: List[Tuple[str, str, str, Callable]] = [
        ('boot_verbosity', "BOOT_VERBOSITY", "Improve Boot Verbosity & Core Utils", boot_verbosity),
        ('core_conflicts', "CORE_CONFLICTS", "Remove Core Conflicts", core_conflict_removal),
        ('core_install', "CORE_INSTALL", "Install Core System Packages", core_install),
        ('docker_install', "DOCKER_INSTALL", "Install Docker Engine", docker_install),
        ('nodejs_install', "NODEJS_INSTALL", "Install Node.js LTS", node_js_lts_install),
        ('ufw', "UFW_SETUP", "Setup UFW Firewall", ufw_setup),
        ('postgres', "POSTGRES_SETUP", "Setup PostgreSQL", postgres_setup),
        ('pgtileserv', "PGTILESERV_SETUP", "Setup pg_tileserv", pg_tileserv_setup),
        ('carto', "CARTO_SETUP", "Setup CartoCSS & OSM Style", carto_setup),
        ('renderd', "RENDERD_SETUP", "Setup Renderd", renderd_setup),
        ('osrm', "OSM_OSRM_SERVER_SETUP", "Setup OSM Data & OSRM", osm_osrm_server_setup),
        ('apache', "APACHE_SETUP", "Setup Apache for mod_tile", apache_modtile_setup),
        ('nginx', "NGINX_SETUP", "Setup Nginx Reverse Proxy", nginx_setup),
        ('certbot', "CERTBOT_SETUP", "Setup Certbot for SSL", certbot_setup),
        ('gtfs_prep', "GTFS_PREP", "Prepare GTFS Data", gtfs_data_prep),
        ('raster_prep', "RASTER_PREP", "Pre-render Raster Tiles", raster_tile_prep),
        ('website_prep', "WEBSITE_PREP", "Prepare Test Website", website_prep),
        ('task_systemd_reload', "SYSTEMD_RELOAD_TASK", "Reload Systemd Daemon (Task)", systemd_reload),
    ]

    overall_success = True
    action_taken = False
    ran_individual_tasks = False

    # Collect tasks to run based on individual flags.
    tasks_to_run_from_flags: List[Dict[str, Any]] = []
    for flag_attr, task_tag, base_desc, func_ref in defined_tasks_map:
        if getattr(parsed_args, flag_attr.replace('-', '_'), False):
            ran_individual_tasks = True
            exec_details = task_execution_details_lookup.get(task_tag)
            dynamic_desc = f"{base_desc}"
            if exec_details: # Add group and step info to description.
                dynamic_desc += f" (Group: '{exec_details[0]}', Step: {exec_details[1]})"
            tasks_to_run_from_flags.append(
                {'flag': flag_attr, 'tag': task_tag, 'desc': dynamic_desc, 'func': func_ref}
            )

    if ran_individual_tasks:
        action_taken = True
        log_map_server(
            f"{config.SYMBOLS['rocket']}====== Running Specified Individual Task(s) ======",
            current_logger=logger
        )
        # Sort tasks based on their defined order in INSTALLATION_GROUPS_ORDER.
        def get_sort_key(task_dict_item: Dict[str, Any]) -> Tuple[int, int]:
            tag_for_sort = task_dict_item['tag']
            group_name, step_in_group = task_execution_details_lookup[tag_for_sort]
            group_idx = group_order_lookup[group_name]
            return (group_idx, step_in_group)

        tasks_to_run_from_flags.sort(key=get_sort_key)

        for task_info in tasks_to_run_from_flags:
            if not overall_success:
                log_map_server(
                    f"{config.SYMBOLS['warning']} Skipping task "
                    f"'{task_info['desc']}' due to previous failure.",
                    "warning", logger
                )
                continue
            step_success = execute_step(
                task_info['tag'], task_info['desc'], task_info['func'],
                logger, prompt_user_for_rerun=cli_prompt_for_rerun
            )
            if not step_success:
                overall_success = False
                # Optionally break here if one individual task failure should stop all.
                # break

    elif parsed_args.full:
        action_taken = True
        log_map_server(
            f"{config.SYMBOLS['rocket']}====== Starting Full Installation Process ======",
            current_logger=logger
        )
        if overall_success: overall_success = core_conflict_removal_group(logger)
        if overall_success: overall_success = prereqs_install_group(logger)
        if overall_success: overall_success = services_setup_group(logger)
        if overall_success: overall_success = systemd_reload_step_group(logger)
        if overall_success: overall_success = data_prep_group(logger)

    # Handle group flags
    elif parsed_args.conflicts_removed_flag:
        action_taken = True
        log_map_server(f"{config.SYMBOLS['rocket']}====== Running Core Conflict Removal Group Only ======", current_logger=logger)
        overall_success = core_conflict_removal_group(logger)
    elif parsed_args.prereqs:
        action_taken = True
        log_map_server(f"{config.SYMBOLS['rocket']}====== Running Prerequisites Installation Group Only ======", current_logger=logger)
        overall_success = prereqs_install_group(logger)
    elif parsed_args.services:
        action_taken = True
        log_map_server(f"{config.SYMBOLS['rocket']}====== Running Services Setup Group Only ======", current_logger=logger)
        overall_success = services_setup_group(logger)
        if overall_success: overall_success = systemd_reload_step_group(logger) # Reload after services
    elif parsed_args.data:
        action_taken = True
        log_map_server(f"{config.SYMBOLS['rocket']}====== Running Data Preparation Group Only ======", current_logger=logger)
        overall_success = data_prep_group(logger)
    elif parsed_args.group_systemd_reload_flag: # Systemd reload as its own group action
        action_taken = True
        log_map_server(f"{config.SYMBOLS['rocket']}====== Running Systemd Reload (Group Action) Only ======", current_logger=logger)
        overall_success = systemd_reload_step_group(logger)


    if not action_taken:
        log_map_server(
            f"{config.SYMBOLS['info']} No installation action specified. "
            "Displaying help.", "info", current_logger=logger
        )
        parser.print_help(file=sys.stderr)
        log_map_server(
            f"{config.SYMBOLS['warning']} No action performed. Exiting with "
            "status code 2 (no operation).", "warning", current_logger=logger
        )
        return 2 # Specific exit code for no operation.

    if not overall_success:
        log_map_server(
            f"{config.SYMBOLS['critical']} One or more steps failed during "
            "the process.", "critical", current_logger=logger
        )
        return 1
    else:
        log_map_server(
            f"{config.SYMBOLS['sparkles']} All requested operations completed "
            "successfully.", "success", current_logger=logger
        )
        if action_taken and not parsed_args.full and not ran_individual_tasks:
            log_map_server(
                f"{config.SYMBOLS['info']} Specified group run completed "
                "successfully.", "info", current_logger=logger
            )
        elif ran_individual_tasks:
            log_map_server(
                f"{config.SYMBOLS['info']} Specified individual task(s) "
                "completed successfully.", "info", current_logger=logger
            )
    return 0


if __name__ == "__main__":
    # If main_map_server_entry is called with no args, it uses sys.argv[1:].
    # If sys.argv has only the script name, sys.argv[1:] is empty.
    # The `args` parameter in main_map_server_entry handles this.
    sys.exit(main_map_server_entry())