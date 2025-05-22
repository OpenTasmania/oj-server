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
Handles sudo execution gracefully for privileged operations.
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
from typing import Callable, List  # For type hinting in execute_step
from typing import Optional  # Added Optional

# Initial logging setup for early messages or import failures
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger_early = logging.getLogger(__name__)

# Ensure the package root is in PYTHONPATH if running script directly for development
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))  # Adjust if your structure is different
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)

# Attempt to import gtfs_processor, but don't fail the whole script yet.
# The actual usage in gtfs_data_prep will handle import errors more specifically.
try:
    from gtfs_processor import utils as gtfs_utils
    from gtfs_processor import main_pipeline as gtfs_main_pipeline
except ImportError as e:
    logger_early.error(
        f"Initial attempt to import gtfs_processor modules failed. This might be resolved later if an environment is set up. Error: {e}")
    gtfs_utils = None  # Define as None to allow script to load
    gtfs_main_pipeline = None

# --- Default Global Variable Values ---
ADMIN_GROUP_IP_DEFAULT = "192.168.128.0/22"
GTFS_FEED_URL_DEFAULT = "https://www.transport.act.gov.au/googletransit/google_transit.zip"
VM_IP_OR_DOMAIN_DEFAULT = "example.com"  # Should be a real domain for Certbot
PG_TILESERV_BINARY_LOCATION_DEFAULT = "https://postgisftw.s3.amazonaws.com/pg_tileserv_latest_linux.zip"
LOG_PREFIX_DEFAULT = "[MAP-SETUP]"
PGHOST_DEFAULT = "localhost"
PGPORT_DEFAULT = "5432"
PGDATABASE_DEFAULT = "gis"
PGUSER_DEFAULT = "osmuser"
PGPASSWORD_DEFAULT = "yourStrongPasswordHere"  # Strongly recommend changing or prompting

# --- State File Configuration ---
STATE_FILE_DIR = "/var/lib/map-server-setup-script"
STATE_FILE = os.path.join(STATE_FILE_DIR, "progress_state.txt")
SCRIPT_VERSION = "1.3"  # Incremented for sudo refactor

# --- Package Lists ---
# These are system packages to be installed by apt.
# Python specific project dependencies should be managed by uv in a venv for gtfs_processor.
PYTHON_SYSTEM_PACKAGES = [  # Renamed to avoid confusion with project venv packages
    "python3", "python3-pip", "python3-venv", "python3-dev", "python3-yaml",
    "python3-pandas", "python3-psycopg2", "python3-psycopg", "python3-pydantic"  # System pydantic
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
CORE_PREREQ_PACKAGES = [
    "git", "unzip", "vim", "build-essential", "software-properties-common",
    "dirmngr", "gnupg", "apt-transport-https", "lsb-release", "ca-certificates",
    "qemu-guest-agent", "ufw", "curl", "wget", "bash", "btop", "screen"
]

# --- Logger Setup ---
logger = logging.getLogger(__name__)  # Main logger for this script

SYMBOLS = {
    "success": "✅", "error": "❌", "warning": "⚠️", "info": "ℹ️", "step": "➡️",
    "gear": "⚙️", "package": "📦", "rocket": "🚀", "sparkles": "✨", "critical": "🔥"
}

# Global variables to be set by argparse
ADMIN_GROUP_IP: str
GTFS_FEED_URL: str
VM_IP_OR_DOMAIN: str
PG_TILESERV_BINARY_LOCATION: str
LOG_PREFIX: str  # For the logger, distinct from the script's default LOG_PREFIX_DEFAULT
PGHOST: str
PGPORT: str
PGDATABASE: str
PGUSER: str
PGPASSWORD: str


def setup_logging_map_server(log_level: int = logging.INFO, log_to_console: bool = True) -> None:
    """Set up logging configuration for this script using the global LOG_PREFIX."""
    global LOG_PREFIX
    # Remove any existing handlers for this specific logger instance to avoid duplicate logs
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    log_formatter = logging.Formatter(
        f"{LOG_PREFIX} %(asctime)s - %(levelname)s - %(message)s",  # Use the global LOG_PREFIX
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_formatter)
        logger.addHandler(console_handler)

    logger.setLevel(log_level)
    logger.propagate = False  # Prevent messages from being passed to the root logger if it's configured differently


def log_map_server(message: str, level: str = "info") -> None:
    """Log a message with the configured prefix and level."""
    if level == "info":
        logger.info(message)
    elif level == "warning":
        logger.warning(message)
    elif level == "error":
        logger.error(message)
    elif level == "critical":
        logger.critical(message)
    else:
        logger.info(message)


# --- Command Execution Helpers ---
def _get_elevated_command_prefix_map_server() -> List[str]:
    """Returns ['sudo'] if not root, otherwise an empty list."""
    return [] if os.geteuid() == 0 else ["sudo"]


def run_command(command: List[str] or str, check: bool = True, shell: bool = False,
                capture_output: bool = False, text: bool = True,
                cmd_input: Optional[str] = None) -> subprocess.CompletedProcess:
    """
    Run a command and handle errors. Logs the command being run.
    """
    command_to_log_str: str
    command_to_run: List[str] or str

    if shell:
        if isinstance(command, list):
            command_to_run = " ".join(command)
        else:  # command is already a string
            command_to_run = command
        command_to_log_str = command_to_run
    else:  # not shell
        if isinstance(command, str):
            # For safety, only allow simple commands as strings without shell=True
            # Or better, enforce command to be a list if shell=False
            log_map_server(
                f"{SYMBOLS['warning']} Running string command '{command}' without shell=True. Consider using a list for arguments or shell=True if it's a complex shell command.",
                "warning")
            command_to_run = command.split()  # Basic split, might not handle quotes well
            command_to_log_str = command
        else:  # command is a list
            command_to_run = command
            command_to_log_str = " ".join(command)

    log_map_server(f"{SYMBOLS['gear']} Executing: {command_to_log_str}")
    try:
        result = subprocess.run(
            command_to_run,
            check=check,
            shell=shell,
            capture_output=capture_output,
            text=text,
            input=cmd_input
        )
        # Optionally log stdout/stderr for non-failing commands if capture_output is True
        if capture_output and not check and result.returncode == 0:  # If check=False and succeeded
            if result.stdout and result.stdout.strip():
                log_map_server(f"   stdout: {result.stdout.strip()}", "info")
            if result.stderr and result.stderr.strip():
                # Some tools use stderr for informational messages (e.g. pipx, curl progress)
                log_map_server(f"   stderr: {result.stderr.strip()}", "info")
        return result
    except subprocess.CalledProcessError as e:
        # For CalledProcessError, stdout and stderr are attributes of e
        stdout_info = e.stdout.strip() if e.stdout else "N/A"
        stderr_info = e.stderr.strip() if e.stderr else "N/A"
        cmd_executed_str = " ".join(e.cmd) if isinstance(e.cmd, list) else str(e.cmd)
        log_map_server(f"{SYMBOLS['error']} Command `{cmd_executed_str}` failed with return code {e.returncode}.",
                       "error")
        if stdout_info != "N/A": log_map_server(f"   stdout: {stdout_info}", "error")
        if stderr_info != "N/A": log_map_server(f"   stderr: {stderr_info}", "error")
        raise
    except FileNotFoundError as e:
        log_map_server(f"{SYMBOLS['error']} Command not found: {e.filename}. Ensure it's installed and in PATH.",
                       "error")
        raise
    except Exception as e:
        log_map_server(f"{SYMBOLS['error']} Unexpected error running command `{command_to_log_str}`: {e}", "error")
        # import traceback # For debugging unhandled exceptions from subprocess
        # log_map_server(traceback.format_exc(), "error")
        raise


def run_elevated_command(command: List[str], check: bool = True,
                         capture_output: bool = False, cmd_input: Optional[str] = None) -> subprocess.CompletedProcess:
    """
    Run a command that may require elevation, handling sudo correctly.
    """
    prefix = _get_elevated_command_prefix_map_server()
    # Ensure command is a list for concatenation
    command_list = list(command)  # Make a copy if it's from a global list
    elevated_command_list = prefix + command_list
    return run_command(elevated_command_list, check, False, capture_output, cmd_input=cmd_input)


# --- State Management Functions ---
def initialize_state_system() -> None:
    if not os.path.isdir(STATE_FILE_DIR):
        log_map_server(f"{SYMBOLS['info']} Creating state directory: {STATE_FILE_DIR}")
        run_elevated_command(["mkdir", "-p", STATE_FILE_DIR])
        run_elevated_command(["chmod", "750", STATE_FILE_DIR])

    if not os.path.isfile(STATE_FILE):
        log_map_server(f"{SYMBOLS['info']} Initializing state file: {STATE_FILE}")
        with tempfile.NamedTemporaryFile(mode='w', delete=False, prefix="mapstate_init_", suffix=".txt") as temp_f:
            temp_f.write(f"# Script Version: {SCRIPT_VERSION}\n")
            temp_file_path = temp_f.name
        try:
            run_elevated_command(["cp", temp_file_path, STATE_FILE])
            run_elevated_command(["chmod", "640", STATE_FILE])
        finally:
            os.unlink(temp_file_path)
    else:
        try:
            result = run_elevated_command(["grep", "^# Script Version:", STATE_FILE], capture_output=True, check=False)
            if result.returncode == 0 and result.stdout:
                stored_version_match = re.search(r"^\# Script Version:\s*(\S+)", result.stdout, re.MULTILINE)
                if stored_version_match:
                    stored_version = stored_version_match.group(1)
                    if stored_version != SCRIPT_VERSION:
                        log_map_server(
                            f"{SYMBOLS['warning']} Script version mismatch. Stored: {stored_version}, Current: {SCRIPT_VERSION}",
                            "warning")
                        log_map_server(f"{SYMBOLS['info']} Clearing state file due to version mismatch.")
                        clear_state_file(write_version_only=True)
                else:  # Version line malformed or not found as expected
                    log_map_server(
                        f"{SYMBOLS['warning']} State file version line not found or malformed. Re-initializing.",
                        "warning")
                    clear_state_file(write_version_only=True)
            elif result.returncode == 1:  # Grep found nothing
                log_map_server(
                    f"{SYMBOLS['warning']} State file exists but is empty or has no version line. Re-initializing.",
                    "warning")
                clear_state_file(write_version_only=True)
            # If grep had other errors, it would raise an exception handled by the outer try-except
        except Exception as e:  # Catch broader exceptions during state file check
            log_map_server(
                f"{SYMBOLS['error']} Error checking script version in state file: {e}. Re-initializing state file.",
                "error")
            clear_state_file(write_version_only=True)


def mark_step_completed(step_tag: str) -> None:
    try:
        result = run_elevated_command(["grep", "-Fxq", step_tag, STATE_FILE], check=False, capture_output=True)
        if result.returncode != 0:
            log_map_server(f"{SYMBOLS['info']} Marking step '{step_tag}' as completed.")
            run_elevated_command(["tee", "-a", STATE_FILE], cmd_input=f"{step_tag}\n", capture_output=False)
        else:
            log_map_server(f"{SYMBOLS['info']} Step '{step_tag}' was already marked as completed.")
    except Exception as e:
        log_map_server(f"{SYMBOLS['error']} Error marking step '{step_tag}': {e}", "error")


def is_step_completed(step_tag: str) -> bool:
    try:
        result = run_elevated_command(["grep", "-Fxq", step_tag, STATE_FILE], check=False, capture_output=True)
        return result.returncode == 0
    except Exception as e:
        log_map_server(f"{SYMBOLS['error']} Error checking if step '{step_tag}' is completed: {e}", "error")
        return False


def clear_state_file(write_version_only: bool = False) -> None:
    log_map_server(f"{SYMBOLS['info']} Clearing state file: {STATE_FILE}")
    content_to_write = f"# Script Version: {SCRIPT_VERSION}\n"
    if not write_version_only:
        content_to_write += f"# State cleared on {datetime.datetime.now().isoformat()}\n"

    with tempfile.NamedTemporaryFile(mode='w', delete=False, prefix="mapstate_clear_", suffix=".txt") as temp_f:
        temp_f.write(content_to_write)
        temp_file_path = temp_f.name
    try:
        run_elevated_command(["cp", temp_file_path, STATE_FILE])
        if not write_version_only:
            log_map_server(f"{SYMBOLS['success']} Progress state file cleared.")
    except Exception as e:
        log_map_server(f"{SYMBOLS['error']} Failed to clear state file: {e}", "error")
    finally:
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


def view_completed_steps() -> List[str]:
    try:
        result = run_elevated_command(["grep", "-v", "^#", STATE_FILE], capture_output=True, check=False)
        if result.returncode == 0 and result.stdout and result.stdout.strip():
            return [line for line in result.stdout.strip().split('\n') if line.strip()]
        return []
    except Exception as e:
        log_map_server(f"{SYMBOLS['error']} Error viewing completed steps: {e}", "error")
        return []


# --- Helper Functions ---
def backup_file(file_path: str) -> bool:
    # Check existence with elevated privileges first
    try:
        run_elevated_command(["test", "-f", file_path], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        log_map_server(f"{SYMBOLS['warning']} File {file_path} does not exist or is not accessible. Cannot backup.",
                       "warning")
        return False
    except Exception as e:
        log_map_server(f"{SYMBOLS['error']} Error checking file existence for backup {file_path}: {e}", "error")
        return False

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = f"{file_path}.bak.{timestamp}"
    try:
        run_elevated_command(["cp", "-a", file_path, backup_path])
        log_map_server(f"{SYMBOLS['success']} Backed up {file_path} to {backup_path}")
        return True
    except Exception as e:
        log_map_server(f"{SYMBOLS['error']} Failed to backup {file_path} to {backup_path}: {e}", "error")
        return False


def validate_cidr(cidr: str) -> bool:
    if not isinstance(cidr, str): return False
    try:
        # A more robust validation would use the `ipaddress` module.
        # For now, using a regex similar to original.
        ip_part, prefix_part = cidr.split('/')
        if not (0 <= int(prefix_part) <= 32): return False
        octets = ip_part.split('.')
        if len(octets) != 4: return False
        return all(0 <= int(o) <= 255 for o in octets)
    except ValueError:  # Catches int() conversion errors or split errors
        return False


def setup_pgpass() -> None:
    global PGPASSWORD, PGUSER, PGHOST, PGPORT, PGDATABASE  # Make sure we use the (potentially CLI overridden) globals
    if not PGPASSWORD or PGPASSWORD == PGPASSWORD_DEFAULT:
        log_map_server(f"{SYMBOLS['info']} PGPASSWORD is not set or is default. .pgpass file not created.", "info")
        return

    try:
        # Use getpass to get current username for home directory, more portable
        current_user_name = getpass.getuser()
        home_dir = os.path.expanduser(f"~{current_user_name}")
        if not os.path.isdir(home_dir):  # Should always exist for a logged-in user
            log_map_server(
                f"{SYMBOLS['error']} Home directory for user '{current_user_name}' not found. Cannot create .pgpass.",
                "error")
            return

        pgpass_file = os.path.join(home_dir, ".pgpass")
        pgpass_entry_content = f"{PGHOST}:{PGPORT}:{PGDATABASE}:{PGUSER}:{PGPASSWORD}"
        pgpass_entry_line = f"{pgpass_entry_content}\n"

        entry_exists = False
        if os.path.isfile(pgpass_file):
            try:
                with open(pgpass_file, 'r') as f_read:
                    if pgpass_entry_content in [line.strip() for line in f_read]:
                        entry_exists = True
            except Exception as e_read:
                log_map_server(f"{SYMBOLS['warning']} Could not read existing .pgpass file at {pgpass_file}: {e_read}",
                               "warning")

        if not entry_exists:
            # Append the entry. Ensure the file is created if it doesn't exist.
            with open(pgpass_file, 'a') as f_append:
                f_append.write(pgpass_entry_line)
            os.chmod(pgpass_file, 0o600)
            log_map_server(
                f"{SYMBOLS['success']} .pgpass file configured/updated at {pgpass_file} for user {current_user_name}.")
        else:
            log_map_server(f"{SYMBOLS['info']} .pgpass entry already exists in {pgpass_file}.")
            # Ensure permissions are still correct even if entry exists
            if os.path.isfile(pgpass_file) and not oct(os.stat(pgpass_file).st_mode).endswith('600'):
                os.chmod(pgpass_file, 0o600)
                log_map_server(f"{SYMBOLS['info']} Corrected permissions for existing .pgpass file to 600.")


    except Exception as e:
        log_map_server(f"{SYMBOLS['error']} Failed to set up .pgpass file: {e}", "error")


# --- Core Installation Functions ---
def systemd_reload() -> None:
    log_map_server(f"{SYMBOLS['gear']} Reloading systemd daemon...")
    run_elevated_command(["systemctl", "daemon-reload"])
    log_map_server(f"{SYMBOLS['success']} Systemd daemon reloaded.")


def boot_verbosity() -> None:
    log_map_server(f"{SYMBOLS['step']} Improving boot verbosity & core utils...")
    if backup_file("/etc/default/grub"):
        run_elevated_command([
            "sed", "-i",  # In-place edit
            r"-e", r'/^GRUB_CMDLINE_LINUX_DEFAULT=/s/\bquiet\b//g',
            r"-e", r'/^GRUB_CMDLINE_LINUX_DEFAULT=/s/\bsplash\b//g',
            r"-e", r'/^GRUB_CMDLINE_LINUX_DEFAULT=/s/  +/ /g',
            r"-e", r'/^GRUB_CMDLINE_LINUX_DEFAULT=/s/" /"/g',
            r"-e", r'/^GRUB_CMDLINE_LINUX_DEFAULT=/s/ "/"/g',
            "/etc/default/grub"
        ])
        run_elevated_command(["update-grub"])
        run_elevated_command(["update-initramfs", "-u"])
        log_map_server(f"{SYMBOLS['success']} Boot verbosity improved.")

    current_user = getpass.getuser()
    log_map_server(f"{SYMBOLS['gear']} Adding user '{current_user}' to 'systemd-journal' group...")
    try:
        run_elevated_command(["usermod", "--append", "--group", "systemd-journal", current_user])
        log_map_server(f"{SYMBOLS['success']} User {current_user} added to systemd-journal group.")
    except Exception as e:
        log_map_server(
            f"{SYMBOLS['warning']} Could not add user {current_user} to systemd-journal group: {e}. This may be non-critical.",
            "warning")

    log_map_server(f"{SYMBOLS['package']} System update and essential utilities install...")
    run_elevated_command(["apt", "update"])
    run_elevated_command(["apt", "--yes", "upgrade"])
    run_elevated_command(["apt", "--yes", "install"] + ["curl", "wget", "bash", "btop", "screen", "ca-certificates"])


def core_conflict_removal() -> None:
    log_map_server(f"{SYMBOLS['step']} Removing conflicting system Node.js (if any)...")
    try:
        result = run_command(["dpkg", "-s", "nodejs"], check=False, capture_output=True)
        if result.returncode == 0:
            log_map_server(f"{SYMBOLS['info']} System 'nodejs' package found. Attempting removal...")
            run_elevated_command(["apt", "remove", "--purge", "--yes", "nodejs", "npm"])
            run_elevated_command(["apt", "--purge", "--yes", "autoremove"])
            log_map_server(f"{SYMBOLS['success']} System nodejs and npm removed.")
        else:
            log_map_server(f"{SYMBOLS['info']} System 'nodejs' not found via dpkg, skipping removal.")
    except Exception as e:
        log_map_server(f"{SYMBOLS['error']} Error during core conflict removal: {e}", "error")


def core_install() -> None:
    log_map_server(f"{SYMBOLS['step']} Installing core system packages...")
    run_elevated_command(["apt", "update"])

    log_map_server(f"{SYMBOLS['package']} Installing prerequisite system utilities (git, build-essential, etc.)...")
    run_elevated_command(["apt", "--yes", "install"] + CORE_PREREQ_PACKAGES)

    log_map_server(f"{SYMBOLS['package']} Installing Python system packages...")
    run_elevated_command(["apt", "--yes", "install"] + PYTHON_SYSTEM_PACKAGES)

    log_map_server(f"{SYMBOLS['package']} Installing PostgreSQL system packages...")
    run_elevated_command(["apt", "--yes", "install"] + POSTGRES_PACKAGES)

    log_map_server(f"{SYMBOLS['package']} Installing mapping system packages...")
    run_elevated_command(["apt", "--yes", "install"] + MAPPING_PACKAGES)

    log_map_server(f"{SYMBOLS['package']} Installing font system packages...")
    run_elevated_command(["apt", "--yes", "install"] + FONT_PACKAGES)

    log_map_server(f"{SYMBOLS['package']} Installing unattended-upgrades...")
    run_elevated_command(["apt", "--yes", "install", "unattended-upgrades"])
    log_map_server(f"{SYMBOLS['success']} Core system packages installation process completed.")


def docker_install() -> None:
    log_map_server(f"{SYMBOLS['step']} Setting up Docker Engine...")
    log_map_server(f"{SYMBOLS['gear']} Adding Docker's official GPG key...")
    run_elevated_command(["install", "--mode", "0755", "--directory", "/etc/apt/keyrings"])

    key_url = "https://download.docker.com/linux/debian/gpg"
    key_dest_tmp = ""
    key_dest_final = "/etc/apt/keyrings/docker.asc"
    try:
        with tempfile.NamedTemporaryFile(delete=False, prefix="dockerkey_", suffix=".asc") as temp_f:
            key_dest_tmp = temp_f.name
        run_command(["curl", "-fsSL", key_url, "-o", key_dest_tmp])
        run_elevated_command(["cp", key_dest_tmp, key_dest_final])
        run_elevated_command(["chmod", "a+r", key_dest_final])
    except Exception as e:
        log_map_server(f"{SYMBOLS['error']} Failed to download or install Docker GPG key: {e}", "error")
        raise
    finally:
        if key_dest_tmp and os.path.exists(key_dest_tmp):
            os.unlink(key_dest_tmp)

    log_map_server(f"{SYMBOLS['gear']} Adding Docker repository to Apt sources...")
    try:
        arch_result = run_command(["dpkg", "--print-architecture"], capture_output=True, check=True)
        arch = arch_result.stdout.strip()
        codename_result = run_command(["lsb_release", "-cs"], capture_output=True, check=True)
        codename = codename_result.stdout.strip()
    except Exception as e:
        log_map_server(f"{SYMBOLS['error']} Could not determine system architecture or codename for Docker setup: {e}",
                       "error")
        raise

    docker_source_list_content = f"deb [arch={arch} signed-by={key_dest_final}] https://download.docker.com/linux/debian {codename} stable\n"
    try:
        run_elevated_command(["tee", "/etc/apt/sources.list.d/docker.list"], cmd_input=docker_source_list_content)
    except Exception as e:
        log_map_server(f"{SYMBOLS['error']} Failed to write Docker apt source list: {e}", "error")
        raise

    log_map_server(f"{SYMBOLS['gear']} Updating apt package list for Docker...")
    run_elevated_command(["apt", "update"])

    docker_packages = ["docker-ce", "docker-ce-cli", "containerd.io", "docker-buildx-plugin", "docker-compose-plugin"]
    log_map_server(f"{SYMBOLS['package']} Installing Docker packages: {', '.join(docker_packages)}...")
    run_elevated_command(["apt", "--yes", "install"] + docker_packages)

    current_user = getpass.getuser()
    log_map_server(f"{SYMBOLS['gear']} Adding current user ({current_user}) to the 'docker' group...")
    try:
        run_elevated_command(["usermod", "--append", "--group", "docker", current_user])
        log_map_server(f"{SYMBOLS['success']} User {current_user} added to 'docker' group.")
        log_map_server(
            f"   {SYMBOLS['warning']} You MUST log out and log back in for this group change to take full effect for your current session.",
            "warning")
    except Exception as e:
        log_map_server(
            f"{SYMBOLS['warning']} Could not add user {current_user} to docker group: {e}. Docker commands might require 'sudo' prefix from this user until logout/login.",
            "warning")

    log_map_server(f"{SYMBOLS['gear']} Enabling and starting Docker services...")
    run_elevated_command(["systemctl", "enable", "docker.service"])
    run_elevated_command(["systemctl", "enable", "containerd.service"])
    run_elevated_command(["systemctl", "start", "docker.service"])  # Start it as well
    log_map_server(f"{SYMBOLS['success']} Docker setup complete.")


def node_js_lts_install() -> None:
    log_map_server(f"{SYMBOLS['step']} Installing Node.js LTS version using NodeSource...")
    try:
        nodesource_setup_url = "https://deb.nodesource.com/setup_lts.x"
        log_map_server(f"{SYMBOLS['gear']} Downloading NodeSource setup script from {nodesource_setup_url}...")
        # Download script content as current user
        curl_result = run_command(["curl", "-fsSL", nodesource_setup_url], capture_output=True, check=True)
        nodesource_script_content = curl_result.stdout

        log_map_server(f"{SYMBOLS['gear']} Executing NodeSource setup script with elevated privileges...")
        # Pipe the script content to 'bash -' executed with elevation
        run_elevated_command(["bash", "-"], cmd_input=nodesource_script_content)

        log_map_server(f"{SYMBOLS['gear']} Updating apt package list after adding NodeSource repo...")
        run_elevated_command(["apt", "update"])
        log_map_server(f"{SYMBOLS['package']} Installing Node.js...")
        run_elevated_command(["apt", "--yes", "install", "nodejs"])

        # Check versions as current user (should be in PATH)
        node_version = run_command(["node", "-v"], capture_output=True, check=False).stdout.strip() or "Not detected"
        npm_version = run_command(["npm", "-v"], capture_output=True, check=False).stdout.strip() or "Not detected"
        log_map_server(f"{SYMBOLS['success']} Node.js installed. Version: {node_version}, NPM Version: {npm_version}")
    except Exception as e:
        log_map_server(f"{SYMBOLS['error']} Failed to install Node.js LTS: {e}", "error")
        raise


def ufw_setup() -> None:
    log_map_server(f"{SYMBOLS['step']} Setting up firewall with ufw...")
    global ADMIN_GROUP_IP  # Ensure we use the potentially CLI-overridden value

    if not validate_cidr(ADMIN_GROUP_IP):
        log_map_server(
            f"{SYMBOLS['error']} Firewall setup aborted: Invalid ADMIN_GROUP_IP CIDR format '{ADMIN_GROUP_IP}'.",
            "error")
        raise ValueError("Invalid ADMIN_GROUP_IP for UFW setup.")

    run_elevated_command(["ufw", "default", "deny", "incoming"])
    run_elevated_command(["ufw", "default", "allow", "outgoing"])
    run_elevated_command(["ufw", "allow", "in", "on", "lo"])
    run_elevated_command(["ufw", "allow", "out", "on", "lo"])

    # Allow from Admin Group
    run_elevated_command(["ufw", "allow", "from", ADMIN_GROUP_IP, "to", "any", "port", "22", "proto", "tcp", "comment",
                          "SSH from Admin"])
    run_elevated_command(
        ["ufw", "allow", "from", ADMIN_GROUP_IP, "to", "any", "port", "5432", "proto", "tcp", "comment",
         "PostgreSQL from Admin"])
    run_elevated_command(["ufw", "allow", "from", ADMIN_GROUP_IP, "to", "any", "port", "80", "proto", "tcp", "comment",
                          "HTTP from Admin"])
    run_elevated_command(["ufw", "allow", "from", ADMIN_GROUP_IP, "to", "any", "port", "443", "proto", "tcp", "comment",
                          "HTTPS from Admin"])

    # Allow proxied services (these listen on localhost, Nginx exposes them)
    run_elevated_command(["ufw", "allow", "80/tcp", "comment", "Nginx HTTP"])  # For external access to Nginx
    run_elevated_command(["ufw", "allow", "443/tcp", "comment", "Nginx HTTPS"])  # For external access to Nginx

    # The following are internal ports, if UFW is very strict, localhost might need explicit allows.
    # However, UFW typically allows loopback. If issues, these might be needed but usually aren't for localhost access.
    # run_elevated_command(["ufw", "allow", "5000/tcp", "comment", "OSRM internal"]) # Nginx proxies this
    # run_elevated_command(["ufw", "allow", "7800/tcp", "comment", "pg_tileserv internal"]) # Nginx proxies this
    # run_elevated_command(["ufw", "allow", "8080/tcp", "comment", "Apache internal"]) # Nginx proxies this

    log_map_server(
        f"{SYMBOLS['warning']} UFW will be enabled. Ensure your SSH access from '{ADMIN_GROUP_IP}' is correct.",
        "warning")
    # UFW enable can sometimes be tricky in scripts if it disconnects SSH.
    # For non-interactive, it might need --force or expect 'y'.
    # Using cmd_input='y\n' to auto-confirm.
    try:
        run_elevated_command(["ufw", "enable"], cmd_input="y\n", check=True)  # Pass 'y' to the prompt
        log_map_server(f"{SYMBOLS['success']} UFW enabled.")
    except subprocess.CalledProcessError as e:
        # Check if it's because it's already enabled
        if "Firewall is already active" in e.stdout or "Firewall is already active" in e.stderr:
            log_map_server(f"{SYMBOLS['info']} UFW is already active.")
        else:
            log_map_server(f"{SYMBOLS['error']} Failed to enable UFW: {e}", "error")
            raise

    log_map_server(f"{SYMBOLS['info']} UFW status:")
    run_elevated_command(["ufw", "status", "verbose"])


def postgres_setup() -> None:
    log_map_server(f"{SYMBOLS['step']} Setting up PostgreSQL user, database, and extensions...")
    global PGUSER, PGPASSWORD, PGDATABASE, PGHOST, PGPORT, ADMIN_GROUP_IP  # Ensure globals

    # It's safer to quote shell arguments if they come from variables
    # psql commands are generally safe if variables don't have SQL metacharacters.
    # For passwords, this is critical. The script uses PGPASSWORD in connection strings later.

    # Create user
    try:
        run_elevated_command(
            ["sudo", "-u", "postgres", "psql", "-c", f"CREATE USER {PGUSER} WITH PASSWORD '{PGPASSWORD}';"])
    except subprocess.CalledProcessError as e:
        if "already exists" in e.stderr:
            log_map_server(
                f"{SYMBOLS['info']} PostgreSQL user '{PGUSER}' already exists. Attempting to update password.", "info")
            run_elevated_command(
                ["sudo", "-u", "postgres", "psql", "-c", f"ALTER USER {PGUSER} WITH PASSWORD '{PGPASSWORD}';"])
        else:
            raise

    # Create database
    try:
        run_elevated_command([
            "sudo", "-u", "postgres", "psql", "-c",
            f"CREATE DATABASE {PGDATABASE} WITH OWNER {PGUSER} ENCODING 'UTF8' LC_COLLATE='en_AU.UTF-8' LC_CTYPE='en_AU.UTF-8' TEMPLATE template0;"
        ])
    except subprocess.CalledProcessError as e:
        if "already exists" in e.stderr:
            log_map_server(f"{SYMBOLS['info']} PostgreSQL database '{PGDATABASE}' already exists.", "info")
        else:
            raise

    # Create extensions
    extensions = ["postgis", "hstore"]
    for ext in extensions:
        try:
            run_elevated_command(
                ["sudo", "-u", "postgres", "psql", "-d", PGDATABASE, "-c", f"CREATE EXTENSION IF NOT EXISTS {ext};"])
        except subprocess.CalledProcessError as e:
            # Log warning but continue, extension might be there but with issues, or DB access problem
            log_map_server(
                f"{SYMBOLS['warning']} Could not create extension {ext} (it might already exist or other issue): {e.stderr}",
                "warning")

    # Set permissions
    run_elevated_command(
        ["sudo", "-u", "postgres", "psql", "-d", PGDATABASE, "-c", f"ALTER SCHEMA public OWNER TO {PGUSER};"])
    run_elevated_command(["sudo", "-u", "postgres", "psql", "-d", PGDATABASE, "-c",
                          f"GRANT ALL ON SCHEMA public TO {PGUSER};"])  # More explicit
    run_elevated_command(["sudo", "-u", "postgres", "psql", "-d", PGDATABASE, "-c",
                          f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {PGUSER};"])
    run_elevated_command(["sudo", "-u", "postgres", "psql", "-d", PGDATABASE, "-c",
                          f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {PGUSER};"])
    run_elevated_command(["sudo", "-u", "postgres", "psql", "-d", PGDATABASE, "-c",
                          f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO {PGUSER};"])

    log_map_server(
        f"{SYMBOLS['success']} PostgreSQL user '{PGUSER}' and database '{PGDATABASE}' with extensions configured.")

    # Configure postgresql.conf
    pg_conf_path = "/etc/postgresql/15/main/postgresql.conf"  # TODO: Make version dynamic or check path
    if not os.path.exists(pg_conf_path):  # Check with os.path before trying to backup with sudo
        log_map_server(f"{SYMBOLS['warning']} PostgreSQL config path {pg_conf_path} not found. Skipping customization.",
                       "warning")
    elif backup_file(pg_conf_path):
        # Important: listen_addresses = '*' is a security consideration. Ensure firewall is tight.
        postgresql_custom_conf = f"""
# --- TRANSIT SERVER CUSTOMISATIONS ---
listen_addresses = '*'
shared_buffers = 2GB
work_mem = 256MB
maintenance_work_mem = 2GB
checkpoint_timeout = 15min
max_wal_size = 4GB
min_wal_size = 2GB
checkpoint_completion_target = 0.9
effective_cache_size = 24GB # Should be ~75% of system RAM if PG is main workload
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_min_duration_statement = 250ms
# Ensure these are not duplicated if run multiple times
# A better approach would be to use sed or augeas to set specific parameters.
# For simplicity now, we append. User must be careful on re-runs.
"""
        # Check if marker exists before appending
        marker = "# --- TRANSIT SERVER CUSTOMISATIONS ---"
        try:
            grep_result = run_elevated_command(["grep", "-q", marker, pg_conf_path], check=False, capture_output=True)
            if grep_result.returncode != 0:  # Marker not found, safe to append
                run_elevated_command(["tee", "-a", pg_conf_path], cmd_input=postgresql_custom_conf)
                log_map_server(f"{SYMBOLS['success']} Customized {pg_conf_path}")
            else:
                log_map_server(
                    f"{SYMBOLS['info']} Customizations marker found in {pg_conf_path}. Assuming already applied or managed manually.",
                    "info")
        except Exception as e:
            log_map_server(f"{SYMBOLS['error']} Error updating {pg_conf_path}: {e}", "error")

    # Configure pg_hba.conf
    pg_hba_path = "/etc/postgresql/15/main/pg_hba.conf"  # TODO: Make version dynamic
    if not os.path.exists(pg_hba_path):
        log_map_server(
            f"{SYMBOLS['warning']} PostgreSQL HBA config path {pg_hba_path} not found. Skipping customization.",
            "warning")
    elif backup_file(pg_hba_path):
        # This will OVERWRITE pg_hba.conf with these specific rules.
        # This is a common approach for controlled environments.
        # Ensure ADMIN_GROUP_IP is validated CIDR.
        if not validate_cidr(ADMIN_GROUP_IP):
            log_map_server(
                f"{SYMBOLS['error']} Invalid ADMIN_GROUP_IP '{ADMIN_GROUP_IP}' for pg_hba.conf. Skipping HBA update.",
                "error")
        else:
            pg_hba_content = f"""# TYPE  DATABASE        USER            ADDRESS                 METHOD
# "local" is for Unix domain socket connections only
local   all             postgres                                peer
local   all             all                                     peer
local   {PGDATABASE}    {PGUSER}                                scram-sha-256
# IPv4 local connections:
host    all             all             127.0.0.1/32            scram-sha-256
host    {PGDATABASE}    {PGUSER}        127.0.0.1/32            scram-sha-256
host    {PGDATABASE}    {PGUSER}        {ADMIN_GROUP_IP}        scram-sha-256
# IPv6 local connections:
host    all             all             ::1/128                 scram-sha-256
host    {PGDATABASE}    {PGUSER}        ::1/128                 scram-sha-256
# Add other necessary rules above this line if needed, or integrate carefully.
"""
            try:
                run_elevated_command(["tee", pg_hba_path], cmd_input=pg_hba_content)  # Overwrite
                log_map_server(f"{SYMBOLS['success']} Customized {pg_hba_path} (Overwritten with new rules).")
            except Exception as e:
                log_map_server(f"{SYMBOLS['error']} Error writing {pg_hba_path}: {e}", "error")

    log_map_server(f"{SYMBOLS['gear']} Restarting and enabling PostgreSQL service...")
    run_elevated_command(["systemctl", "restart", "postgresql"])
    run_elevated_command(["systemctl", "enable", "postgresql"])
    log_map_server(f"{SYMBOLS['info']} PostgreSQL service status:")
    run_elevated_command(["systemctl", "status", "postgresql", "--no-pager", "-l"])


def pg_tileserv_setup() -> None:
    log_map_server(f"{SYMBOLS['step']} Setting up pg_tileserv...")
    global PG_TILESERV_BINARY_LOCATION, PGUSER, PGPASSWORD, PGHOST, PGPORT, PGDATABASE

    pg_tileserv_bin_path = "/usr/local/bin/pg_tileserv"
    if not command_exists(pg_tileserv_bin_path):  # Check if binary itself exists using shutil.which via command_exists
        log_map_server(
            f"{SYMBOLS['info']} pg_tileserv not found at {pg_tileserv_bin_path}, downloading from {PG_TILESERV_BINARY_LOCATION}...")
        temp_zip_path = ""
        temp_dir = ""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip', prefix="pgtileserv_") as temp_file:
                temp_zip_path = temp_file.name

            run_command(["wget", PG_TILESERV_BINARY_LOCATION, "-O", temp_zip_path])  # Download as user
            temp_dir = tempfile.mkdtemp(prefix="pgtileserv_extract_")
            run_command(["unzip", "-j", temp_zip_path, "pg_tileserv", "-d", temp_dir])  # -j to junk paths

            run_elevated_command(["mv", os.path.join(temp_dir, "pg_tileserv"), pg_tileserv_bin_path])
            log_map_server(f"{SYMBOLS['success']} pg_tileserv installed to {pg_tileserv_bin_path}.")
        except Exception as e:
            log_map_server(f"{SYMBOLS['error']} Failed to download or install pg_tileserv: {e}", "error")
            raise
        finally:
            if temp_zip_path and os.path.exists(temp_zip_path): os.unlink(temp_zip_path)
            if temp_dir and os.path.isdir(temp_dir): shutil.rmtree(temp_dir)
    else:
        log_map_server(f"{SYMBOLS['info']} pg_tileserv already exists at {pg_tileserv_bin_path}.")

    run_command([pg_tileserv_bin_path, "--version"])  # Run as user to check version

    pg_tileserv_config_dir = "/etc/pg_tileserv"
    pg_tileserv_config_file = os.path.join(pg_tileserv_config_dir, "config.toml")
    run_elevated_command(["mkdir", "-p", pg_tileserv_config_dir])

    # Construct DATABASE_URL carefully, especially if PGPASSWORD can have special chars.
    # For subprocess, it's usually fine if not using shell=True for the final ExecStart.
    # Python's urllib.parse.quote_plus could be used for password if needed in connection string.
    db_url_for_config = f"postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}"

    pg_tileserv_config_content = f"""HttpHost = "0.0.0.0" # Listen on all interfaces, UFW controls access
HttpPort = 7800
DatabaseUrl = "{db_url_for_config}"
DefaultMaxFeatures = 10000
PublishSchemas = "public,gtfs" # Add gtfs schema
URIPrefix = "/vector" # Base path for tile requests
DevelopmentMode = false # Set to true for more verbose logging during dev
AllowFunctionSources = true # If you use function-based tile sources
# MaxConnections = 20 # Optional: limit DB connections
# CacheSizeMB = 128 # Optional: internal cache size
"""
    try:
        run_elevated_command(["tee", pg_tileserv_config_file], cmd_input=pg_tileserv_config_content)
        log_map_server(f"{SYMBOLS['success']} Created {pg_tileserv_config_file}")
    except Exception as e:
        log_map_server(f"{SYMBOLS['error']} Failed to write pg_tileserv config: {e}", "error")
        raise

    # Create pgtileserv_user if it doesn't exist
    pgtileserv_system_user = "pgtileservuser"  # Changed from pgtileserv_user to avoid potential name collisions
    try:
        run_command(["id", pgtileserv_system_user], check=True, capture_output=True)
        log_map_server(f"{SYMBOLS['info']} System user {pgtileserv_system_user} already exists.")
    except subprocess.CalledProcessError:  # User does not exist
        log_map_server(f"{SYMBOLS['info']} Creating system user {pgtileserv_system_user}...")
        run_elevated_command([
            "useradd", "--system", "--shell", "/usr/sbin/nologin",
            "--home-dir", "/var/empty", "--user-group", pgtileserv_system_user
        ])
        log_map_server(f"{SYMBOLS['success']} Created system user {pgtileserv_system_user}.")

    # Set permissions
    run_elevated_command(["chmod", "750", pg_tileserv_bin_path])  # Execute for user/group
    run_elevated_command(["chown", f"{pgtileserv_system_user}:{pgtileserv_system_user}", pg_tileserv_bin_path])
    run_elevated_command(["chmod", "640", pg_tileserv_config_file])  # Readable by user/group
    run_elevated_command(["chown", f"{pgtileserv_system_user}:{pgtileserv_system_user}", pg_tileserv_config_file])

    pg_tileserv_service_file = "/etc/systemd/system/pg_tileserv.service"
    # DATABASE_URL in ExecStart might be problematic if password has special chars for systemd parsing.
    # Better to use EnvironmentFile or pass directly if simple.
    # Simpler: pg_tileserv reads DATABASE_URL from its config.toml if not in env.
    # So we can remove it from Environment= here if config.toml sets DatabaseUrl
    pg_tileserv_service_content = f"""[Unit]
Description=pg_tileserv - Vector Tile Server for PostGIS
Wants=network-online.target postgresql.service
After=network-online.target postgresql.service

[Service]
User={pgtileserv_system_user}
Group={pgtileserv_system_user}
# Environment="DATABASE_URL={db_url_for_config}" # pg_tileserv will use its config.toml
ExecStart={pg_tileserv_bin_path} --config {pg_tileserv_config_file}
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=pg_tileserv
PrivateTmp=true
ProtectSystem=full
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
"""
    try:
        run_elevated_command(["tee", pg_tileserv_service_file], cmd_input=pg_tileserv_service_content)
        log_map_server(f"{SYMBOLS['success']} Created {pg_tileserv_service_file}")
    except Exception as e:
        log_map_server(f"{SYMBOLS['error']} Failed to write pg_tileserv systemd service file: {e}", "error")
        raise

    systemd_reload()
    run_elevated_command(["systemctl", "enable", "pg_tileserv"])
    run_elevated_command(["systemctl", "restart", "pg_tileserv"])  # Use restart
    log_map_server(f"{SYMBOLS['info']} pg_tileserv service status:")
    run_elevated_command(["systemctl", "status", "pg_tileserv", "--no-pager", "-l"])


# ... (Continue refactoring for ALL other functions: carto_setup, renderd_setup, osm_osrm_server_setup,
#      apache_modtile_setup, nginx_setup, certbot_setup, gtfs_data_prep, raster_tile_prep, website_prep) ...
# ... (The menu functions and argument parsing in main_map_server would remain structurally similar,
#      but they call these core functions that are being refactored.) ...

# --- Example for carto_setup (illustrative) ---
def carto_setup() -> None:
    log_map_server(f"{SYMBOLS['step']} Setting up CartoCSS compiler and OpenStreetMap-Carto stylesheet...")
    log_map_server(f"{SYMBOLS['package']} Installing CartoCSS compiler (carto) globally via npm...")

    if not command_exists("npm"):
        log_map_server(
            f"{SYMBOLS['error']} NPM (Node Package Manager) not found. Node.js needs to be installed first. Skipping carto setup.",
            "error")
        return  # Or raise an error if this is critical

    try:
        run_elevated_command(["npm", "install", "-g", "carto"])  # Global npm install often needs sudo
        carto_version_result = run_command(["carto", "-v"], capture_output=True, check=False)  # carto -v runs as user
        carto_version = carto_version_result.stdout.strip() if carto_version_result.returncode == 0 else "Not found or error"
        log_map_server(f"{SYMBOLS['success']} CartoCSS compiler installed. Version: {carto_version}")
    except Exception as e:
        log_map_server(f"{SYMBOLS['error']} Failed to install carto: {e}", "error")
        return  # Or raise

    log_map_server(f"{SYMBOLS['gear']} Setting up OpenStreetMap-Carto stylesheet...")
    osm_carto_base_dir = "/opt/openstreetmap-carto"
    if not os.path.isdir(osm_carto_base_dir):  # Check as current user
        log_map_server(f"{SYMBOLS['info']} Cloning OpenStreetMap-Carto repository to {osm_carto_base_dir}...")
        # Git clone can be to a user-writable temp location first, then sudo mv if /opt needs root
        # Or, ensure /opt is writable by a setup user, or use sudo git clone.
        # For simplicity, using sudo git clone here.
        run_elevated_command(
            ["git", "clone", "https://github.com/gravitystorm/openstreetmap-carto.git", osm_carto_base_dir])
    else:
        log_map_server(
            f"{SYMBOLS['info']} Directory {osm_carto_base_dir} already exists. Assuming up-to-date or managed manually.")

    # Temporarily chown to current user to run scripts that write inside the repo
    current_user = getpass.getuser()
    current_group = getpass.getgrgid(os.getgid()).gr_name  # More reliable group name

    # Ensure these directories exist before chown attempt
    run_elevated_command(["mkdir", "-p", osm_carto_base_dir])  # Ensure base dir exists with root
    run_elevated_command(["chown", "-R", f"{current_user}:{current_group}", osm_carto_base_dir])
    log_map_server(
        f"{SYMBOLS['info']} Temporarily changed ownership of {osm_carto_base_dir} to {current_user}:{current_group} for script execution.")

    original_cwd = os.getcwd()
    try:
        os.chdir(osm_carto_base_dir)
        log_map_server(
            f"{SYMBOLS['gear']} Getting external data for OpenStreetMap-Carto style (running as {current_user})...")
        # These scripts should run as the user who owns the files now
        if command_exists("python3"):
            run_command(["python3", "scripts/get-external-data.py"])
        elif command_exists("python"):
            run_command(["python", "scripts/get-external-data.py"])
        else:
            log_map_server(
                f"{SYMBOLS['warning']} Python not found, cannot run get-external-data.py. Shapefiles might be missing.",
                "warning")

        log_map_server(f"{SYMBOLS['gear']} Compiling project.mml to mapnik.xml (running as {current_user})...")
        # carto command runs as user because npm -g might install to user's prefix if not run with actual sudo shell
        # Or, if npm global install was sudo'd, carto should be in global path.
        # Assuming 'carto' is now in PATH for the current user.
        with open("carto_compile_log.txt", "w") as compile_log_file:  # Log to user-writable file
            carto_result = run_command(["carto", "project.mml"], capture_output=True,
                                       check=False)  # Run as current user
            if carto_result.stdout:
                with open("mapnik.xml", "w") as mapnik_file:  # Write as current user
                    mapnik_file.write(carto_result.stdout)
            if carto_result.stderr:
                compile_log_file.write(f"stderr:\n{carto_result.stderr}\n")
            if carto_result.returncode != 0:
                log_map_server(
                    f"{SYMBOLS['error']} Failed to compile mapnik.xml. Check 'carto_compile_log.txt' in {osm_carto_base_dir}.",
                    "error")
                # Revert ownership if failed partway through user operations
                run_elevated_command(
                    ["chown", "-R", f"root:root", osm_carto_base_dir])  # Example, or a dedicated system user
                return

        if not os.path.isfile("mapnik.xml") or os.path.getsize("mapnik.xml") == 0:
            log_map_server(f"{SYMBOLS['error']} mapnik.xml was not created or is empty. Check 'carto_compile_log.txt'.",
                           "error")
            run_elevated_command(["chown", "-R", f"root:root", osm_carto_base_dir])
            return

        # Operations requiring sudo again
        mapnik_style_dir = "/usr/local/share/maps/style/openstreetmap-carto"
        run_elevated_command(["mkdir", "-p", mapnik_style_dir])
        run_elevated_command(["cp", "mapnik.xml", os.path.join(mapnik_style_dir, "mapnik.xml")])
        log_map_server(f"{SYMBOLS['success']} mapnik.xml copied to {mapnik_style_dir}/")

    except Exception as e:
        log_map_server(f"{SYMBOLS['error']} Error during Carto setup: {e}", "error")
        # Ensure ownership is reverted in case of any error
        run_elevated_command(["chown", "-R", f"root:root", osm_carto_base_dir])
        raise
    finally:
        os.chdir(original_cwd)
        # Revert ownership of /opt/openstreetmap-carto to root or a dedicated system user
        log_map_server(
            f"{SYMBOLS['info']} Reverting ownership of {osm_carto_base_dir} (example: to root:root). Adjust if needed.")
        run_elevated_command(["chown", "-R", f"root:root", osm_carto_base_dir])

    log_map_server(f"{SYMBOLS['gear']} Updating font cache...")
    run_elevated_command(["fc-cache", "-fv"])
    log_map_server(f"{SYMBOLS['success']} Carto and OSM stylesheet setup attempted.")


# --- Definition of view_configuration ---
def view_configuration() -> None:
    """Display the current configuration."""
    global ADMIN_GROUP_IP, GTFS_FEED_URL, VM_IP_OR_DOMAIN, PG_TILESERV_BINARY_LOCATION, LOG_PREFIX
    global PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD

    # Use LOG_PREFIX which is set from args, not LOG_PREFIX_DEFAULT for display if overridden
    current_log_prefix = LOG_PREFIX

    config_text = f"{SYMBOLS['info']} Current effective configuration values:\n\n"
    config_text += f"  ADMIN_GROUP_IP:              {ADMIN_GROUP_IP}\n"
    config_text += f"  GTFS_FEED_URL:               {GTFS_FEED_URL}\n"
    config_text += f"  VM_IP_OR_DOMAIN:             {VM_IP_OR_DOMAIN}\n"
    config_text += f"  PG_TILESERV_BINARY_LOCATION: {PG_TILESERV_BINARY_LOCATION}\n"
    config_text += f"  LOG_PREFIX (for logger):     {current_log_prefix}\n\n"
    config_text += f"  PGHOST:                      {PGHOST}\n"
    config_text += f"  PGPORT:                      {PGPORT}\n"
    config_text += f"  PGDATABASE:                  {PGDATABASE}\n"
    config_text += f"  PGUSER:                      {PGUSER}\n"
    # Avoid printing actual password, show default or if it's been set by user from default
    pg_password_display = "[DEFAULT - Insecure]" if PGPASSWORD == PGPASSWORD_DEFAULT else "[SET BY USER/ARG]"
    if not PGPASSWORD: pg_password_display = "[NOT SET]"
    config_text += f"  PGPASSWORD:                  {pg_password_display}\n\n"
    config_text += f"  STATE_FILE_PATH:             {STATE_FILE}\n"
    config_text += f"  SCRIPT_VERSION:              {SCRIPT_VERSION}\n"
    config_text += f"  TIMESTAMP (current run):     {datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S')}\n\n"
    config_text += "You can override these using command-line options. Use -h for details."

    print("\n" + config_text + "\n")


def show_menu() -> None:
    """Display the main menu and handle user input."""
    # This function needs to be fully defined if used.
    # For now, main_map_server relies on CLI flags.
    log_map_server(f"{SYMBOLS['info']} Interactive menu not fully implemented in this snippet. Use CLI flags.", "info")
    print("\nAvailable CLI flags (use -h for more details):")
    print("  --full        Run all installation steps.")
    print("  --prereqs     Install prerequisites group only.")
    print("  --services    Setup services group only.")
    print("  --data        Prepare data group only.")
    print("  --step TAG    Run a single specific step by its tag.")
    print("  --view-config View current configuration.")
    print("  --view-state  View completed steps.")
    print("  --clear-state Clear all progress state.")


# Define ALL step functions here (boot_verbosity, core_install, etc.)
# For brevity, only a few are fully fleshed out with the new sudo handling.
# You need to apply the run_elevated_command pattern to ALL functions
# that perform privileged operations.

# Example for a function that was in the original script but not fully refactored above:
def apache_modtile_setup() -> None:
    log_map_server(f"{SYMBOLS['step']} Setting up Apache with mod_tile...")
    # ...
    # Replace run_sudo_command(["sed", ...]) with run_elevated_command(["sed", ...])
    # Replace run_sudo_command(["tee", ...]) with run_elevated_command(["tee", ...], cmd_input=...)
    # ...
    log_map_server(f"{SYMBOLS['info']} Apache/mod_tile setup needs full refactoring for sudo.", "info")


def nginx_setup() -> None:
    log_map_server(f"{SYMBOLS['step']} Setting up Nginx as a reverse proxy...")
    log_map_server(f"{SYMBOLS['info']} Nginx setup needs full refactoring for sudo.", "info")


def certbot_setup() -> None:
    log_map_server(f"{SYMBOLS['step']} Setting up Certbot for SSL...")
    log_map_server(f"{SYMBOLS['info']} Certbot setup needs full refactoring for sudo.", "info")


def gtfs_data_prep() -> None:
    log_map_server(f"{SYMBOLS['step']} Preparing GTFS data...")
    global GTFS_FEED_URL, PGPASSWORD, PGUSER, PGHOST, PGPORT, PGDATABASE

    # Example of sudo use for log file (if needed)
    gtfs_log_file = "/var/log/gtfs_processor_app.log"
    try:
        run_elevated_command(["touch", gtfs_log_file])
        # Attempt to chown to a non-root user if possible, e.g., PGUSER or 'nobody'
        # This depends on PGUSER existing and being appropriate.
        # For now, let's assume if root creates it, it's fine for logging if GTFS runs as root.
        # If GTFS part runs as user (ideal via uv), log should be user-writable.
        run_elevated_command(["chown", f"{getpass.getuser()}:{getpass.getgrgid(os.getgid()).gr_name}",
                              gtfs_log_file])  # Or a dedicated user
        log_map_server(f"{SYMBOLS['info']} Ensured GTFS log file exists: {gtfs_log_file}")
    except Exception as e:
        log_map_server(f"{SYMBOLS['warning']} Could not create/chown GTFS log file {gtfs_log_file}: {e}", "warning")

    os.environ["GTFS_FEED_URL"] = GTFS_FEED_URL
    os.environ["PG_OSM_PASSWORD"] = PGPASSWORD  # Be cautious with env vars for passwords
    os.environ["PG_OSM_USER"] = PGUSER
    os.environ["PG_OSM_HOST"] = PGHOST
    os.environ["PG_OSM_PORT"] = PGPORT
    os.environ["PG_OSM_DATABASE"] = PGDATABASE

    log_map_server(f"{SYMBOLS['info']} Attempting to run GTFS ETL pipeline...")
    if gtfs_utils and gtfs_main_pipeline:
        try:
            gtfs_utils.setup_logging(  # Use the one from gtfs_processor
                log_level=logging.INFO,
                log_file=gtfs_log_file,  # Log to the prepared file
                log_to_console=True  # Also show ETL logs on console
            )
            log_map_server(
                f"{SYMBOLS['rocket']} Running GTFS ETL pipeline with URL: {GTFS_FEED_URL}. Check {gtfs_log_file} for details.")
            success = gtfs_main_pipeline.run_full_gtfs_etl_pipeline()
            if success:
                log_map_server(f"{SYMBOLS['success']} GTFS ETL pipeline completed successfully.")
                # Verification commands would ideally use PGUSER without direct sudo psql
                # Requires .pgpass to be set up and PGUSER to have SELECT rights
                log_map_server(f"{SYMBOLS['info']} Verifying data import (counts from tables)...")
                # Example: run_command(["psql", "-h", PGHOST, ... -c "SELECT COUNT(*) ..."], capture_output=True)
            else:
                log_map_server(f"{SYMBOLS['error']} GTFS ETL pipeline FAILED. Check {gtfs_log_file}.", "error")
                # Do not raise here, let execute_step handle it
        except Exception as e:
            log_map_server(f"{SYMBOLS['error']} An error occurred during GTFS processing: {e}", "error")
            log_map_server(
                f"   {SYMBOLS['warning']} This is likely the Pydantic issue. `gtfs_processor` needs to run in a controlled environment (e.g., via `uv`).",
                "warning")
            # Do not raise here, let execute_step handle it
    else:
        log_map_server(
            f"{SYMBOLS['error']} `gtfs_processor` modules (utils, main_pipeline) not imported. Cannot run GTFS ETL.",
            "error")
        # This implies the initial import failed.

    # Cron job setup would also need careful handling of sudo for crontab -u <user>
    log_map_server(f"{SYMBOLS['info']} Cron job setup for GTFS needs review and full sudo refactoring.", "info")


def osm_osrm_server_setup() -> None:
    log_map_server(f"{SYMBOLS['step']} Setting up OSM data and OSRM...")
    log_map_server(
        f"{SYMBOLS['info']} OSRM setup needs full refactoring for sudo, especially Docker commands if user isn't in docker group yet.",
        "info")


def raster_tile_prep() -> None:
    log_map_server(f"{SYMBOLS['step']} Pre-rendering raster tiles...")
    log_map_server(f"{SYMBOLS['info']} Raster tile prep (render_list) needs full refactoring for sudo if required.",
                   "info")


def website_prep() -> None:
    log_map_server(f"{SYMBOLS['step']} Preparing test website...")
    log_map_server(f"{SYMBOLS['info']} Website prep needs full refactoring for sudo.", "info")


# Grouped actions
def core_conflict_removal_group() -> bool:
    return execute_step("CORE_CONFLICTS", "Remove Core Conflicts (e.g. system node)", core_conflict_removal)


def prereqs_install_group() -> bool:
    log_map_server(f"--- {SYMBOLS['info']} Starting Prerequisites Installation Group ---")
    success = True
    success = success and execute_step("BOOT_VERBOSITY", "Improve Boot Verbosity & Core Utils", boot_verbosity)
    # core_conflict_removal is now standalone or part of this group
    success = success and execute_step("CORE_INSTALL", "Install Core Packages (Python, PG, GIS, Fonts)", core_install)
    success = success and execute_step("DOCKER_INSTALL", "Install Docker Engine", docker_install)
    success = success and execute_step("NODEJS_INSTALL", "Install Node.js (LTS from NodeSource)", node_js_lts_install)
    log_map_server(f"--- {SYMBOLS['info']} Prerequisites Installation Group Finished (Success: {success}) ---")
    return success


def services_setup_group() -> bool:
    log_map_server(f"--- {SYMBOLS['info']} Starting Services Setup Group ---")
    success = True
    success = success and execute_step("UFW_SETUP", "Setup UFW Firewall", ufw_setup)
    success = success and execute_step("POSTGRES_SETUP", "Setup PostgreSQL Database & User", postgres_setup)
    success = success and execute_step("PGTILESERV_SETUP", "Setup pg_tileserv", pg_tileserv_setup)
    success = success and execute_step("CARTO_SETUP", "Setup CartoCSS Compiler & OSM Style", carto_setup)
    success = success and execute_step("RENDERD_SETUP", "Setup Renderd for Raster Tiles", renderd_setup)
    success = success and execute_step("OSM_OSRM_SERVER_SETUP", "Setup OSM Data & OSRM", osm_osrm_server_setup)
    success = success and execute_step("APACHE_SETUP", "Setup Apache for mod_tile", apache_modtile_setup)
    success = success and execute_step("NGINX_SETUP", "Setup Nginx Reverse Proxy", nginx_setup)
    success = success and execute_step("CERTBOT_SETUP", "Setup Certbot for SSL (optional)", certbot_setup)
    log_map_server(f"--- {SYMBOLS['info']} Services Setup Group Finished (Success: {success}) ---")
    return success


def data_prep_group() -> bool:
    log_map_server(f"--- {SYMBOLS['info']} Starting Data Preparation Group ---")
    success = True
    success = success and execute_step("GTFS_PREP", "Prepare GTFS Data (Download & Import)", gtfs_data_prep)
    success = success and execute_step("RASTER_PREP", "Pre-render Raster Tiles (Optional & Long Task!)",
                                       raster_tile_prep)
    success = success and execute_step("WEBSITE_PREP", "Prepare Test Website (index.html)", website_prep)
    log_map_server(f"--- {SYMBOLS['info']} Data Preparation Group Finished (Success: {success}) ---")
    return success


def systemd_reload_group() -> bool:  # Renamed to avoid conflict if there's a menu option for single step
    return execute_step("SYSTEMD_RELOAD_GROUP", "Reload Systemd Daemon (Group Action)", systemd_reload)


def main_map_server() -> None:
    """Main entry point for the map server setup script."""
    # Define globals that will be set by args
    global ADMIN_GROUP_IP, GTFS_FEED_URL, VM_IP_OR_DOMAIN, PG_TILESERV_BINARY_LOCATION, LOG_PREFIX
    global PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD

    parser = argparse.ArgumentParser(
        description="Map Server Setup Script. Automates the installation and configuration of various mapping services.",
        epilog="Example: ./install_map_server.py --full -v mymapserver.example.com",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-a", "--admin-group-ip", default=ADMIN_GROUP_IP_DEFAULT, help="Admin group IP range (CIDR).")
    parser.add_argument("-f", "--gtfs-feed-url", default=GTFS_FEED_URL_DEFAULT, help="GTFS feed URL.")
    parser.add_argument("-v", "--vm-ip-or-domain", default=VM_IP_OR_DOMAIN_DEFAULT,
                        help="VM IP or Domain Name for web server.")
    parser.add_argument("-b", "--pg-tileserv-binary-location", default=PG_TILESERV_BINARY_LOCATION_DEFAULT,
                        help="pg_tileserv binary download URL.")
    parser.add_argument("-l", "--log-prefix", default=LOG_PREFIX_DEFAULT, help="Log message prefix for console output.")
    parser.add_argument("-H", "--pghost", default=PGHOST_DEFAULT, help="PostgreSQL host.")
    parser.add_argument("-P", "--pgport", default=PGPORT_DEFAULT, help="PostgreSQL port.")
    parser.add_argument("-D", "--pgdatabase", default=PGDATABASE_DEFAULT, help="PostgreSQL database name.")
    parser.add_argument("-U", "--pguser", default=PGUSER_DEFAULT, help="PostgreSQL username.")
    parser.add_argument("-W", "--pgpassword", default=PGPASSWORD_DEFAULT,
                        help="PostgreSQL password. IMPORTANT: Change this default!")

    parser.add_argument("--full", action="store_true", help="Run full installation process (all groups in sequence).")
    parser.add_argument("--prereqs", action="store_true", help="Run prerequisites installation group only.")
    parser.add_argument("--services", action="store_true", help="Run services setup group only.")
    parser.add_argument("--data", action="store_true", help="Run data preparation group only.")
    # TODO: Implement single step execution and menu if needed
    # parser.add_argument("--step", type=str, help="Run a single specific step by its tag (e.g., DOCKER_INSTALL).")
    parser.add_argument("--view-config", action="store_true", help="View current configuration settings and exit.")
    parser.add_argument("--view-state", action="store_true",
                        help="View completed installation steps from state file and exit.")
    parser.add_argument("--clear-state", action="store_true", help="Clear all progress state from state file and exit.")

    args = parser.parse_args()

    # Set global variables from command-line arguments or defaults
    ADMIN_GROUP_IP = args.admin_group_ip
    GTFS_FEED_URL = args.gtfs_feed_url
    VM_IP_OR_DOMAIN = args.vm_ip_or_domain
    PG_TILESERV_BINARY_LOCATION = args.pg_tileserv_binary_location
    LOG_PREFIX = args.log_prefix  # This will be used by setup_logging_map_server
    PGHOST = args.pghost
    PGPORT = args.pgport
    PGDATABASE = args.pgdatabase
    PGUSER = args.pguser
    PGPASSWORD = args.pgpassword

    setup_logging_map_server()  # Setup logger with the potentially overridden LOG_PREFIX

    if PGPASSWORD == PGPASSWORD_DEFAULT:
        log_map_server(
            f"{SYMBOLS['warning']} WARNING: Using default PostgreSQL password. Please change this via -W option or by editing PGPASSWORD_DEFAULT in the script for security.",
            "warning")

    # Initial sudo check message
    if os.geteuid() != 0:
        log_map_server(
            f"{SYMBOLS['info']} Script not run as root. 'sudo' will be used for privileged operations. You may be prompted for your password.",
            "info")
    else:
        log_map_server(f"{SYMBOLS['info']} Script is running as root. Privileged operations will run directly.", "info")

    initialize_state_system()  # Initialize or check state file (version, etc.)
    setup_pgpass()  # Sets up .pgpass for the current user for PG cli tools

    if args.view_config:
        view_configuration()
        return
    if args.view_state:
        completed = view_completed_steps()
        if completed:
            log_map_server(f"{SYMBOLS['info']} Completed steps recorded in state file:")
            for s in completed: print(f"  - {s}")
        else:
            log_map_server(f"{SYMBOLS['info']} No steps marked as completed in state file.")
        return
    if args.clear_state:
        confirm_clear = input(
            f"{SYMBOLS['warning']} Are you sure you want to clear all progress state from {STATE_FILE}? (yes/NO): ").strip().lower()
        if confirm_clear == "yes":
            clear_state_file()
        else:
            log_map_server(f"{SYMBOLS['info']} State clearing cancelled.", "info")
        return

    # --- Execution Logic ---
    overall_success = True
    action_taken = False

    if args.full:
        action_taken = True
        log_map_server(f"{SYMBOLS['rocket']}====== Starting Full Installation Process ======")
        overall_success = overall_success and execute_step("CORE_CONFLICTS_MAIN", "Remove Core Conflicts",
                                                           core_conflict_removal)
        if overall_success: overall_success = overall_success and prereqs_install_group()
        if overall_success: overall_success = overall_success and services_setup_group()
        if overall_success: overall_success = overall_success and systemd_reload_group()  # Reload after service definitions
        if overall_success: overall_success = overall_success and data_prep_group()

        if overall_success:
            log_map_server(f"{SYMBOLS['success']}====== Full Installation Process Completed Successfully ======")
        else:
            log_map_server(f"{SYMBOLS['critical']}====== Full Installation Process Encountered Errors ======",
                           "critical")
    elif args.prereqs:
        action_taken = True
        log_map_server(f"{SYMBOLS['rocket']}====== Running Prerequisites Installation Group Only ======")
        overall_success = prereqs_install_group()
    elif args.services:
        action_taken = True
        log_map_server(f"{SYMBOLS['rocket']}====== Running Services Setup Group Only ======")
        overall_success = services_setup_group()
        if overall_success: overall_success = overall_success and systemd_reload_group()  # Good to reload after services
    elif args.data:
        action_taken = True
        log_map_server(f"{SYMBOLS['rocket']}====== Running Data Preparation Group Only ======")
        overall_success = data_prep_group()
    # Add elif for args.step if implemented

    if not action_taken:
        log_map_server(f"{SYMBOLS['info']} No installation action specified (e.g., --full, --prereqs). Showing help.",
                       "info")
        parser.print_help()
        # Alternatively, call show_menu() if interactive mode is desired as default
        # show_menu()
        sys.exit(0)

    if not overall_success:
        log_map_server(f"{SYMBOLS['critical']}One or more steps failed during the process.", "critical")
        sys.exit(1)
    else:
        log_map_server(f"{SYMBOLS['sparkles']} All requested operations completed successfully.", "info")


def command_exists(command: str) -> bool:
    """Check if a command exists in PATH using shutil.which()."""
    return shutil.which(command) is not None


def execute_step(step_tag: str, step_description: str, step_function: Callable[[], None]) -> bool:
    """
    Execute a single step with state tracking.
    Calls the step_function which should contain the actual logic for the step.
    The step_function itself should handle its own exceptions if it wants to log
    specific details before this wrapper catches a general Exception.
    """
    run_this_step = True
    if is_step_completed(step_tag):  # Assumes is_step_completed is defined
        log_map_server(f"{SYMBOLS['info']} Step '{step_description}' ({step_tag}) is already marked as completed.")
        try:
            user_input = input(f"   {SYMBOLS['info']} Do you want to re-run it anyway? (y/N): ").strip().lower()
        except EOFError:  # Handle non-interactive environments
            user_input = 'n'
            log_map_server(f"{SYMBOLS['warning']} No user input (EOF), defaulting to skip re-run.", "warning")

        if user_input != 'y':
            log_map_server(f"{SYMBOLS['info']} Skipping already completed step: {step_tag} - {step_description}")
            run_this_step = False

    if run_this_step:
        log_map_server(f"--- {SYMBOLS['step']} Executing step: {step_description} ({step_tag}) ---")
        try:
            step_function()  # Call the specific function for this step
            mark_step_completed(step_tag)  # Assumes mark_step_completed is defined
            log_map_server(f"--- {SYMBOLS['success']} Successfully completed step: {step_description} ({step_tag}) ---")
            return True
        except subprocess.CalledProcessError as e:
            # Error already logged by run_command or run_elevated_command if they raised it
            log_map_server(f"{SYMBOLS['error']} Step FAILED (Command Execution Error): {step_description} ({step_tag})",
                           "error")
            # No need to log e.cmd, e.stdout, e.stderr again if run_command did it.
            return False
        except Exception as e:
            log_map_server(f"{SYMBOLS['error']} Step FAILED (Unexpected Error): {step_description} ({step_tag})",
                           "error")
            log_map_server(f"   Error details: {str(e)}", "error")
            # For debugging, you might want to uncomment the next two lines:
            # import traceback
            # log_map_server(traceback.format_exc(), "error")
            return False

    return True  # Returns True if step was skipped (not a failure), or if it ran and succeeded.


def renderd_setup() -> None:
    """Set up renderd for raster tiles."""
    log_map_server(f"{SYMBOLS['step']} Setting up renderd for raster tiles...")
    global VM_IP_OR_DOMAIN  # Assuming this is a global or passed in

    # Get number of CPU cores for num_threads
    try:
        num_cores = os.cpu_count()
        if num_cores is None:
            num_cores = 2  # Default to 2 if os.cpu_count() returns None
            log_map_server(
                f"{SYMBOLS['warning']} Could not determine CPU core count, defaulting to {num_cores} for renderd threads.",
                "warning")
    except Exception as e:
        num_cores = 2
        log_map_server(
            f"{SYMBOLS['warning']} Error getting CPU core count ({e}), defaulting to {num_cores} for renderd threads.",
            "warning")

    renderd_conf_path = "/etc/renderd.conf"
    log_map_server(f"{SYMBOLS['gear']} Creating {renderd_conf_path}...")
    # It's safer to check if mapnik-config is available and use it.
    # mapnik_plugins_dir_cmd = ["mapnik-config", "--input-plugins-version"]
    # For simplicity, assuming a common path structure for plugins_dir.
    # On Debian, mapnik-config --input-plugins often points to something like /usr/lib/mapnik/3.1/input/
    # A more robust way would be to run `mapnik-config --input-plugins` and parse.
    # For now, using a common pattern.
    mapnik_plugins_dir = "/usr/lib/mapnik/$(mapnik-config --input-plugins-version)/input/"  # This will be literally written, systemd might not expand it.
    # Let's try to get the actual path:
    try:
        mapnik_config_ip_ver_res = run_command(["mapnik-config", "--input-plugins-version"], capture_output=True,
                                               check=True)
        mapnik_ip_ver = mapnik_config_ip_ver_res.stdout.strip()
        mapnik_plugins_dir_resolved = f"/usr/lib/mapnik/{mapnik_ip_ver}/input/"
        log_map_server(
            f"{SYMBOLS['info']} Determined Mapnik plugins directory version: {mapnik_ip_ver} -> {mapnik_plugins_dir_resolved}")
    except Exception as e:
        mapnik_plugins_dir_resolved = "/usr/lib/mapnik/3.0/input/"  # Fallback
        log_map_server(
            f"{SYMBOLS['warning']} Could not determine Mapnik plugins version via mapnik-config ({e}). Using fallback: {mapnik_plugins_dir_resolved}",
            "warning")

    renderd_conf_content = f"""[renderd]
num_threads={num_cores * 2}
tile_dir=/var/lib/mod_tile
stats_file=/var/run/renderd/renderd.stats
font_dir_recurse=1

[mapnik]
plugins_dir={mapnik_plugins_dir_resolved}
font_dir=/usr/share/fonts/
font_dir_recurse=1

[default]
URI=/hot/
XML=/usr/local/share/maps/style/openstreetmap-carto/mapnik.xml
HOST={VM_IP_OR_DOMAIN if VM_IP_OR_DOMAIN != VM_IP_OR_DOMAIN_DEFAULT else "localhost"}
TILESIZE=256
#MAXZOOM=20 # Usually defined in the style XML itself
"""  # Used VM_IP_OR_DOMAIN for HOST, or localhost if default
    try:
        run_elevated_command(["tee", renderd_conf_path], cmd_input=renderd_conf_content)
        log_map_server(f"{SYMBOLS['success']} Created/Updated {renderd_conf_path}")
    except Exception as e:
        log_map_server(f"{SYMBOLS['error']} Failed to write {renderd_conf_path}: {e}", "error")
        raise

    renderd_service_path = "/etc/systemd/system/renderd.service"
    log_map_server(f"{SYMBOLS['gear']} Creating {renderd_service_path}...")
    renderd_service_content = f"""[Unit]
Description=Map tile rendering daemon (renderd)
Documentation=man:renderd(8)
After=network.target auditd.service postgresql.service

[Service]
User=www-data
Group=www-data
RuntimeDirectory=renderd
RuntimeDirectoryMode=0755
# The -f flag keeps renderd in the foreground, which is standard for systemd services.
ExecStart=/usr/bin/renderd -f -c {renderd_conf_path}
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=renderd
PrivateTmp=true
ProtectSystem=full
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
"""
    try:
        run_elevated_command(["tee", renderd_service_path], cmd_input=renderd_service_content)
        log_map_server(f"{SYMBOLS['success']} Created/Updated {renderd_service_path}")
    except Exception as e:
        log_map_server(f"{SYMBOLS['error']} Failed to write {renderd_service_path}: {e}", "error")
        raise

    log_map_server(f"{SYMBOLS['gear']} Creating necessary directories and setting permissions for renderd...")
    run_elevated_command(["mkdir", "-p", "/var/lib/mod_tile"])
    run_elevated_command(
        ["mkdir", "-p", "/var/run/renderd"])  # systemd RuntimeDirectory should handle this, but defensive
    run_elevated_command(["chown", "-R", "www-data:www-data", "/var/lib/mod_tile"])
    run_elevated_command(["chown", "-R", "www-data:www-data", "/var/run/renderd"])

    systemd_reload()  # Assumes this function is defined
    log_map_server(f"{SYMBOLS['gear']} Enabling and restarting renderd service...")
    run_elevated_command(["systemctl", "enable", "renderd"])
    run_elevated_command(["systemctl", "restart", "renderd"])
    log_map_server(f"{SYMBOLS['info']} renderd service status:")
    run_elevated_command(["systemctl", "status", "renderd", "--no-pager", "-l"])
    log_map_server(f"{SYMBOLS['success']} Renderd setup complete.")


if __name__ == "__main__":
    try:
        main_map_server()
    except KeyboardInterrupt:
        # Ensure logger is available even if main_map_server didn't fully run setup_logging_map_server
        # This basicConfig ensures *something* handles the log message.
        logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
        logger.warning(f"\n{SYMBOLS['warning']} Installation process interrupted by user (Ctrl+C). Exiting.")
        sys.exit(130)
    except Exception as e:
        logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
        logger.critical(f"{SYMBOLS['critical']} A critical unhandled error occurred at the top level: {e}")
        import traceback

        logger.error(traceback.format_exc())
        sys.exit(1)
