# configure/postgres_configurator.py
# -*- coding: utf-8 -*-
"""
Handles configuration of PostgreSQL, including users, databases, extensions,
permissions, and server configuration files.
"""
import logging
import os
import subprocess  # For CalledProcessError
from typing import Optional

from common.command_utils import log_map_server, run_command, run_elevated_command
from common.file_utils import backup_file  # Assuming backup_file is in common.file_utils
from setup import config  # For DB params, SYMBOLS, SCRIPT_VERSION
from setup.state_manager import get_current_script_hash  # For config file comments

module_logger = logging.getLogger(__name__)

# Determine PostgreSQL version and config directory (could be a shared utility)
# For now, keeping it similar to the original script.
# TODO: Make pg_version dynamically detectable or a central config.
PG_VERSION = "17"  # As per original script context; adjust if necessary
PG_CONF_DIR = f"/etc/postgresql/{PG_VERSION}/main"
PG_CONF_FILE = os.path.join(PG_CONF_DIR, "postgresql.conf")
PG_HBA_FILE = os.path.join(PG_CONF_DIR, "pg_hba.conf")


def _check_pg_config_dir_exists(current_logger: Optional[logging.Logger] = None) -> None:
    """Checks if the PostgreSQL configuration directory exists."""
    logger_to_use = current_logger if current_logger else module_logger
    if not os.path.isdir(PG_CONF_DIR):
        try:
            run_elevated_command(
                ["test", "-d", PG_CONF_DIR],
                check=True,
                capture_output=True,
                current_logger=logger_to_use,
            )
        except subprocess.CalledProcessError as e:
            log_map_server(
                f"{config.SYMBOLS['error']} PostgreSQL config directory not found: {PG_CONF_DIR}. "
                f"Is PostgreSQL v{PG_VERSION} installed and paths correct?",
                "error",
                logger_to_use,
            )
            raise FileNotFoundError(f"PostgreSQL config directory {PG_CONF_DIR} not found.") from e


def create_postgres_user_and_db(current_logger: Optional[logging.Logger] = None) -> None:
    """Creates the PostgreSQL user and database if they don't exist."""
    logger_to_use = current_logger if current_logger else module_logger
    _check_pg_config_dir_exists(logger_to_use)  # Ensure PG is likely installed

    # Create PostgreSQL user
    try:
        log_map_server(f"{config.SYMBOLS['gear']} Creating PostgreSQL user '{config.PGUSER}'...", "info", logger_to_use)
        run_command(
            ["sudo", "-u", "postgres", "psql", "-c",
             f"CREATE USER {config.PGUSER} WITH PASSWORD '{config.PGPASSWORD}';"],
            capture_output=True, current_logger=logger_to_use
        )
        log_map_server(f"{config.SYMBOLS['success']} PostgreSQL user '{config.PGUSER}' created.", "success",
                       logger_to_use)
    except subprocess.CalledProcessError as e:
        if e.stderr and "already exists" in e.stderr.lower():
            log_map_server(
                f"{config.SYMBOLS['info']} PostgreSQL user '{config.PGUSER}' already exists. Attempting to update password.",
                "info", logger_to_use)
            run_command(
                ["sudo", "-u", "postgres", "psql", "-c",
                 f"ALTER USER {config.PGUSER} WITH PASSWORD '{config.PGPASSWORD}';"],
                capture_output=True, current_logger=logger_to_use
            )
            log_map_server(f"{config.SYMBOLS['success']} Password for PostgreSQL user '{config.PGUSER}' updated.",
                           "success", logger_to_use)
        else:
            err_msg = e.stderr.strip() if e.stderr else "Unknown psql error during user creation."
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to create/alter PostgreSQL user '{config.PGUSER}'. Error: {err_msg}",
                "error", logger_to_use)
            raise

    # Create PostgreSQL database
    try:
        log_map_server(f"{config.SYMBOLS['gear']} Creating PostgreSQL database '{config.PGDATABASE}'...", "info",
                       logger_to_use)
        run_command(
            ["sudo", "-u", "postgres", "psql", "-c",
             f"CREATE DATABASE {config.PGDATABASE} WITH OWNER {config.PGUSER} ENCODING 'UTF8' LC_COLLATE='en_AU.UTF-8' LC_CTYPE='en_AU.UTF-8' TEMPLATE template0;"],
            capture_output=True, current_logger=logger_to_use
        )
        log_map_server(f"{config.SYMBOLS['success']} PostgreSQL database '{config.PGDATABASE}' created.", "success",
                       logger_to_use)
    except subprocess.CalledProcessError as e:
        if e.stderr and "already exists" in e.stderr.lower():
            log_map_server(f"{config.SYMBOLS['info']} PostgreSQL database '{config.PGDATABASE}' already exists.",
                           "info", logger_to_use)
        else:
            err_msg = e.stderr.strip() if e.stderr else "Unknown psql error during database creation."
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to create PostgreSQL database '{config.PGDATABASE}'. Error: {err_msg}",
                "error", logger_to_use)
            raise


def enable_postgres_extensions(current_logger: Optional[logging.Logger] = None) -> None:
    """Ensures necessary PostgreSQL extensions (PostGIS, Hstore) are enabled."""
    logger_to_use = current_logger if current_logger else module_logger
    _check_pg_config_dir_exists(logger_to_use)

    extensions = ["postgis", "hstore"]
    for ext in extensions:
        log_map_server(
            f"{config.SYMBOLS['gear']} Ensuring PostgreSQL extension '{ext}' is available in database '{config.PGDATABASE}'...",
            "info", logger_to_use)
        try:
            run_command(
                ["sudo", "-u", "postgres", "psql", "-d", config.PGDATABASE, "-c",
                 f"CREATE EXTENSION IF NOT EXISTS {ext};"],
                current_logger=logger_to_use
            )
            log_map_server(f"{config.SYMBOLS['success']} PostgreSQL extension '{ext}' ensured.", "success",
                           logger_to_use)
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.strip() if e.stderr else f"Unknown psql error enabling extension {ext}."
            log_map_server(f"{config.SYMBOLS['error']} Failed to enable PostgreSQL extension '{ext}'. Error: {err_msg}",
                           "error", logger_to_use)
            raise


def set_postgres_permissions(current_logger: Optional[logging.Logger] = None) -> None:
    """Sets database permissions for the application user."""
    logger_to_use = current_logger if current_logger else module_logger
    _check_pg_config_dir_exists(logger_to_use)

    log_map_server(
        f"{config.SYMBOLS['gear']} Setting database permissions for user '{config.PGUSER}' on database '{config.PGDATABASE}'...",
        "info", logger_to_use)
    db_permission_commands = [
        f"ALTER SCHEMA public OWNER TO {config.PGUSER};",
        f"GRANT ALL ON SCHEMA public TO {config.PGUSER};",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {config.PGUSER};",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {config.PGUSER};",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO {config.PGUSER};",
    ]
    try:
        for cmd_sql in db_permission_commands:
            run_command(
                ["sudo", "-u", "postgres", "psql", "-d", config.PGDATABASE, "-c", cmd_sql],
                current_logger=logger_to_use,
            )
        log_map_server(f"{config.SYMBOLS['success']} Database permissions set for user '{config.PGUSER}'.", "success",
                       logger_to_use)
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip() if e.stderr else "Unknown psql error setting permissions."
        log_map_server(f"{config.SYMBOLS['error']} Failed to set PostgreSQL permissions. Error: {err_msg}", "error",
                       logger_to_use)
        raise


def customize_postgresql_conf(current_logger: Optional[logging.Logger] = None) -> None:
    """Customizes postgresql.conf with performance and logging settings."""
    logger_to_use = current_logger if current_logger else module_logger
    _check_pg_config_dir_exists(logger_to_use)
    script_hash = get_current_script_hash(logger_instance=logger_to_use) or "UNKNOWN_HASH"

    if backup_file(PG_CONF_FILE, current_logger=logger_to_use):
        customisation_marker = f"# --- TRANSIT SERVER CUSTOMISATIONS - Appended by script V"
        # Check if any version of the marker exists
        grep_result = run_elevated_command(
            ["grep", "-qF", customisation_marker, PG_CONF_FILE],
            check=False, capture_output=True, current_logger=logger_to_use
        )
        if grep_result.returncode != 0:  # Marker not found
            content_to_append = f"""
# --- TRANSIT SERVER CUSTOMISATIONS - Appended by script V{script_hash} ---
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
            try:
                run_elevated_command(["tee", "-a", PG_CONF_FILE], cmd_input=content_to_append,
                                     current_logger=logger_to_use)
                log_map_server(f"{config.SYMBOLS['success']} Appended custom settings to {PG_CONF_FILE}", "success",
                               logger_to_use)
            except Exception as e:
                log_map_server(f"{config.SYMBOLS['error']} Error updating {PG_CONF_FILE}: {e}", "error", logger_to_use)
        else:
            log_map_server(
                f"{config.SYMBOLS['info']} Customizations marker already found in {PG_CONF_FILE}. Assuming settings are applied.",
                "info", logger_to_use)


def customize_pg_hba_conf(current_logger: Optional[logging.Logger] = None) -> None:
    """Customizes pg_hba.conf for client authentication."""
    logger_to_use = current_logger if current_logger else module_logger
    _check_pg_config_dir_exists(logger_to_use)
    from common.network_utils import validate_cidr  # Moved import
    script_hash = get_current_script_hash(logger_instance=logger_to_use) or "UNKNOWN_HASH"

    if not validate_cidr(config.ADMIN_GROUP_IP, current_logger=logger_to_use):
        log_map_server(
            f"{config.SYMBOLS['error']} Invalid ADMIN_GROUP_IP '{config.ADMIN_GROUP_IP}' for pg_hba.conf. Skipping HBA update.",
            "error", logger_to_use)
        return  # Or raise error if HBA config is critical

    if backup_file(PG_HBA_FILE, current_logger=logger_to_use):
        hba_content = f"""# pg_hba.conf configured by script V{script_hash}
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
        try:
            run_elevated_command(["tee", PG_HBA_FILE], cmd_input=hba_content, current_logger=logger_to_use)
            log_map_server(f"{config.SYMBOLS['success']} Overwrote {PG_HBA_FILE} with new rules.", "success",
                           logger_to_use)
        except Exception as e:
            log_map_server(f"{config.SYMBOLS['error']} Error writing {PG_HBA_FILE}: {e}", "error", logger_to_use)


def restart_and_enable_postgres_service(current_logger: Optional[logging.Logger] = None) -> None:
    """Restarts and enables the PostgreSQL service."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['gear']} Restarting and enabling PostgreSQL service...", "info", logger_to_use)
    try:
        run_elevated_command(["systemctl", "restart", "postgresql"], current_logger=logger_to_use)
        run_elevated_command(["systemctl", "enable", "postgresql"], current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['info']} PostgreSQL service status:", "info", logger_to_use)
        run_elevated_command(["systemctl", "status", "postgresql", "--no-pager", "-l"], current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} PostgreSQL service restarted and enabled.", "success",
                       logger_to_use)
    except subprocess.CalledProcessError as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to restart/enable PostgreSQL service. Error: {e.stderr or e.stdout}",
            "error", logger_to_use)
        raise