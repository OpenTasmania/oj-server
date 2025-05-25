# setup/services/postgres.py
"""
Handles the setup and configuration of PostgreSQL.
"""
import logging
import os
import subprocess
from typing import Optional

from setup import config
from setup.command_utils import run_command, run_elevated_command, log_map_server
from setup.helpers import backup_file, validate_cidr  # Import necessary helpers

module_logger = logging.getLogger(__name__)


def postgres_setup(current_logger: Optional[logging.Logger] = None) -> None:
    """Set up PostgreSQL user, database, extensions, and configurations."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Setting up PostgreSQL...",
        "info",
        logger_to_use,
    )

    pg_version = "15"  # TODO: Make this detectable or configurable
    pg_conf_dir = f"/etc/postgresql/{pg_version}/main"
    pg_conf_file = os.path.join(pg_conf_dir, "postgresql.conf")
    pg_hba_file = os.path.join(pg_conf_dir, "pg_hba.conf")

    if not os.path.isdir(pg_conf_dir):
        try:
            run_elevated_command(
                ["test", "-d", pg_conf_dir],
                check=True,
                capture_output=True,
                current_logger=logger_to_use,
            )
        except subprocess.CalledProcessError as e:
            log_map_server(
                f"{config.SYMBOLS['error']} PostgreSQL config directory not found: {pg_conf_dir}. Is PostgreSQL v{pg_version} installed?",
                "error",
                logger_to_use,
            )
            raise FileNotFoundError(
                f"PostgreSQL config directory {pg_conf_dir} not found."
            ) from e

    # Create user
    try:
        log_map_server(
            f"{config.SYMBOLS['gear']} Creating PostgreSQL user '{config.PGUSER}'...",
            "info",
            logger_to_use,
        )
        run_command(
            [
                "sudo",
                "-u",
                "postgres",
                "psql",
                "-c",
                f"CREATE USER {config.PGUSER} WITH PASSWORD '{config.PGPASSWORD}';",
            ],
            capture_output=True,
            current_logger=logger_to_use,
        )
    except subprocess.CalledProcessError as e:
        if e.stderr and "already exists" in e.stderr.lower():
            log_map_server(
                f"{config.SYMBOLS['info']} PostgreSQL user '{config.PGUSER}' already exists. Attempting to update password.",
                "info",
                logger_to_use,
            )
            run_command(
                [
                    "sudo",
                    "-u",
                    "postgres",
                    "psql",
                    "-c",
                    f"ALTER USER {config.PGUSER} WITH PASSWORD '{config.PGPASSWORD}';",
                ],
                capture_output=True,
                current_logger=logger_to_use,
            )
        else:
            err_msg = (
                e.stderr.strip()
                if e.stderr
                else "Unknown psql error during user creation."
            )
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to create/alter PostgreSQL user '{config.PGUSER}'. Error: {err_msg}",
                "error",
                logger_to_use,
            )
            raise

    # Create database
    try:
        log_map_server(
            f"{config.SYMBOLS['gear']} Creating PostgreSQL database '{config.PGDATABASE}'...",
            "info",
            logger_to_use,
        )
        run_command(
            [
                "sudo",
                "-u",
                "postgres",
                "psql",
                "-c",
                f"CREATE DATABASE {config.PGDATABASE} WITH OWNER {config.PGUSER} ENCODING 'UTF8' LC_COLLATE='en_AU.UTF-8' LC_CTYPE='en_AU.UTF-8' TEMPLATE template0;",
            ],
            capture_output=True,
            current_logger=logger_to_use,
        )
    except subprocess.CalledProcessError as e:
        if e.stderr and "already exists" in e.stderr.lower():
            log_map_server(
                f"{config.SYMBOLS['info']} PostgreSQL database '{config.PGDATABASE}' already exists.",
                "info",
                logger_to_use,
            )
        else:
            err_msg = (
                e.stderr.strip()
                if e.stderr
                else "Unknown psql error during database creation."
            )
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to create PostgreSQL database '{config.PGDATABASE}'. Error: {err_msg}",
                "error",
                logger_to_use,
            )
            raise

    extensions = ["postgis", "hstore"]
    for ext in extensions:
        log_map_server(
            f"{config.SYMBOLS['gear']} Ensuring PostgreSQL extension '{ext}' in '{config.PGDATABASE}'...",
            "info",
            logger_to_use,
        )
        run_command(
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

    log_map_server(
        f"{config.SYMBOLS['gear']} Setting database permissions for user '{config.PGUSER}'...",
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
        f"{config.SYMBOLS['success']} PostgreSQL user, database, extensions, and permissions configured.",
        "success",
        logger_to_use,
    )

    if backup_file(pg_conf_file, current_logger=logger_to_use):
        postgresql_custom_conf_content = f"""
# --- TRANSIT SERVER CUSTOMISATIONS - Appended by script V{config.SCRIPT_HASH} ---
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
        customisation_marker = (
            "# --- TRANSIT SERVER CUSTOMISATIONS - Appended by script"
        )
        try:
            grep_result = run_elevated_command(
                ["grep", "-qF", customisation_marker, pg_conf_file],
                check=False,
                capture_output=True,
                current_logger=logger_to_use,
            )
            if grep_result.returncode != 0:
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
                    f"{config.SYMBOLS['info']} Customizations marker already found in {pg_conf_file}. Assuming settings are applied or managed manually.",
                    "info",
                    logger_to_use,
                )
        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error updating {pg_conf_file}: {e}",
                "error",
                logger_to_use,
            )

    if backup_file(pg_hba_file, current_logger=logger_to_use):
        if not validate_cidr(
            config.ADMIN_GROUP_IP, current_logger=logger_to_use
        ):
            log_map_server(
                f"{config.SYMBOLS['error']} Invalid ADMIN_GROUP_IP '{config.ADMIN_GROUP_IP}' for pg_hba.conf. Skipping HBA update.",
                "error",
                logger_to_use,
            )
        else:
            pg_hba_content = f"""# pg_hba.conf configured by script V{config.SCRIPT_HASH}
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
                run_elevated_command(
                    ["tee", pg_hba_file],
                    cmd_input=pg_hba_content,
                    current_logger=logger_to_use,
                )
                log_map_server(
                    f"{config.SYMBOLS['success']} Overwrote {pg_hba_file} with new rules.",
                    "success",
                    logger_to_use,
                )
            except Exception as e:
                log_map_server(
                    f"{config.SYMBOLS['error']} Error writing {pg_hba_file}: {e}",
                    "error",
                    logger_to_use,
                )

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
