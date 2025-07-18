"""
Dataprocessing Plugin for OpenJourney Server

This plugin provides data processing capabilities for batch operations and data pipeline management.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from installer_app.utils.plugin_interface import InstallerPlugin

logger = logging.getLogger(__name__)


class DataprocessingPlugin(InstallerPlugin):
    """Plugin for data processing and batch operations."""

    def __init__(self):
        self.plugin_dir = Path(__file__).parent
        self.kubernetes_dir = self.plugin_dir / "kubernetes"

    @property
    def name(self) -> str:
        """Return the plugin name."""
        return "Dataprocessing"

    def get_database_requirements(self) -> Dict[str, Any]:
        """Return database requirements for data processing."""
        return {
            "requires_postgres": True,
            "requires_extensions": ["postgis"],
            "requires_schemas": ["processing"],
            "requires_tables": ["processing_jobs", "processing_logs"],
        }

    def post_config_load(self, config: dict) -> dict:
        """Ensure data processing configuration exists with defaults."""
        if "dataprocessing" not in config:
            config["dataprocessing"] = {}

        # Set default configuration values
        dataprocessing_config = config["dataprocessing"]
        dataprocessing_config.setdefault("enabled", True)
        dataprocessing_config.setdefault(
            "job_schedule", "0 2 * * *"
        )  # Daily at 2 AM
        dataprocessing_config.setdefault("max_concurrent_jobs", 3)
        dataprocessing_config.setdefault("job_timeout", "3600")  # 1 hour
        dataprocessing_config.setdefault("retry_attempts", 3)
        dataprocessing_config.setdefault("data_retention_days", 30)

        # Database connection settings
        dataprocessing_config.setdefault("db_host", "postgres-service")
        dataprocessing_config.setdefault("db_port", 5432)
        dataprocessing_config.setdefault("db_name", "openjourney")
        dataprocessing_config.setdefault("db_user", "postgres")

        # Processing pipeline configuration
        dataprocessing_config.setdefault(
            "pipelines",
            {
                "gtfs_processing": {
                    "enabled": True,
                    "schedule": "0 3 * * *",  # Daily at 3 AM
                    "input_format": "gtfs",
                    "output_format": "postgis",
                },
                "osm_processing": {
                    "enabled": True,
                    "schedule": "0 4 * * 0",  # Weekly on Sunday at 4 AM
                    "input_format": "osm_pbf",
                    "output_format": "postgis",
                },
                "route_optimization": {
                    "enabled": True,
                    "schedule": "0 5 * * *",  # Daily at 5 AM
                    "depends_on": ["gtfs_processing", "osm_processing"],
                },
            },
        )

        # Storage configuration
        dataprocessing_config.setdefault(
            "storage",
            {
                "input_path": "/data/input",
                "output_path": "/data/output",
                "temp_path": "/data/temp",
                "logs_path": "/data/logs",
                "volume_size": "10Gi",
            },
        )

        logger.info(
            f"Dataprocessing plugin configured with {len(dataprocessing_config['pipelines'])} pipelines"
        )
        return config

    def pre_apply_k8s(self, manifests: dict) -> dict:
        """Add data processing Kubernetes manifests to the deployment."""
        if not self.kubernetes_dir.exists():
            logger.warning(
                f"Dataprocessing kubernetes directory not found: {self.kubernetes_dir}"
            )
            return manifests

        # Load all YAML files from the kubernetes directory
        for yaml_file in self.kubernetes_dir.glob("*.yaml"):
            if yaml_file.name == "kustomization.yaml":
                continue  # Skip kustomization files

            try:
                with open(yaml_file, "r") as f:
                    content = f.read()
                    manifests[f"dataprocessing_{yaml_file.stem}"] = content
                    logger.info(
                        f"Added dataprocessing manifest: {yaml_file.name}"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to load dataprocessing manifest {yaml_file}: {e}"
                )

        return manifests

    def post_database_setup(self, db_connection):
        """Setup data processing database schema and tables."""
        try:
            with db_connection.cursor() as cursor:
                # Create processing schema
                cursor.execute("CREATE SCHEMA IF NOT EXISTS processing;")
                logger.info("Processing schema created")

                # Create processing jobs table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS processing.processing_jobs (
                        job_id SERIAL PRIMARY KEY,
                        job_name VARCHAR(255) NOT NULL,
                        job_type VARCHAR(100) NOT NULL,
                        status VARCHAR(50) DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        error_message TEXT,
                        input_data JSONB,
                        output_data JSONB,
                        metadata JSONB
                    );
                """)

                # Create processing logs table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS processing.processing_logs (
                        log_id SERIAL PRIMARY KEY,
                        job_id INTEGER REFERENCES processing.processing_jobs(job_id),
                        log_level VARCHAR(20) NOT NULL,
                        message TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        context JSONB
                    );
                """)

                # Create indexes for better performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_processing_jobs_status 
                    ON processing.processing_jobs(status);
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_processing_jobs_created_at 
                    ON processing.processing_jobs(created_at);
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_processing_logs_job_id 
                    ON processing.processing_logs(job_id);
                """)

                logger.info("Data processing database schema setup completed")

            db_connection.commit()

        except Exception as e:
            logger.error(
                f"Failed to setup data processing database components: {e}"
            )
            db_connection.rollback()
            raise

    def on_install_complete(self):
        """Called when installation is complete."""
        logger.info(
            "Dataprocessing plugin installation completed successfully"
        )
        logger.info(
            "Data processing jobs will run according to configured schedules"
        )
        logger.info(
            "Job monitoring available through processing.processing_jobs table"
        )
        logger.info("Logs available through processing.processing_logs table")

    def on_error(self, error: Exception):
        """Called when an error occurs during installation."""
        logger.error(f"Dataprocessing plugin installation failed: {error}")
        logger.error(
            "Check data processing job logs: kubectl logs -l app=data-processing"
        )
        logger.error(
            "Common issues: database connectivity, storage permissions, job configuration"
        )


def get_plugin():
    """Return the plugin instance."""
    return DataprocessingPlugin()
