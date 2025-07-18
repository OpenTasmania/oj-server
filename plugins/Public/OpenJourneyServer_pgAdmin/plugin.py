"""
pgAdmin Plugin for OpenJourney Server

This plugin provides pgAdmin web interface for PostgreSQL database management.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from installer_app.utils.plugin_interface import InstallerPlugin

logger = logging.getLogger(__name__)


class PgAdminPlugin(InstallerPlugin):
    """Plugin for pgAdmin database administration interface."""

    def __init__(self):
        self.plugin_dir = Path(__file__).parent
        self.kubernetes_dir = self.plugin_dir / "kubernetes"

    @property
    def name(self) -> str:
        """Return the plugin name."""
        return "pgAdmin"

    def get_database_requirements(self) -> Dict[str, Any]:
        """Return database requirements for pgAdmin."""
        return {
            "requires_postgres": True,
            "requires_extensions": [],
            "requires_schemas": [],
            "requires_tables": [],
        }

    def post_config_load(self, config: dict) -> dict:
        """Ensure pgAdmin configuration exists with defaults."""
        if "pgadmin" not in config:
            config["pgadmin"] = {}

        # Set default configuration values
        pgadmin_config = config["pgadmin"]
        pgadmin_config.setdefault("enabled", True)
        pgadmin_config.setdefault("default_email", "admin@openjourney.local")
        pgadmin_config.setdefault("default_password", "admin")
        pgadmin_config.setdefault("listen_port", 80)
        pgadmin_config.setdefault("server_mode", True)

        logger.info(
            f"pgAdmin plugin configured with email: {pgadmin_config['default_email']}"
        )
        return config

    def pre_apply_k8s(self, manifests: dict) -> dict:
        """Add pgAdmin Kubernetes manifests to the deployment."""
        if not self.kubernetes_dir.exists():
            logger.warning(
                f"pgAdmin kubernetes directory not found: {self.kubernetes_dir}"
            )
            return manifests

        # Load all YAML files from the kubernetes directory
        for yaml_file in self.kubernetes_dir.glob("*.yaml"):
            if yaml_file.name == "kustomization.yaml":
                continue  # Skip kustomization files

            try:
                with open(yaml_file, "r") as f:
                    content = f.read()
                    manifests[f"pgadmin_{yaml_file.stem}"] = content
                    logger.info(f"Added pgAdmin manifest: {yaml_file.name}")
            except Exception as e:
                logger.error(
                    f"Failed to load pgAdmin manifest {yaml_file}: {e}"
                )

        return manifests

    def on_install_complete(self):
        """Called when installation is complete."""
        logger.info("pgAdmin plugin installation completed successfully")
        logger.info(
            "pgAdmin will be available at the configured ingress endpoint"
        )
        logger.info(
            "Default login: admin@openjourney.local / admin (change in production)"
        )

    def on_error(self, error: Exception):
        """Called when an error occurs during installation."""
        logger.error(f"pgAdmin plugin installation failed: {error}")
        logger.error(
            "Check pgAdmin pod logs for more details: kubectl logs -l app=pgadmin"
        )


def get_plugin():
    """Return the plugin instance."""
    return PgAdminPlugin()
