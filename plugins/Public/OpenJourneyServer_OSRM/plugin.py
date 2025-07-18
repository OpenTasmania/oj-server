# -*- coding: utf-8 -*-
"""
OSRM Plugin for OpenJourney Server (Private)

This plugin provides OSRM (Open Source Routing Machine) routing services with
enhanced private features and proprietary routing algorithms.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from installer.installer_app.utils.plugin_interface import InstallerPlugin

logger = logging.getLogger(__name__)


class OSRMPlugin(InstallerPlugin):
    """Private plugin for OSRM routing service with enhanced features."""

    def __init__(self):
        self.plugin_dir = Path(__file__).parent
        self.kubernetes_dir = self.plugin_dir / "kubernetes"
        self.osrm_daemon_dir = self.plugin_dir / "osrm_daemon"

    @property
    def name(self) -> str:
        """Return the plugin name."""
        return "OSRM"

    def get_database_requirements(self) -> Dict[str, Any]:
        """Return database requirements for OSRM."""
        return {
            "requires_postgres": True,
            "requires_extensions": ["postgis"],
            "requires_schemas": ["routing"],
            "requires_tables": [
                "routing_profiles",
                "routing_cache",
                "routing_analytics",
            ],
        }

    def post_config_load(self, config: dict) -> dict:
        """Ensure OSRM configuration exists with defaults."""
        if "osrm" not in config:
            config["osrm"] = {}

        # Set default configuration values
        osrm_config = config["osrm"]
        osrm_config.setdefault("enabled", True)
        osrm_config.setdefault("image_tag", "osrm/osrm-backend:latest")
        osrm_config.setdefault("listen_port", 5000)
        osrm_config.setdefault("max_table_size", 8000)
        osrm_config.setdefault("max_matching_size", 5000)
        osrm_config.setdefault("max_viaroute_size", 10000)
        osrm_config.setdefault("max_trip_size", 1000)

        # Private routing features
        osrm_config.setdefault(
            "private_features",
            {
                "enhanced_algorithms": True,
                "traffic_integration": True,
                "custom_profiles": True,
                "analytics_tracking": True,
                "route_optimization": True,
                "multi_modal_routing": True,
            },
        )

        # Routing profiles configuration
        osrm_config.setdefault(
            "profiles",
            {
                "driving": {
                    "enabled": True,
                    "data_file": "/data/driving.osrm",
                    "algorithm": "CH",  # Contraction Hierarchies
                    "max_speed": 130,
                },
                "walking": {
                    "enabled": True,
                    "data_file": "/data/walking.osrm",
                    "algorithm": "MLD",  # Multi-Level Dijkstra
                    "max_speed": 6,
                },
                "cycling": {
                    "enabled": True,
                    "data_file": "/data/cycling.osrm",
                    "algorithm": "CH",
                    "max_speed": 25,
                },
                "public_transport": {
                    "enabled": True,
                    "data_file": "/data/transit.osrm",
                    "algorithm": "MLD",
                    "gtfs_integration": True,
                },
            },
        )

        # Performance and caching
        osrm_config.setdefault(
            "performance",
            {
                "threads": 4,
                "shared_memory": True,
                "cache_size": "2G",
                "mmap_memory": True,
            },
        )

        # Database connection for analytics
        osrm_config.setdefault(
            "database",
            {
                "host": "postgres-service",
                "port": 5432,
                "name": "openjourney",
                "user": "postgres",
                "analytics_enabled": True,
            },
        )

        logger.info(
            f"OSRM plugin configured with {len(osrm_config['profiles'])} routing profiles"
        )
        return config

    def pre_apply_k8s(self, manifests: dict) -> dict:
        """Add OSRM Kubernetes manifests to the deployment."""
        if not self.kubernetes_dir.exists():
            logger.warning(
                f"OSRM kubernetes directory not found: {self.kubernetes_dir}"
            )
            return manifests

        # Load all YAML files from the kubernetes directory
        for yaml_file in self.kubernetes_dir.glob("*.yaml"):
            if yaml_file.name == "kustomization.yaml":
                continue  # Skip kustomization files

            try:
                with open(yaml_file, "r") as f:
                    content = f.read()
                    manifests[f"osrm_{yaml_file.stem}"] = content
                    logger.info(f"Added OSRM manifest: {yaml_file.name}")
            except Exception as e:
                logger.error(f"Failed to load OSRM manifest {yaml_file}: {e}")

        return manifests

    def post_database_setup(self, db_connection):
        """Setup OSRM database schema and tables for analytics."""
        try:
            with db_connection.cursor() as cursor:
                # Create routing schema
                cursor.execute("CREATE SCHEMA IF NOT EXISTS routing;")
                logger.info("Routing schema created")

                # Create routing profiles table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS routing.routing_profiles (
                        profile_id SERIAL PRIMARY KEY,
                        profile_name VARCHAR(100) UNIQUE NOT NULL,
                        profile_config JSONB NOT NULL,
                        data_file_path VARCHAR(255),
                        algorithm VARCHAR(50),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT true
                    );
                """)

                # Create routing cache table for performance
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS routing.routing_cache (
                        cache_id SERIAL PRIMARY KEY,
                        route_hash VARCHAR(64) UNIQUE NOT NULL,
                        profile_name VARCHAR(100) NOT NULL,
                        start_point GEOMETRY(POINT, 4326),
                        end_point GEOMETRY(POINT, 4326),
                        route_geometry GEOMETRY(LINESTRING, 4326),
                        route_data JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        access_count INTEGER DEFAULT 1,
                        last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # Create routing analytics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS routing.routing_analytics (
                        analytics_id SERIAL PRIMARY KEY,
                        request_id UUID DEFAULT gen_random_uuid(),
                        profile_name VARCHAR(100),
                        service_type VARCHAR(50), -- route, table, match, trip, etc.
                        start_point GEOMETRY(POINT, 4326),
                        end_point GEOMETRY(POINT, 4326),
                        waypoints GEOMETRY(MULTIPOINT, 4326),
                        distance_meters FLOAT,
                        duration_seconds FLOAT,
                        processing_time_ms INTEGER,
                        cache_hit BOOLEAN DEFAULT false,
                        user_agent TEXT,
                        ip_address INET,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata JSONB
                    );
                """)

                # Create indexes for performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_routing_cache_hash 
                    ON routing.routing_cache(route_hash);
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_routing_cache_points 
                    ON routing.routing_cache USING GIST(start_point, end_point);
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_routing_analytics_timestamp 
                    ON routing.routing_analytics(timestamp);
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_routing_analytics_profile 
                    ON routing.routing_analytics(profile_name);
                """)

                logger.info("OSRM database schema setup completed")

            db_connection.commit()

        except Exception as e:
            logger.error(f"Failed to setup OSRM database components: {e}")
            db_connection.rollback()
            raise

    def on_install_complete(self):
        """Called when installation is complete."""
        logger.info("OSRM plugin installation completed successfully")
        logger.info(
            "OSRM routing service is now available with enhanced private features"
        )
        logger.info("Available endpoints:")
        logger.info(
            "  - /route/v1/{profile}/{coordinates} - Route calculation"
        )
        logger.info("  - /table/v1/{profile}/{coordinates} - Distance matrix")
        logger.info("  - /match/v1/{profile}/{coordinates} - Map matching")
        logger.info(
            "  - /trip/v1/{profile}/{coordinates} - Trip optimization"
        )
        logger.info("  - /nearest/v1/{profile}/{coordinates} - Nearest road")
        logger.info(
            "Analytics and caching enabled for performance optimization"
        )

    def on_error(self, error: Exception):
        """Called when an error occurs during installation."""
        logger.error(f"OSRM plugin installation failed: {error}")
        logger.error("Check OSRM pod logs: kubectl logs -l app=osrm")
        logger.error(
            "Common issues: data file preparation, memory allocation, profile configuration"
        )


def get_plugin():
    """Return the plugin instance."""
    return OSRMPlugin()
