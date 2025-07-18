# -*- coding: utf-8 -*-
"""
pgAgent Plugin for OpenJourney Server

This plugin provides pgAgent for PostgreSQL job scheduling and maintenance tasks.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from installer_app.utils.plugin_interface import InstallerPlugin

logger = logging.getLogger(__name__)


class PgAgentPlugin(InstallerPlugin):
    """Plugin for pgAgent database job scheduler."""

    def __init__(self):
        self.plugin_dir = Path(__file__).parent
        self.kubernetes_dir = self.plugin_dir / "kubernetes"

    @property
    def name(self) -> str:
        """Return the plugin name."""
        return "pgAgent"

    def get_database_requirements(self) -> Dict[str, Any]:
        """Return database requirements for pgAgent."""
        return {
            "requires_postgres": True,
            "requires_extensions": ["pgagent"],
            "requires_schemas": ["pgagent"],
            "requires_tables": [],
        }

    def post_config_load(self, config: dict) -> dict:
        """Ensure pgAgent configuration exists with defaults."""
        if "pgagent" not in config:
            config["pgagent"] = {}

        # Set default configuration values
        pgagent_config = config["pgagent"]
        pgagent_config.setdefault("enabled", True)
        pgagent_config.setdefault("db_host", "postgres-service")
        pgagent_config.setdefault("db_port", 5432)
        pgagent_config.setdefault("db_name", "openjourney")
        pgagent_config.setdefault(
            "poll_time", 10
        )  # seconds between job checks
        pgagent_config.setdefault("retry_on_crash", "yes")
        pgagent_config.setdefault(
            "log_level", 1
        )  # 0=DEBUG, 1=LOG, 2=WARNING, 3=ERROR

        logger.info(
            f"pgAgent plugin configured for database: {pgagent_config['db_host']}:{pgagent_config['db_port']}"
        )
        return config

    def pre_apply_k8s(self, manifests: dict) -> dict:
        """Add pgAgent Kubernetes manifests to the deployment."""
        if not self.kubernetes_dir.exists():
            logger.warning(
                f"pgAgent kubernetes directory not found: {self.kubernetes_dir}"
            )
            return manifests

        # Load all YAML files from the kubernetes directory
        for yaml_file in self.kubernetes_dir.glob("*.yaml"):
            if yaml_file.name == "kustomization.yaml":
                continue  # Skip kustomization files

            try:
                with open(yaml_file, "r") as f:
                    content = f.read()
                    manifests[f"pgagent_{yaml_file.stem}"] = content
                    logger.info(f"Added pgAgent manifest: {yaml_file.name}")
            except Exception as e:
                logger.error(
                    f"Failed to load pgAgent manifest {yaml_file}: {e}"
                )

        return manifests

    def post_database_setup(self, db_connection):
        """Setup pgAgent extension and schema after database is ready."""
        try:
            with db_connection.cursor() as cursor:
                # Create pgagent extension if it doesn't exist
                cursor.execute("CREATE EXTENSION IF NOT EXISTS pgagent;")
                logger.info("pgAgent extension created successfully")

                # Verify pgagent schema exists
                cursor.execute("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name = 'pgagent'
                """)

                if cursor.fetchone():
                    logger.info("pgAgent schema verified")
                else:
                    logger.warning(
                        "pgAgent schema not found after extension creation"
                    )

            db_connection.commit()

        except Exception as e:
            logger.error(f"Failed to setup pgAgent database components: {e}")
            db_connection.rollback()
            raise

    def on_install_complete(self):
        """Called when installation is complete."""
        logger.info("pgAgent plugin installation completed successfully")
        logger.info(
            "pgAgent will run as a scheduled job for database maintenance"
        )
        logger.info(
            "Jobs can be configured through pgAdmin or direct SQL commands"
        )

    def on_error(self, error: Exception):
        """Called when an error occurs during installation."""
        logger.error(f"pgAgent plugin installation failed: {error}")
        logger.error(
            "Check pgAgent cronjob logs: kubectl logs -l app=pgagent"
        )


def get_plugin():
    """Return the plugin instance."""
    return PgAgentPlugin()
