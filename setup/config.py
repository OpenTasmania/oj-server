# setup/config.py
"""
Centralized configuration, constants, and default values for the map server setup.

This module defines default global variable values, state file configurations,
package lists for apt installation, logging symbols, and mutable configuration
variables that can be updated by other parts of the application (e.g., via
command-line arguments).
"""

from os import environ
from pathlib import Path

# --- Default Global Variable Values ---
ADMIN_GROUP_IP_DEFAULT: str = "192.168.128.0/22"
GTFS_FEED_URL_DEFAULT: str = (
    "https://www.transport.act.gov.au/googletransit/google_transit.zip"
)
# Should be a real FQDN for Certbot to work.
VM_IP_OR_DOMAIN_DEFAULT: str = "example.com"
PG_TILESERV_BINARY_LOCATION_DEFAULT: str = (
    "https://postgisftw.s3.amazonaws.com/pg_tileserv_latest_linux.zip"
)
# Default log prefix if not overridden.
LOG_PREFIX_DEFAULT: str = "[MAP-SETUP]"
PGHOST_DEFAULT: str = "127.0.0.1"
PGPORT_DEFAULT: str = "5432"
PGDATABASE_DEFAULT: str = "gis"
PGUSER_DEFAULT: str = "osmuser"
# IMPORTANT: User should change this via CLI or be warned.
PGPASSWORD_DEFAULT: str = "yourStrongPasswordHere"


# --- State File Configuration ---
STATE_FILE_DIR: str = "/var/lib/map-server-setup-script"
STATE_FILE_PATH: Path = Path(STATE_FILE_DIR) / "progress_state.txt"
# Represents the version of the setup script logic.
SCRIPT_VERSION: str = "1.3.1"

# Define the root directory of the 'osm' project for hashing.
# This assumes config.py is in osm/setup/
OSM_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


# --- Package Lists (for apt installation) ---
CORE_PREREQ_PACKAGES: list[str] = [
    "git",
    "unzip",
    "vim",
    "build-essential",
    "software-properties-common",
    "dirmngr",
    "gnupg",
    "apt-transport-https",
    "lsb-release",
    "ca-certificates",
    "qemu-guest-agent",
    "ufw",
    "curl",
    "wget",
    "bash",
    "btop",
    "screen",
]

# System-level Python packages.
PYTHON_SYSTEM_PACKAGES: list[str] = [
    "python3",
    "python3-pip",
    "python3-venv",
    "python3-dev",
    "python3-yaml",
    "python3-pandas",
    "python3-psycopg2",
    "python3-psycopg", # General purpose PostgreSQL adapter
    "python3-pydantic",
]

POSTGRES_PACKAGES: list[str] = [
    "postgresql",
    "postgresql-contrib",
    "postgis",
    # The versioned packages ensure correct PostGIS scripts for the default
    # PG version on Debian. Adjust if targeting a different PostgreSQL version.
    "postgresql-15-postgis-3",  # For PostgreSQL 15 (Debian 12 default)
    "postgresql-15-postgis-3-scripts",
]

FONT_PACKAGES: list[str] = [
    "fontconfig",
    "fonts-noto-core",
    "fonts-noto-cjk",
    "fonts-noto-ui-core",
    "fonts-noto-mono",
    "fonts-dejavu",
    "fonts-dejavu-core",
    "fonts-dejavu-extra",
    "fonts-unifont",
    "fonts-hanazono",
    "fonts-sil-gentium-basic",
    "fonts-firacode",
    "fonts-crosextra-carlito",
    "fonts-takao-gothic",
    "fonts-takao-mincho",
    "fonts-takao",
]

MAPPING_PACKAGES: list[str] = [
    "cmake",
    "libbz2-dev",
    "libstxxl-dev",
    "libstxxl1v5",
    "libxml2-dev",
    "libzip-dev",
    "libboost-all-dev",
    "lua5.4",
    "liblua5.4-dev",
    "libtbb-dev",
    "libluabind-dev",
    "pkg-config",
    "apache2",
    "libapache2-mod-tile",
    "renderd",
    "mapnik-utils",
    "python3-mapnik",
    "libmapnik-dev",
    "xmlstarlet",
    "nginx",
    "osm2pgsql",
    "gdal-bin",
    "osmium-tool",
    "osmcoastline",
]


# --- Symbols for Logging ---
SYMBOLS: dict[str, str] = {
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "step": "➡️",
    "gear": "⚙️",
    "package": "📦",
    "rocket": "🚀",
    "sparkles": "✨",
    "critical": "🔥",
    "debug": "🐛"
}


# --- Mutable Configuration Variables ---
# These are initialized with defaults and will be updated by argparse in
# main.py. Other modules will import this 'config' module and access these as
# 'config.VARIABLE_NAME'.

ADMIN_GROUP_IP: str = ADMIN_GROUP_IP_DEFAULT
GTFS_FEED_URL: str = GTFS_FEED_URL_DEFAULT
VM_IP_OR_DOMAIN: str = VM_IP_OR_DOMAIN_DEFAULT
PG_TILESERV_BINARY_LOCATION: str = PG_TILESERV_BINARY_LOCATION_DEFAULT
# This will be set by main.py from args for the logger format.
LOG_PREFIX: str = LOG_PREFIX_DEFAULT
PGHOST: str = PGHOST_DEFAULT
PGPORT: str = PGPORT_DEFAULT
PGDATABASE: str = PGDATABASE_DEFAULT
PGUSER: str = PGUSER_DEFAULT
PGPASSWORD: str = PGPASSWORD_DEFAULT

# Developer override flag for unsafe operations (e.g., using default password)
DEV_OVERRIDE_UNSAFE_PASSWORD: bool = False


# Set environment variables that might be used by external tools (e.g. psql)
# or other parts of the application that expect them.
environ["PGHOST"] = PGHOST
environ["PGPORT"] = PGPORT
environ["PGDATABASE"] = PGDATABASE
environ["PGUSER"] = PGUSER
environ["PGPASSWORD"] = PGPASSWORD
