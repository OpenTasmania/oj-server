# setup/config.py
"""
Centralized configuration, constants, and default values for the map server setup.
"""
from os import environ
from os.path import join

# --- Default Global Variable Values ---
ADMIN_GROUP_IP_DEFAULT = "192.168.128.0/22"
GTFS_FEED_URL_DEFAULT = (
    "https://www.transport.act.gov.au/googletransit/google_transit.zip"
)
VM_IP_OR_DOMAIN_DEFAULT = (
    "example.com"  # Should be a real FQDN for Certbot to work
)
PG_TILESERV_BINARY_LOCATION_DEFAULT = (
    "https://postgisftw.s3.amazonaws.com/pg_tileserv_latest_linux.zip"
)
LOG_PREFIX_DEFAULT = "[MAP-SETUP]"  # Default log prefix if not overridden
PGHOST_DEFAULT = "localhost"
PGPORT_DEFAULT = "5432"
PGDATABASE_DEFAULT = "gis"
PGUSER_DEFAULT = "osmuser"
PGPASSWORD_DEFAULT = "yourStrongPasswordHere"  # IMPORTANT: User should change this via CLI or be warned

# --- State File Configuration ---
STATE_FILE_DIR = "/var/lib/map-server-setup-script"
STATE_FILE_PATH = join(STATE_FILE_DIR, "progress_state.txt")
SCRIPT_VERSION = "1.3.1"  # Represents the version of the setup script logic

# --- Package Lists (for apt installation) ---
CORE_PREREQ_PACKAGES = [
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
PYTHON_SYSTEM_PACKAGES = [  # System-level Python packages
    "python3",
    "python3-pip",
    "python3-venv",
    "python3-dev",
    "python3-yaml",
    "python3-pandas",
    "python3-psycopg2",
    "python3-psycopg",
    "python3-pydantic",
]
POSTGRES_PACKAGES = [
    "postgresql",
    "postgresql-contrib",
    "postgis",
    # The versioned packages ensure correct PostGIS scripts for the default PG version on Debian.
    # Adjust if targeting a different PostgreSQL version.
    "postgresql-15-postgis-3",  # For PostgreSQL 15 (Debian 12 default)
    "postgresql-15-postgis-3-scripts",
]
FONT_PACKAGES = [
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
MAPPING_PACKAGES = [
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
SYMBOLS = {
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
}

# --- Mutable Configuration Variables ---
# These are initialized with defaults and will be updated by argparse in main.py.
# Other modules will import this 'config' module and access these as 'config.VARIABLE_NAME'.
ADMIN_GROUP_IP: str = ADMIN_GROUP_IP_DEFAULT
GTFS_FEED_URL: str = GTFS_FEED_URL_DEFAULT
VM_IP_OR_DOMAIN: str = VM_IP_OR_DOMAIN_DEFAULT
PG_TILESERV_BINARY_LOCATION: str = PG_TILESERV_BINARY_LOCATION_DEFAULT
LOG_PREFIX: str = (
    LOG_PREFIX_DEFAULT  # This will be set by main.py from args for the logger format
)
PGHOST: str = PGHOST_DEFAULT
PGPORT: str = PGPORT_DEFAULT
PGDATABASE: str = PGDATABASE_DEFAULT
PGUSER: str = PGUSER_DEFAULT
PGPASSWORD: str = PGPASSWORD_DEFAULT

environ["PGHOST"] = PGHOST
environ["PGPORT"] = PGPORT
environ["PGDATABASE"] = PGDATABASE
environ["PGUSER"] = PGUSER
environ["PGPASSWORD"] = PGPASSWORD