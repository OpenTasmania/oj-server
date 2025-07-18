#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenJourneyServer_OpenStreetMap Plugin for OpenJourney Server

This plugin provides OpenJourneyServer_OpenStreetMap tile rendering capabilities for the OpenJourney server.
It manages the renderd service, tile caching, and integration with the mapping stack including
Mapnik, mod_tile, and Apache for serving raster tiles.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

import sys
from pathlib import Path

# Add the installer directory to the Python path
installer_path = Path(__file__).parent.parent.parent.parent / "installer"
sys.path.insert(0, str(installer_path))

from installer_app.utils.plugin_interface import InstallerPlugin
from installer_app.utils.database_utils import (
    get_database_manager,
    DatabaseManager,
    Migration,
)


class OpenStreetMapPlugin(InstallerPlugin):
    """
    OpenJourneyServer-OpenStreetMap Plugin for OpenJourney Server.

    This plugin handles the installation and configuration of OpenJourneyServer-OpenStreetMap tile rendering
    capabilities, including renderd service, tile caching, and Mapnik integration.
    """

    def __init__(self):
        """Initialize the OpenJourneyServer-OpenStreetMap plugin."""
        self.logger = logging.getLogger(self.__class__.__name__)

    @property
    def name(self) -> str:
        """Return the plugin name."""
        return "OpenJourneyServer-OpenStreetMap"

    def get_database_requirements(self) -> Dict[str, Any]:
        """Return database requirements for OpenJourneyServer-OpenStreetMap processing."""
        return {
            "extensions": ["postgis", "hstore"],
            "schemas": ["osm"],
            "roles": [
                {
                    "name": "osm_reader",
                    "permissions": ["SELECT"],
                    "tables": ["osm.*"],
                },
                {
                    "name": "osm_writer",
                    "permissions": ["SELECT", "INSERT", "UPDATE", "DELETE"],
                    "tables": ["osm.*"],
                },
            ],
        }

    def get_required_tables(self) -> List[str]:
        """Return list of required tables for OpenJourneyServer-OpenStreetMap processing."""
        return [
            "osm.planet_osm_point",
            "osm.planet_osm_line",
            "osm.planet_osm_polygon",
            "osm.planet_osm_roads",
        ]

    def get_optional_tables(self) -> List[str]:
        """Return list of optional tables."""
        return [
            "osm.planet_osm_ways",
            "osm.planet_osm_rels",
            "osm.planet_osm_nodes",
        ]

    def should_create_table(
        self, table_name: str, data_context: dict
    ) -> bool:
        """Determine if a specific table should be created."""
        # Always create required tables
        if table_name in self.get_required_tables():
            return True

        # Create optional tables based on configuration
        config = data_context.get("osm_config", {})

        if table_name == "osm.planet_osm_ways":
            return bool(config.get("enable_ways_table", True))
        elif table_name == "osm.planet_osm_rels":
            return bool(config.get("enable_relations_table", True))
        elif table_name == "osm.planet_osm_nodes":
            return bool(
                config.get("enable_nodes_table", False)
            )  # Usually not needed for rendering

        return False

    def get_database_manager(self, config: dict) -> DatabaseManager:
        """Get database manager instance."""
        return get_database_manager(config)

    def create_table(self, db_manager: DatabaseManager, table_name: str):
        """Create a specific table for OpenJourneyServer-OpenStreetMap data."""
        self.logger.info(f"Creating table: {table_name}")

        if table_name == "osm.planet_osm_point":
            self._create_planet_osm_point_table(db_manager)
        elif table_name == "osm.planet_osm_line":
            self._create_planet_osm_line_table(db_manager)
        elif table_name == "osm.planet_osm_polygon":
            self._create_planet_osm_polygon_table(db_manager)
        elif table_name == "osm.planet_osm_roads":
            self._create_planet_osm_roads_table(db_manager)
        elif table_name == "osm.planet_osm_ways":
            self._create_planet_osm_ways_table(db_manager)
        elif table_name == "osm.planet_osm_rels":
            self._create_planet_osm_rels_table(db_manager)
        elif table_name == "osm.planet_osm_nodes":
            self._create_planet_osm_nodes_table(db_manager)
        else:
            self.logger.warning(f"Unknown table: {table_name}")

    def _create_planet_osm_point_table(self, db_manager: DatabaseManager):
        """Create the planet_osm_point table for point features."""
        sql = """
        CREATE TABLE IF NOT EXISTS osm.planet_osm_point (
            osm_id BIGINT,
            access TEXT,
            addr_housename TEXT,
            addr_housenumber TEXT,
            addr_interpolation TEXT,
            admin_level TEXT,
            aerialway TEXT,
            aeroway TEXT,
            amenity TEXT,
            area TEXT,
            barrier TEXT,
            bicycle TEXT,
            brand TEXT,
            bridge TEXT,
            boundary TEXT,
            building TEXT,
            capital TEXT,
            construction TEXT,
            covered TEXT,
            culvert TEXT,
            cutting TEXT,
            denomination TEXT,
            disused TEXT,
            embankment TEXT,
            foot TEXT,
            generator_source TEXT,
            harbour TEXT,
            highway TEXT,
            historic TEXT,
            horse TEXT,
            intermittent TEXT,
            junction TEXT,
            landuse TEXT,
            layer INTEGER,
            leisure TEXT,
            lock TEXT,
            man_made TEXT,
            military TEXT,
            motorcar TEXT,
            name TEXT,
            natural TEXT,
            office TEXT,
            oneway TEXT,
            operator TEXT,
            place TEXT,
            population TEXT,
            power TEXT,
            power_source TEXT,
            public_transport TEXT,
            railway TEXT,
            ref TEXT,
            religion TEXT,
            route TEXT,
            service TEXT,
            shop TEXT,
            sport TEXT,
            surface TEXT,
            toll TEXT,
            tourism TEXT,
            tower_type TEXT,
            tracktype TEXT,
            tunnel TEXT,
            water TEXT,
            waterway TEXT,
            wetland TEXT,
            width TEXT,
            wood TEXT,
            z_order INTEGER,
            way_area REAL,
            tags HSTORE,
            way GEOMETRY(POINT, 3857)
        );
        
        CREATE INDEX IF NOT EXISTS planet_osm_point_way_idx ON osm.planet_osm_point USING GIST (way);
        CREATE INDEX IF NOT EXISTS planet_osm_point_osm_id_idx ON osm.planet_osm_point (osm_id);
        """
        db_manager.execute_sql(sql)

    def _create_planet_osm_line_table(self, db_manager: DatabaseManager):
        """Create the planet_osm_line table for linear features."""
        sql = """
        CREATE TABLE IF NOT EXISTS osm.planet_osm_line (
            osm_id BIGINT,
            access TEXT,
            addr_housename TEXT,
            addr_housenumber TEXT,
            addr_interpolation TEXT,
            admin_level TEXT,
            aerialway TEXT,
            aeroway TEXT,
            amenity TEXT,
            area TEXT,
            barrier TEXT,
            bicycle TEXT,
            brand TEXT,
            bridge TEXT,
            boundary TEXT,
            building TEXT,
            construction TEXT,
            covered TEXT,
            culvert TEXT,
            cutting TEXT,
            denomination TEXT,
            disused TEXT,
            embankment TEXT,
            foot TEXT,
            generator_source TEXT,
            harbour TEXT,
            highway TEXT,
            historic TEXT,
            horse TEXT,
            intermittent TEXT,
            junction TEXT,
            landuse TEXT,
            layer INTEGER,
            leisure TEXT,
            lock TEXT,
            man_made TEXT,
            military TEXT,
            motorcar TEXT,
            name TEXT,
            natural TEXT,
            office TEXT,
            oneway TEXT,
            operator TEXT,
            place TEXT,
            population TEXT,
            power TEXT,
            power_source TEXT,
            public_transport TEXT,
            railway TEXT,
            ref TEXT,
            religion TEXT,
            route TEXT,
            service TEXT,
            shop TEXT,
            sport TEXT,
            surface TEXT,
            toll TEXT,
            tourism TEXT,
            tower_type TEXT,
            tracktype TEXT,
            tunnel TEXT,
            water TEXT,
            waterway TEXT,
            wetland TEXT,
            width TEXT,
            wood TEXT,
            z_order INTEGER,
            way_area REAL,
            tags HSTORE,
            way GEOMETRY(LINESTRING, 3857)
        );
        
        CREATE INDEX IF NOT EXISTS planet_osm_line_way_idx ON osm.planet_osm_line USING GIST (way);
        CREATE INDEX IF NOT EXISTS planet_osm_line_osm_id_idx ON osm.planet_osm_line (osm_id);
        """
        db_manager.execute_sql(sql)

    def _create_planet_osm_polygon_table(self, db_manager: DatabaseManager):
        """Create the planet_osm_polygon table for polygon features."""
        sql = """
        CREATE TABLE IF NOT EXISTS osm.planet_osm_polygon (
            osm_id BIGINT,
            access TEXT,
            addr_housename TEXT,
            addr_housenumber TEXT,
            addr_interpolation TEXT,
            admin_level TEXT,
            aerialway TEXT,
            aeroway TEXT,
            amenity TEXT,
            area TEXT,
            barrier TEXT,
            bicycle TEXT,
            brand TEXT,
            bridge TEXT,
            boundary TEXT,
            building TEXT,
            construction TEXT,
            covered TEXT,
            culvert TEXT,
            cutting TEXT,
            denomination TEXT,
            disused TEXT,
            embankment TEXT,
            foot TEXT,
            generator_source TEXT,
            harbour TEXT,
            highway TEXT,
            historic TEXT,
            horse TEXT,
            intermittent TEXT,
            junction TEXT,
            landuse TEXT,
            layer INTEGER,
            leisure TEXT,
            lock TEXT,
            man_made TEXT,
            military TEXT,
            motorcar TEXT,
            name TEXT,
            natural TEXT,
            office TEXT,
            oneway TEXT,
            operator TEXT,
            place TEXT,
            population TEXT,
            power TEXT,
            power_source TEXT,
            public_transport TEXT,
            railway TEXT,
            ref TEXT,
            religion TEXT,
            route TEXT,
            service TEXT,
            shop TEXT,
            sport TEXT,
            surface TEXT,
            toll TEXT,
            tourism TEXT,
            tower_type TEXT,
            tracktype TEXT,
            tunnel TEXT,
            water TEXT,
            waterway TEXT,
            wetland TEXT,
            width TEXT,
            wood TEXT,
            z_order INTEGER,
            way_area REAL,
            tags HSTORE,
            way GEOMETRY(MULTIPOLYGON, 3857)
        );
        
        CREATE INDEX IF NOT EXISTS planet_osm_polygon_way_idx ON osm.planet_osm_polygon USING GIST (way);
        CREATE INDEX IF NOT EXISTS planet_osm_polygon_osm_id_idx ON osm.planet_osm_polygon (osm_id);
        CREATE INDEX IF NOT EXISTS planet_osm_polygon_way_area_idx ON osm.planet_osm_polygon (way_area);
        """
        db_manager.execute_sql(sql)

    def _create_planet_osm_roads_table(self, db_manager: DatabaseManager):
        """Create the planet_osm_roads table for road features."""
        sql = """
        CREATE TABLE IF NOT EXISTS osm.planet_osm_roads (
            osm_id BIGINT,
            access TEXT,
            addr_housename TEXT,
            addr_housenumber TEXT,
            addr_interpolation TEXT,
            admin_level TEXT,
            aerialway TEXT,
            aeroway TEXT,
            amenity TEXT,
            area TEXT,
            barrier TEXT,
            bicycle TEXT,
            brand TEXT,
            bridge TEXT,
            boundary TEXT,
            building TEXT,
            construction TEXT,
            covered TEXT,
            culvert TEXT,
            cutting TEXT,
            denomination TEXT,
            disused TEXT,
            embankment TEXT,
            foot TEXT,
            generator_source TEXT,
            harbour TEXT,
            highway TEXT,
            historic TEXT,
            horse TEXT,
            intermittent TEXT,
            junction TEXT,
            landuse TEXT,
            layer INTEGER,
            leisure TEXT,
            lock TEXT,
            man_made TEXT,
            military TEXT,
            motorcar TEXT,
            name TEXT,
            natural TEXT,
            office TEXT,
            oneway TEXT,
            operator TEXT,
            place TEXT,
            population TEXT,
            power TEXT,
            power_source TEXT,
            public_transport TEXT,
            railway TEXT,
            ref TEXT,
            religion TEXT,
            route TEXT,
            service TEXT,
            shop TEXT,
            sport TEXT,
            surface TEXT,
            toll TEXT,
            tourism TEXT,
            tower_type TEXT,
            tracktype TEXT,
            tunnel TEXT,
            water TEXT,
            waterway TEXT,
            wetland TEXT,
            width TEXT,
            wood TEXT,
            z_order INTEGER,
            way_area REAL,
            tags HSTORE,
            way GEOMETRY(LINESTRING, 3857)
        );
        
        CREATE INDEX IF NOT EXISTS planet_osm_roads_way_idx ON osm.planet_osm_roads USING GIST (way);
        CREATE INDEX IF NOT EXISTS planet_osm_roads_osm_id_idx ON osm.planet_osm_roads (osm_id);
        """
        db_manager.execute_sql(sql)

    def _create_planet_osm_ways_table(self, db_manager: DatabaseManager):
        """Create the planet_osm_ways table for way metadata."""
        sql = """
        CREATE TABLE IF NOT EXISTS osm.planet_osm_ways (
            id BIGINT PRIMARY KEY,
            nodes BIGINT[],
            tags HSTORE
        );
        
        CREATE INDEX IF NOT EXISTS planet_osm_ways_id_idx ON osm.planet_osm_ways (id);
        """
        db_manager.execute_sql(sql)

    def _create_planet_osm_rels_table(self, db_manager: DatabaseManager):
        """Create the planet_osm_rels table for relation metadata."""
        sql = """
        CREATE TABLE IF NOT EXISTS osm.planet_osm_rels (
            id BIGINT PRIMARY KEY,
            way_off SMALLINT,
            rel_off SMALLINT,
            parts BIGINT[],
            members TEXT[],
            tags HSTORE
        );
        
        CREATE INDEX IF NOT EXISTS planet_osm_rels_id_idx ON osm.planet_osm_rels (id);
        """
        db_manager.execute_sql(sql)

    def _create_planet_osm_nodes_table(self, db_manager: DatabaseManager):
        """Create the planet_osm_nodes table for node metadata."""
        sql = """
        CREATE TABLE IF NOT EXISTS osm.planet_osm_nodes (
            id BIGINT PRIMARY KEY,
            lat INTEGER,
            lon INTEGER,
            tags HSTORE
        );
        
        CREATE INDEX IF NOT EXISTS planet_osm_nodes_id_idx ON osm.planet_osm_nodes (id);
        """
        db_manager.execute_sql(sql)

    def ensure_tables_exist(
        self, db_manager: DatabaseManager, data_context: Optional[dict] = None
    ):
        """Ensure all required tables exist."""
        if data_context is None:
            data_context = {}

        # Create schema
        db_manager.execute_sql("CREATE SCHEMA IF NOT EXISTS osm;")

        # Create required tables
        for table_name in self.get_required_tables():
            if self.should_create_table(table_name, data_context):
                self.create_table(db_manager, table_name)

        # Create optional tables
        for table_name in self.get_optional_tables():
            if self.should_create_table(table_name, data_context):
                self.create_table(db_manager, table_name)

    def analyze_osm_data_context(self, config: dict) -> dict:
        """Analyze OpenJourneyServer-OpenStreetMap configuration to determine data context."""
        osm_config = config.get("openstreetmap", {})
        renderd_config = config.get("renderd", {})

        return {
            "osm_config": osm_config,
            "renderd_config": renderd_config,
            "has_renderd": bool(renderd_config),
            "enable_ways_table": osm_config.get("enable_ways_table", True),
            "enable_relations_table": osm_config.get(
                "enable_relations_table", True
            ),
            "enable_nodes_table": osm_config.get("enable_nodes_table", False),
        }

    def get_renderd_configuration(self, config: dict) -> dict:
        """Get renderd configuration for the plugin."""
        renderd_config = config.get("renderd", {})

        # Default configuration
        default_config = {
            "num_threads_multiplier": 1,
            "tile_cache_dir": "/var/lib/mod_tile",
            "run_dir": "/var/run/renderd",
            "socket_path": "/var/run/renderd/renderd.sock",
            "mapnik_xml_stylesheet_path": "/usr/local/share/maps/style/openstreetmap-carto/mapnik.xml",
            "mapnik_plugins_dir_override": "/usr/lib/x86_64-linux-gnu/mapnik/4.0/input/",
            "uri_path_segment": "hot",
        }

        # Merge with provided configuration
        default_config.update(renderd_config)
        return default_config

    def post_config_load(self, config: dict) -> dict:
        """Hook called after configuration is loaded."""
        # Add OpenJourneyServer-OpenStreetMap specific configuration validation
        if "openstreetmap" not in config:
            config["openstreetmap"] = {
                "enable_ways_table": True,
                "enable_relations_table": True,
                "enable_nodes_table": False,
            }

        # Ensure renderd configuration exists
        if "renderd" not in config:
            config["renderd"] = self.get_renderd_configuration({})

        return config

    def pre_apply_k8s(self, manifests: dict) -> dict:
        """Hook called before Kubernetes manifests are applied."""
        # Add renderd deployment if configured
        renderd_config = manifests.get("config", {}).get("renderd", {})
        if renderd_config:
            self._add_renderd_deployment(manifests, renderd_config)

        return manifests

    def _add_renderd_deployment(self, manifests: dict, renderd_config: dict):
        """Add renderd deployment to Kubernetes manifests."""
        # This would add the renderd deployment configuration
        # Implementation depends on the specific Kubernetes setup
        self.logger.info("Adding renderd deployment to manifests")

    def pre_database_setup(self, config: dict) -> dict:
        """Hook called before database setup."""
        # Analyze OpenJourneyServer-OpenStreetMap data context
        data_context = self.analyze_osm_data_context(config)
        config["_osm_data_context"] = data_context

        return config

    def post_database_setup(self, db_connection):
        """Hook called after database is ready."""
        self.logger.info(
            "OpenJourneyServer-OpenStreetMap database setup completed"
        )

    def on_install_complete(self):
        """Hook called after installation is complete."""
        self.logger.info(
            "OpenJourneyServer-OpenStreetMap plugin installation completed successfully"
        )
        self.logger.info("You can now import OSM data using osm2pgsql")

    def on_error(self, error: Exception):
        """Hook called if an error occurs during installation."""
        self.logger.error(
            f"OpenJourneyServer-OpenStreetMap plugin installation failed: {str(error)}"
        )

    def setup_database_schema(self, config: dict):
        """Setup the database schema for OpenJourneyServer-OpenStreetMap processing."""
        db_manager = self.get_database_manager(config)
        data_context = config.get("_osm_data_context", {})
        self.ensure_tables_exist(db_manager, data_context)


class OpenStreetMapMigration001(Migration):
    """Initial OpenJourneyServer-OpenStreetMap schema migration."""

    def __init__(self):
        super().__init__(
            "001", "Initial OpenJourneyServer-OpenStreetMap schema"
        )

    def up(self, db_manager: DatabaseManager):
        """Apply the migration."""
        plugin = OpenStreetMapPlugin()
        plugin.ensure_tables_exist(db_manager)

    def down(self, db_manager: DatabaseManager):
        """Rollback the migration."""
        tables = [
            "osm.planet_osm_nodes",
            "osm.planet_osm_rels",
            "osm.planet_osm_ways",
            "osm.planet_osm_roads",
            "osm.planet_osm_polygon",
            "osm.planet_osm_line",
            "osm.planet_osm_point",
        ]

        for table in tables:
            db_manager.execute_sql(f"DROP TABLE IF EXISTS {table} CASCADE;")

        db_manager.execute_sql("DROP SCHEMA IF EXISTS osm CASCADE;")
