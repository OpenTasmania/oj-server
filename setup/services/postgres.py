# setup/services/postgres.py
# -*- coding: utf-8 -*-
"""
Handles the setup and configuration of PostgreSQL.

This module includes functions to create the PostgreSQL user and database,
enable necessary extensions (PostGIS, Hstore), configure permissions,
customize `postgresql.conf` and `pg_hba.conf`, and restart the
PostgreSQL service.
"""

import logging
import os
import subprocess  # For CalledProcessError
from typing import Optional

from setup import config
from setup.command_utils import (
    log_map_server,
    run_command,
    run_elevated_command,
)
from setup.helpers import backup_file, validate_cidr

# Assuming get_current_script_hash is needed for comments in config files
from setup.state_manager import get_current_script_hash

module_logger = logging.getLogger(__name__)


def postgres_setup(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Set up PostgreSQL user, database, extensions, and configurations.

    Args:
        current_logger: Optional logger instance to use. If None,
                        the module's default logger is used.

    Raises:
        FileNotFoundError: If the PostgreSQL configuration directory
                           (e.g., /etc/postgresql/15/main) is not found,
                           indicating PostgreSQL might not be installed or
                           the version is different.
        subprocess.CalledProcessError: If any critical `psql` or `systemctl`
                                     command fails.
        Exception: For other unexpected errors during setup.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Setting up PostgreSQL...",
        "info",
        logger_to_use,
    )
    script_hash_for_comments = get_current_script_hash(
        logger_instance=logger_to_use
    ) or "UNKNOWN_HASH"

    # TODO: Make pg_version dynamically detectable or a central config.
    pg_version = "15"
    pg_conf_dir = f"/etc/postgresql/{pg_version}/main"
    pg_conf_file = os.path.join(pg_conf_dir, "postgresql.conf")
    pg_hba_file = os.path.join(pg_conf_dir, "pg_hba.conf")

    if not os.path.isdir(pg_conf_dir):
        # Attempt an elevated check if the initial check fails.
        try:
            run_elevated_command(
                ["test", "-d", pg_conf_dir],
                check=True,
                capture_output=True,  # Suppress test command's output
                current_logger=logger_to_use,
            )
        except subprocess.CalledProcessError as e:
            log_map_server(
                f"{config.SYMBOLS['error']} PostgreSQL config directory not "
                f"found: {pg_conf_dir}. Is PostgreSQL v{pg_version} "
                "installed?",
                "error",
                logger_to_use,
            )
            raise FileNotFoundError(
                f"PostgreSQL config directory {pg_conf_dir} not found."
            ) from e

    # Create PostgreSQL user
    try:
        log_map_server(
            f"{config.SYMBOLS['gear']} Creating PostgreSQL user "
            f"'{config.PGUSER}'...",
            "info",
            logger_to_use,
        )
        # run_command uses sudo -u postgres internally for psql.
        run_command(
            [
                "sudo", "-u", "postgres", "psql", "-c",
                f"CREATE USER {config.PGUSER} WITH PASSWORD '{config.PGPASSWORD}';",
            ],
            capture_output=True,  # Capture output to check for "already exists"
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
            run_command(
                [
                    "sudo", "-u", "postgres", "psql", "-c",
                    f"ALTER USER {config.PGUSER} WITH PASSWORD '{config.PGPASSWORD}';",
                ],
                capture_output=True,  # Capture to avoid verbose output on success
                current_logger=logger_to_use,
            )
        else:
            err_msg = e.stderr.strip() if e.stderr else \
                "Unknown psql error during user creation."
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to create/alter PostgreSQL "
                f"user '{config.PGUSER}'. Error: {err_msg}",
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
        run_command(
            [
                "sudo", "-u", "postgres", "psql", "-c",
                f"CREATE DATABASE {config.PGDATABASE} WITH OWNER {config.PGUSER} "
                f"ENCODING 'UTF8' LC_COLLATE='en_AU.UTF-8' "
                f"LC_CTYPE='en_AU.UTF-8' TEMPLATE template0;",
            ],
            capture_output=True,  # Capture output
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
            err_msg = e.stderr.strip() if e.stderr else \
                "Unknown psql error during database creation."
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to create PostgreSQL "
                f"database '{config.PGDATABASE}'. Error: {err_msg}",
                "error",
                logger_to_use,
            )
            raise

    # Ensure necessary extensions are created in the database
    extensions = ["postgis", "hstore"]
    for ext in extensions:
        log_map_server(
            f"{config.SYMBOLS['gear']} Ensuring PostgreSQL extension '{ext}' "
            f"is available in database '{config.PGDATABASE}'...",
            "info",
            logger_to_use,
        )
        run_command(
            [
                "sudo", "-u", "postgres", "psql", "-d", config.PGDATABASE,
                "-c", f"CREATE EXTENSION IF NOT EXISTS {ext};",
            ],
            current_logger=logger_to_use,  # Output is usually minimal here
        )

    # Set database permissions for the created user
    log_map_server(
        f"{config.SYMBOLS['gear']} Setting database permissions for user "
        f"'{config.PGUSER}' on database '{config.PGDATABASE}'...",
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
        run_command(
            ["sudo", "-u", "postgres", "psql", "-d", config.PGDATABASE, "-c", cmd_sql],
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
        # Marker to check if customizations have already been applied
        customisation_marker = (
            "# --- TRANSIT SERVER CUSTOMISATIONS - Appended by script V"
        )  # Partial marker to find any version
        postgresql_custom_conf_content = f"""
# --- TRANSIT SERVER CUSTOMISATIONS - Appended by script V{script_hash_for_comments} ---
listen_addresses = '*'
shared_buffers = 2GB          # Adjust based on available RAM (e.g., 25% of total RAM)
work_mem = 256MB              # Memory per sort/hash operation, adjust based on query complexity
maintenance_work_mem = 2GB    # For VACUUM, CREATE INDEX, etc.
checkpoint_timeout = 15min    # Interval between automatic WAL checkpoints
max_wal_size = 4GB            # Max WAL size before triggering a checkpoint
min_wal_size = 2GB            # Min WAL size to recycle
checkpoint_completion_target = 0.9 # Spread checkpoint I/O over time
effective_cache_size = 6GB    # Estimate of RAM available for disk caching by OS and PG
logging_collector = on
log_directory = 'log'         # Relative to PGDATA, or absolute path
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log' # Rotated log files
log_min_duration_statement = 250ms # Log statements slower than this (ms)
# --- END TRANSIT SERVER CUSTOMISATIONS ---
"""
        try:
            # Check if the customisation marker is already in the file
            grep_result = run_elevated_command(
                ["grep", "-qF", customisation_marker, pg_conf_file],
                check=False, capture_output=True, current_logger=logger_to_use,
            )
            if grep_result.returncode != 0:  # Marker not found, append settings
                run_elevated_command(
                    ["tee", "-a", pg_conf_file],  # Append to the file
                    cmd_input=postgresql_custom_conf_content,
                    current_logger=logger_to_use,
                )
                log_map_server(
                    f"{config.SYMBOLS['success']} Appended custom settings to "
                    f"{pg_conf_file}",
                    "success", logger_to_use
                )
            else:
                log_map_server(
                    f"{config.SYMBOLS['info']} Customizations marker already "
                    f"found in {pg_conf_file}. Assuming settings are applied "
                    "or managed manually.",
                    "info", logger_to_use
                )
        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error updating {pg_conf_file}: {e}",
                "error", logger_to_use
            )
            # Non-critical, proceed with HBA config

    # Customize pg_hba.conf
    if backup_file(pg_hba_file, current_logger=logger_to_use):
        if not validate_cidr(config.ADMIN_GROUP_IP, current_logger=logger_to_use):
            log_map_server(
                f"{config.SYMBOLS['error']} Invalid ADMIN_GROUP_IP "
                f"'{config.ADMIN_GROUP_IP}' for pg_hba.conf. "
                "Skipping HBA update.",
                "error", logger_to_use
            )
        else:
            pg_hba_content = f"""# pg_hba.conf configured by script V{script_hash_for_comments}
# For security, this overwrites existing pg_hba.conf. Review carefully.
# TYPE  DATABASE        USER            ADDRESS                 METHOD

# "local" is for Unix domain socket connections only
local   all             postgres                                peer
local   all             all                                     peer
local   {config.PGDATABASE}    {config.PGUSER}                                scram-sha-256

# IPv4 local connections:
host    all             all             127.0.0.1/32            scram-sha-256
host    {config.PGDATABASE}    {config.PGUSER}        127.0.0.1/32            scram-sha-256
# Allow connections from admin IP range for the specific database and user
host    {config.PGDATABASE}    {config.PGUSER}        {config.ADMIN_GROUP_IP}       scram-sha-256

# IPv6 local connections:
host    all             all             ::1/128                 scram-sha-256
host    {config.PGDATABASE}    {config.PGUSER}        ::1/128                 scram-sha-256
# Add IPv6 admin access if needed:
# host    {config.PGDATABASE}    {config.PGUSER}        admin_ipv6_cidr         scram-sha-256
"""
            try:
                run_elevated_command(
                    ["tee", pg_hba_file],  # Overwrites the file
                    cmd_input=pg_hba_content,
                    current_logger=logger_to_use,
                )
                log_map_server(
                    f"{config.SYMBOLS['success']} Overwrote {pg_hba_file} "
                    "with new rules.",
                    "success", logger_to_use
                )
            except Exception as e:
                log_map_server(
                    f"{config.SYMBOLS['error']} Error writing {pg_hba_file}: {e}",
                    "error", logger_to_use
                )
                # pg_hba.conf is critical; consider re-raising if overwrite fails.

    # Restart and enable PostgreSQL service
    log_map_server(
        f"{config.SYMBOLS['gear']} Restarting and enabling PostgreSQL service...",
        "info", logger_to_use
    )
    run_elevated_command(
        ["systemctl", "restart", "postgresql"], current_logger=logger_to_use
    )
    run_elevated_command(
        ["systemctl", "enable", "postgresql"], current_logger=logger_to_use
    )
    log_map_server(
        f"{config.SYMBOLS['info']} PostgreSQL service status:",
        "info", logger_to_use
    )
    run_elevated_command(
        ["systemctl", "status", "postgresql", "--no-pager", "-l"],
        current_logger=logger_to_use,
    )
    log_map_server(
        f"{config.SYMBOLS['success']} PostgreSQL setup completed.",
        "success", logger_to_use
    )
