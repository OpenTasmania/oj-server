# setup/config_models.py
# -*- coding: utf-8 -*-
"""
Pydantic models for application configuration.

This module defines the structured settings for the application,
including defaults, type annotations, and descriptions.
It utilizes Pydantic for data validation and settings management.
"""

from pathlib import Path
from typing import Dict, Union

from pydantic import (
    BaseModel,
    Field,
    FilePath,
    DirectoryPath,
    HttpUrl,
    PostgresDsn
)
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Default Static Values (can be overridden by config file/env/cli) ---
ADMIN_GROUP_IP_DEFAULT: str = "192.168.128.0/22"
GTFS_FEED_URL_DEFAULT: str = "https://www.transport.act.gov.au/googletransit/google_transit.zip"
VM_IP_OR_DOMAIN_DEFAULT: str = "example.com"
PG_TILESERV_BINARY_LOCATION_DEFAULT: str = "https://postgisftw.s3.amazonaws.com/pg_tileserv_latest_linux.zip"
LOG_PREFIX_DEFAULT: str = "[MAP-SETUP]"

PGHOST_DEFAULT: str = "127.0.0.1"
PGPORT_DEFAULT: int = 5432
PGDATABASE_DEFAULT: str = "gis"
PGUSER_DEFAULT: str = "osmuser"
PGPASSWORD_DEFAULT: str = "yourStrongPasswordHere"

CONTAINER_RUNTIME_COMMAND_DEFAULT: str = "docker"
OSRM_IMAGE_TAG_DEFAULT: str = "osrm/osrm-backend:latest"

PG_HBA_TEMPLATE_DEFAULT: str = """\
# pg_hba.conf configured by script V{script_hash}
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             postgres                                peer
local   all             all                                     peer
local   {pg_database}    {pg_user}                                scram-sha-256
host    all             all             127.0.0.1/32            scram-sha-256
host    {pg_database}    {pg_user}        127.0.0.1/32            scram-sha-256
host    {pg_database}    {pg_user}        {admin_group_ip}       scram-sha-256
host    all             all             ::1/128                 scram-sha-256
host    {pg_database}    {pg_user}        ::1/128                 scram-sha-256
"""

# Default template for postgresql.conf additions
POSTGRESQL_CONF_ADDITIONS_TEMPLATE_DEFAULT: str = """\
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


class PostgresSettings(BaseSettings):
    """PostgreSQL connection settings."""
    model_config = SettingsConfigDict(
        env_prefix='PG_',
        extra='ignore'
    )

    host: str = Field(default=PGHOST_DEFAULT, description="PostgreSQL host.")
    port: int = Field(default=PGPORT_DEFAULT, description="PostgreSQL port.")
    database: str = Field(default=PGDATABASE_DEFAULT, description="PostgreSQL database name.")
    user: str = Field(default=PGUSER_DEFAULT, description="PostgreSQL username.")
    password: str = Field(default=PGPASSWORD_DEFAULT, description="PostgreSQL password.", exclude=True)

    hba_template: str = Field(
        default=PG_HBA_TEMPLATE_DEFAULT,
        description="Template for pg_hba.conf content. Supports placeholders like {pg_database}, {pg_user}, {admin_group_ip}, {script_hash}."
    )
    postgresql_conf_additions_template: str = Field(
        default=POSTGRESQL_CONF_ADDITIONS_TEMPLATE_DEFAULT,
        description="Template for additions to postgresql.conf. Supports placeholder {script_hash}."
    )
    # Optional: field for PostgreSQL version if it needs to be configurable
    # version: str = Field(default="17", description="Major PostgreSQL version.")


class AppSettings(BaseSettings):
    """Main application settings."""
    model_config = SettingsConfigDict(extra='ignore')

    admin_group_ip: str = Field(default=ADMIN_GROUP_IP_DEFAULT, description="Admin group IP range (CIDR).")
    gtfs_feed_url: Union[HttpUrl, str] = Field(default=GTFS_FEED_URL_DEFAULT, description="URL of the GTFS feed.")
    vm_ip_or_domain: str = Field(default=VM_IP_OR_DOMAIN_DEFAULT,
                                 description="Public IP address or FQDN of this server.")
    pg_tileserv_binary_location: Union[HttpUrl, str] = Field(default=PG_TILESERV_BINARY_LOCATION_DEFAULT,
                                                             description="URL or local path for the pg_tileserv binary.")
    log_prefix: str = Field(default=LOG_PREFIX_DEFAULT,
                            description="Prefix for log messages from the main installer script.")
    dev_override_unsafe_password: bool = Field(default=False,
                                               description="DEV FLAG: Allow using default PGPASSWORD for .pgpass and suppress related warnings.")

    container_runtime_command: str = Field(default=CONTAINER_RUNTIME_COMMAND_DEFAULT,
                                           description="Command for the container runtime CLI (e.g., docker, podman).")
    osrm_image_tag: str = Field(default=OSRM_IMAGE_TAG_DEFAULT,
                                description="Docker image tag for OSRM backend (e.g., osrm/osrm-backend:latest).")

    pg: PostgresSettings = Field(default_factory=PostgresSettings)

    # Static symbols, could also be loaded from a separate static config if preferred
    symbols: Dict[str, str] = Field(default_factory=lambda: {
        "success": "✅", "error": "❌", "warning": "⚠️", "info": "ℹ️",
        "step": "➡️", "gear": "⚙️", "package": "📦", "rocket": "🚀",
        "sparkles": "✨", "critical": "🔥", "debug": "🐛",
    })