#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GTFS Plugin for OpenJourney Server
Implements the enhanced InstallerPlugin interface with database optimization features.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from installer_app.utils.plugin_interface import InstallerPlugin
from installer_app.utils.database_utils import (
    get_database_manager,
    DatabaseManager,
    Migration,
)


class GTFSPlugin(InstallerPlugin):
    """
    A plugin for handling GTFS data integration with database operations.

    The GTFSPlugin class is used to manage GTFS-related data within a database. It provides
    capabilities to define database requirements, manage Python dependencies, determine table
    creation based on context, and execute database operations such as creating the necessary tables.
    This plugin is designed to integrate with systems that rely on GTFS (General Transit Feed
    Specification) data and includes extended support for optional features like OpenJourney extensions.

    Attributes:
        logger: A logger instance to track plugin operations.

    Methods:
        name: Provides the unique identifier of the plugin.
        get_python_dependencies: Lists the Python package dependencies needed by this plugin.
        get_database_requirements: Describes required and optional database tables and estimated sizes.
        get_required_tables: Retrieves a list of all required table names.
        get_optional_tables: Retrieves a list of optional table names.
        should_create_table: Determines if a specific table should be created based on provided data context.
        get_database_manager: Returns the database manager instance based on configuration.
        create_table: Executes SQL commands to create a database table given its name and required schema.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._db_manager = None
        self._required_tables = set()
        self._created_tables = set()

    @property
    def name(self) -> str:
        """A unique name for the plugin."""
        return "GTFSPlugin"

    def get_python_dependencies(self) -> List[str]:
        """
        Retrieves the list of Python dependencies required for the application.

        Returns
        -------
        List[str]
            A list of strings specifying the Python dependencies with version
            specifications.
        """
        return ["gtfs-kit>10.3.0,<11.0.0"]

    def get_database_requirements(self) -> Dict[str, Any]:
        """
        Retrieves a dictionary specifying the database requirements including required tables,
        optional tables, required extensions, and an estimation of row counts for specific tables.

        Returns:
            Dict[str, Any]: A dictionary outlining the database requirements, classified as required
            tables, optional tables, required extensions, and estimated row counts for relevant tables.
        """
        return {
            "required_tables": [
                "data_sources",
                "routes",
                "stops",
                "segments",
                "temporal_data",  # Essential for GTFS calendar data
            ],
            "optional_tables": [
                "path_geometry",  # Only if shapes.txt present
                "fares",  # Only if fare_attributes.txt present
                "fare_rules",  # Only if fare_rules.txt present
                "transfers",  # Only if transfers.txt present
                "vehicle_profiles",  # OpenJourney extension
                "navigation_instructions",  # OpenJourney extension
                "cargo_data",  # OpenJourney extension
            ],
            "required_extensions": [],  # PostGIS only needed for geometry tables
            "estimated_row_count": {
                "routes": 1000,
                "stops": 5000,
                "segments": 10000,
                "temporal_data": 100,
                "path_geometry": 50000,  # Only if shapes present
            },
        }

    def get_required_tables(self) -> List[str]:
        """
        Retrieves the names of required database tables.

        This method obtains a list of table names that are necessary for the database
        to function correctly based on its requirements.

        Returns:
            List[str]: A list of table names that are required.
        """
        requirements = self.get_database_requirements()
        return list(requirements["required_tables"])

    def get_optional_tables(self) -> List[str]:
        """
        Fetches the names of optional tables specified in the database requirements.

        This method retrieves database requirements and extracts any optional tables
        defined in the requirements.

        Returns
        -------
        List[str]
            A list containing the names of optional tables. If no optional tables are
            defined, an empty list is returned.
        """
        requirements = self.get_database_requirements()
        return list(requirements.get("optional_tables", []))

    def should_create_table(
        self, table_name: str, data_context: dict
    ) -> bool:
        """
        Determines whether a database table should be created based on its name
        and the provided data context.

        Parameters:
        table_name: str
            The name of the table to evaluate for creation.
        data_context: dict
            A dictionary containing context data that indicates the presence
            or absence of data attributes required for creating certain tables.

        Returns:
        bool
            True if the table should be created; False otherwise.
        """
        # Always create required tables
        if table_name in self.get_required_tables():
            return True

        # Create optional tables only if we have data for them
        optional_table_conditions = {
            "path_geometry": data_context.get("has_shapes", False),
            "fares": data_context.get("has_fare_data", False),
            "fare_rules": data_context.get("has_fare_rules", False),
            "transfers": data_context.get("has_transfers", False),
            "vehicle_profiles": data_context.get("has_vehicle_data", False),
            "navigation_instructions": data_context.get(
                "has_navigation", False
            ),
            "cargo_data": data_context.get("has_cargo", False),
            "temporal_data": data_context.get("has_calendar", False),
        }

        return bool(optional_table_conditions.get(table_name, False))

    def get_database_manager(self, config: dict) -> DatabaseManager:
        """
        Retrieves or creates a database manager instance using the provided configuration.
        If a database manager already exists, it will return the existing one. If not, the function
        will attempt to create a new database manager. Handles exceptions during the creation process
        by logging the error and raising the exception.

        Args:
            config (dict): Configuration dictionary required to initialize the database manager.

        Returns:
            DatabaseManager: An instance of the DatabaseManager class.

        Raises:
            Exception: If an error occurs during the creation of the database manager.
        """
        if self._db_manager is None:
            try:
                self._db_manager = get_database_manager(config)
                self.logger.info("Database manager established")
            except Exception as e:
                self.logger.error(f"Error creating database manager: {e}")
                raise
        return self._db_manager

    def create_table(self, db_manager: DatabaseManager, table_name: str):
        """Create a specific table based on its name."""
        table_definitions = {
            "data_sources": """
                CREATE TABLE IF NOT EXISTS openjourney.data_sources (
                    source_id TEXT PRIMARY KEY,
                    source_name TEXT,
                    source_type TEXT,
                    source_url TEXT,
                    source_timezone TEXT,
                    source_lang TEXT,
                    source_email TEXT,
                    source_phone TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """,
            "routes": """
                CREATE TABLE IF NOT EXISTS openjourney.routes (
                    route_id TEXT PRIMARY KEY,
                    route_name TEXT,
                    agency_id TEXT,
                    agency_route_id TEXT,
                    transit_mode TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """,
            "stops": """
                CREATE TABLE IF NOT EXISTS openjourney.stops (
                    stop_id TEXT PRIMARY KEY,
                    stop_name TEXT,
                    geom GEOMETRY(POINT, 4326),
                    stop_lat REAL,
                    stop_lon REAL,
                    location_type INTEGER,
                    parent_station TEXT,
                    wheelchair_boarding INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_stops_geom ON openjourney.stops USING GIST (geom);
            """,
            "segments": """
                CREATE TABLE IF NOT EXISTS openjourney.segments (
                    segment_id TEXT PRIMARY KEY,
                    route_id TEXT REFERENCES openjourney.routes(route_id),
                    start_stop_id TEXT,
                    end_stop_id TEXT,
                    distance REAL,
                    duration INTEGER,
                    transport_mode TEXT,
                    accessibility TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_segments_route_id ON openjourney.segments (route_id);
            """,
            "path_geometry": """
                CREATE TABLE IF NOT EXISTS openjourney.path_geometry (
                    point_id SERIAL PRIMARY KEY,
                    segment_id TEXT REFERENCES openjourney.segments(segment_id),
                    geom GEOMETRY(POINT, 4326),
                    latitude REAL,
                    longitude REAL,
                    sequence INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_path_geometry_geom ON openjourney.path_geometry USING GIST (geom);
                CREATE INDEX IF NOT EXISTS idx_path_geometry_segment_id ON openjourney.path_geometry (segment_id);
            """,
            "fares": """
                CREATE TABLE IF NOT EXISTS openjourney.fares (
                    fare_id TEXT PRIMARY KEY,
                    price REAL,
                    currency_type TEXT,
                    payment_method TEXT,
                    transfers INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """,
            "fare_rules": """
                CREATE TABLE IF NOT EXISTS openjourney.fare_rules (
                    id SERIAL PRIMARY KEY,
                    fare_id TEXT REFERENCES openjourney.fares(fare_id),
                    route_id TEXT REFERENCES openjourney.routes(route_id),
                    origin_id TEXT,
                    destination_id TEXT,
                    contains_id TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_fare_rules_fare_id ON openjourney.fare_rules (fare_id);
                CREATE INDEX IF NOT EXISTS idx_fare_rules_route_id ON openjourney.fare_rules (route_id);
            """,
            "transfers": """
                CREATE TABLE IF NOT EXISTS openjourney.transfers (
                    id SERIAL PRIMARY KEY,
                    from_stop_id TEXT,
                    to_stop_id TEXT,
                    transfer_type INTEGER,
                    min_transfer_time INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """,
            "vehicle_profiles": """
                CREATE TABLE IF NOT EXISTS openjourney.vehicle_profiles (
                    profile_id TEXT PRIMARY KEY,
                    vehicle_type TEXT,
                    accessibility_json JSONB,
                    dimensions_json JSONB,
                    capacity_json JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """,
            "navigation_instructions": """
                CREATE TABLE IF NOT EXISTS openjourney.navigation_instructions (
                    instruction_id SERIAL PRIMARY KEY,
                    segment_id TEXT REFERENCES openjourney.segments(segment_id),
                    instruction TEXT,
                    distance REAL,
                    duration INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_navigation_instructions_segment_id ON openjourney.navigation_instructions (segment_id);
            """,
            "cargo_data": """
                CREATE TABLE IF NOT EXISTS openjourney.cargo_data (
                    cargo_id TEXT PRIMARY KEY,
                    cargo_type TEXT,
                    weight REAL,
                    volume REAL,
                    hazardous BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """,
            "temporal_data": """
                CREATE TABLE IF NOT EXISTS openjourney.temporal_data (
                    service_id TEXT PRIMARY KEY,
                    start_date DATE,
                    end_date DATE,
                    monday BOOLEAN DEFAULT FALSE,
                    tuesday BOOLEAN DEFAULT FALSE,
                    wednesday BOOLEAN DEFAULT FALSE,
                    thursday BOOLEAN DEFAULT FALSE,
                    friday BOOLEAN DEFAULT FALSE,
                    saturday BOOLEAN DEFAULT FALSE,
                    sunday BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_temporal_data_dates ON openjourney.temporal_data (start_date, end_date);
            """,
        }

        if table_name not in table_definitions:
            raise ValueError(f"Unknown table: {table_name}")

        try:
            db_manager.connection.execute(table_definitions[table_name])
            self._created_tables.add(table_name)
            self.logger.info(f"Created table: {table_name}")
        except Exception as e:
            self.logger.error(f"Error creating table {table_name}: {e}")
            raise

    def create_update_triggers(self, db_manager: DatabaseManager):
        """Create update triggers for tables with updated_at columns."""
        try:
            # Create the trigger function
            db_manager.connection.execute("""
                CREATE OR REPLACE FUNCTION openjourney.update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
            """)

            # Apply triggers to tables with updated_at columns
            tables_with_updated_at = [
                "data_sources",
                "routes",
                "segments",
                "fares",
                "stops",
                "vehicle_profiles",
                "cargo_data",
                "temporal_data",
            ]

            for table in tables_with_updated_at:
                if table in self._created_tables:
                    db_manager.connection.execute(f"""
                        DROP TRIGGER IF EXISTS update_{table}_updated_at ON openjourney.{table};
                        CREATE TRIGGER update_{table}_updated_at 
                        BEFORE UPDATE ON openjourney.{table} 
                        FOR EACH ROW EXECUTE FUNCTION openjourney.update_updated_at_column();
                    """)

            self.logger.info("Created update triggers")
        except Exception as e:
            self.logger.error(f"Error creating triggers: {e}")
            raise

    def ensure_tables_exist(
        self, db_manager: DatabaseManager, data_context: Optional[dict] = None
    ):
        """
        Ensures that the required and optional tables, along with necessary database extensions
        and schema, exist in the specified database. Missing tables are created if they are not
        already present. Optional tables are created conditionally based on the provided
        data context.

        Arguments:
            db_manager (DatabaseManager): The database manager instance responsible for
                executing database operations.
            data_context (Optional[dict]): An optional dictionary with context data used
                for conditional creation of optional tables.

        Raises:
            Exception: If an error occurs while ensuring the existence of tables, schema,
                or extensions.

        """
        if data_context is None:
            data_context = {}

        try:
            # Create schema first
            if not db_manager.schema_exists("openjourney"):
                db_manager.create_schema("openjourney")

            # Ensure PostGIS extension exists
            if not db_manager.extension_exists("postgis"):
                db_manager.create_extension("postgis")

            # Get existing tables
            existing_tables = set(db_manager.get_tables("openjourney"))

            # Determine which tables to create
            required_tables = set(self.get_required_tables())
            optional_tables = set(self.get_optional_tables())

            tables_to_create = required_tables - existing_tables

            # Add optional tables if conditions are met
            for table in optional_tables:
                if table not in existing_tables and self.should_create_table(
                    table, data_context
                ):
                    tables_to_create.add(table)

            # Create missing tables
            for table in tables_to_create:
                self.create_table(db_manager, table)

            # Create triggers if we created any tables
            if tables_to_create:
                self.create_update_triggers(db_manager)

            self.logger.info(
                f"Database setup complete. Created tables: {tables_to_create}"
            )

        except Exception as e:
            self.logger.error(f"Error ensuring tables exist: {e}")
            raise

    def analyze_gtfs_data_context(self, config: dict) -> dict:
        """
        Analyzes the GTFS data context based on the provided configuration.

        This method evaluates the presence of various features within a
        GTFS feed using hints provided in the given configuration. It updates
        a dictionary that reflects the availability of key feature categories
        such as shapes, fares, fare rules, transfers, and others, and finally
        returns this dictionary for further use.

        Parameters:
            config (dict): A dictionary containing GTFS configuration details,
                           which includes information about enabled features.

        Returns:
            dict: A dictionary indicating the availability of specific GTFS
                  data categories based on the provided configuration.
        """
        data_context = {
            "has_shapes": False,
            "has_fare_data": False,
            "has_fare_rules": False,
            "has_transfers": False,
            "has_vehicle_data": False,
            "has_navigation": False,
            "has_cargo": False,
            "has_calendar": False,
        }

        # This would be enhanced to actually analyze GTFS feeds
        # For now, we'll use configuration hints
        gtfs_config = config.get("gtfs", {})
        features = gtfs_config.get("features", [])

        data_context.update({
            "has_shapes": "shapes" in features,
            "has_fare_data": "fares" in features,
            "has_fare_rules": "fare_rules" in features,
            "has_transfers": "transfers" in features,
            "has_vehicle_data": "vehicle_profiles" in features,
            "has_navigation": "navigation" in features,
            "has_cargo": "cargo" in features,
            "has_calendar": "calendar" in features,
        })

        return data_context

    # InstallerPlugin interface methods
    def post_config_load(self, config: dict) -> dict:
        """
        Configures and updates the given configuration dictionary with GTFS-specific
        settings. Ensures that GTFS-related keys and values are added if they do not
        already exist. This function is primarily used after the initial loading of
        the configuration.

        Parameters:
        config: dict
            The configuration dictionary to be updated. It should contain the
            application settings and any other related configurations, if available.

        Returns:
        dict
            The updated configuration dictionary containing the GTFS-specific
            settings, if they were not already present.
        """
        self.logger.info("GTFS Plugin: Configuration loaded")

        # Add GTFS-specific configuration if not present
        if "gtfs" not in config:
            config["gtfs"] = {
                "enabled": True,
                "features": ["routes", "stops", "segments", "calendar"],
            }

        return config

    def pre_apply_k8s(self, manifests: dict) -> dict:
        """
        Prepares Kubernetes manifests for deployment.

        This function modifies the provided Kubernetes manifests by adding GTFS daemon
        manifests if they are not already present. It looks for GTFS-specific manifests
        in the `gtfs_daemon` directory located relative to the script's file directory
        and incorporates them into the manifests dictionary. It logs any additions or
        errors encountered during the process.

        Args:
            manifests (dict): A dictionary of Kubernetes manifest file names and their
                contents.

        Returns:
            dict: The updated Kubernetes manifests after adding GTFS-specific manifests.
        """
        self.logger.info("GTFS Plugin: Preparing Kubernetes manifests")

        # Add GTFS daemon manifests if not present
        gtfs_manifest_dir = Path(__file__).parent / "gtfs_daemon"
        if gtfs_manifest_dir.exists():
            # Load GTFS-specific manifests
            for manifest_file in gtfs_manifest_dir.glob("*.yaml"):
                if manifest_file.name not in manifests:
                    try:
                        with open(manifest_file, "r") as f:
                            manifests[manifest_file.name] = f.read()
                        self.logger.info(
                            f"Added GTFS manifest: {manifest_file.name}"
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Error loading manifest {manifest_file}: {e}"
                        )

        return manifests

    def pre_database_setup(self, config: dict) -> dict:
        """Hook called before database setup."""
        self.logger.info("GTFS Plugin: Preparing database setup")

        # Analyze what tables we'll need based on configuration
        data_context = self.analyze_gtfs_data_context(config)
        config["gtfs_data_context"] = data_context

        return config

    def post_database_setup(self, db_connection):
        """Hook called after database is ready."""
        self.logger.info("GTFS Plugin: Database setup complete")
        # Database tables will be created lazily when data is processed

    def on_install_complete(self):
        """Hook called after the installation is successfully completed."""
        self.logger.info("GTFS Plugin: Installation completed successfully")

        # Close database connection if open
        if self._db_manager:
            try:
                self._db_manager.connection.close()
                self._db_manager = None
            except Exception as e:
                self.logger.error(f"Error closing database connection: {e}")

    def on_error(self, error: Exception):
        """Hook called if an error occurs during installation."""
        self.logger.error(
            f"GTFS Plugin: Installation error occurred: {error}"
        )

        # Close database connection if open
        if self._db_manager:
            try:
                self._db_manager.connection.close()
                self._db_manager = None
            except Exception as e:
                self.logger.error(f"Error closing database connection: {e}")

    def setup_database_schema(self, config: dict):
        """Setup database schema based on configuration and data context."""
        try:
            db_manager = self.get_database_manager(config)
            data_context = config.get("gtfs_data_context", {})
            self.ensure_tables_exist(db_manager, data_context)
        except Exception as e:
            self.logger.error(f"Error setting up database schema: {e}")
            raise


class GTFSMigration001(Migration):
    """Initial GTFS schema migration."""

    def __init__(self):
        super().__init__("initial_schema", "001", "GTFSPlugin")

    def up(self, db_manager: DatabaseManager):
        """Apply the migration - create initial GTFS schema."""
        plugin = GTFSPlugin()

        # Create schema and required extensions
        if not db_manager.schema_exists("openjourney"):
            db_manager.create_schema("openjourney")

        if not db_manager.extension_exists("postgis"):
            db_manager.create_extension("postgis")

        # Create required tables
        data_context = {"has_calendar": True}  # Enable calendar by default
        plugin.ensure_tables_exist(db_manager, data_context)

    def down(self, db_manager: DatabaseManager):
        """Rollback the migration - remove GTFS schema."""
        # Drop tables in reverse dependency order
        tables_to_drop = [
            "path_geometry",
            "navigation_instructions",
            "fare_rules",
            "segments",
            "transfers",
            "fares",
            "temporal_data",
            "cargo_data",
            "vehicle_profiles",
            "stops",
            "routes",
            "data_sources",
        ]

        for table in tables_to_drop:
            if db_manager.table_exists(table, "openjourney"):
                db_manager.connection.execute(
                    f"DROP TABLE IF EXISTS openjourney.{table} CASCADE"
                )

        # Drop the trigger function
        db_manager.connection.execute(
            "DROP FUNCTION IF EXISTS openjourney.update_updated_at_column() CASCADE"
        )
