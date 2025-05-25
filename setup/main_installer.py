# setup/main_installer.py
"""
Main entry point and orchestrator for the Map Server Setup script.
Handles argument parsing, logging setup, and calls a sequence of setup steps
from various modules within the 'setup' package.
"""
import argparse
import logging
import os
import sys

from setup import config
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
from setup.services.service_orchestrator import services_setup_group
# Import individual service setup functions:
from setup.services.ufw import ufw_setup
from setup.state_manager import (
    initialize_state_system,
    view_completed_steps,
    clear_state_file,
    get_current_script_hash
)
from setup.ui import view_configuration, execute_step

logger = logging.getLogger(__name__)


def setup_main_logging() -> None:
    level_str = os.environ.get("LOGLEVEL", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)

    if not isinstance(level, int):
        # This print goes to stderr, good for pre-logger issues
        print(
            f"Warning: Invalid LOGLEVEL string '{level_str}'. Defaulting to INFO.",
            file=sys.stderr,
        )
        level = logging.INFO

    log_prefix_for_formatter = config.LOG_PREFIX

    log_formatter = logging.Formatter(
        f"{log_prefix_for_formatter} %(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)
    logger.setLevel(level)
    logger.propagate = False


def systemd_reload_step_group(current_logger) -> bool:
    """Group function for systemd_reload, can be kept for --systemd-reload group flag."""
    # The lambda's parameter is named to avoid conflict with 'current_logger' from outer scope.
    return execute_step(
        "SYSTEMD_RELOAD_MAIN",
        "Reload Systemd Daemon (Group Action)",
        lambda logger_param: systemd_reload(current_logger=logger_param),
        current_logger,
    )


def main_map_server_entry(args=None) -> int:  # type: ignore
    parser = argparse.ArgumentParser(
        description="Map Server Installer Script. Automates installation and configuration.",
        epilog="Example: python3 ./setup/main_installer.py --full -v mymap.example.com",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=False,
    )
    parser.add_argument(
        "-h", "--help", action="help", default=argparse.SUPPRESS,
        help="show this help message and exit",
    )

    # Configuration arguments
    parser.add_argument("-a", "--admin-group-ip", default=config.ADMIN_GROUP_IP_DEFAULT,
                        help="Admin group IP range (CIDR).")
    parser.add_argument("-f", "--gtfs-feed-url", default=config.GTFS_FEED_URL_DEFAULT, help="GTFS feed URL.")
    parser.add_argument("-v", "--vm-ip-or-domain", default=config.VM_IP_OR_DOMAIN_DEFAULT, help="VM IP or Domain Name.")
    parser.add_argument("-b", "--pg-tileserv-binary-location", default=config.PG_TILESERV_BINARY_LOCATION_DEFAULT,
                        help="pg_tileserv binary URL.")
    parser.add_argument("-l", "--log-prefix", default=config.LOG_PREFIX_DEFAULT, help="Log message prefix.")
    parser.add_argument("-H", "--pghost", default=config.PGHOST_DEFAULT, help="PostgreSQL host.")
    parser.add_argument("-P", "--pgport", default=config.PGPORT_DEFAULT, help="PostgreSQL port.")
    parser.add_argument("-D", "--pgdatabase", default=config.PGDATABASE_DEFAULT, help="PostgreSQL database name.")
    parser.add_argument("-U", "--pguser", default=config.PGUSER_DEFAULT, help="PostgreSQL username.")
    parser.add_argument("-W", "--pgpassword", default=config.PGPASSWORD_DEFAULT,
                        help="PostgreSQL password. IMPORTANT: Change this default!")

    # --- Add new individual task arguments ---
    parser.add_argument("--boot-verbosity", action="store_true", help="Run boot verbosity setup only.")
    parser.add_argument("--core-conflicts", action="store_true", help="Run core conflict removal only.")
    parser.add_argument("--core-install", action="store_true", help="Run core package installation only.")
    parser.add_argument("--docker-install", action="store_true", help="Run Docker installation only.")
    parser.add_argument("--nodejs-install", action="store_true", help="Run Node.js installation only.")
    parser.add_argument("--ufw", action="store_true", help="Run UFW setup only.")
    parser.add_argument("--postgres", action="store_true", help="Run PostgreSQL setup only.")
    parser.add_argument("--pgtileserv", action="store_true", help="Run pg_tileserv setup only.")
    parser.add_argument("--carto", action="store_true", help="Run CartoCSS & OSM Style setup only.")
    parser.add_argument("--renderd", action="store_true", help="Run Renderd setup only.")
    parser.add_argument("--osrm", action="store_true", help="Run OSM Data & OSRM setup only.")
    parser.add_argument("--apache", action="store_true", help="Run Apache for mod_tile setup only.")
    parser.add_argument("--nginx", action="store_true", help="Run Nginx reverse proxy setup only.")
    parser.add_argument("--certbot", action="store_true", help="Run Certbot SSL setup only.")
    parser.add_argument("--gtfs-prep", action="store_true", help="Run GTFS data preparation only.")
    parser.add_argument("--raster-prep", action="store_true", help="Run raster tile pre-rendering only.")
    parser.add_argument("--website-prep", action="store_true", help="Run test website preparation only.")
    parser.add_argument("--task-systemd-reload", dest="task_systemd_reload_flag", action="store_true",
                        help="Run systemd reload as a single task.")

    # Existing group flags
    parser.add_argument("--full", action="store_true", help="Run full installation process (all groups in sequence).")
    parser.add_argument("--conflicts-removed", dest="conflicts_removed_flag", action="store_true",
                        help="Run core conflict removal group only.")
    parser.add_argument("--prereqs", action="store_true", help="Run prerequisites installation group only.")
    parser.add_argument("--services", action="store_true", help="Run services setup group only.")
    parser.add_argument("--data", action="store_true", help="Run data preparation group only.")
    parser.add_argument("--systemd-reload", dest="group_systemd_reload_flag", action="store_true",
                        help="Run systemd reload (original group action).")

    # Utility flags
    parser.add_argument("--view-config", action="store_true", help="View current configuration settings and exit.")
    parser.add_argument("--view-state", action="store_true",
                        help="View completed installation steps from state file and exit.")
    parser.add_argument("--clear-state", action="store_true", help="Clear all progress state from state file and exit.")
    parser.add_argument("--im-a-developer-get-me-out-of-here", "--dev-override-unsafe-password", action="store_true",
                        dest="dev_override_unsafe_password",
                        help="Developer flag: Allow using default PGPASSWORD for .pgpass and suppress related warnings. USE WITH CAUTION.")

    try:
        print(f"DEBUG SYS.ARGV for main_installer.py (before parse_args): {sys.argv}", file=sys.stderr)
        print(f"DEBUG args passed to main_map_server_entry: {args}", file=sys.stderr)
        if args is None and ("-h" in sys.argv or "--help" in sys.argv):
            parser.print_help(sys.stderr)
            print(f"\n{config.SYMBOLS['info']} Script was called with argv: {sys.argv}", file=sys.stderr)
            print(f"{config.SYMBOLS['info']} Argparse is exiting with status code: 0 (due to help request)",
                  file=sys.stderr)
            return 0

        parsed_args = parser.parse_args(args)
        print(f"DEBUG Parsed args object: {parsed_args}", file=sys.stderr)

    except SystemExit as e:
        print("\n--- ArgParse Error Exit Intercepted in setup/main_installer.py ---", file=sys.stderr)
        print(f"    Script was called with argv: {sys.argv}", file=sys.stderr)
        print(f"    ArgParse error caused exit with status code: {e.code}", file=sys.stderr)
        print("--- End ArgParse Error Context ---", file=sys.stderr)
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

    setup_main_logging()

    log_map_server(f"{config.SYMBOLS['sparkles']} Starting Map Server Setup (Version: {config.SCRIPT_VERSION})...",
                   current_logger=logger)
    current_hash = get_current_script_hash(logger_instance=logger)
    log_map_server(f"Current SCRIPT_HASH: {current_hash or 'Could not determine'}", "info", current_logger=logger)

    if config.PGPASSWORD == config.PGPASSWORD_DEFAULT and not parsed_args.view_config and not config.DEV_OVERRIDE_UNSAFE_PASSWORD:
        log_map_server(f"{config.SYMBOLS['warning']} WARNING: Using default PostgreSQL password. This is INSECURE.",
                       "warning", current_logger=logger)
        log_map_server(
            "   Provide a password via -W option or use --dev-override-unsafe-password (at your own risk) to use the default for .pgpass.",
            "warning", current_logger=logger)
    elif config.DEV_OVERRIDE_UNSAFE_PASSWORD and config.PGPASSWORD == config.PGPASSWORD_DEFAULT:
        log_map_server(
            f"{config.SYMBOLS['warning']} DEV OVERRIDE: Using default PostgreSQL password for .pgpass setup due to --dev-override-unsafe-password flag.",
            "warning", current_logger=logger)

    if os.geteuid() != 0:
        all_system_packages_to_check = (
                config.CORE_PREREQ_PACKAGES + config.PYTHON_SYSTEM_PACKAGES +
                config.POSTGRES_PACKAGES + config.MAPPING_PACKAGES + config.FONT_PACKAGES
        )
        if any(not check_package_installed(p, current_logger=logger) for p in all_system_packages_to_check):
            log_map_server(
                f"{config.SYMBOLS['info']} Script not run as root & system packages may need installing. 'sudo' will be used.",
                "info", current_logger=logger)
    else:
        log_map_server(f"{config.SYMBOLS['info']} Script is running as root.", "info", current_logger=logger)

    initialize_state_system(current_logger=logger)
    setup_pgpass(
        pg_host=config.PGHOST, pg_port=config.PGPORT, pg_database=config.PGDATABASE,
        pg_user=config.PGUSER, pg_password=config.PGPASSWORD,
        pg_password_default=config.PGPASSWORD_DEFAULT,
        allow_default_for_dev=config.DEV_OVERRIDE_UNSAFE_PASSWORD,
        current_logger=logger
    )

    if parsed_args.view_config:
        view_configuration(current_logger=logger)
        return 0
    if parsed_args.view_state:
        completed_steps = view_completed_steps(current_logger=logger)
        if completed_steps:
            log_map_server(f"{config.SYMBOLS['info']} Completed steps recorded in state file:", "info",
                           current_logger=logger)
            for s_idx, s_item in enumerate(completed_steps):
                print(f"  {s_idx + 1}. {s_item}")
        else:
            log_map_server(f"{config.SYMBOLS['info']} No steps marked as completed in state file.", "info",
                           current_logger=logger)
        return 0
    if parsed_args.clear_state:
        try:
            confirm_clear = input(
                f"{config.SYMBOLS['warning']} Are you sure you want to clear all progress state from {config.STATE_FILE_PATH}? (yes/NO): ").strip().lower()
        except EOFError:
            confirm_clear = "no"
            log_map_server(f"{config.SYMBOLS['warning']} No user input (EOF), defaulting to 'NO' for clearing state.",
                           "warning", current_logger=logger)
        if confirm_clear == "yes":
            clear_state_file(current_logger=logger)
        else:
            log_map_server(f"{config.SYMBOLS['info']} State clearing cancelled.", "info", current_logger=logger)
        return 0

    defined_tasks = [
        ('boot_verbosity', "BOOT_VERBOSITY", "Improve Boot Verbosity & Core Utils", boot_verbosity),
        ('core_conflicts', "CORE_CONFLICTS", "Remove Core Conflicts (e.g., system node)", core_conflict_removal),
        ('core_install', "CORE_INSTALL", "Install Core System Packages", core_install),
        ('docker_install', "DOCKER_INSTALL", "Install Docker Engine", docker_install),
        ('nodejs_install', "NODEJS_INSTALL", "Install Node.js LTS (from NodeSource)", node_js_lts_install),
        ('ufw', "UFW_SETUP", "Setup UFW Firewall", ufw_setup),
        ('postgres', "POSTGRES_SETUP", "Setup PostgreSQL Database & User", postgres_setup),
        ('pgtileserv', "PGTILESERV_SETUP", "Setup pg_tileserv", pg_tileserv_setup),
        ('carto', "CARTO_SETUP", "Setup CartoCSS Compiler & OSM Style", carto_setup),
        ('renderd', "RENDERD_SETUP", "Setup Renderd for Raster Tiles", renderd_setup),
        ('osrm', "OSM_OSRM_SERVER_SETUP", "Setup OSM Data & OSRM", osm_osrm_server_setup),
        ('apache', "APACHE_SETUP", "Setup Apache for mod_tile", apache_modtile_setup),
        ('nginx', "NGINX_SETUP", "Setup Nginx Reverse Proxy", nginx_setup),
        ('certbot', "CERTBOT_SETUP", "Setup Certbot for SSL (optional, requires FQDN)", certbot_setup),
        ('gtfs_prep', "GTFS_PREP", "Prepare GTFS Data (Download & Import)", gtfs_data_prep),
        ('raster_prep', "RASTER_PREP", "Pre-render Raster Tiles", raster_tile_prep),
        ('website_prep', "WEBSITE_PREP", "Prepare Test Website", website_prep),
        ('task_systemd_reload_flag', "SYSTEMD_RELOAD_TASK", "Reload Systemd Daemon (Individual Task)", systemd_reload),
    ]

    overall_success = True
    action_taken = False
    ran_individual_tasks = False

    tasks_to_run_from_flags = []
    for flag_name, _, _, _ in defined_tasks:
        if getattr(parsed_args, flag_name.replace('-', '_'),
                   False):  # Ensure hyphens in flags are underscores in attributes
            ran_individual_tasks = True
            action_taken = True
            # Store the full task definition if its flag is set
            # Find the task definition again to get all its details
            task_details = next(item for item in defined_tasks if item[0] == flag_name)
            tasks_to_run_from_flags.append(
                {'flag': flag_name, 'tag': task_details[1], 'desc': task_details[2], 'func': task_details[3]})
            # No break here, collect all specified individual tasks

    if ran_individual_tasks:
        log_map_server(f"{config.SYMBOLS['rocket']}====== Running Specified Individual Task(s) ======",
                       current_logger=logger)
        for task_info in tasks_to_run_from_flags:
            if not overall_success:
                log_map_server(
                    f"{config.SYMBOLS['warning']} Skipping task '{task_info['desc']}' due to previous failure in this run.",
                    "warning", logger)
                continue
            step_success = execute_step(task_info['tag'], task_info['desc'], task_info['func'], logger)
            overall_success = overall_success and step_success

    elif parsed_args.full:
        action_taken = True
        log_map_server(f"{config.SYMBOLS['rocket']}====== Starting Full Installation Process ======",
                       current_logger=logger)
        overall_success = overall_success and core_conflict_removal_group(current_logger=logger)
        if overall_success:
            overall_success = overall_success and prereqs_install_group(current_logger=logger)
        if overall_success:
            overall_success = overall_success and services_setup_group(current_logger=logger)
        if overall_success:
            overall_success = overall_success and systemd_reload_step_group(current_logger=logger)
        if overall_success:
            overall_success = overall_success and data_prep_group(current_logger=logger)

    elif parsed_args.conflicts_removed_flag:
        action_taken = True
        log_map_server(f"{config.SYMBOLS['rocket']}====== Running Core Conflict Removal Group Only ======",
                       current_logger=logger)
        overall_success = core_conflict_removal_group(current_logger=logger)

    elif parsed_args.prereqs:
        action_taken = True
        log_map_server(f"{config.SYMBOLS['rocket']}====== Running Prerequisites Installation Group Only ======",
                       current_logger=logger)
        overall_success = prereqs_install_group(current_logger=logger)

    elif parsed_args.services:
        action_taken = True
        log_map_server(f"{config.SYMBOLS['rocket']}====== Running Services Setup Group Only ======",
                       current_logger=logger)
        overall_success = services_setup_group(current_logger=logger)
        if overall_success:
            overall_success = overall_success and systemd_reload_step_group(current_logger=logger)

    elif parsed_args.data:
        action_taken = True
        log_map_server(f"{config.SYMBOLS['rocket']}====== Running Data Preparation Group Only ======",
                       current_logger=logger)
        overall_success = data_prep_group(current_logger=logger)

    elif parsed_args.group_systemd_reload_flag:
        action_taken = True
        log_map_server(f"{config.SYMBOLS['rocket']}====== Running Systemd Reload (Group Action) Only ======",
                       current_logger=logger)
        overall_success = systemd_reload_step_group(current_logger=logger)

    if not action_taken:
        log_map_server(f"{config.SYMBOLS['info']} No installation action specified. Displaying help.", "info",
                       current_logger=logger)
        print(f"\n{config.SYMBOLS['info']} Script was called with argv: {sys.argv}", file=sys.stderr)
        parser.print_help(file=sys.stderr)
        log_map_server(f"{config.SYMBOLS['warning']} No action performed. Exiting with status code 2 (no operation).",
                       "warning", current_logger=logger)
        return 2

    if not overall_success:
        log_map_server(f"{config.SYMBOLS['critical']} One or more steps failed during the process.", "critical",
                       current_logger=logger)
        return 1
    else:
        log_map_server(f"{config.SYMBOLS['sparkles']} All requested operations completed successfully.", "success",
                       current_logger=logger)
        if action_taken and not parsed_args.full and not ran_individual_tasks:
            log_map_server(f"{config.SYMBOLS['info']} Specified group run completed successfully.", "info",
                           current_logger=logger)
        elif ran_individual_tasks:
            log_map_server(f"{config.SYMBOLS['info']} Specified individual task(s) completed successfully.", "info",
                           current_logger=logger)
    return 0


if __name__ == "__main__":
    sys.exit(main_map_server_entry())
