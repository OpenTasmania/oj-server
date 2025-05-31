# setup/services_setup.py
# -*- coding: utf-8 -*-
"""
Functions for setting up and configuring various map-related services.

This module is intended to orchestrate the setup of services like UFW,
PostgreSQL, pg_tileserv, CartoCSS, and others. It defines individual setup
functions (many as placeholders) and a group function to run them sequentially.
"""

import logging
import os
import subprocess  # For CalledProcessError specifically
from typing import Callable, List, Optional, Tuple

from setup import config
from setup.cli_handler import cli_prompt_for_rerun
from common.command_utils import log_map_server, run_elevated_command
from setup.helpers import backup_file, validate_cidr
from setup.step_executor import execute_step

module_logger = logging.getLogger(__name__)


def ufw_setup(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Set up Uncomplicated Firewall (UFW).

    Configures default policies, allows SSH and PostgreSQL from admin IP,
    and allows HTTP/HTTPS. Enables UFW if inactive.

    Args:
        current_logger: Optional logger instance.

    Raises:
        ValueError: If ADMIN_GROUP_IP in config has an invalid CIDR format.
        subprocess.CalledProcessError: If a ufw command fails critically.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Setting up firewall with ufw...",
        "info",
        logger_to_use,
    )

    if not validate_cidr(config.ADMIN_GROUP_IP, current_logger=logger_to_use):
        msg = (
            f"Firewall setup aborted: Invalid ADMIN_GROUP_IP CIDR format "
            f"'{config.ADMIN_GROUP_IP}'."
        )
        log_map_server(
            f"{config.SYMBOLS['error']} {msg}", "error", logger_to_use
        )
        raise ValueError(msg)

    try:
        # Set default policies
        run_elevated_command(
            ["ufw", "default", "deny", "incoming"],
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["ufw", "default", "allow", "outgoing"],
            current_logger=logger_to_use,
        )
        # Allow traffic on loopback interface
        run_elevated_command(
            ["ufw", "allow", "in", "on", "lo"], current_logger=logger_to_use
        )
        run_elevated_command(
            ["ufw", "allow", "out", "on", "lo"], current_logger=logger_to_use
        )

        # Allow specific services
        run_elevated_command(
            [
                "ufw",
                "allow",
                "from",
                config.ADMIN_GROUP_IP,
                "to",
                "any",
                "port",
                "22",
                "proto",
                "tcp",
                "comment",
                "SSH from Admin",
            ],
            current_logger=logger_to_use,
        )
        run_elevated_command(
            [
                "ufw",
                "allow",
                "from",
                config.ADMIN_GROUP_IP,
                "to",
                "any",
                "port",
                "5432",
                "proto",
                "tcp",
                "comment",
                "PostgreSQL from Admin",
            ],
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["ufw", "allow", "http", "comment", "Nginx HTTP"],
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["ufw", "allow", "https", "comment", "Nginx HTTPS"],
            current_logger=logger_to_use,
        )

        log_map_server(
            f"{config.SYMBOLS['warning']} UFW will be enabled. Ensure SSH from "
            f"'{config.ADMIN_GROUP_IP}' & Nginx ports (80, 443) are allowed.",
            "warning",
            logger_to_use,
        )

        # Enable UFW if it's inactive
        status_result = run_elevated_command(
            ["ufw", "status"],
            capture_output=True,
            check=False,  # Don't fail if status command itself has issues
            current_logger=logger_to_use,
        )
        if (
            status_result.stdout
            and "inactive" in status_result.stdout.lower()
        ):
            run_elevated_command(
                ["ufw", "enable"],
                cmd_input="y\n",  # Auto-confirm the enabling prompt
                check=True,
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{config.SYMBOLS['success']} UFW enabled.",
                "success",
                logger_to_use,
            )
        else:
            status_output = (
                status_result.stdout.strip()
                if status_result.stdout
                else "N/A"
            )
            log_map_server(
                f"{config.SYMBOLS['info']} UFW is already active or status "
                f"not 'inactive'. Status: {status_output}",
                "info",
                logger_to_use,
            )

        log_map_server(
            f"{config.SYMBOLS['info']} UFW status details:",
            "info",
            logger_to_use,
        )
        run_elevated_command(
            ["ufw", "status", "verbose"], current_logger=logger_to_use
        )
        log_map_server(
            f"{config.SYMBOLS['success']} UFW setup completed.",
            "success",
            logger_to_use,
        )
    except subprocess.CalledProcessError as e:
        # Errors from run_elevated_command (if check=True) are caught here
        log_map_server(
            f"{config.SYMBOLS['error']} Error during UFW setup: {e}. "
            f"Command: '{e.cmd}', Stderr: {e.stderr}",
            "error",
            logger_to_use,
        )
        raise
    except Exception as e:
        # Catch any other unexpected errors
        log_map_server(
            f"{config.SYMBOLS['error']} Unexpected error during UFW setup: {e}",
            "error",
            logger_to_use,
        )
        raise


def postgres_setup(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Set up PostgreSQL database, user, extensions, and configurations.

    Args:
        current_logger: Optional logger instance.

    Raises:
        FileNotFoundError: If PostgreSQL configuration directory is not found.
        subprocess.CalledProcessError: If a psql or systemctl command fails.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Setting up PostgreSQL...",
        "info",
        logger_to_use,
    )

    # TODO: Make pg_version dynamically detectable or more robust.
    pg_version = "15"
    pg_conf_dir = f"/etc/postgresql/{pg_version}/main"
    pg_conf_file = os.path.join(pg_conf_dir, "postgresql.conf")
    pg_hba_file = os.path.join(pg_conf_dir, "pg_hba.conf")

    if not os.path.isdir(pg_conf_dir):
        log_map_server(
            f"{config.SYMBOLS['error']} PostgreSQL config directory not found: "
            f"{pg_conf_dir}. Is PostgreSQL v{pg_version} installed?",
            "error",
            logger_to_use,
        )
        raise FileNotFoundError(
            f"PostgreSQL config directory {pg_conf_dir} not found."
        )

    # Create PostgreSQL user
    try:
        log_map_server(
            f"{config.SYMBOLS['gear']} Creating PostgreSQL user "
            f"'{config.PGUSER}'...",
            "info",
            logger_to_use,
        )
        # Using run_elevated_command which prepends sudo if needed.
        # The command itself uses `sudo -u postgres psql ...`
        run_elevated_command(
            [
                "sudo",
                "-u",
                "postgres",
                "psql",
                "-c",
                f"CREATE USER {config.PGUSER} WITH PASSWORD '{config.PGPASSWORD}';",
            ],
            current_logger=logger_to_use,
        )
    except subprocess.CalledProcessError as e:
        if e.stderr and "already exists" in e.stderr.lower():
            log_map_server(
                f"{config.SYMBOLS['info']} PostgreSQL user '{config.PGUSER}' "
                "already exists. Attempting to update password.",
                "info",
                logger_to_use,
            )
            run_elevated_command(
                [
                    "sudo",
                    "-u",
                    "postgres",
                    "psql",
                    "-c",
                    f"ALTER USER {config.PGUSER} WITH PASSWORD '{config.PGPASSWORD}';",
                ],
                current_logger=logger_to_use,
            )
        else:
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to create/alter "
                f"PostgreSQL user '{config.PGUSER}'. Error: {e.stderr}",
                "error",
                logger_to_use,
            )
            raise

    # Create PostgreSQL database
    try:
        log_map_server(
            f"{config.SYMBOLS['gear']} Creating PostgreSQL database "
            f"'{config.PGDATABASE}'...",
            "info",
            logger_to_use,
        )
        run_elevated_command(
            [
                "sudo",
                "-u",
                "postgres",
                "psql",
                "-c",
                f"CREATE DATABASE {config.PGDATABASE} WITH OWNER {config.PGUSER} "
                f"ENCODING 'UTF8' LC_COLLATE='en_AU.UTF-8' "
                f"LC_CTYPE='en_AU.UTF-8' TEMPLATE template0;",
            ],
            current_logger=logger_to_use,
        )
    except subprocess.CalledProcessError as e:
        if e.stderr and "already exists" in e.stderr.lower():
            log_map_server(
                f"{config.SYMBOLS['info']} PostgreSQL database "
                f"'{config.PGDATABASE}' already exists.",
                "info",
                logger_to_use,
            )
        else:
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to create PostgreSQL "
                f"database '{config.PGDATABASE}'. Error: {e.stderr}",
                "error",
                logger_to_use,
            )
            raise

    # Ensure extensions are created
    extensions = ["postgis", "hstore"]
    for ext in extensions:
        log_map_server(
            f"{config.SYMBOLS['gear']} Ensuring PostgreSQL extension '{ext}' "
            f"in '{config.PGDATABASE}'...",
            "info",
            logger_to_use,
        )
        run_elevated_command(
            [
                "sudo",
                "-u",
                "postgres",
                "psql",
                "-d",
                config.PGDATABASE,
                "-c",
                f"CREATE EXTENSION IF NOT EXISTS {ext};",
            ],
            current_logger=logger_to_use,
        )

    # Set database permissions
    log_map_server(
        f"{config.SYMBOLS['gear']} Setting database permissions for user "
        f"'{config.PGUSER}'...",
        "info",
        logger_to_use,
    )
    db_permission_commands = [
        f"ALTER SCHEMA public OWNER TO {config.PGUSER};",
        f"GRANT ALL ON SCHEMA public TO {config.PGUSER};",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {config.PGUSER};",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {config.PGUSER};",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO {config.PGUSER};",
    ]
    for cmd_sql in db_permission_commands:
        run_elevated_command(
            [
                "sudo",
                "-u",
                "postgres",
                "psql",
                "-d",
                config.PGDATABASE,
                "-c",
                cmd_sql,
            ],
            current_logger=logger_to_use,
        )
    log_map_server(
        f"{config.SYMBOLS['success']} PostgreSQL user, database, extensions, "
        "and permissions configured.",
        "success",
        logger_to_use,
    )

    # Customize postgresql.conf
    if backup_file(pg_conf_file, current_logger=logger_to_use):
        customisation_marker = (
            "# --- TRANSIT SERVER CUSTOMISATIONS - Appended by script ---"
        )
        # Check if customizations already exist
        grep_result = run_elevated_command(
            ["grep", "-qF", customisation_marker, pg_conf_file],
            check=False,
            capture_output=True,
            current_logger=logger_to_use,
        )
        if grep_result.returncode != 0:  # Marker not found, append settings
            # Define postgresql_custom_conf_content based on your requirements
            postgresql_custom_conf_content = f"""
{customisation_marker}
listen_addresses = '*'
shared_buffers = 2GB
work_mem = 256MB
maintenance_work_mem = 2GB
checkpoint_timeout = 15min
max_wal_size = 4GB
min_wal_size = 2GB
checkpoint_completion_target = 0.9
effective_cache_size = 6GB
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_min_duration_statement = 250ms
# --- END TRANSIT SERVER CUSTOMISATIONS ---
"""
            run_elevated_command(
                ["tee", "-a", pg_conf_file],
                cmd_input=postgresql_custom_conf_content,
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{config.SYMBOLS['success']} Appended custom settings to {pg_conf_file}",
                "success",
                logger_to_use,
            )
        else:
            log_map_server(
                f"{config.SYMBOLS['info']} Customizations marker already found "
                f"in {pg_conf_file}. Assuming settings are applied or "
                "managed manually.",
                "info",
                logger_to_use,
            )

    # Customize pg_hba.conf
    if backup_file(pg_hba_file, current_logger=logger_to_use):
        if not validate_cidr(
            config.ADMIN_GROUP_IP, current_logger=logger_to_use
        ):
            log_map_server(
                f"{config.SYMBOLS['error']} Invalid ADMIN_GROUP_IP "
                f"'{config.ADMIN_GROUP_IP}' for pg_hba.conf. Skipping HBA update.",
                "error",
                logger_to_use,
            )
        else:
            # Define pg_hba_content based on your security requirements
            pg_hba_content = f"""# pg_hba.conf configured by script V{config.SCRIPT_VERSION}
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             postgres                                peer
local   all             all                                     peer
local   {config.PGDATABASE}    {config.PGUSER}                                scram-sha-256
host    all             all             127.0.0.1/32            scram-sha-256
host    {config.PGDATABASE}    {config.PGUSER}        127.0.0.1/32            scram-sha-256
host    {config.PGDATABASE}    {config.PGUSER}        {config.ADMIN_GROUP_IP}       scram-sha-256
host    all             all             ::1/128                 scram-sha-256
host    {config.PGDATABASE}    {config.PGUSER}        ::1/128                 scram-sha-256
"""
            run_elevated_command(
                ["tee", pg_hba_file],  # Overwrites the file
                cmd_input=pg_hba_content,
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{config.SYMBOLS['success']} Overwrote {pg_hba_file} with new rules.",
                "success",
                logger_to_use,
            )

    # Restart PostgreSQL service
    log_map_server(
        f"{config.SYMBOLS['gear']} Restarting and enabling PostgreSQL service...",
        "info",
        logger_to_use,
    )
    run_elevated_command(
        ["systemctl", "restart", "postgresql"], current_logger=logger_to_use
    )
    run_elevated_command(
        ["systemctl", "enable", "postgresql"], current_logger=logger_to_use
    )
    log_map_server(
        f"{config.SYMBOLS['info']} PostgreSQL service status:",
        "info",
        logger_to_use,
    )
    run_elevated_command(
        ["systemctl", "status", "postgresql", "--no-pager", "-l"],
        current_logger=logger_to_use,
    )
    log_map_server(
        f"{config.SYMBOLS['success']} PostgreSQL setup completed.",
        "success",
        logger_to_use,
    )


def pg_tileserv_setup(
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Placeholder for pg_tileserv setup.

    Args:
        current_logger: Optional logger instance.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Placeholder for pg_tileserv_setup",
        "info",
        logger_to_use,
    )
    # TODO: Implement full refactored logic for pg_tileserv_setup.
    # This would involve downloading, configuring, and setting up the service.
    # Refer to the provided 'osm/setup/services/pg_tileserv.py' for the
    # original logic to be adapted here.


def carto_setup(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Placeholder for CartoCSS compiler and OpenStreetMap-Carto stylesheet setup.

    Args:
        current_logger: Optional logger instance.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Placeholder for carto_setup",
        "info",
        logger_to_use,
    )
    # TODO: Implement full refactored logic for carto_setup.
    # Refer to 'osm/setup/services/carto.py'.


# Placeholder for other service setup functions:
# renderd_setup, osm_osrm_server_setup, apache_modtile_setup,
# nginx_setup, certbot_setup.
# These should be defined similarly, taking current_logger as an argument.


def services_setup_group(current_logger: logging.Logger) -> bool:
    """
    Run all service setup steps as a group.

    Args:
        current_logger: The logger instance to use for this group.

    Returns:
        True if all steps in the group succeed, False otherwise.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"--- {config.SYMBOLS['info']} Starting Services Setup Group ---",
        "info",
        logger_to_use,
    )
    overall_success = True

    # Define all steps in this group.
    # Ensure function references are correct and they expect `current_logger`.
    step_definitions_in_group: List[Tuple[str, str, Callable]] = [
        ("UFW_SETUP", "Setup UFW Firewall", ufw_setup),
        (
            "POSTGRES_SETUP",
            "Setup PostgreSQL Database & User",
            postgres_setup,
        ),
        ("PGTILESERV_SETUP", "Setup pg_tileserv", pg_tileserv_setup),
        ("CARTO_SETUP", "Setup CartoCSS Compiler & OSM Style", carto_setup),
        # TODO: Add other service setup functions here when implemented.
        # e.g. ("RENDERD_SETUP", "Setup Renderd", renderd_setup),
    ]

    for tag, desc, func in step_definitions_in_group:
        if not execute_step(
            step_tag=tag,
            step_description=desc,
            step_function=func,  # type: ignore
            current_logger_instance=logger_to_use,
            prompt_user_for_rerun=cli_prompt_for_rerun,
        ):
            overall_success = False
            log_map_server(
                f"{config.SYMBOLS['error']} Step '{desc}' failed. "
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
