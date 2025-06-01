# setup/config.py
# -*- coding: utf-8 -*-
"""
Centralized static constants and definitions for the map server setup.

This module defines truly static values for the setup scripts, such as
default package lists for apt installation, logging symbols, state file
configurations, and fixed project paths.

Mutable runtime configuration (like database hosts, IP addresses, specific URLs)
is now handled by 'setup/config_models.py' and 'setup/config_loader.py'.
"""

from pathlib import Path
# Removed 'from os import environ' as we are no longer setting environment variables here.

# --- Static Project Definitions ---
# Represents the version of the setup script logic (used in comments, state file).
SCRIPT_VERSION: str = "1.4" # Or a new version number reflecting these changes

# Define the root directory of the 'osm' project.
# This assumes config.py is in setup/
OSM_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


# --- State File Configuration (Static Paths) ---
STATE_FILE_DIR: str = "/var/lib/map-server-setup-script"
STATE_FILE_PATH: Path = Path(STATE_FILE_DIR) / "progress_state.txt"


# --- Symbols for Logging (Static) ---
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
    "debug": "🐛",
}


# --- Package Lists (Static - for apt installation by core_prerequisites.py) ---
CORE_PREREQ_PACKAGES: list[str] = [
    "git", "unzip", "vim", "build-essential", "gir1.2-packagekitglib-1.0",
    "gir1.2-glib-2.0", "packagekit", "python-apt-common", "dirmngr",
    "gnupg", "apt-transport-https", "lsb-release", "ca-certificates",
    "qemu-guest-agent", "ufw", "curl", "wget", "bash", "btop", "screen",
]

PYTHON_SYSTEM_PACKAGES: list[str] = [
    "python3", "python3-pip", "python3-venv", "python3-dev",
]

POSTGRES_PACKAGES: list[str] = [
    "postgresql-17", "libpq-dev", "postgresql-common", "postgis",
    "postgresql-17-postgis-3", "postgresql-17-postgis-3-scripts",
]

FONT_PACKAGES: list[str] = [
    "fontconfig", "fonts-noto-core", "fonts-noto-cjk", "fonts-noto-ui-core",
    "fonts-noto-mono", "fonts-dejavu", "fonts-dejavu-core", "fonts-dejavu-extra",
    "fonts-unifont", "fonts-hanazono", "fonts-sil-gentium-basic", "fonts-firacode",
    "fonts-crosextra-carlito", "fonts-takao-gothic", "fonts-takao-mincho", "fonts-takao",
]

MAPPING_PACKAGES: list[str] = [
    "cmake", "libbz2-dev", "libstxxl-dev", "libstxxl1v5", "libxml2-dev",
    "libzip-dev", "libboost-all-dev", "lua5.4", "liblua5.4-dev", "libtbb-dev",
    "libluabind-dev", "pkg-config", "apache2", "libapache2-mod-tile", "renderd",
    "mapnik-utils", "python3-mapnik", "libmapnik-dev", "xmlstarlet", "nginx",
    "osm2pgsql", "gdal-bin", "osmium-tool", "osmcoastline",
]

# --- REMOVED Mutable Configuration Variables and their _DEFAULT counterparts ---
# ADMIN_GROUP_IP_DEFAULT, GTFS_FEED_URL_DEFAULT, etc. are now in config_models.py
# Mutable ADMIN_GROUP_IP, GTFS_FEED_URL, etc. are now accessed via the APP_CONFIG object
# loaded from config_models.py and config_loader.py.

# --- REMOVED Environment Variable Settings at end of file ---
# environ["PGHOST"] = PGHOST etc. are no longer set here.
# Database connection parameters will be sourced from the APP_CONFIG.pg object.
# External tools needing environment variables (like psql CLI if used directly by user)
# would rely on a .pgpass file (created by common.pgpass_utils) or manual ENV setup.