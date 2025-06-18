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

SCRIPT_VERSION: str = "1.4"

OSM_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

STATE_FILE_DIR: str = "/var/lib/map-server-setup-script"
STATE_FILE_PATH: Path = Path(STATE_FILE_DIR) / "progress_state.txt"

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

CORE_PREREQ_PACKAGES: list[str] = [
    "git",
    "unzip",
    "vim",
    "build-essential",
    "gir1.2-packagekitglib-1.0",
    "gir1.2-glib-2.0",
    "packagekit",
    "python-apt-common",
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

PYTHON_SYSTEM_PACKAGES: list[str] = [
    "python3",
    "python3-pip",
    "python3-venv",
    "python3-dev",
]

POSTGRES_PACKAGES: list[str] = [
    "postgresql-17",
    "libpq-dev",
    "postgresql-common",
    "postgis",
    "postgresql-17-postgis-3",
    "postgresql-17-postgis-3-scripts",
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
