# setup/services_setup.py
"""
Functions for setting up and configuring various map-related services.
"""
import logging
import os
import getpass
import shutil
import tempfile
import time
import subprocess  # For CalledProcessError specifically

from . import config  # For config.PGUSER, config.ADMIN_GROUP_IP, config.SYMBOLS etc.
# Corrected import: SYMBOLS removed from here
from .command_utils import run_command, run_elevated_command, log_map_server, command_exists
from .helpers import backup_file, validate_cidr, systemd_reload
from .ui import execute_step  # To call individual steps if this module had sub-steps

module_logger = logging.getLogger(__name__)


def ufw_setup(current_logger=None) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Setting up firewall with ufw...", "info", logger_to_use)

    if not validate_cidr(config.ADMIN_GROUP_IP, current_logger=logger_to_use):
        msg = f"Firewall setup aborted: Invalid ADMIN_GROUP_IP CIDR format '{config.ADMIN_GROUP_IP}'."
        log_map_server(f"{config.SYMBOLS['error']} {msg}", "error", logger_to_use)
        raise ValueError(msg)

    try:
        run_elevated_command(["ufw", "default", "deny", "incoming"], current_logger=logger_to_use)
        run_elevated_command(["ufw", "default", "allow", "outgoing"], current_logger=logger_to_use)
        run_elevated_command(["ufw", "allow", "in", "on", "lo"], current_logger=logger_to_use)
        run_elevated_command(["ufw", "allow", "out", "on", "lo"], current_logger=logger_to_use)

        run_elevated_command(
            ["ufw", "allow", "from", config.ADMIN_GROUP_IP, "to", "any", "port", "22", "proto", "tcp", "comment",
             "SSH from Admin"],
            current_logger=logger_to_use
        )
        run_elevated_command(
            ["ufw", "allow", "from", config.ADMIN_GROUP_IP, "to", "any", "port", "5432", "proto", "tcp", "comment",
             "PostgreSQL from Admin"],
            current_logger=logger_to_use
        )
        run_elevated_command(["ufw", "allow", "http", "comment", "Nginx HTTP"], current_logger=logger_to_use)
        run_elevated_command(["ufw", "allow", "https", "comment", "Nginx HTTPS"], current_logger=logger_to_use)

        log_map_server(
            f"{config.SYMBOLS['warning']} UFW will be enabled. Ensure SSH from '{config.ADMIN_GROUP_IP}' & Nginx ports (80, 443) are allowed.",
            "warning", logger_to_use)

        status_result = run_elevated_command(["ufw", "status"], capture_output=True, check=False,
                                             current_logger=logger_to_use)
        if "inactive" in status_result.stdout.lower():
            run_elevated_command(["ufw", "enable"], cmd_input="y\n", check=True, current_logger=logger_to_use)
            log_map_server(f"{config.SYMBOLS['success']} UFW enabled.", "success", logger_to_use)
        else:
            log_map_server(
                f"{config.SYMBOLS['info']} UFW is already active or status not 'inactive'. Status: {status_result.stdout.strip()}",
                "info", logger_to_use)

        log_map_server(f"{config.SYMBOLS['info']} UFW status details:", "info", logger_to_use)
        run_elevated_command(["ufw", "status", "verbose"], current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['success']} UFW setup completed.", "success", logger_to_use)
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['error']} Error during UFW setup: {e}", "error", logger_to_use)
        raise


def postgres_setup(current_logger=None) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Setting up PostgreSQL...", "info", logger_to_use)

    pg_version = "15"
    pg_conf_dir = f"/etc/postgresql/{pg_version}/main"
    pg_conf_file = os.path.join(pg_conf_dir, "postgresql.conf")
    pg_hba_file = os.path.join(pg_conf_dir, "pg_hba.conf")

    if not os.path.isdir(pg_conf_dir):  # This check should be fine without sudo
        log_map_server(
            f"{config.SYMBOLS['error']} PostgreSQL config directory not found: {pg_conf_dir}. Is PostgreSQL v{pg_version} installed?",
            "error", logger_to_use)
        raise FileNotFoundError(f"PostgreSQL config directory {pg_conf_dir} not found.")

    try:
        log_map_server(f"{config.SYMBOLS['gear']} Creating PostgreSQL user '{config.PGUSER}'...", "info", logger_to_use)
        run_elevated_command(["sudo", "-u", "postgres", "psql", "-c",
                              f"CREATE USER {config.PGUSER} WITH PASSWORD '{config.PGPASSWORD}';"],
                             current_logger=logger_to_use)
    except subprocess.CalledProcessError as e:
        if "already exists" in e.stderr.lower():
            log_map_server(
                f"{config.SYMBOLS['info']} PostgreSQL user '{config.PGUSER}' already exists. Updating password.",
                "info", logger_to_use)
            run_elevated_command(["sudo", "-u", "postgres", "psql", "-c",
                                  f"ALTER USER {config.PGUSER} WITH PASSWORD '{config.PGPASSWORD}';"],
                                 current_logger=logger_to_use)
        else:
            raise

    try:
        log_map_server(f"{config.SYMBOLS['gear']} Creating PostgreSQL database '{config.PGDATABASE}'...", "info",
                       logger_to_use)
        run_elevated_command([
            "sudo", "-u", "postgres", "psql", "-c",
            f"CREATE DATABASE {config.PGDATABASE} WITH OWNER {config.PGUSER} ENCODING 'UTF8' LC_COLLATE='en_AU.UTF-8' LC_CTYPE='en_AU.UTF-8' TEMPLATE template0;"
        ], current_logger=logger_to_use)
    except subprocess.CalledProcessError as e:
        if "already exists" in e.stderr.lower():
            log_map_server(f"{config.SYMBOLS['info']} PostgreSQL database '{config.PGDATABASE}' already exists.",
                           "info", logger_to_use)
        else:
            raise

    extensions = ["postgis", "hstore"]
    for ext in extensions:
        log_map_server(f"{config.SYMBOLS['gear']} Ensuring PostgreSQL extension '{ext}' in '{config.PGDATABASE}'...",
                       "info", logger_to_use)
        run_elevated_command(
            ["sudo", "-u", "postgres", "psql", "-d", config.PGDATABASE, "-c", f"CREATE EXTENSION IF NOT EXISTS {ext};"],
            current_logger=logger_to_use)

    log_map_server(f"{config.SYMBOLS['gear']} Setting database permissions for user '{config.PGUSER}'...", "info",
                   logger_to_use)
    db_permission_commands = [
        f"ALTER SCHEMA public OWNER TO {config.PGUSER};",
        f"GRANT ALL ON SCHEMA public TO {config.PGUSER};",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {config.PGUSER};",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {config.PGUSER};",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO {config.PGUSER};"
    ]
    for cmd_sql in db_permission_commands:
        run_elevated_command(["sudo", "-u", "postgres", "psql", "-d", config.PGDATABASE, "-c", cmd_sql],
                             current_logger=logger_to_use)
    log_map_server(f"{config.SYMBOLS['success']} PostgreSQL user, database, extensions, and permissions configured.",
                   "success", logger_to_use)

    if backup_file(pg_conf_file, current_logger=logger_to_use):
        # ... (postgresql.conf content and update logic as before, using config.SYMBOLS) ...
        customisation_marker = "# --- TRANSIT SERVER CUSTOMISATIONS - Appended by script ---"
        grep_result = run_elevated_command(["grep", "-qF", customisation_marker, pg_conf_file], check=False,
                                           capture_output=True, current_logger=logger_to_use)
        if grep_result.returncode != 0:
            # Define postgresql_custom_conf_content here
            postgresql_custom_conf_content = "..."  # (As in your original script)
            run_elevated_command(["tee", "-a", pg_conf_file], cmd_input=postgresql_custom_conf_content,
                                 current_logger=logger_to_use)
            log_map_server(f"{config.SYMBOLS['success']} Customized {pg_conf_file}", "success", logger_to_use)
        else:
            log_map_server(f"{config.SYMBOLS['info']} Customizations marker found in {pg_conf_file}.", "info",
                           logger_to_use)

    if backup_file(pg_hba_file, current_logger=logger_to_use):
        if not validate_cidr(config.ADMIN_GROUP_IP, current_logger=logger_to_use):
            log_map_server(f"{config.SYMBOLS['error']} Invalid ADMIN_GROUP_IP for pg_hba.conf. Skipping HBA update.",
                           "error", logger_to_use)
        else:
            # Define pg_hba_content here
            pg_hba_content = "..."  # (As in your original script, using config variables)
            run_elevated_command(["tee", pg_hba_file], cmd_input=pg_hba_content, current_logger=logger_to_use)
            log_map_server(f"{config.SYMBOLS['success']} Customized {pg_hba_file} (Overwritten).", "success",
                           logger_to_use)

    log_map_server(f"{config.SYMBOLS['gear']} Restarting and enabling PostgreSQL service...", "info", logger_to_use)
    run_elevated_command(["systemctl", "restart", "postgresql"], current_logger=logger_to_use)
    run_elevated_command(["systemctl", "enable", "postgresql"], current_logger=logger_to_use)
    log_map_server(f"{config.SYMBOLS['info']} PostgreSQL service status:", "info", logger_to_use)
    run_elevated_command(["systemctl", "status", "postgresql", "--no-pager", "-l"], current_logger=logger_to_use)
    log_map_server(f"{config.SYMBOLS['success']} PostgreSQL setup completed.", "success", logger_to_use)


# Define other service setup functions (pg_tileserv_setup, carto_setup, etc.) here,
# refactoring them to use run_elevated_command, run_command, log_map_server(config.SYMBOLS...),
# and config.VARIABLES. They should all accept current_logger.

# Example:
def pg_tileserv_setup(current_logger=None):
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Placeholder for pg_tileserv_setup", "info", logger_to_use)
    # ... (Full refactored logic for pg_tileserv_setup) ...


def carto_setup(current_logger=None):
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Placeholder for carto_setup", "info", logger_to_use)
    # ... (Full refactored logic for carto_setup) ...


# ... and so on for renderd_setup, osm_osrm_server_setup, apache_modtile_setup, nginx_setup, certbot_setup ...


def services_setup_group(current_logger) -> bool:
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"--- {config.SYMBOLS['info']} Starting Services Setup Group ---", "info", logger_to_use)
    overall_success = True

    step_definitions_in_group = [
        ("UFW_SETUP", "Setup UFW Firewall", ufw_setup),
        ("POSTGRES_SETUP", "Setup PostgreSQL Database & User", postgres_setup),
        ("PGTILESERV_SETUP", "Setup pg_tileserv", pg_tileserv_setup),
        ("CARTO_SETUP", "Setup CartoCSS Compiler & OSM Style", carto_setup),
        # TODO: Add other service setup functions here
        # ("RENDERD_SETUP", "Setup Renderd for Raster Tiles", renderd_setup),
        # ("OSM_OSRM_SERVER_SETUP", "Setup OSM Data & OSRM", osm_osrm_server_setup),
        # ("APACHE_SETUP", "Setup Apache for mod_tile", apache_modtile_setup),
        # ("NGINX_SETUP", "Setup Nginx Reverse Proxy", nginx_setup),
        # ("CERTBOT_SETUP", "Setup Certbot for SSL (optional)", certbot_setup),
    ]

    for tag, desc, func in step_definitions_in_group:
        if not execute_step(tag, desc, func, logger_to_use):  # execute_step from ui.py
            overall_success = False
            log_map_server(f"{config.SYMBOLS['error']} Step '{desc}' failed. Aborting services setup group.", "error",
                           logger_to_use)
            break

    log_map_server(
        f"--- {config.SYMBOLS['info']} Services Setup Group Finished (Overall Success: {overall_success}) ---",
        "info" if overall_success else "error", logger_to_use)
    return overall_success