"""
Apache Plugin for OpenJourney Server

This plugin provides Apache HTTP server with mod_tile for serving map tiles.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from installer_app.utils.plugin_interface import InstallerPlugin

logger = logging.getLogger(__name__)


class ApachePlugin(InstallerPlugin):
    """Plugin for Apache HTTP server with mod_tile support."""

    def __init__(self):
        self.plugin_dir = Path(__file__).parent
        self.kubernetes_dir = self.plugin_dir / "kubernetes"

    @property
    def name(self) -> str:
        """Return the plugin name."""
        return "Apache"

    def get_database_requirements(self) -> Dict[str, Any]:
        """Return database requirements for Apache."""
        return {
            "requires_postgres": False,  # Apache doesn't directly access database
            "requires_extensions": [],
            "requires_schemas": [],
            "requires_tables": [],
        }

    def post_config_load(self, config: dict) -> dict:
        """Ensure Apache configuration exists with defaults."""
        if "apache" not in config:
            config["apache"] = {}

        # Set default configuration values
        apache_config = config["apache"]
        apache_config.setdefault("enabled", True)
        apache_config.setdefault("listen_port", 8080)
        apache_config.setdefault("server_name", "localhost")
        apache_config.setdefault("document_root", "/var/www/html")
        apache_config.setdefault("mod_tile_enabled", True)
        apache_config.setdefault("tile_dir", "/var/cache/renderd/tiles")
        apache_config.setdefault(
            "renderd_socket", "/var/run/renderd/renderd.sock"
        )
        apache_config.setdefault("max_zoom", 18)
        apache_config.setdefault("min_zoom", 0)
        apache_config.setdefault("cors_enabled", True)

        # Tile server configuration
        apache_config.setdefault(
            "tile_server",
            {
                "uri": "/osm_tiles/",
                "xml": "/home/renderer/src/openstreetmap-carto/mapnik.xml",
                "host": "tile.openstreetmap.org",
                "htcp_host": "proxy.openstreetmap.org",
            },
        )

        logger.info(
            f"Apache plugin configured on port: {apache_config['listen_port']}"
        )
        return config

    def pre_apply_k8s(self, manifests: dict) -> dict:
        """Add Apache Kubernetes manifests to the deployment."""
        if not self.kubernetes_dir.exists():
            logger.warning(
                f"Apache kubernetes directory not found: {self.kubernetes_dir}"
            )
            return manifests

        # Load all YAML files from the kubernetes directory
        for yaml_file in self.kubernetes_dir.glob("*.yaml"):
            if yaml_file.name == "kustomization.yaml":
                continue  # Skip kustomization files

            try:
                with open(yaml_file, "r") as f:
                    content = f.read()
                    manifests[f"apache_{yaml_file.stem}"] = content
                    logger.info(f"Added Apache manifest: {yaml_file.name}")
            except Exception as e:
                logger.error(
                    f"Failed to load Apache manifest {yaml_file}: {e}"
                )

        return manifests

    def on_install_complete(self):
        """Called when installation is complete."""
        logger.info("Apache plugin installation completed successfully")
        logger.info("Apache HTTP server with mod_tile is now available")
        logger.info("Tile serving endpoint: /osm_tiles/{z}/{x}/{y}.png")
        logger.info("Static content will be served from the document root")

    def on_error(self, error: Exception):
        """Called when an error occurs during installation."""
        logger.error(f"Apache plugin installation failed: {error}")
        logger.error(
            "Check Apache pod logs for more details: kubectl logs -l app=apache"
        )
        logger.error(
            "Common issues: mod_tile configuration, renderd socket permissions"
        )


def get_plugin():
    """Return the plugin instance."""
    return ApachePlugin()
