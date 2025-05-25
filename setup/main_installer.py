# setup/main.py
"""
Main entry point and orchestrator for the Map Server Setup script.
Handles argument parsing, logging setup, and calls a sequence of setup steps
from various modules within the 'setup' package.
"""
import argparse
import logging
import os
import sys

# Use relative imports for modules within the 'setup' package
from setup import config
from setup.command_utils import log_map_server, check_package_installed
from setup.core_setup import prereqs_install_group, core_conflict_removal_group
from setup.data_processing import data_prep_group
from setup.helpers import setup_pgpass, systemd_reload
from setup.services.service_orchestrator import services_setup_group
from setup.state_manager import (
    initialize_state_system,
    view_completed_steps,
    clear_state_file,
)

from setup.ui import view_configuration, execute_step

logger = logging.getLogger(__name__)


def setup_main_logging() -> None:
    level_str = os.environ.get("LOGLEVEL", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)

    if not isinstance(level, int):
        print(
            f"Warning: Invalid LOGLEVEL string '{level_str}'. Defaulting to INFO.",
            file=sys.stderr,
        )
        level = logging.INFO

    log_formatter = logging.Formatter(
        f"{config.LOG_PREFIX} %(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)
    logger.setLevel(level)
    logger.propagate = False


def systemd_reload_step_group(current_logger) -> bool:
    return execute_step(
        "SYSTEMD_RELOAD_MAIN",
        "Reload Systemd Daemon",
        lambda cl_lambda: systemd_reload(
            current_logger=cl_lambda
        ),  # Lambda correctly takes a logger
        current_logger,
    )


def main_map_server_entry(args=None) -> int:
    parser = argparse.ArgumentParser(
        description="Map Server Installer Script. Automates installation and configuration.",
        epilog="Example: python3 ./setup/main_installer.py --full -v mymap.example.com",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=False,  # We'll handle help explicitly to show argv
    )
    # Add a custom help argument
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        default=argparse.SUPPRESS,
        help="show this help message and exit",
    )

    # Add other arguments
    parser.add_argument(
        "-a",
        "--admin-group-ip",
        default=config.ADMIN_GROUP_IP_DEFAULT,
        help="Admin group IP range (CIDR).",
    )
    parser.add_argument(
        "-f",
        "--gtfs-feed-url",
        default=config.GTFS_FEED_URL_DEFAULT,
        help="GTFS feed URL.",
    )
    parser.add_argument(
        "-v",
        "--vm-ip-or-domain",
        default=config.VM_IP_OR_DOMAIN_DEFAULT,
        help="VM IP or Domain Name.",
    )
    parser.add_argument(
        "-b",
        "--pg-tileserv-binary-location",
        default=config.PG_TILESERV_BINARY_LOCATION_DEFAULT,
        help="pg_tileserv binary URL.",
    )
    parser.add_argument(
        "-l",
        "--log-prefix",
        default=config.LOG_PREFIX_DEFAULT,
        help="Log message prefix.",
    )
    parser.add_argument(
        "-H",
        "--pghost",
        default=config.PGHOST_DEFAULT,
        help="PostgreSQL host.",
    )
    parser.add_argument(
        "-P",
        "--pgport",
        default=config.PGPORT_DEFAULT,
        help="PostgreSQL port.",
    )
    parser.add_argument(
        "-D",
        "--pgdatabase",
        default=config.PGDATABASE_DEFAULT,
        help="PostgreSQL database name.",
    )
    parser.add_argument(
        "-U",
        "--pguser",
        default=config.PGUSER_DEFAULT,
        help="PostgreSQL username.",
    )
    parser.add_argument(
        "-W",
        "--pgpassword",
        default=config.PGPASSWORD_DEFAULT,
        help="PostgreSQL password. IMPORTANT: Change this default!",
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full installation process (all groups in sequence).",
    )
    parser.add_argument(
        "--conflicts-removed",
        dest="conflicts_removed_flag",
        action="store_true",
        help="Run core conflict removal group only.",
    )
    parser.add_argument(
        "--prereqs",
        action="store_true",
        help="Run prerequisites installation group only.",
    )
    parser.add_argument(
        "--services",
        action="store_true",
        help="Run services setup group only.",
    )
    parser.add_argument(
        "--data", action="store_true", help="Run data preparation group only."
    )
    parser.add_argument(
        "--systemd-reload",
        dest="systemd_reload_flag",
        action="store_true",
        help="Run systemd reload only.",
    )

    parser.add_argument(
        "--view-config",
        action="store_true",
        help="View current configuration settings and exit.",
    )
    parser.add_argument(
        "--view-state",
        action="store_true",
        help="View completed installation steps from state file and exit.",
    )
    parser.add_argument(
        "--clear-state",
        action="store_true",
        help="Clear all progress state from state file and exit.",
    )

    parser.add_argument(
        "--im-a-developer-get-me-out-of-here",
        "--dev-override-unsafe-password",
        action="store_true",
        dest="dev_override_unsafe_password",
        help="Developer flag: Allow using default PGPASSWORD for .pgpass and suppress related warnings. USE WITH CAUTION.",
    )
    try:
        # Print sys.argv as seen by this script for debugging.
        # Using print to stderr to ensure it's seen even if logging isn't fully set up or if script exits early.
        print(
            f"DEBUG SYS.ARGV for setup/main.py (before parse_args): {sys.argv}",
            file=sys.stderr,
        )

        # Print the args passed to this function for debugging
        print(
            f"DEBUG args passed to main_map_server_entry: {args}",
            file=sys.stderr,
        )

        # Check if -h or --help is in sys.argv before full parsing, to customize its output
        if args is None and ("-h" in sys.argv or "--help" in sys.argv):
            parser.print_help(sys.stderr)
            print(
                f"\n{config.SYMBOLS['info']} Script was called with argv: {sys.argv}",
                file=sys.stderr,
            )
            print(
                f"{config.SYMBOLS['info']} Argparse is exiting with status code: 0 (due to help request)",
                file=sys.stderr,
            )
            return 0  # Standard exit code for help

        # Parse the arguments passed to this function, or sys.argv if none were passed
        args = parser.parse_args(args)

        print(
            f"DEBUG Parsed args object: {args}", file=sys.stderr
        )  # For checking parsed values

        # Print specific argument values for debugging
        print(
            f"DEBUG args.dev_override_unsafe_password value: {args.dev_override_unsafe_password}",
            file=sys.stderr,
        )

    except SystemExit as e:
        # This catches exits from parse_args() due to errors (e.g., unknown argument)
        # argparse would have already printed its error message and usage to stderr.
        print(
            "\n--- ArgParse Error Exit Intercepted in setup/main.py ---",
            file=sys.stderr,
        )
        print(f"    Script was called with argv: {sys.argv}", file=sys.stderr)
        print(
            f"    ArgParse error caused exit with status code: {e.code}",
            file=sys.stderr,
        )
        print("--- End ArgParse Error Context ---", file=sys.stderr)
        return e.code

        # Update mutable config variables in config.py
    config.ADMIN_GROUP_IP = args.admin_group_ip
    config.GTFS_FEED_URL = args.gtfs_feed_url
    config.VM_IP_OR_DOMAIN = args.vm_ip_or_domain
    config.PG_TILESERV_BINARY_LOCATION = args.pg_tileserv_binary_location
    config.LOG_PREFIX = args.log_prefix
    config.PGHOST = args.pghost
    config.PGPORT = args.pgport
    config.PGDATABASE = args.pgdatabase
    config.PGUSER = args.pguser
    config.PGPASSWORD = args.pgpassword
    config.DEV_OVERRIDE_UNSAFE_PASSWORD = args.dev_override_unsafe_password

    setup_main_logging()

    log_map_server(
        f"{config.SYMBOLS['sparkles']} Starting Map Server Setup (Version: {config.SCRIPT_VERSION})...",
        current_logger=logger,
    )
    log_map_server(
        f"DEBUG config.DEV_OVERRIDE_UNSAFE_PASSWORD is now: {config.DEV_OVERRIDE_UNSAFE_PASSWORD}",
        "info",
        current_logger=logger,
    )

    if (
            config.PGPASSWORD == config.PGPASSWORD_DEFAULT
            and not args.view_config
            and not config.DEV_OVERRIDE_UNSAFE_PASSWORD
    ):
        log_map_server(
            f"{config.SYMBOLS['warning']} WARNING: Using default PostgreSQL password. This is INSECURE.",
            "warning",
            current_logger=logger,
        )
        log_map_server(
            "   Provide a password via -W option or use --dev-override-unsafe-password (at your own risk) to use the default for .pgpass.",
            "warning",
            current_logger=logger,
        )
    elif (
            config.DEV_OVERRIDE_UNSAFE_PASSWORD
            and config.PGPASSWORD == config.PGPASSWORD_DEFAULT
    ):
        log_map_server(
            f"{config.SYMBOLS['warning']} DEV OVERRIDE: Using default PostgreSQL password for .pgpass setup due to --dev-override-unsafe-password flag.",
            "warning",
            current_logger=logger,
        )

    if os.geteuid() != 0:
        all_system_packages_to_check = (
                config.CORE_PREREQ_PACKAGES
                + config.PYTHON_SYSTEM_PACKAGES
                + config.POSTGRES_PACKAGES
                + config.MAPPING_PACKAGES
                + config.FONT_PACKAGES
        )
        if any(
                not check_package_installed(p, current_logger=logger)
                for p in all_system_packages_to_check
        ):
            log_map_server(
                f"{config.SYMBOLS['info']} Script not run as root & system packages need installing. 'sudo' will be used. You may be prompted for your password.",
                "info",
                current_logger=logger,
            )
    else:
        log_map_server(
            f"{config.SYMBOLS['info']} Script is running as root. Privileged operations will run directly.",
            "info",
            current_logger=logger,
        )

    initialize_state_system(current_logger=logger)
    setup_pgpass(
        pg_host=config.PGHOST,
        pg_port=config.PGPORT,
        pg_database=config.PGDATABASE,
        pg_user=config.PGUSER,
        pg_password=config.PGPASSWORD,
        pg_password_default=config.PGPASSWORD_DEFAULT,
        allow_default_for_dev=config.DEV_OVERRIDE_UNSAFE_PASSWORD,
        current_logger=logger,
    )

    if args.view_config:
        view_configuration(current_logger=logger)
        return 0
    if args.view_state:
        completed = view_completed_steps(current_logger=logger)
        if completed:
            log_map_server(
                f"{config.SYMBOLS['info']} Completed steps recorded in state file:",
                "info",
                current_logger=logger,
            )
            for s_idx, s_item in enumerate(completed):
                print(f"  {s_idx + 1}. {s_item}")
        else:
            log_map_server(
                f"{config.SYMBOLS['info']} No steps marked as completed in state file.",
                "info",
                current_logger=logger,
            )
        return 0
    if args.clear_state:
        try:
            confirm_clear = (
                input(
                    f"{config.SYMBOLS['warning']} Are you sure you want to clear all progress state from {config.STATE_FILE_PATH}? (yes/NO): "
                )
                .strip()
                .lower()
            )
        except EOFError:
            confirm_clear = "no"
            log_map_server(
                f"{config.SYMBOLS['warning']} No user input (EOF), defaulting to 'NO' for clearing state.",
                "warning",
                current_logger=logger,
            )
        if confirm_clear == "yes":
            clear_state_file(current_logger=logger)
        else:
            log_map_server(
                f"{config.SYMBOLS['info']} State clearing cancelled.",
                "info",
                current_logger=logger,
            )
        return 0

    overall_success = True
    action_taken = False

    if args.full:
        action_taken = True
        log_map_server(
            f"{config.SYMBOLS['rocket']}====== Starting Full Installation Process ======",
            current_logger=logger,
        )
        overall_success = overall_success and core_conflict_removal_group(
            current_logger=logger
        )
        if overall_success:
            overall_success = overall_success and prereqs_install_group(
                current_logger=logger
            )
        if overall_success:
            overall_success = overall_success and services_setup_group(
                current_logger=logger
            )
        if overall_success:
            overall_success = overall_success and systemd_reload_step_group(
                current_logger=logger
            )
        if overall_success:
            overall_success = overall_success and data_prep_group(
                current_logger=logger
            )

    elif args.conflicts_removed_flag:
        action_taken = True
        log_map_server(
            f"{config.SYMBOLS['rocket']}====== Running Core Conflict Removal Group Only ======",
            current_logger=logger,
        )
        overall_success = core_conflict_removal_group(current_logger=logger)
    elif args.prereqs:
        action_taken = True
        log_map_server(
            f"{config.SYMBOLS['rocket']}====== Running Prerequisites Installation Group Only ======",
            current_logger=logger,
        )
        overall_success = prereqs_install_group(current_logger=logger)
    elif args.services:
        action_taken = True
        log_map_server(
            f"{config.SYMBOLS['rocket']}====== Running Services Setup Group Only ======",
            current_logger=logger,
        )
        overall_success = services_setup_group(current_logger=logger)
        if overall_success:
            overall_success = overall_success and systemd_reload_step_group(
                current_logger=logger
            )
    elif args.data:
        action_taken = True
        log_map_server(
            f"{config.SYMBOLS['rocket']}====== Running Data Preparation Group Only ======",
            current_logger=logger,
        )
        overall_success = data_prep_group(current_logger=logger)
    elif args.systemd_reload_flag:
        action_taken = True
        log_map_server(
            f"{config.SYMBOLS['rocket']}====== Running Systemd Reload Only ======",
            current_logger=logger,
        )
        overall_success = systemd_reload_step_group(current_logger=logger)

    if not action_taken:
        log_map_server(
            f"{config.SYMBOLS['info']} No installation action specified. Displaying help.",
            "info",
            current_logger=logger,
        )
        # Print argv context before printing help
        print(
            f"\n{config.SYMBOLS['info']} Script was called with argv: {sys.argv}",
            file=sys.stderr,
        )
        if args is not None:
            parser.print_help(file=sys.stderr)
        else:  # Should not happen if -h was caught, but as a fallback
            print(
                "Error: Argument parsing failed before args object was created.",
                file=sys.stderr,
            )
        log_map_server(
            f"{config.SYMBOLS['warning']} No action performed. Exiting with status code 2 (no operation).",
            "warning",
            current_logger=logger,
        )
        return 2

    if not overall_success:
        log_map_server(
            f"{config.SYMBOLS['critical']}One or more steps failed during the process.",
            "critical",
            current_logger=logger,
        )
        return 1
    else:
        log_map_server(
            f"{config.SYMBOLS['sparkles']} All requested operations completed.",
            "success",
            current_logger=logger,
        )
        if action_taken and not args.full:
            log_map_server(
                f"{config.SYMBOLS['info']} Partial run completed successfully.",
                "info",
                current_logger=logger,
            )
    return 0
