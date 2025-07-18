"""
pg_tileserv Plugin for OpenJourney Server

This plugin provides pg_tileserv for serving vector tiles directly from PostgreSQL/PostGIS.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from installer_app.utils.plugin_interface import InstallerPlugin

logger = logging.getLogger(__name__)


class PgTileservPlugin(InstallerPlugin):
    """Plugin for pg_tileserv vector tile server."""

    def __init__(self):
        self.plugin_dir = Path(__file__).parent
        self.kubernetes_dir = self.plugin_dir / "kubernetes"

    @property
    def name(self) -> str:
        """Return the plugin name."""
        return "pg_tileserv"

    def get_database_requirements(self) -> Dict[str, Any]:
        """Return database requirements for pg_tileserv."""
        return {
            "requires_postgres": True,
            "requires_extensions": ["postgis"],
            "requires_schemas": [],
            "requires_tables": [],
        }

    def post_config_load(self, config: dict) -> dict:
        """Ensure pg_tileserv configuration exists with defaults."""
        if "pg_tileserv" not in config:
            config["pg_tileserv"] = {}

        # Set default configuration values
        pg_tileserv_config = config["pg_tileserv"]
        pg_tileserv_config.setdefault("enabled", True)
        pg_tileserv_config.setdefault("http_port", 7800)
        pg_tileserv_config.setdefault("db_host", "postgres-service")
        pg_tileserv_config.setdefault("db_port", 5432)
        pg_tileserv_config.setdefault("db_name", "openjourney")
        pg_tileserv_config.setdefault("db_user", "postgres")
        pg_tileserv_config.setdefault("pool_size", 4)
        pg_tileserv_config.setdefault("pool_size_max", 16)
        pg_tileserv_config.setdefault("listen_address", "0.0.0.0")
        pg_tileserv_config.setdefault("cors_origins", ["*"])
        pg_tileserv_config.setdefault("default_resolution", 4096)
        pg_tileserv_config.setdefault("default_buffer", 256)
        pg_tileserv_config.setdefault("max_features_per_tile", 10000)

        # Vector tile configuration
        pg_tileserv_config.setdefault(
            "tile_config",
            {
                "cache_control": "public, max-age=3600",
                "gzip": True,
                "debug": False,
                "pretty": False,
            },
        )

        # Database connection string
        db_url = f"postgresql://{pg_tileserv_config['db_user']}@{pg_tileserv_config['db_host']}:{pg_tileserv_config['db_port']}/{pg_tileserv_config['db_name']}"
        pg_tileserv_config["database_url"] = db_url

        logger.info(
            f"pg_tileserv plugin configured on port: {pg_tileserv_config['http_port']}"
        )
        return config

    def pre_apply_k8s(self, manifests: dict) -> dict:
        """Add pg_tileserv Kubernetes manifests to the deployment."""
        if not self.kubernetes_dir.exists():
            logger.warning(
                f"pg_tileserv kubernetes directory not found: {self.kubernetes_dir}"
            )
            return manifests

        # Load all YAML files from the kubernetes directory
        for yaml_file in self.kubernetes_dir.glob("*.yaml"):
            if yaml_file.name == "kustomization.yaml":
                continue  # Skip kustomization files

            try:
                with open(yaml_file, "r") as f:
                    content = f.read()
                    manifests[f"pg_tileserv_{yaml_file.stem}"] = content
                    logger.info(
                        f"Added pg_tileserv manifest: {yaml_file.name}"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to load pg_tileserv manifest {yaml_file}: {e}"
                )

        return manifests

    def post_database_setup(self, db_connection):
        """Setup PostGIS extension after database is ready."""
        try:
            with db_connection.cursor() as cursor:
                # Ensure PostGIS extension is available
                cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
                logger.info("PostGIS extension verified for pg_tileserv")

                # Check for spatial tables that can be served as vector tiles
                cursor.execute("""
                    SELECT schemaname, tablename, attname, type 
                    FROM geometry_columns 
                    WHERE schemaname NOT IN ('information_schema', 'topology', 'tiger')
                    LIMIT 5
                """)

                spatial_tables = cursor.fetchall()
                if spatial_tables:
                    logger.info(
                        f"Found {len(spatial_tables)} spatial tables available for vector tiles"
                    )
                    for table in spatial_tables:
                        logger.info(
                            f"  - {table[0]}.{table[1]} ({table[2]}: {table[3]})"
                        )
                else:
                    logger.info(
                        "No spatial tables found yet - they will be available once data is loaded"
                    )

            db_connection.commit()

        except Exception as e:
            logger.error(
                f"Failed to setup pg_tileserv database components: {e}"
            )
            db_connection.rollback()
            raise

    def on_install_complete(self):
        """Called when installation is complete."""
        logger.info("pg_tileserv plugin installation completed successfully")
        logger.info("Vector tile server is now available")
        logger.info(
            "Vector tiles endpoint: /collections/{table_name}/items.mvt"
        )
        logger.info("Table list endpoint: /collections.json")
        logger.info("Health check endpoint: /health")

    def on_error(self, error: Exception):
        """Called when an error occurs during installation."""
        logger.error(f"pg_tileserv plugin installation failed: {error}")
        logger.error(
            "Check pg_tileserv pod logs: kubectl logs -l app=pg-tileserv"
        )
        logger.error(
            "Common issues: PostGIS extension, database connectivity, spatial table access"
        )


def get_plugin():
    """Return the plugin instance."""
    return PgTileservPlugin()
