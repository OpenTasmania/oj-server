#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Server setup and configuration script for development environments
Copyright 2025 plawler

This script handles the setup and configuration of a map server environment, including:
- PostgreSQL with PostGIS
- pg_tileserv for vector tiles
- Renderd for raster tiles
- OSRM for routing
- Apache with mod_tile
- Nginx as a reverse proxy
- GTFS data processing

The script provides a menu-driven interface for user interaction and tracks the progress of installation steps.
"""

## TODO: Use python to install docker images

import argparse
import datetime
import getpass
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import List, Callable

logging.basicConfig(level=logging.ERROR)
logger_fallback = logging.getLogger(__name__)
# Ensure the package root is in PYTHONPATH if running script directly for development
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)

try:
    from gtfs_processor import utils
except ImportError as e:
    # Fallback for cases where the script might be run before the package is properly installed
    logger_fallback.error(
        f"Failed to import gtfs_processor modules. Ensure the package is installed or PYTHONPATH is set.")
    logger_fallback.error(f"Package Root (attempted): {PACKAGE_ROOT}")
    logger_fallback.error(f"Sys Path: {sys.path}")
    logger_fallback.error(f"ImportError: {e}")
    sys.exit(1)

# --- Default Global Variable Values ---
ADMIN_GROUP_IP_DEFAULT = "192.168.128.0/22"
GTFS_FEED_URL_DEFAULT = "https://www.transport.act.gov.au/googletransit/google_transit.zip"
VM_IP_OR_DOMAIN_DEFAULT = "example.com"
PG_TILESERV_BINARY_LOCATION_DEFAULT = "https://postgisftw.s3.amazonaws.com/pg_tileserv_latest_linux.zip"
LOG_PREFIX_DEFAULT = "[SETUP]"
PGHOST_DEFAULT = "localhost"
PGPORT_DEFAULT = "5432"
PGDATABASE_DEFAULT = "gis"
PGUSER_DEFAULT = "osmuser"
PGPASSWORD_DEFAULT = "yourStrongPasswordHere"

# --- State File Configuration ---
STATE_FILE_DIR = "/var/lib/map-server-setup-script"
STATE_FILE = os.path.join(STATE_FILE_DIR, "progress_state.txt")
SCRIPT_VERSION = "1.1"  # Increment if script logic/steps change significantly

# --- Package Lists ---
PYTHON_PACKAGES = [
    "python3", "python3-pip", "python3-venv", "python3-dev", "python3-yaml",
    "python3-pandas", "python3-psycopg2", "python3-psycopg"
]
POSTGRES_PACKAGES = [
    "postgresql", "postgresql-contrib", "postgis", "postgresql-15-postgis-3",
    "postgresql-15-postgis-3-scripts"
]
FONT_PACKAGES = [
    "fontconfig", "fonts-noto-core", "fonts-noto-cjk", "fonts-noto-ui-core", "fonts-noto-mono",
    "fonts-dejavu", "fonts-dejavu-core", "fonts-dejavu-extra", "fonts-unifont", "fonts-hanazono",
    "fonts-sil-gentium-basic", "fonts-firacode", "fonts-crosextra-carlito", "fonts-takao-gothic",
    "fonts-takao-mincho", "fonts-takao"
]
MAPPING_PACKAGES = [
    "cmake", "libbz2-dev", "libstxxl-dev", "libstxxl1v5", "libxml2-dev", "libzip-dev",
    "libboost-all-dev", "lua5.4", "liblua5.4-dev", "libtbb-dev", "libluabind-dev", "pkg-config",
    "apache2", "libapache2-mod-tile", "renderd", "mapnik-utils", "python3-mapnik", "libmapnik-dev",
    "xmlstarlet", "nginx", "osm2pgsql", "gdal-bin", "osmium-tool", "osmcoastline"
]

# --- Logger Setup ---
logger = logging.getLogger(__name__)


def setup_logging(log_level: int = logging.INFO, log_to_console: bool = True) -> None:
    """
    Set up logging configuration.

    Args:
        log_level: The logging level to use
        log_to_console: Whether to log to console
    """
    logging.basicConfig(
        level=log_level,
        format=f"{LOG_PREFIX} %(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Disable console logging if not requested
    if not log_to_console:
        logging.getLogger().removeHandler(logging.getLogger().handlers[0])


def log(message: str) -> None:
    """
    Log a message with the configured prefix.

    Args:
        message: The message to log
    """
    logger.info(message)


# --- Command Execution Helpers ---
def run_command(command: List[str], check: bool = True, shell: bool = False,
                capture_output: bool = False) -> subprocess.CompletedProcess:
    """
    Run a command and handle errors.

    Args:
        command: The command to run as a list of strings
        check: Whether to check the return code
        shell: Whether to run the command in a shell
        capture_output: Whether to capture stdout and stderr

    Returns:
        The completed process object
    """
    try:
        if shell and isinstance(command, list):
            command = " ".join(command)

        log(f"Running command: {command}")
        result = subprocess.run(
            command,
            check=check,
            shell=shell,
            capture_output=capture_output,
            text=True
        )
        return result
    except subprocess.CalledProcessError as e:
        log(f"Command failed with return code {e.returncode}")
        log(f"Command output: {e.stdout if hasattr(e, 'stdout') else 'N/A'}")
        log(f"Command error: {e.stderr if hasattr(e, 'stderr') else 'N/A'}")
        raise


def run_sudo_command(command: List[str], check: bool = True,
                     capture_output: bool = False) -> subprocess.CompletedProcess:
    """
    Run a command with sudo and handle errors.

    Args:
        command: The command to run as a list of strings
        check: Whether to check the return code
        capture_output: Whether to capture stdout and stderr

    Returns:
        The completed process object
    """
    sudo_command = ["sudo"] + command
    return run_command(sudo_command, check, False, capture_output)


# --- State Management Functions ---
def initialize_state_system() -> None:
    """
    Initialize the state system for tracking progress.
    Ensures directory and file exist with appropriate permissions.
    """
    # Ensure directory exists
    if not os.path.isdir(STATE_FILE_DIR):
        log(f"Creating state directory: {STATE_FILE_DIR}")
        run_sudo_command(["mkdir", "-p", STATE_FILE_DIR])
        run_sudo_command(["chmod", "750", STATE_FILE_DIR])

    # Ensure file exists
    if not os.path.isfile(STATE_FILE):
        log(f"Initializing state file: {STATE_FILE}")
        run_sudo_command(["touch", STATE_FILE])
        run_sudo_command(["chmod", "640", STATE_FILE])
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write(f"# Script Version: {SCRIPT_VERSION}\n")
            temp_file_path = temp_file.name
        run_sudo_command(["cp", temp_file_path, STATE_FILE])
        os.unlink(temp_file_path)
    else:
        # Check script version in state file
        result = run_sudo_command(["grep", "^# Script Version:", STATE_FILE], capture_output=True)
        if result.returncode == 0:
            stored_version = result.stdout.strip().split()[-1]
            if stored_version != SCRIPT_VERSION:
                # In a real implementation, we would use a dialog library like PyInquirer
                # For simplicity, we'll just print a message and clear the state file
                log(f"Script version mismatch. Stored: {stored_version}, Current: {SCRIPT_VERSION}")
                log("Clearing state file due to version mismatch.")
                with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                    temp_file.write(f"# Script Version: {SCRIPT_VERSION}\n")
                    temp_file_path = temp_file.name
                run_sudo_command(["cp", temp_file_path, STATE_FILE])
                os.unlink(temp_file_path)


def mark_step_completed(step_tag: str) -> None:
    """
    Mark a step as completed in the state file.

    Args:
        step_tag: The tag identifying the step
    """
    # Check if already marked to avoid duplicates
    result = run_sudo_command(["grep", "-Fxq", step_tag, STATE_FILE], check=False)
    if result.returncode != 0:
        log(f"Marking step '{step_tag}' as completed.")
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write(f"{step_tag}\n")
            temp_file_path = temp_file.name
        run_sudo_command(["tee", "-a", STATE_FILE], input=open(temp_file_path, 'r').read(), check=False)
        os.unlink(temp_file_path)
    else:
        log(f"Step '{step_tag}' was already marked as completed.")


def is_step_completed(step_tag: str) -> bool:
    """
    Check if a step is marked as completed in the state file.

    Args:
        step_tag: The tag identifying the step

    Returns:
        True if the step is completed, False otherwise
    """
    result = run_sudo_command(["grep", "-Fxq", step_tag, STATE_FILE], check=False)
    return result.returncode == 0


def clear_state_file() -> None:
    """
    Clear the state file, resetting all progress.
    """
    log(f"Clearing state file: {STATE_FILE}")
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write(f"# Script Version: {SCRIPT_VERSION}\n")
        temp_file_path = temp_file.name
    run_sudo_command(["cp", temp_file_path, STATE_FILE])
    os.unlink(temp_file_path)
    log("Progress state file cleared. All steps will need to be re-run.")


def view_completed_steps() -> List[str]:
    """
    View the steps marked as completed in the state file.

    Returns:
        A list of completed step tags
    """
    result = run_sudo_command(["grep", "-v", "^# Script Version:", STATE_FILE], capture_output=True, check=False)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip().split('\n')
    return []


# --- Helper Functions ---
def backup_file(file_path: str) -> bool:
    """
    Create a backup of a file with timestamp.

    Args:
        file_path: The path to the file to backup

    Returns:
        True if backup was successful, False otherwise
    """
    if not os.path.isfile(file_path):
        log(f"Warning: File {file_path} does not exist, cannot backup.")
        return False

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    backup_path = f"{file_path}.bak.{timestamp}"
    run_sudo_command(["cp", file_path, backup_path])
    log(f"Backed up {file_path} to {backup_path}")
    return True


def validate_cidr(cidr: str) -> bool:
    """
    Validate a CIDR notation IP address range.

    Args:
        cidr: The CIDR notation string to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        # Simple validation - in a real implementation, we would use ipaddress module
        parts = cidr.split('/')
        if len(parts) != 2:
            return False

        ip_parts = parts[0].split('.')
        if len(ip_parts) != 4:
            return False

        for part in ip_parts:
            num = int(part)
            if num < 0 or num > 255:
                return False

        prefix = int(parts[1])
        if prefix < 0 or prefix > 32:
            return False

        return True
    except (ValueError, IndexError):
        return False


def setup_pgpass() -> None:
    """
    Set up .pgpass file for PostgreSQL authentication.
    """
    if not PGPASSWORD:
        log("INFO: PGPASSWORD is not set. .pgpass file not created. Some PostgreSQL operations might require manual password entry or other auth methods.")
        return

    # Get correct home directory
    home_dir = os.path.expanduser("~")
    pgpass_file = os.path.join(home_dir, ".pgpass")

    # Create .pgpass file
    with open(pgpass_file, 'w') as f:
        f.write(f"{PGHOST}:{PGPORT}:{PGDATABASE}:{PGUSER}:{PGPASSWORD}\n")

    # Set permissions
    os.chmod(pgpass_file, 0o600)
    log(f".pgpass file configured at {pgpass_file} for user {getpass.getuser()}.")


# --- Core Installation Functions ---
def systemd_reload() -> None:
    """Reload systemd daemon."""
    log("Reloading systemd daemon")
    run_sudo_command(["systemctl", "daemon-reload"])


def boot_verbosity() -> None:
    """Improve boot verbosity and add core utilities."""
    log("Improving boot verbosity")
    if backup_file("/etc/default/grub"):
        # Use sed to modify grub configuration
        run_sudo_command([
            "sed", "-i.sedbak_grub_verbosity", "-E",
            "-e", "/^GRUB_CMDLINE_LINUX_DEFAULT=/s/\\bquiet\\b//g",
            "-e", "/^GRUB_CMDLINE_LINUX_DEFAULT=/s/\\bsplash\\b//g",
            "-e", "/^GRUB_CMDLINE_LINUX_DEFAULT=/s/  +/ /g",
            "-e", "/^GRUB_CMDLINE_LINUX_DEFAULT=/s/\" /\"/g",
            "-e", "/^GRUB_CMDLINE_LINUX_DEFAULT=/s/ \"/\"/g",
            "/etc/default/grub"
        ])
        run_sudo_command(["update-grub"])
        run_sudo_command(["update-initramfs", "-u"])

    log("Configuring and adding core utilities")
    run_sudo_command(["usermod", "--append", "--group", "systemd-journal", getpass.getuser()])

    run_sudo_command(["apt", "update"])
    run_sudo_command(["apt", "--yes", "upgrade"])
    run_sudo_command(["apt", "--yes", "install", "bash", "btop", "curl", "screen", "wget"])


def core_conflict_removal() -> None:
    """Remove unwanted tools (e.g., system Node.js if using NVM or nodesource)."""
    log("Removing unwanted tools (e.g., system Node.js if using NVM or nodesource)")

    # Check if Node.js is installed by package manager
    result = run_command(["dpkg", "-s", "nodejs"], check=False, capture_output=True)
    if result.returncode == 0:
        run_sudo_command(["apt", "remove", "--purge", "--yes", "nodejs", "npm"])
        run_sudo_command(["apt", "--purge", "--yes", "autoremove"])
        log("System nodejs and npm removed.")
    else:
        log("System nodejs not found via dpkg, skipping removal.")


def core_install() -> None:
    """Install core system packages."""
    log("Installing core system packages")
    run_sudo_command(["apt", "update"])

    log("Adding prerequisites")
    run_sudo_command([
        "apt", "--yes", "install", "git", "unzip", "vim", "build-essential", "software-properties-common",
        "dirmngr", "gnupg", "apt-transport-https", "lsb-release", "ca-certificates", "qemu-guest-agent", "ufw"
    ])

    log("Installing Python packages")
    run_sudo_command(["apt", "--yes", "install"] + PYTHON_PACKAGES)

    log("Installing PostgreSQL packages")
    run_sudo_command(["apt", "--yes", "install"] + POSTGRES_PACKAGES)

    log("Installing mapping packages")
    run_sudo_command(["apt", "--yes", "install"] + MAPPING_PACKAGES)

    log("Installing font packages")
    run_sudo_command(["apt", "--yes", "install"] + FONT_PACKAGES)

    run_sudo_command(["apt", "--yes", "install", "unattended-upgrades"])


def docker_install() -> None:
    """Set up Docker's official APT repository and install Docker."""
    log("Setting up Docker's official APT repository")
    log("Adding Docker's official GPG key")
    run_sudo_command(["install", "--mode", "0755", "--directory", "/etc/apt/keyrings"])

    # Download GPG key to a temporary location first, then move with sudo
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file_path = temp_file.name

    run_command(["curl", "-fsSL", "https://download.docker.com/linux/debian/gpg", "-o", temp_file_path])
    run_sudo_command(["mv", temp_file_path, "/etc/apt/keyrings/docker.asc"])
    run_sudo_command(["chmod", "a+r", "/etc/apt/keyrings/docker.asc"])

    log("Adding the repository to Apt sources")
    # Get architecture and codename
    arch = run_command(["dpkg", "--print-architecture"], capture_output=True).stdout.strip()
    codename = run_command(["lsb_release", "-cs"], capture_output=True).stdout.strip()

    # Create sources list entry
    docker_source = f"deb [arch={arch} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian {codename} stable"
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write(docker_source)
        temp_file_path = temp_file.name

    run_sudo_command(["tee", "/etc/apt/sources.list.d/docker.list"], input=open(temp_file_path, 'r').read())
    os.unlink(temp_file_path)

    run_sudo_command(["apt", "update"])
    run_sudo_command([
        "apt", "--yes", "install", "docker-ce", "docker-ce-cli", "containerd.io",
        "docker-buildx-plugin", "docker-compose-plugin"
    ])

    log(f"Adding current user ({getpass.getuser()}) to the 'docker' group")
    run_sudo_command(["usermod", "--append", "--group", "docker", getpass.getuser()])
    log("You may need to log out and log back in for the 'docker' group change to take effect.")

    run_sudo_command(["systemctl", "enable", "docker.service"])
    run_sudo_command(["systemctl", "enable", "containerd.service"])


def node_js_lts_install() -> None:
    """Install Node.js LTS version using NodeSource."""
    log("Installing Node.js LTS version using NodeSource")

    # Download and run the NodeSource setup script
    run_command(["curl", "-fsSL", "https://deb.nodesource.com/setup_lts.x"], capture_output=True, check=True)
    run_sudo_command(["bash", "-c", "curl -fsSL https://deb.nodesource.com/setup_lts.x | bash -"])

    run_sudo_command(["apt", "update"])
    run_sudo_command(["apt", "--yes", "install", "nodejs"])

    # Get Node.js and NPM versions
    node_version = run_command(["node", "-v"], capture_output=True, check=False).stdout.strip() or "Not installed"
    npm_version = run_command(["npm", "-v"], capture_output=True, check=False).stdout.strip() or "Not installed"

    log(f"Node.js version: {node_version}")
    log(f"NPM version: {npm_version}")


def ufw_setup() -> None:
    """Set up firewall with ufw."""
    log("Setting up firewall with ufw")

    if not validate_cidr(ADMIN_GROUP_IP):
        log("Firewall setup aborted due to invalid ADMIN_GROUP_IP.")
        return

    run_sudo_command(["ufw", "default", "deny", "incoming"])
    run_sudo_command(["ufw", "default", "allow", "outgoing"])
    run_sudo_command(["ufw", "allow", "in", "on", "lo"])
    run_sudo_command(["ufw", "allow", "out", "on", "lo"])

    run_sudo_command(["ufw", "allow", "from", ADMIN_GROUP_IP, "to", "any", "port", "22", "proto", "tcp", "comment",
                      "Allow SSH from Admin Group"])
    run_sudo_command(["ufw", "allow", "from", ADMIN_GROUP_IP, "to", "any", "port", "5432", "proto", "tcp", "comment",
                      "Allow PostgreSQL from Admin Group"])
    run_sudo_command(["ufw", "allow", "from", ADMIN_GROUP_IP, "to", "any", "port", "80", "proto", "tcp", "comment",
                      "Allow HTTP from Admin Group"])
    run_sudo_command(["ufw", "allow", "from", ADMIN_GROUP_IP, "to", "any", "port", "443", "proto", "tcp", "comment",
                      "Allow HTTPS from Admin Group"])

    run_sudo_command(["ufw", "allow", "5000/tcp", "comment", "OSRM proxied by Nginx"])
    run_sudo_command(["ufw", "allow", "7800/tcp", "comment", "pg_tileserv proxied by Nginx"])
    run_sudo_command(["ufw", "allow", "8080/tcp", "comment", "Apache serving raster tiles behind Nginx"])

    # In a real implementation, we would use a dialog library to confirm enabling UFW
    # For simplicity, we'll just enable it
    log("Enabling UFW firewall. Ensure your SSH access is correctly allowed.")
    run_sudo_command(["ufw", "enable"], input="y\n")

    log("UFW enabled. Status:")
    run_sudo_command(["ufw", "status", "verbose"])


def postgres_setup() -> None:
    """Set up PostgreSQL user, database, and extensions."""
    log("Setting up PostgreSQL user, database, and extensions")

    # Create user
    run_sudo_command(["sudo", "-u", "postgres", "psql", "-c", f"CREATE USER {PGUSER} WITH PASSWORD '{PGPASSWORD}';"])

    # Create database
    run_sudo_command([
        "sudo", "-u", "postgres", "psql", "-c",
        f"CREATE DATABASE {PGDATABASE} WITH OWNER {PGUSER} ENCODING 'UTF8' LC_COLLATE='en_AU.UTF-8' LC_CTYPE='en_AU.UTF-8' TEMPLATE template0;"
    ])

    # Create extensions
    run_sudo_command(
        ["sudo", "-u", "postgres", "psql", "-d", PGDATABASE, "-c", "CREATE EXTENSION IF NOT EXISTS postgis;"])
    run_sudo_command(
        ["sudo", "-u", "postgres", "psql", "-d", PGDATABASE, "-c", "CREATE EXTENSION IF NOT EXISTS hstore;"])

    # Set permissions
    run_sudo_command(
        ["sudo", "-u", "postgres", "psql", "-d", PGDATABASE, "-c", f"ALTER SCHEMA public OWNER TO {PGUSER};"])
    run_sudo_command([
        "sudo", "-u", "postgres", "psql", "-d", PGDATABASE, "-c",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {PGUSER};"
    ])
    run_sudo_command([
        "sudo", "-u", "postgres", "psql", "-d", PGDATABASE, "-c",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {PGUSER};"
    ])
    run_sudo_command([
        "sudo", "-u", "postgres", "psql", "-d", PGDATABASE, "-c",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO {PGUSER};"
    ])

    log(f"PostgreSQL user '{PGUSER}' and database '{PGDATABASE}' with PostGIS/HStore created.")

    # Configure postgresql.conf
    if backup_file("/etc/postgresql/15/main/postgresql.conf"):
        postgresql_custom_conf = """
### TRANSIT SERVER CUSTOMISATION FROM HERE ON
listen_addresses = '*' # QGIS on admin network needs direct access, set to '*' and rely on ufw & pg_hba.conf
shared_buffers = 2GB
work_mem = 256MB
maintenance_work_mem = 2GB
checkpoint_timeout = 15min
max_wal_size = 4GB
min_wal_size = 2GB
checkpoint_completion_target = 0.9
effective_cache_size = 24GB
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_min_duration_statement = 250ms
"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write(postgresql_custom_conf)
            temp_file_path = temp_file.name

        run_sudo_command(["tee", "-a", "/etc/postgresql/15/main/postgresql.conf"],
                         input=open(temp_file_path, 'r').read())
        os.unlink(temp_file_path)
        log("Customized postgresql.conf")

    # Configure pg_hba.conf
    if backup_file("/etc/postgresql/15/main/pg_hba.conf"):
        pg_hba_content = f"""# TRANSIT SERVER CUSTOMIAATION
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             postgres                                peer
local   all             all                                     peer
local   {PGDATABASE}   {PGUSER}                                   scram-sha-256
host    all             all             127.0.0.1/32            scram-sha-256
host    {PGDATABASE}   {PGUSER}           127.0.0.1/32            scram-sha-256
host    {PGDATABASE}   {PGUSER}           {ADMIN_GROUP_IP}       scram-sha-256
host    all             all             ::1/128                 scram-sha-256
host    {PGDATABASE}   {PGUSER}           ::1/128                 scram-sha-256
"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write(pg_hba_content)
            temp_file_path = temp_file.name

        run_sudo_command(["tee", "/etc/postgresql/15/main/pg_hba.conf"], input=open(temp_file_path, 'r').read())
        os.unlink(temp_file_path)
        log("Customized pg_hba.conf")

    # Restart and enable PostgreSQL
    run_sudo_command(["systemctl", "restart", "postgresql"])
    run_sudo_command(["systemctl", "enable", "postgresql"])
    log("PostgreSQL service restarted and enabled. Status:")
    run_sudo_command(["systemctl", "status", "postgresql", "--no-pager", "-l"])


def pg_tileserv_setup() -> None:
    """Set up pg_tileserv for vector tiles."""
    log("Setting up pg_tileserv")

    # Download and install pg_tileserv if not already installed
    if not os.path.isfile("/usr/local/bin/pg_tileserv"):
        log(f"pg_tileserv not found, downloading from {PG_TILESERV_BINARY_LOCATION}...")

        # Download to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
            temp_zip_path = temp_file.name

        run_command(["wget", PG_TILESERV_BINARY_LOCATION, "-O", temp_zip_path])

        # Create temporary directory for extraction
        temp_dir = tempfile.mkdtemp()

        # Extract pg_tileserv binary
        run_command(["unzip", temp_zip_path, "pg_tileserv", "-d", temp_dir])

        # Move to final location
        run_sudo_command(["mv", os.path.join(temp_dir, "pg_tileserv"), "/usr/local/bin/"])

        # Clean up
        os.unlink(temp_zip_path)
        shutil.rmtree(temp_dir)

        log("pg_tileserv installed.")
    else:
        log("pg_tileserv already exists.")

    # Check version
    run_command(["/usr/local/bin/pg_tileserv", "--version"])

    # Create configuration directory
    run_sudo_command(["mkdir", "-p", "/etc/pg_tileserv"])

    # Create configuration file
    pg_tileserv_config = f"""HttpHost = "0.0.0.0"
HttpPort = 7800
DatabaseUrl = "postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}"
DefaultMaxFeatures = 10000
PublishSchemas = "public"
URIPrefix = "/vector"
DevelopmentMode = true
AllowFunctionSources = true
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write(pg_tileserv_config)
        temp_file_path = temp_file.name

    run_sudo_command(["tee", "/etc/pg_tileserv/config.toml"], input=open(temp_file_path, 'r').read())
    os.unlink(temp_file_path)
    log("Created /etc/pg_tileserv/config.toml")

    # Create systemd service file
    pg_tileserv_service = f"""[Unit]
Description=pg_tileserv - Vector Tile Server for PostGIS
Wants=network-online.target postgresql.service
After=network-online.target postgresql.service

[Service]
User=pgtileserv_user
Group=pgtileserv_user
Environment="DATABASE_URL=postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}"
ExecStart=/usr/local/bin/pg_tileserv --debug --config /etc/pg_tileserv/config.toml
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=pg_tileserv

[Install]
WantedBy=multi-user.target
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write(pg_tileserv_service)
        temp_file_path = temp_file.name

    run_sudo_command(["tee", "/etc/systemd/system/pg_tileserv.service"], input=open(temp_file_path, 'r').read())
    os.unlink(temp_file_path)
    log("Created /etc/systemd/system/pg_tileserv.service")

    # Create user if it doesn't exist
    result = run_command(["id", "pgtileserv_user"], check=False, capture_output=True)
    if result.returncode != 0:
        run_sudo_command([
            "useradd", "--system", "--shell", "/usr/sbin/nologin",
            "--home-dir", "/var/empty", "--user-group", "pgtileserv_user"
        ])
        log("Created system user pgtileserv_user")
    else:
        log("System user pgtileserv_user already exists")

    # Set permissions
    run_sudo_command(["chmod", "700", "/usr/local/bin/pg_tileserv"])
    run_sudo_command(["chown", "pgtileserv_user:pgtileserv_user", "/usr/local/bin/pg_tileserv"])
    run_sudo_command(["chmod", "640", "/etc/pg_tileserv/config.toml"])
    run_sudo_command(["chown", "pgtileserv_user:pgtileserv_user", "/etc/pg_tileserv/config.toml"])

    # Reload systemd, enable and start service
    systemd_reload()
    run_sudo_command(["systemctl", "enable", "pg_tileserv"])
    run_sudo_command(["systemctl", "start", "pg_tileserv"])
    log("pg_tileserv service enabled and started. Status:")
    run_sudo_command(["systemctl", "status", "pg_tileserv", "--no-pager", "-l"])


def carto_setup() -> None:
    """Set up CartoCSS compiler and OpenStreetMap-Carto stylesheet."""
    log("Installing CartoCSS compiler (carto)")

    # Check if npm is installed
    result = run_command(["command", "-v", "npm"], check=False, capture_output=True, shell=True)
    if result.returncode != 0:
        log("NPM not found. Skipping carto setup. Please install Node.js/NPM first.")
        return

    # Install carto globally
    run_sudo_command(["npm", "install", "-g", "carto"])

    # Check carto version
    result = run_command(["carto", "-v"], check=False, capture_output=True)
    carto_version = result.stdout.strip() if result.returncode == 0 else "Failed to get version"
    log(f"Carto version: {carto_version}")

    # Set up OpenStreetMap-Carto stylesheet
    log("Setting up OpenStreetMap-Carto stylesheet")
    if not os.path.isdir("/opt/openstreetmap-carto"):
        run_sudo_command([
            "git", "clone", "https://github.com/gravitystorm/openstreetmap-carto.git",
            "/opt/openstreetmap-carto"
        ])
    else:
        log("Directory /opt/openstreetmap-carto already exists. Assuming it's up-to-date or managed manually.")

    # Temporarily change ownership
    run_sudo_command(["chown", "-R", f"{getpass.getuser()}:{getpass.getuser()}", "/opt/openstreetmap-carto"])

    # Change to directory and run setup
    current_dir = os.getcwd()
    try:
        os.chdir("/opt/openstreetmap-carto")

        # Get external data
        log("Getting external data for OpenStreetMap-Carto style...")
        if shutil.which("python3"):
            run_command(["python3", "scripts/get-external-data.py"])
        elif shutil.which("python"):
            run_command(["python", "scripts/get-external-data.py"])
        else:
            log("Python not found, cannot run get-external-data.py. Shapefiles might be missing.")

        # Compile project.mml to mapnik.xml
        log("Compiling project.mml to mapnik.xml...")
        with open("carto_convert_warnings_and_errors_log.txt", "w") as error_log:
            result = run_command(
                ["carto", "project.mml"],
                check=False,
                capture_output=True
            )
            if result.returncode == 0:
                with open("mapnik.xml", "w") as mapnik_file:
                    mapnik_file.write(result.stdout)
                error_log.write(result.stderr)
            else:
                error_log.write(f"Error: {result.stderr}")
                log("ERROR: Failed to compile mapnik.xml. Check carto_convert_warnings_and_errors_log.txt in /opt/openstreetmap-carto.")
                return

        # Check if mapnik.xml was created
        if not os.path.isfile("mapnik.xml") or os.path.getsize("mapnik.xml") == 0:
            log("ERROR: mapnik.xml was not created or is empty. Check carto_convert_warnings_and_errors_log.txt in /opt/openstreetmap-carto.")
            return

        # Create directory for mapnik.xml
        run_sudo_command(["mkdir", "-p", "/usr/local/share/maps/style/openstreetmap-carto"])

        # Copy mapnik.xml to final location
        run_sudo_command(["cp", "mapnik.xml", "/usr/local/share/maps/style/openstreetmap-carto/"])
        log("mapnik.xml copied to /usr/local/share/maps/style/openstreetmap-carto/")

    finally:
        os.chdir(current_dir)

    # Update font cache
    log("Ensuring Fontconfig is aware of all installed fonts")
    run_sudo_command(["fc-cache", "-fv"])


def renderd_setup() -> None:
    """Set up renderd for raster tiles."""
    log("Setting up renderd")

    # Get number of CPU cores for num_threads
    num_cores = os.cpu_count() or 2  # Default to 2 if os.cpu_count() returns None

    # Create renderd configuration file
    renderd_conf = f"""[renderd]
num_threads={num_cores * 2}
tile_dir=/var/lib/mod_tile
stats_file=/var/run/renderd/renderd.stats
font_dir_recurse=1

[mapnik]
plugins_dir=/usr/lib/mapnik/$(mapnik-config --input-plugins-version)/input/
font_dir=/usr/share/fonts/
font_dir_recurse=1

[default]
URI=/hot/
XML=/usr/local/share/maps/style/openstreetmap-carto/mapnik.xml
HOST=localhost
TILESIZE=256
# HMAXZOOM=20
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write(renderd_conf)
        temp_file_path = temp_file.name

    run_sudo_command(["tee", "/etc/renderd.conf"], input=open(temp_file_path, 'r').read())
    os.unlink(temp_file_path)
    log("Created /etc/renderd.conf")

    # Create systemd service file
    renderd_service = """[Unit]
Description=Daemon that renders map tiles using mapnik
Documentation=man:renderd
After=network.target auditd.service

[Service]
User=www-data
Group=www-data
RuntimeDirectory=renderd
RuntimeDirectoryMode=0755
ExecStart=/usr/bin/renderd -f -c /etc/renderd.conf

[Install]
WantedBy=multi-user.target
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write(renderd_service)
        temp_file_path = temp_file.name

    run_sudo_command(["tee", "/etc/systemd/system/renderd.service"], input=open(temp_file_path, 'r').read())
    os.unlink(temp_file_path)
    log("Created /etc/systemd/system/renderd.service")

    # Create necessary directories and set permissions
    run_sudo_command(["mkdir", "-p", "/var/lib/mod_tile", "/var/run/renderd"])
    run_sudo_command(["chown", "-R", "www-data:www-data", "/var/lib/mod_tile", "/var/run/renderd"])

    # Reload systemd, enable and start service
    systemd_reload()
    run_sudo_command(["systemctl", "enable", "renderd"])
    run_sudo_command(["systemctl", "start", "renderd"])
    log("Renderd service enabled and started. Status:")
    run_sudo_command(["systemctl", "status", "renderd", "--no-pager", "-l"])


def osm_osrm_server_setup() -> None:
    """Set up OSM data and OSRM."""
    log("Setting up OSM data and OSRM")

    # Create OSM data directory
    run_sudo_command(["mkdir", "-p", "/opt/osm_data"])
    run_sudo_command(["chown", f"{getpass.getuser()}:{getpass.getuser()}", "/opt/osm_data"])

    # Change to OSM data directory
    current_dir = os.getcwd()
    try:
        os.chdir("/opt/osm_data")

        # Download OSM PBF for Australia if not present
        log("Downloading OSM PBF for Australia (if not present)")
        if not os.path.isfile("australia-latest.osm.pbf"):
            run_command([
                "wget", "https://download.geofabrik.de/australia-oceania/australia-latest.osm.pbf",
                "-O", "australia-latest.osm.pbf"
            ])
        else:
            log("australia-latest.osm.pbf already exists.")

        # Check if download was successful
        if not os.path.isfile("australia-latest.osm.pbf"):
            log("ERROR: Failed to download australia-latest.osm.pbf.")
            return

        # Get script directory for sample data
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Extract Tasmania region if sample data exists
        tasmania_json_path = os.path.join(script_dir, "sampledata", "TasmaniaRegionMap.json")
        if os.path.isfile(tasmania_json_path):
            run_sudo_command(["cp", tasmania_json_path, "/opt/osm_data/TasmaniaRegionMap.json"])
            log("Extracting Tasmania from Australian map")
            run_command([
                "osmium", "extract", "--overwrite", "--strategy", "smart",
                "-p", "/opt/osm_data/TasmaniaRegionMap.json",
                "/opt/osm_data/australia-latest.osm.pbf",
                "-o", "/opt/osm_data/TasmaniaRegionMap.osm.pbf"
            ])
        else:
            log(f"Warning: TasmaniaRegionMap.json not found in {script_dir}/sampledata. Skipping Tasmania extract.")

        # Extract Hobart region if sample data exists
        hobart_json_path = os.path.join(script_dir, "sampledata", "HobartRegionMap.json")
        if os.path.isfile(hobart_json_path):
            run_sudo_command(["cp", hobart_json_path, "/opt/osm_data/HobartRegionMap.json"])
            log("Extracting Hobart from Australian map")
            run_command([
                "osmium", "extract", "--overwrite", "--strategy", "smart",
                "-p", "/opt/osm_data/HobartRegionMap.json",
                "/opt/osm_data/australia-latest.osm.pbf",
                "-o", "/opt/osm_data/HobartRegionMap.osm.pbf"
            ])
        else:
            log(f"Warning: HobartRegionMap.json not found in {script_dir}/sampledata. Skipping Hobart extract.")

        # Determine which PBF file to import
        osm_pbf_to_import = "/opt/osm_data/HobartRegionMap.osm.pbf"  # Default to Hobart
        if not os.path.isfile(osm_pbf_to_import) and os.path.isfile("/opt/osm_data/TasmaniaRegionMap.osm.pbf"):
            log("Hobart extract not found, using Tasmania extract for osm2pgsql import.")
            osm_pbf_to_import = "/opt/osm_data/TasmaniaRegionMap.osm.pbf"
        elif not os.path.isfile(osm_pbf_to_import):
            log("ERROR: No suitable PBF file (Hobart or Tasmania extract) found for osm2pgsql import in /opt/osm_data.")
            return

        log(f"Using {osm_pbf_to_import} for osm2pgsql import.")

        # Locate OSM-Carto Lua script
        log("Locating OSM-Carto Flex Lua script...")
        osm_carto_dir = "/opt/openstreetmap-carto"
        osm_carto_lua_found = None

        for lua_candidate in [
            os.path.join(osm_carto_dir, "openstreetmap-carto-flex.lua"),
            os.path.join(osm_carto_dir, "openstreetmap-carto.lua")
        ]:
            if os.path.isfile(lua_candidate):
                osm_carto_lua_found = lua_candidate
                break

        if not osm_carto_lua_found:
            log(f"ERROR: OSM-Carto Lua script not found in {osm_carto_dir}. osm2pgsql import cannot proceed with flex backend.")
            return

        log(f"Found OSM-Carto Lua script for flex backend: {osm_carto_lua_found}")

        # Import OSM data into PostGIS using osm2pgsql
        log("Starting osm2pgsql import into PostGIS using Flex backend...")

        # Set cache size and flat nodes path
        osm2pgsql_cache_size = os.environ.get("OSM2PGSQL_CACHE_DEFAULT", "24000")
        flat_nodes_dir = "/opt/osm_data"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d")

        # Create flat nodes directory
        os.makedirs(flat_nodes_dir, exist_ok=True)

        # Run osm2pgsql
        run_command([
            "osm2pgsql",
            "--verbose",
            "--create",
            "--database", PGDATABASE,
            "--username", PGUSER,
            "--host", PGHOST,
            "--port", PGPORT,
            "--slim",
            "--hstore",
            "--multi-geometry",
            "--tag-transform-script", osm_carto_lua_found,
            "--style", osm_carto_lua_found,
            "--output=flex",
            "-C", osm2pgsql_cache_size,
            "--number-processes", str(os.cpu_count() or 1),
            "--flat-nodes", f"{flat_nodes_dir}/flat-nodes-{timestamp}.bin",
            osm_pbf_to_import
        ])

        log("osm2pgsql import with Flex backend completed successfully.")

        # OSRM setup
        log("Setting up OSRM...")

        # Set OSRM variables
        osm_pbf_for_osrm = osm_pbf_to_import
        osrm_data_on_host = "/opt/osrm_data"
        osrm_docker_image_processing = "osrm/osrm-backend:latest"
        data_label_processing = "map"
        osrm_profile_in_container = "/opt/car.lua"

        # Create OSRM data directory
        run_sudo_command(["mkdir", "-p", osrm_data_on_host])
        run_sudo_command(["chown", f"{os.getuid()}:{os.getgid()}", osrm_data_on_host])
        run_sudo_command(["chmod", "u+rwx", osrm_data_on_host])

        # Run osrm-extract via Docker
        log("Running osrm-extract via Docker...")
        pbf_filename_only = os.path.basename(osm_pbf_for_osrm)

        # Docker command to run osrm-extract
        run_sudo_command([
            "docker", "run", "--rm",
            "-u", f"{os.getuid()}:{os.getgid()}",
            "-v", f"{osm_pbf_for_osrm}:/mnt_readonly_pbf/{pbf_filename_only}:ro",
            "-v", f"{osrm_data_on_host}:/data_output",
            "-w", "/data_output",
            osrm_docker_image_processing,
            "sh", "-c",
            f"cp \"/mnt_readonly_pbf/{pbf_filename_only}\" \"./{pbf_filename_only}\" && "
            f"osrm-extract -p \"{osrm_profile_in_container}\" \"./{pbf_filename_only}\" && "
            f"rm \"./{pbf_filename_only}\""
        ])

        # Rename output files to use the specified label
        log(f"osrm-extract completed. Renaming output files to use label '{data_label_processing}'...")
        pbf_basename_no_ext = os.path.splitext(os.path.splitext(pbf_filename_only)[0])[0]  # Remove both .osm and .pbf

        if os.path.isfile(f"{osrm_data_on_host}/{pbf_basename_no_ext}.osrm"):
            for file_to_rename in os.listdir(osrm_data_on_host):
                if file_to_rename.startswith(pbf_basename_no_ext):
                    extension_part = file_to_rename[len(pbf_basename_no_ext):]
                    new_full_path = f"{osrm_data_on_host}/{data_label_processing}{extension_part}"

                    if pbf_basename_no_ext != data_label_processing:
                        run_sudo_command(["mv", f"{osrm_data_on_host}/{file_to_rename}", new_full_path])
                        log(f"Renamed {file_to_rename} to {os.path.basename(new_full_path)}")
                    else:
                        log(f"Filename {file_to_rename} already matches. No rename needed.")
        else:
            log(f"Warning: Expected output {osrm_data_on_host}/{pbf_basename_no_ext}.osrm not found. Renaming might be incomplete.")

        # Run osrm-partition via Docker
        log("Running osrm-partition via Docker...")
        run_sudo_command([
            "docker", "run", "--rm",
            "-u", f"{os.getuid()}:{os.getgid()}",
            "-v", f"{osrm_data_on_host}:/data_osrm",
            "-w", "/data_osrm",
            osrm_docker_image_processing,
            "osrm-partition", f"/data_osrm/{data_label_processing}.osrm"
        ])

        # Run osrm-customize via Docker
        log("Running osrm-customize via Docker...")
        run_sudo_command([
            "docker", "run", "--rm",
            "-u", f"{os.getuid()}:{os.getgid()}",
            "-v", f"{osrm_data_on_host}:/data_osrm",
            "-w", "/data_osrm",
            osrm_docker_image_processing,
            "osrm-customize", f"/data_osrm/{data_label_processing}.osrm"
        ])

        # Create systemd service file for OSRM
        osrm_routed_service = f"""[Unit]
Description=OSRM Routing Engine Docker Container
Requires=docker.service
After=docker.service network-online.target

[Service]
Restart=always
RestartSec=10s
ExecStart=/usr/bin/docker run --rm --name osrm_routed_container \\
          -p 127.0.0.1:5000:5000 \\
          -v {osrm_data_on_host}:/data:ro \\
          {osrm_docker_image_processing} \\
          osrm-routed --algorithm MLD /data/{data_label_processing}.osrm --max-table-size 8000
ExecStop=/usr/bin/docker stop osrm_routed_container

[Install]
WantedBy=multi-user.target
"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write(osrm_routed_service)
            temp_file_path = temp_file.name

        run_sudo_command(["tee", "/etc/systemd/system/osrm-routed-docker.service"],
                         input=open(temp_file_path, 'r').read())
        os.unlink(temp_file_path)
        log("Created /etc/systemd/system/osrm-routed-docker.service")

        # Reload systemd, enable and start OSRM service
        systemd_reload()
        run_sudo_command(["systemctl", "enable", "osrm-routed-docker.service"])
        run_sudo_command(["systemctl", "start", "osrm-routed-docker.service"])
        log("OSRM Docker service enabled and started. Status:")
        run_sudo_command(["systemctl", "status", "osrm-routed-docker.service", "--no-pager", "-l"])

    finally:
        os.chdir(current_dir)


def apache_modtile_setup() -> None:
    """Set up Apache with mod_tile."""
    log("Setting up Apache with mod_tile")

    # Check if Apache is installed
    result = run_command(["command", "-v", "apache2"], check=False, capture_output=True, shell=True)
    if result.returncode != 0:
        log("Apache2 not found. Skipping Apache/mod_tile setup.")
        return

    # Configure Apache to listen on port 8080 instead of 80
    if backup_file("/etc/apache2/ports.conf"):
        run_sudo_command([
            "sed", "-i.bak_ports_conf", "s/Listen 80/Listen 8080/", "/etc/apache2/ports.conf"
        ])
        log("Apache configured to listen on port 8080.")

    # Create mod_tile configuration file
    apache_modtile_conf = """ModTileRenderdSocketName /var/run/renderd/renderd.sock
ModTileEnableStats On
ModTileStatsFile /var/log/apache2/mod_tile_stats.txt
ModTileBulkMode Off
ModTileRequestTimeout 5
ModTileMissingRequestTimeout 30

<IfModule mod_expires.c>
    ExpiresActive On
    ExpiresByType image/png "access plus 1 month"
</IfModule>
<IfModule mod_headers.c>
    Header set Cache-Control "max-age=2592000, public"
</IfModule>
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write(apache_modtile_conf)
        temp_file_path = temp_file.name

    run_sudo_command(["tee", "/etc/apache2/conf-available/mod_tile.conf"], input=open(temp_file_path, 'r').read())
    os.unlink(temp_file_path)
    log("Created /etc/apache2/conf-available/mod_tile.conf")

    # Create Apache site configuration file for tiles
    apache_tiles_site_conf = """<VirtualHost *:8080>
    ServerAdmin webmaster@localhost
    # DocumentRoot /var/www/html (not strictly needed for mod_tile if only serving tiles)
    LoadModule tile_module /usr/lib/apache2/modules/mod_tile.so # Ensure this path is correct
    AddTileConfig /hot/ tile.openstreetmap.org # Example, adjust to your renderd URI
    ErrorLog ${APACHE_LOG_DIR}/tiles_error.log
    CustomLog ${APACHE_LOG_DIR}/tiles_access.log combined
</VirtualHost>
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write(apache_tiles_site_conf)
        temp_file_path = temp_file.name

    run_sudo_command(["tee", "/etc/apache2/sites-available/001-tiles.conf"], input=open(temp_file_path, 'r').read())
    os.unlink(temp_file_path)
    log("Created /etc/apache2/sites-available/001-tiles.conf")

    # Enable Apache modules and site
    run_sudo_command(["a2enmod", "tile"])
    run_sudo_command(["a2enmod", "expires"])
    run_sudo_command(["a2enmod", "headers"])
    run_sudo_command(["a2ensite", "001-tiles.conf"])

    # Disable default site if it exists
    result = run_command(["test", "-L", "/etc/apache2/sites-enabled/000-default.conf"], check=False)
    if result.returncode == 0:
        run_sudo_command(["a2dissite", "000-default.conf"])
        log("Disabled default Apache site.")

    # Reload systemd, enable and restart Apache
    systemd_reload()
    run_sudo_command(["systemctl", "enable", "apache2"])
    run_sudo_command(["systemctl", "restart", "apache2"])
    log("Apache service enabled and restarted. Status:")
    run_sudo_command(["systemctl", "status", "apache2", "--no-pager", "-l"])


def nginx_setup() -> None:
    """Set up Nginx as a reverse proxy."""
    log("Setting up Nginx as a reverse proxy")

    # Check if Nginx is installed
    result = run_command(["command", "-v", "nginx"], check=False, capture_output=True, shell=True)
    if result.returncode != 0:
        log("Nginx not found. Skipping Nginx setup.")
        return

    # Create test page directory and simple index.html
    run_sudo_command(["mkdir", "-p", "/var/www/html/map_test_page"])

    # Simple initial index.html
    simple_index_html = """<!DOCTYPE html><html><head><title>Nginx Test</title></head><body><h1>Nginx is Active!</h1><p>Further map content will be here.</p></body></html>
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write(simple_index_html)
        temp_file_path = temp_file.name

    run_sudo_command(["tee", "/var/www/html/map_test_page/index.html"], input=open(temp_file_path, 'r').read())
    os.unlink(temp_file_path)

    # Set permissions
    run_sudo_command(["chown", "-R", "www-data:www-data", "/var/www/html/map_test_page"])
    run_sudo_command(["chmod", "-R", "755", "/var/www/html/map_test_page"])

    # Create Nginx configuration
    nginx_transit_proxy_conf = f"""# Define proxy cache paths in /etc/nginx/nginx.conf http block if using cache
# Example:
# proxy_cache_path /var/cache/nginx/vector_cache levels=1:2 keys_zone=VECTOR_CACHE:10m max_size=1g inactive=60m use_temp_path=off;
# proxy_cache_path /var/cache/nginx/raster_cache levels=1:2 keys_zone=RASTER_CACHE:100m max_size=10g inactive=24h use_temp_path=off;
# sudo mkdir -p /var/cache/nginx && sudo chown www-data:www-data /var/cache/nginx

server {{
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name {VM_IP_OR_DOMAIN} _; # Use configured VM_IP_OR_DOMAIN or wildcard

    # Access and error logs
    access_log /var/log/nginx/transit_proxy.access.log;
    error_log /var/log/nginx/transit_proxy.error.log;

    # Vector Tiles from pg_tileserv (listening on localhost:7800)
    location /vector/ {{
        proxy_pass http://localhost:7800/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # proxy_cache VECTOR_CACHE; # Uncomment to enable caching
        # proxy_cache_valid 200 302 1h;
        # proxy_cache_valid 404 1m;
    }}

    # Raster Tiles from Apache/mod_tile (listening on localhost:8080)
    location /raster/hot/ {{ # Match renderd style URI
        proxy_pass http://localhost:8080/hot/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # proxy_cache RASTER_CACHE; # Uncomment to enable caching
        # proxy_cache_valid 200 302 24h;
        # proxy_cache_use_stale error timeout invalid_header http_500 http_502 http_503 http_504;
    }}

    # OSRM Routing Engine (listening on localhost:5000)
    location /route/v1/ {{
        proxy_pass http://localhost:5000/route/v1/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}

    # Static test page / main site
    location / {{
        root /var/www/html/map_test_page;
        index index.html index.htm;
        try_files $uri $uri/ /index.html;
    }}
}}
"""
    # Replace $ with $$ in the Nginx config to avoid string interpolation issues
    nginx_transit_proxy_conf = nginx_transit_proxy_conf.replace("$host", "$$host")
    nginx_transit_proxy_conf = nginx_transit_proxy_conf.replace("$remote_addr", "$$remote_addr")
    nginx_transit_proxy_conf = nginx_transit_proxy_conf.replace("$proxy_add_x_forwarded_for",
                                                                "$$proxy_add_x_forwarded_for")
    nginx_transit_proxy_conf = nginx_transit_proxy_conf.replace("$scheme", "$$scheme")
    nginx_transit_proxy_conf = nginx_transit_proxy_conf.replace("$uri", "$$uri")

    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write(nginx_transit_proxy_conf)
        temp_file_path = temp_file.name

    run_sudo_command(["tee", "/etc/nginx/sites-available/transit_proxy"], input=open(temp_file_path, 'r').read())
    os.unlink(temp_file_path)
    log("Created Nginx site configuration /etc/nginx/sites-available/transit_proxy")

    # Create symlink if target exists
    if os.path.isfile("/etc/nginx/sites-available/transit_proxy"):
        run_sudo_command(
            ["ln", "-sf", "/etc/nginx/sites-available/transit_proxy", "/etc/nginx/sites-enabled/transit_proxy"])
        log("Enabled Nginx site transit_proxy.")
    else:
        log("ERROR: /etc/nginx/sites-available/transit_proxy not found. Cannot enable site.")
        return

    # Disable default site if it exists
    if os.path.islink("/etc/nginx/sites-enabled/default"):
        run_sudo_command(["rm", "/etc/nginx/sites-enabled/default"])
        log("Disabled default Nginx site.")

    # Test Nginx configuration
    log("Testing Nginx configuration...")
    result = run_sudo_command(["nginx", "-t"], check=False)
    if result.returncode == 0:
        log("Nginx configuration test successful.")
        systemd_reload()
        run_sudo_command(["systemctl", "enable", "nginx"])
        run_sudo_command(["systemctl", "restart", "nginx"])
        log("Nginx service enabled and restarted. Status:")
        run_sudo_command(["systemctl", "status", "nginx", "--no-pager", "-l"])
    else:
        log("ERROR: Nginx configuration test failed. Please check logs.")
        return


def certbot_setup() -> None:
    """Set up SSL certificates using Certbot."""
    log("Certbot (SSL certificate) setup")

    # Skip if VM_IP_OR_DOMAIN is default or an IP address
    if VM_IP_OR_DOMAIN == VM_IP_OR_DOMAIN_DEFAULT or re.match(r'^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$',
                                                              VM_IP_OR_DOMAIN):
        log(f"Skipping Certbot setup: VM_IP_OR_DOMAIN is default ('{VM_IP_OR_DOMAIN_DEFAULT}') or an IP address. Certbot requires a public FQDN.")
        return

    # Install Certbot and Nginx plugin
    run_sudo_command(["apt", "update"])
    run_sudo_command(["apt", "install", "-y", "certbot", "python3-certbot-nginx"])

    # Run Certbot for the domain
    log(f"Running Certbot for {VM_IP_OR_DOMAIN}...")
    result = run_sudo_command([
        "certbot", "--nginx",
        "-d", VM_IP_OR_DOMAIN,
        "--non-interactive",
        "--agree-tos",
        "--email", f"admin@{VM_IP_OR_DOMAIN}",
        "--redirect"
    ], check=False)

    if result.returncode == 0:
        log(f"Certbot setup for {VM_IP_OR_DOMAIN} completed. HTTPS should be configured.")
        log("Certbot timer for renewal should be active. Check with: sudo systemctl list-timers")
    else:
        log("ERROR: Certbot setup failed. Check Certbot logs in /var/log/letsencrypt/.")


def gtfs_data_prep() -> None:
    """Prepare GTFS data using the gtfs_processor module."""
    log("Preparing GTFS data using gtfs_processor module")

    # Create log file
    run_sudo_command(["touch", "/var/log/gtfs_processor_app.log"])
    run_sudo_command(["chown", "nobody:nogroup", "/var/log/gtfs_processor_app.log"])

    # Set environment variables for gtfs_processor
    os.environ["GTFS_FEED_URL"] = GTFS_FEED_URL
    os.environ["PG_OSM_PASSWORD"] = PGPASSWORD
    os.environ["PG_OSM_USER"] = PGUSER
    os.environ["PG_OSM_HOST"] = PGHOST
    os.environ["PG_OSM_PORT"] = PGPORT
    os.environ["PG_OSM_DATABASE"] = PGDATABASE

    # Import gtfs_processor modules
    try:
        from gtfs_processor import main_pipeline, utils

        # Setup logging
        utils.setup_logging(
            log_level=logging.INFO,
            log_file="/var/log/gtfs_processor_app.log",
            log_to_console=True
        )

        # Run the GTFS ETL pipeline
        log(f"Running GTFS ETL pipeline with URL: {GTFS_FEED_URL}")
        success = main_pipeline.run_full_gtfs_etl_pipeline()

        if success:
            log("GTFS ETL pipeline completed successfully")
            log("Verifying data import (counts from tables):")
            run_sudo_command(["sudo", "-u", PGUSER, "psql", "-h", PGHOST, "-p", PGPORT, "-d", PGDATABASE, "-c",
                              "SELECT COUNT(*) FROM gtfs_stops;"])
            run_sudo_command(["sudo", "-u", PGUSER, "psql", "-h", PGHOST, "-p", PGPORT, "-d", PGDATABASE, "-c",
                              "SELECT COUNT(*) FROM gtfs_routes;"])
        else:
            log("ERROR: GTFS ETL pipeline failed")
            return
    except ImportError as e:
        log(f"ERROR: Failed to import gtfs_processor modules: {e}")
        log("Make sure the gtfs_processor package is installed and PYTHONPATH is set correctly")
        return
    except Exception as e:
        log(f"ERROR: An error occurred during GTFS processing: {e}")
        return

    # Set up cron job for daily GTFS updates
    log("Setting up cron job for daily GTFS updates")

    # Find Python executable
    python_executable = shutil.which("python3") or shutil.which("python")
    if not python_executable:
        log("ERROR: Python executable not found. Cannot set up cron job for GTFS update.")
        return

    # Create cron job using update_gtfs module from gtfs_processor
    cron_user = PGUSER
    cron_job = f"0 3 * * * GTFS_FEED_URL='{GTFS_FEED_URL}' PG_OSM_PASSWORD='{PGPASSWORD}' PG_OSM_USER='{PGUSER}' PG_OSM_HOST='{PGHOST}' PG_OSM_PORT='{PGPORT}' PG_OSM_DATABASE='{PGDATABASE}' {python_executable} -m gtfs_processor.update_gtfs >> /var/log/gtfs_processor_app.log 2>&1\n"

    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        # Get existing crontab
        result = run_sudo_command(["crontab", "-u", cron_user, "-l"], check=False, capture_output=True)
        if result.returncode == 0:
            # Filter out any existing gtfs_processor entries
            existing_crontab = result.stdout
            filtered_crontab = "\n".join([line for line in existing_crontab.splitlines()
                                          if "gtfs_processor" not in line and "update_gtfs.py" not in line])
            temp_file.write(filtered_crontab)
            if not filtered_crontab.endswith("\n"):
                temp_file.write("\n")

        # Add new cron job
        temp_file.write(cron_job)
        temp_file_path = temp_file.name

    # Install new crontab
    run_sudo_command(["crontab", "-u", cron_user, temp_file_path])
    os.unlink(temp_file_path)
    log(f"Cron job for GTFS update configured for user {cron_user}.")


def raster_tile_prep() -> None:
    """Pre-render raster tiles."""
    log("Raster tile pre-rendering (optional)")

    # Check if renderd is active
    result = run_command(["systemctl", "is-active", "--quiet", "renderd"], check=False)
    if result.returncode != 0:
        log("Renderd is not active. Attempting to start...")
        run_sudo_command(["systemctl", "start", "renderd"])
        time.sleep(2)  # Give it a moment to start

        # Check again
        result = run_command(["systemctl", "is-active", "--quiet", "renderd"], check=False)
        if result.returncode != 0:
            log("ERROR: Renderd could not be started. Skipping tile pre-rendering.")
            return

    # Check if render_list is available
    if not shutil.which("render_list"):
        log("render_list command not found (part of mapnik-utils or similar). Skipping tile pre-rendering.")
        return

    # Run render_list
    log("Starting raster tile pre-rendering (zoom 0-12)...")
    run_sudo_command(["render_list", "--all", "--min-zoom=0", "--max-zoom=12", f"--num-threads={os.cpu_count() or 1}"])
    log("Raster tile pre-rendering task submitted. Monitor renderd logs and CPU usage.")


def website_prep() -> None:
    """Prepare test website."""
    log("Preparing test website (index.html)")

    # Create directory
    run_sudo_command(["mkdir", "-p", "/var/www/html/map_test_page"])

    # Create index.html
    index_html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Transit System Map Test</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
          integrity="sha256-p4NxAoJBhดูรายละเอียดཔിൻവലിക്കാവുന്നതാണ്sha512-puBpdR0798OZvTTbP4A8bRjEnFRP বঙ্গেরFulde."
          crossorigin=""/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
            integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
    <link href='https://unpkg.com/maplibre-gl@4.1.0/dist/maplibre-gl.css' rel='stylesheet'/>
    <script src='https://unpkg.com/maplibre-gl@4.1.0/dist/maplibre-gl.js'></script>
    <style>
        body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; }}
        #map-raster, #map-vector {{ height: 400px; border: 1px solid #ccc; margin-bottom: 20px;}}
        .map-container {{ position: relative; width: 95%; margin: 10px auto; }}
        .info {{ padding: 15px; background: #f4f4f4; border-bottom: 1px solid #ddd; margin-bottom: 20px; text-align: center;}}
        h3 {{text-align: center; margin-top: 20px;}}
    </style>
</head>
<body>

<div class="info">
    <h2>Map Test Page</h2>
    <p>Testing Raster Tiles (Leaflet) and Vector Tiles (MapLibre GL JS with basic styling).</p>
    <p>Your VM IP/Domain: <strong>{VM_IP_OR_DOMAIN}</strong></p>
    <p>Access this page at: http://{VM_IP_OR_DOMAIN}/</p>
</div>

<h3>Raster Tiles (Leaflet - OSM Base)</h3>
<div id="map-raster" class="map-container"></div>

<h3>Vector Tiles (MapLibre GL JS - GTFS Stops & Shapes if available)</h3>
<div id="map-vector" class="map-container"></div>

<script>
    var hobartCoords = [-42.8826, 147.3257]; // Lat, Lng for Leaflet
    var hobartCoordsMapLibre = [147.3257, -42.8826]; // Lng, Lat for MapLibre

    // --- Raster Map (Leaflet) ---
    var rasterMap = L.map('map-raster').setView(hobartCoords, 13);
    L.tileLayer('http://{VM_IP_OR_DOMAIN}/raster/hot/{{z}}/{{x}}/{{y}}.png', {{
        maxZoom: 19,
        attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, Tiles by Local Server'
    }}).addTo(rasterMap);
    L.marker(hobartCoords).addTo(rasterMap).bindPopup('Hobart (Raster OSM Tiles)');

    // --- Vector Map (MapLibre GL JS) ---
    try {{
        var vectorMap = new maplibregl.Map({{
            container: 'map-vector',
            style: {{
                'version': 8,
                'sources': {{
                    'pgtileserv_stops': {{
                        'type': 'vector',
                        'tiles': ['http://{VM_IP_OR_DOMAIN}/vector/public.gtfs_stops/{{z}}/{{x}}/{{y}}.pbf'],
                        'maxzoom': 16
                    }},
                    'pgtileserv_shapes': {{ // Assuming a layer 'public.gtfs_shapes_lines' exists
                        'type': 'vector',
                        'tiles': ['http://{VM_IP_OR_DOMAIN}/vector/public.gtfs_shapes_lines/{{z}}/{{x}}/{{y}}.pbf'],
                        'maxzoom': 16
                    }}
                }},
                'layers': [
                    {{ // Background layer
                        'id': 'background',
                        'type': 'background',
                        'paint': {{ 'background-color': '#f0f0f0' }}
                    }},
                    {{ // GTFS Shapes (lines)
                        'id': 'gtfs-shapes-lines',
                        'type': 'line',
                        'source': 'pgtileserv_shapes',
                        'source-layer': 'public.gtfs_shapes_lines', // Ensure this is the correct layer name in your PBF
                        'layout': {{ 'line-join': 'round', 'line-cap': 'round' }},
                        'paint': {{ 'line-color': '#3887be', 'line-width': 2 }}
                    }},
                    {{ // GTFS Stops (circles)
                        'id': 'gtfs-stops-circles',
                        'type': 'circle',
                        'source': 'pgtileserv_stops',
                        'source-layer': 'public.gtfs_stops', // Ensure this is the correct layer name in your PBF
                        'paint': {{
                            'circle-radius': 5,
                            'circle-color': '#e60000',
                            'circle-stroke-width': 1,
                            'circle-stroke-color': '#ffffff'
                        }}
                    }}
                ]
            }},
            center: hobartCoordsMapLibre,
            zoom: 12
        }});
        vectorMap.addControl(new maplibregl.NavigationControl());

        // Optional: Add a marker for context if stops aren't loading
        new maplibregl.Marker().setLngLat(hobartCoordsMapLibre).setPopup(new maplibregl.Popup().setText('Hobart (Vector Map View)')).addTo(vectorMap);

    }} catch (e) {{
        console.error("Error initializing MapLibre GL map:", e);
        document.getElementById('map-vector').innerHTML = "<p style='color:red; text-align:center;'>Error initializing MapLibre GL map. Check browser console (F12) for details. Ensure pg_tileserv is running and serving vector tiles.</p>";
    }}
</script>
</body>
</html>
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
        temp_file.write(index_html_content)
        temp_file_path = temp_file.name

    run_sudo_command(["tee", "/var/www/html/map_test_page/index.html"], input=open(temp_file_path, 'r').read())
    os.unlink(temp_file_path)

    # Set permissions
    run_sudo_command(["chown", "-R", "www-data:www-data", "/var/www/html/map_test_page"])
    run_sudo_command(["chmod", "-R", "755", "/var/www/html/map_test_page"])

    log(f"Updated /var/www/html/map_test_page/index.html with test map page.")
    log(f"You should be able to access the test page at http://{VM_IP_OR_DOMAIN}/")


# Define step execution function
def execute_step(step_tag: str, step_description: str, step_function: Callable) -> bool:
    """Execute a single step with state tracking."""
    run_this_step = True

    if is_step_completed(step_tag):
        log(f"Step '{step_description}' ({step_tag}) is already marked as completed.")
        user_input = input("Do you want to re-run it anyway? (y/N): ").strip().lower()
        if user_input != 'y':
            log(f"Skipping already completed step: {step_tag} - {step_description}")
            run_this_step = False

    if run_this_step:
        log(f"--- Executing step: {step_description} ({step_tag}) ---")
        try:
            step_function()
            mark_step_completed(step_tag)
            log(f"--- Successfully completed step: {step_description} ({step_tag}) ---")
            return True
        except Exception as e:
            log(f"ERROR: Step failed: {step_description} ({step_tag})")
            log(f"Error details: {str(e)}")
            return False

    return True  # Step was skipped, not a failure


# Define grouped actions
def core_conflict_removal_group() -> bool:
    return execute_step("CORE_CONFLICTS", "Remove Core Conflicts (e.g. system node)", core_conflict_removal)


def prereqs_install_group() -> bool:
    log("--- Starting Prerequisites Installation Group ---")
    success = True
    success = success and execute_step("BOOT_VERBOSITY", "Improve Boot Verbosity & Core Utils", boot_verbosity)
    success = success and execute_step("CORE_INSTALL", "Install Core Packages (Python, PG, GIS, Fonts)",
                                       core_install)
    success = success and execute_step("DOCKER_INSTALL", "Install Docker Engine", docker_install)
    success = success and execute_step("NODEJS_INSTALL", "Install Node.js (LTS from NodeSource)",
                                       node_js_lts_install)
    log("--- Prerequisites Installation Group Finished ---")
    return success


def services_setup_group() -> bool:
    log("--- Starting Services Setup Group ---")
    success = True
    success = success and execute_step("UFW_SETUP", "Setup UFW Firewall", ufw_setup)
    success = success and execute_step("POSTGRES_SETUP", "Setup PostgreSQL Database & User", postgres_setup)
    success = success and execute_step("PGTILESERV_SETUP", "Setup pg_tileserv", pg_tileserv_setup)
    success = success and execute_step("CARTO_SETUP", "Setup CartoCSS Compiler & OSM Style", carto_setup)
    success = success and execute_step("RENDERD_SETUP", "Setup Renderd for Raster Tiles", renderd_setup)
    success = success and execute_step("OSM_SERVER_SETUP", "Setup OSM Data (osm2pgsql, OSRM)", osm_osrm_server_setup)
    success = success and execute_step("APACHE_SETUP", "Setup Apache for mod_tile", apache_modtile_setup)
    success = success and execute_step("NGINX_SETUP", "Setup Nginx Reverse Proxy", nginx_setup)
    success = success and execute_step("CERTBOT_SETUP", "Setup Certbot for SSL (optional)", certbot_setup)
    log("--- Services Setup Group Finished ---")
    return success


def data_prep_group() -> bool:
    log("--- Starting Data Preparation Group ---")
    success = True
    success = success and execute_step("GTFS_PREP", "Prepare GTFS Data (Download & Import)", gtfs_data_prep)
    success = success and execute_step("RASTER_PREP", "Pre-render Raster Tiles (Optional & Long Task!)",
                                       raster_tile_prep)
    success = success and execute_step("WEBSITE_PREP", "Prepare Test Website (index.html)", website_prep)
    log("--- Data Preparation Group Finished ---")
    return success


def systemd_reload_group() -> bool:
    return execute_step("SYSTEMD_RELOAD", "Reload Systemd Daemon", systemd_reload)


# --- Main Function ---
def main() -> None:
    """
    Main entry point for the script.

    Parses command-line arguments, sets up logging, and runs the installation process.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Server setup and configuration script for development environments",
        epilog="For more information, see the README.md file."
    )
    parser.add_argument("-a", dest="admin_group_ip", default=ADMIN_GROUP_IP_DEFAULT,
                        help=f"Admin group IP range (CIDR format). Default: {ADMIN_GROUP_IP_DEFAULT}")
    parser.add_argument("-f", dest="gtfs_feed_url", default=GTFS_FEED_URL_DEFAULT,
                        help=f"GTFS feed URL. Default: {GTFS_FEED_URL_DEFAULT}")
    parser.add_argument("-v", dest="vm_ip_or_domain", default=VM_IP_OR_DOMAIN_DEFAULT,
                        help=f"VM IP or Domain Name for web server. Default: {VM_IP_OR_DOMAIN_DEFAULT}")
    parser.add_argument("-b", dest="pg_tileserv_binary_location", default=PG_TILESERV_BINARY_LOCATION_DEFAULT,
                        help=f"pg_tileserv binary download URL. Default: {PG_TILESERV_BINARY_LOCATION_DEFAULT}")
    parser.add_argument("-l", dest="log_prefix", default=LOG_PREFIX_DEFAULT,
                        help=f"Log message prefix. Default: {LOG_PREFIX_DEFAULT}")
    parser.add_argument("-H", dest="pghost", default=PGHOST_DEFAULT,
                        help=f"PostgreSQL host. Default: {PGHOST_DEFAULT}")
    parser.add_argument("-P", dest="pgport", default=PGPORT_DEFAULT,
                        help=f"PostgreSQL port. Default: {PGPORT_DEFAULT}")
    parser.add_argument("-D", dest="pgdatabase", default=PGDATABASE_DEFAULT,
                        help=f"PostgreSQL database name. Default: {PGDATABASE_DEFAULT}")
    parser.add_argument("-U", dest="pguser", default=PGUSER_DEFAULT,
                        help=f"PostgreSQL username. Default: {PGUSER_DEFAULT}")
    parser.add_argument("-W", dest="pgpassword", default=PGPASSWORD_DEFAULT,
                        help=f"PostgreSQL password. Default: {PGPASSWORD_DEFAULT}")
    parser.add_argument("--full", action="store_true", help="Run full installation process")
    parser.add_argument("--prereqs", action="store_true", help="Install prerequisites only")
    parser.add_argument("--services", action="store_true", help="Setup services only")
    parser.add_argument("--data", action="store_true", help="Prepare data only")
    parser.add_argument("--view-config", action="store_true", help="View current configuration")
    parser.add_argument("--view-state", action="store_true", help="View completed steps")
    parser.add_argument("--clear-state", action="store_true", help="Clear progress state")

    args = parser.parse_args()

    # Set global variables from command-line arguments
    global ADMIN_GROUP_IP, GTFS_FEED_URL, VM_IP_OR_DOMAIN, PG_TILESERV_BINARY_LOCATION, LOG_PREFIX
    global PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD

    ADMIN_GROUP_IP = args.admin_group_ip
    GTFS_FEED_URL = args.gtfs_feed_url
    VM_IP_OR_DOMAIN = args.vm_ip_or_domain
    PG_TILESERV_BINARY_LOCATION = args.pg_tileserv_binary_location
    LOG_PREFIX = args.log_prefix
    PGHOST = args.pghost
    PGPORT = args.pgport
    PGDATABASE = args.pgdatabase
    PGUSER = args.pguser
    PGPASSWORD = args.pgpassword

    # Set up logging
    setup_logging()

    # Initialize state system
    initialize_state_system()

    # Setup .pgpass file
    setup_pgpass()

    # Process command-line arguments for specific actions
    if args.view_config:
        view_configuration()
        return

    if args.view_state:
        completed_steps = view_completed_steps()
        if completed_steps:
            log("Completed steps:")
            for step in completed_steps:
                log(f"  - {step}")
        else:
            log("No steps have been marked as completed yet.")
        return

    if args.clear_state:
        clear_state_file()
        return

    # Process command-line arguments for specific installation groups
    if args.full:
        log("====== Starting Full Installation Process ======")
        success = True
        success = success and core_conflict_removal_group()
        success = success and prereqs_install_group()
        success = success and services_setup_group()
        success = success and systemd_reload_group()
        success = success and data_prep_group()

        if success:
            log("====== Full Installation Process Completed Successfully ======")
        else:
            log("====== Full Installation Process Completed with Errors ======")
        return

    if args.prereqs:
        log("====== Starting Prerequisites Installation Only ======")
        success = prereqs_install_group()
        if success:
            log("====== Prerequisites Installation Finished Successfully ======")
        else:
            log("====== Prerequisites Installation Finished with Errors ======")
        return

    if args.services:
        log("====== Starting Services Setup Only ======")
        success = services_setup_group()
        if success:
            log("====== Services Setup Finished Successfully ======")
        else:
            log("====== Services Setup Finished with Errors ======")
        return

    if args.data:
        log("====== Starting Data Preparation Only ======")
        success = data_prep_group()
        if success:
            log("====== Data Preparation Finished Successfully ======")
        else:
            log("====== Data Preparation Finished with Errors ======")
        return

    # If no specific action was requested, show menu
    show_menu()


def view_configuration() -> None:
    """Display the current configuration."""
    config_text = "Current global variable configurations:\n\n"
    config_text += f"ADMIN_GROUP_IP:              {ADMIN_GROUP_IP}\n"
    config_text += f"GTFS_FEED_URL:               {GTFS_FEED_URL}\n"
    config_text += f"VM_IP_OR_DOMAIN:             {VM_IP_OR_DOMAIN}\n"
    config_text += f"PG_TILESERV_BINARY_LOCATION: {PG_TILESERV_BINARY_LOCATION}\n"
    config_text += f"LOG_PREFIX:                  {LOG_PREFIX}\n\n"
    config_text += f"PGHOST:                      {PGHOST}\n"
    config_text += f"PGPORT:                      {PGPORT}\n"
    config_text += f"PGDATABASE:                  {PGDATABASE}\n"
    config_text += f"PGUSER:                      {PGUSER}\n"
    config_text += f"PGPASSWORD:                  [REDACTED FOR DISPLAY]\n\n"
    config_text += f"TIMESTAMP (current run):     {datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S')}\n\n"
    config_text += "You can override these using command-line options when starting the script. Use the -h option for details."

    print("\n" + config_text + "\n")


def show_menu() -> None:
    """Display the main menu and handle user input."""
    while True:
        print("\n" + "=" * 80)
        print(f"Server Setup Configuration Script (v{SCRIPT_VERSION})")
        print("=" * 80)
        print("Choose an action:")
        print("1. Full Installation (All Steps)")
        print("2. Install Prerequisites Only")
        print("3. Setup Core Services Only")
        print("4. Prepare Data Only (GTFS, Tiles, Website)")
        print("5. Custom Step Selection")
        print("6. View Current Configuration")
        print("7. Manage Setup State (View/Clear Progress)")
        print("8. Systemd Daemon Reload Only")
        print("9. Remove Core Conflicts Only")
        print("10. Exit Script")

        choice = input("\nEnter your choice (1-10): ").strip()

        if choice == "1":
            run_full_installation()
        elif choice == "2":
            run_prereqs_installation()
        elif choice == "3":
            run_services_setup()
        elif choice == "4":
            run_data_preparation()
        elif choice == "5":
            run_custom_selection()
        elif choice == "6":
            view_configuration()
        elif choice == "7":
            manage_state()
        elif choice == "8":
            run_systemd_reload_interactive()
        elif choice == "9":
            run_core_conflict_removal_interactive()
        elif choice == "10":
            confirm = input("Are you sure you want to exit? (y/N): ").strip().lower()
            if confirm == 'y':
                print("Exiting script. Goodbye!")
                break
        else:
            print("Invalid choice. Please enter a number between 1 and 10.")

        # Pause before showing menu again
        input("\nPress Enter to continue...")


def run_full_installation() -> None:
    """Run the full installation process."""
    confirm = input("This will attempt to run ALL setup steps. Completed steps can be skipped or re-run.\n"
                    "This can take a very long time and make significant changes to your system.\n"
                    "Are you sure you want to proceed? (y/N): ").strip().lower()

    if confirm == 'y':
        log("====== Starting Full Installation Process ======")
        success = True
        success = success and core_conflict_removal_group()
        success = success and prereqs_install_group()
        success = success and services_setup_group()
        success = success and systemd_reload_group()
        success = success and data_prep_group()

        if success:
            log("====== Full Installation Process Completed Successfully ======")
        else:
            log("====== Full Installation Process Completed with Errors ======")
    else:
        log("Full installation cancelled by user.")


def run_prereqs_installation() -> None:
    """Run the prerequisites installation process."""
    confirm = input("Install core system packages, Python, PostgreSQL, mapping tools, fonts, Docker, and Node.js?\n"
                    "Completed steps can be skipped or re-run.\n"
                    "Are you sure you want to proceed? (y/N): ").strip().lower()

    if confirm == 'y':
        log("====== Starting Prerequisites Installation Only ======")
        success = prereqs_install_group()
        if success:
            log("====== Prerequisites Installation Finished Successfully ======")
        else:
            log("====== Prerequisites Installation Finished with Errors ======")
    else:
        log("Prerequisites installation cancelled by user.")


def run_services_setup() -> None:
    """Run the services setup process."""
    confirm = input(
        "Setup UFW, PostgreSQL, pg_tileserv, Carto, Renderd, OSM/OSRM, Apache, Nginx, and optionally Certbot?\n"
        "Completed steps can be skipped or re-run.\n"
        "Are you sure you want to proceed? (y/N): ").strip().lower()

    if confirm == 'y':
        log("====== Starting Services Setup Only ======")
        success = services_setup_group()
        if success:
            log("====== Services Setup Finished Successfully ======")
        else:
            log("====== Services Setup Finished with Errors ======")
    else:
        log("Services setup cancelled by user.")


def run_data_preparation() -> None:
    """Run the data preparation process."""
    confirm = input("Prepare GTFS data, optionally pre-render raster tiles, and setup test website?\n"
                    "Completed steps can be skipped or re-run.\n"
                    "Are you sure you want to proceed? (y/N): ").strip().lower()

    if confirm == 'y':
        log("====== Starting Data Preparation Only ======")
        success = data_prep_group()
        if success:
            log("====== Data Preparation Finished Successfully ======")
        else:
            log("====== Data Preparation Finished with Errors ======")
    else:
        log("Data preparation cancelled by user.")


def run_systemd_reload_interactive() -> None:
    """Run systemd reload interactively."""
    log("====== Starting Systemd Daemon Reload ======")
    execute_step("SYSTEMD_RELOAD_INTERACTIVE", "Reload Systemd Daemon (Interactive)", systemd_reload)


def run_core_conflict_removal_interactive() -> None:
    """Run core conflict removal interactively."""
    log("====== Starting Core Conflict Removal ======")
    execute_step("CORE_CONFLICTS_INTERACTIVE", "Remove Core Conflicts (e.g. system node) (Interactive)",
                 core_conflict_removal)


def manage_state() -> None:
    """Manage the state file (view or clear progress)."""
    print("\nState Management:")
    print("1. View Completed Steps")
    print("2. Clear All Progress (Force Re-run All)")
    print("3. Return to Main Menu")

    choice = input("\nEnter your choice (1-3): ").strip()

    if choice == "1":
        completed_steps = view_completed_steps()
        if completed_steps:
            print("\nCompleted Steps:")
            for step in completed_steps:
                print(f"  - {step}")
        else:
            print("\nNo steps have been marked as completed yet.")
    elif choice == "2":
        confirm = input("Are you sure you want to clear ALL recorded progress?\n"
                        "This action cannot be undone. All steps will be treated as new if re-run.\n"
                        "Are you sure? (y/N): ").strip().lower()
        if confirm == 'y':
            clear_state_file()
            print("Progress state file cleared. All steps will need to be re-run.")
        else:
            print("State file not cleared.")
    elif choice == "3":
        return
    else:
        print("Invalid choice.")


def run_custom_selection() -> None:
    """Run custom selection of steps."""
    all_steps = [
        ("CORE_CONFLICTS", "Remove Core Conflicts (e.g. system node)"),
        ("BOOT_VERBOSITY", "Improve Boot Verbosity & Core Utils"),
        ("CORE_INSTALL", "Install Core Packages (Python, PG, GIS, Fonts)"),
        ("DOCKER_INSTALL", "Install Docker Engine"),
        ("NODEJS_INSTALL", "Install Node.js (LTS from NodeSource)"),
        ("UFW_SETUP", "Setup UFW Firewall"),
        ("POSTGRES_SETUP", "Setup PostgreSQL Database & User"),
        ("PGTILESERV_SETUP", "Setup pg_tileserv"),
        ("CARTO_SETUP", "Setup CartoCSS Compiler & OSM Style"),
        ("RENDERD_SETUP", "Setup Renderd for Raster Tiles"),
        ("OSM_SERVER_SETUP", "Setup OSM Data (osm2pgsql, OSRM)"),
        ("APACHE_SETUP", "Setup Apache for mod_tile"),
        ("NGINX_SETUP", "Setup Nginx Reverse Proxy"),
        ("CERTBOT_SETUP", "Setup Certbot for SSL (requires FQDN & Nginx)"),
        ("SYSTEMD_RELOAD", "Reload Systemd Daemon (after service changes)"),
        ("GTFS_PREP", "Prepare GTFS Data (Download & Import)"),
        ("RASTER_PREP", "Pre-render Raster Tiles (Can be very long!)"),
        ("WEBSITE_PREP", "Prepare Test Website (index.html)")
    ]

    print("\nSelect steps to perform (they will be executed in the displayed order):")
    for i, (tag, desc) in enumerate(all_steps, 1):
        status = "[X]" if is_step_completed(tag) else "[ ]"
        print(f"{i}. {status} {desc} ({tag})")

    print("\nEnter the numbers of the steps you want to run, separated by spaces:")
    selection = input().strip()

    try:
        selected_indices = [int(x) - 1 for x in selection.split()]
        selected_steps = [all_steps[i] for i in selected_indices if 0 <= i < len(all_steps)]

        if not selected_steps:
            print("No valid steps selected.")
            return

        print("\nYou selected:")
        for tag, desc in selected_steps:
            print(f"- {desc} ({tag})")

        confirm = input("\nProceed with these steps? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Custom step execution cancelled.")
            return

        log("Executing custom selected steps in predefined system order...")
        overall_success = True

        # Execute steps in the original order, not the selection order
        for tag, desc in all_steps:
            if (tag, desc) in selected_steps:
                # Map tag to function
                function_map = {
                    # "CORE_CONFLICTS": core_conflict_removal,
                    "BOOT_VERBOSITY": boot_verbosity,
                    "CORE_INSTALL": core_install,
                    "DOCKER_INSTALL": docker_install,
                    # "NODEJS_INSTALL": node_js_lts_install,
                    "UFW_SETUP": ufw_setup,
                    "POSTGRES_SETUP": postgres_setup,
                    "PGTILESERV_SETUP": pg_tileserv_setup,
                    "CARTO_SETUP": carto_setup,
                    "RENDERD_SETUP": renderd_setup,
                    "OSM_SERVER_SETUP": osm_osrm_server_setup,
                    "APACHE_SETUP": apache_modtile_setup,
                    "NGINX_SETUP": nginx_setup,
                    "CERTBOT_SETUP": certbot_setup,
                    "SYSTEMD_RELOAD": systemd_reload,
                    "GTFS_PREP": gtfs_data_prep,
                    "RASTER_PREP": raster_tile_prep,
                    "WEBSITE_PREP": website_prep
                }

                if tag in function_map:
                    if not execute_step(tag, desc, function_map[tag]):
                        overall_success = False
                        log(f"Execution of '{tag}' failed. Halting custom steps.")
                        break
                else:
                    log(f"Error: Unknown tag '{tag}' in custom selection logic.")
                    overall_success = False
                    break

        if overall_success:
            log("All selected custom steps have been processed.")
        else:
            log("Custom step processing halted due to a failure or user cancellation within a step.")

    except ValueError:
        print("Invalid input. Please enter numbers separated by spaces.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    main()
