#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database utilities for OpenJourney Server plugins.
Provides common database operations and management functions.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, cast


class DatabaseConnection(ABC):
    """Abstract base class for database connections."""

    @abstractmethod
    def connect(self, config: Dict[str, Any]):
        """Establish database connection."""
        pass

    @abstractmethod
    def close(self):
        """Close database connection."""
        pass

    @abstractmethod
    def execute(self, query: str, params: Optional[tuple] = None):
        """Execute a query."""
        pass

    @abstractmethod
    def fetchall(
        self, query: str, params: Optional[tuple] = None
    ) -> List[tuple]:
        """Execute query and fetch all results."""
        pass

    @abstractmethod
    def fetchone(
        self, query: str, params: Optional[tuple] = None
    ) -> Optional[tuple]:
        """Execute query and fetch one result."""
        pass

    @abstractmethod
    def commit(self):
        """Commit transaction."""
        pass

    @abstractmethod
    def rollback(self):
        """Rollback transaction."""
        pass


class PostgreSQLConnection(DatabaseConnection):
    """PostgreSQL database connection implementation."""

    def __init__(self):
        self.connection = None
        self.logger = logging.getLogger(__name__)

    def connect(self, config: Dict[str, Any]):
        """Establish PostgreSQL connection."""
        try:
            import psycopg2

            db_config = config.get("database", {})
            self.connection = psycopg2.connect(
                host=db_config.get("host", "localhost"),
                port=db_config.get("port", 5432),
                database=db_config.get("database", "openjourney"),
                user=db_config.get("user", "postgres"),
                password=db_config.get("password", ""),
            )
            self.logger.info("PostgreSQL connection established")
        except ImportError as e:
            raise ImportError(
                "psycopg2 is required for PostgreSQL connections"
            ) from e
        except Exception as e:
            self.logger.error(f"Error connecting to PostgreSQL: {e}")
            raise

    def close(self):
        """Close PostgreSQL connection."""
        if self.connection:
            try:
                self.connection.close()
                self.connection = None
                self.logger.info("PostgreSQL connection closed")
            except Exception as e:
                self.logger.error(f"Error closing PostgreSQL connection: {e}")

    def execute(self, query: str, params: Optional[tuple] = None):
        """Execute a PostgreSQL query."""
        if not self.connection:
            raise RuntimeError("Database connection not established")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            self.logger.error(f"Error executing query: {e}")
            raise

    def fetchall(
        self, query: str, params: Optional[tuple] = None
    ) -> List[tuple]:
        """Execute query and fetch all results."""
        if not self.connection:
            raise RuntimeError("Database connection not established")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                result = cursor.fetchall()
                return result if result is not None else []
        except Exception as e:
            self.logger.error(f"Error fetching results: {e}")
            raise

    def fetchone(
        self, query: str, params: Optional[tuple] = None
    ) -> Optional[tuple]:
        """Execute query and fetch one result."""
        if not self.connection:
            raise RuntimeError("Database connection not established")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                result = cursor.fetchone()
                return cast(Optional[tuple], result)
        except Exception as e:
            self.logger.error(f"Error fetching result: {e}")
            raise

    def commit(self):
        """Commit transaction."""
        if self.connection:
            self.connection.commit()

    def rollback(self):
        """Rollback transaction."""
        if self.connection:
            self.connection.rollback()


class DatabaseManager:
    """Database manager for plugin operations."""

    def __init__(self, connection: DatabaseConnection):
        self.connection = connection
        self.logger = logging.getLogger(__name__)

    def schema_exists(self, schema_name: str) -> bool:
        """Check if a schema exists."""
        try:
            result = self.connection.fetchone(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.schemata 
                    WHERE schema_name = %s
                )
            """,
                (schema_name,),
            )
            return result[0] if result else False
        except Exception as e:
            self.logger.error(f"Error checking schema existence: {e}")
            return False

    def create_schema(self, schema_name: str, if_not_exists: bool = True):
        """Create a database schema."""
        try:
            if_not_exists_clause = "IF NOT EXISTS" if if_not_exists else ""
            query = f"CREATE SCHEMA {if_not_exists_clause} {schema_name}"
            self.connection.execute(query)
            self.logger.info(f"Schema '{schema_name}' created/verified")
        except Exception as e:
            self.logger.error(f"Error creating schema '{schema_name}': {e}")
            raise

    def table_exists(
        self, table_name: str, schema_name: str = "public"
    ) -> bool:
        """Check if a table exists in the specified schema."""
        try:
            result = self.connection.fetchone(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = %s AND table_name = %s
                )
            """,
                (schema_name, table_name),
            )
            return result[0] if result else False
        except Exception as e:
            self.logger.error(f"Error checking table existence: {e}")
            return False

    def get_tables(self, schema_name: str = "public") -> List[str]:
        """Get list of tables in the specified schema."""
        try:
            results = self.connection.fetchall(
                """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = %s
                ORDER BY table_name
            """,
                (schema_name,),
            )
            return [row[0] for row in results]
        except Exception as e:
            self.logger.error(f"Error getting tables: {e}")
            return []

    def index_exists(
        self, index_name: str, schema_name: str = "public"
    ) -> bool:
        """Check if an index exists."""
        try:
            result = self.connection.fetchone(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_indexes 
                    WHERE schemaname = %s AND indexname = %s
                )
            """,
                (schema_name, index_name),
            )
            return result[0] if result else False
        except Exception as e:
            self.logger.error(f"Error checking index existence: {e}")
            return False

    def function_exists(
        self, function_name: str, schema_name: str = "public"
    ) -> bool:
        """Check if a function exists."""
        try:
            result = self.connection.fetchone(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.routines 
                    WHERE routine_schema = %s AND routine_name = %s
                )
            """,
                (schema_name, function_name),
            )
            return result[0] if result else False
        except Exception as e:
            self.logger.error(f"Error checking function existence: {e}")
            return False

    def trigger_exists(
        self, trigger_name: str, table_name: str, schema_name: str = "public"
    ) -> bool:
        """Check if a trigger exists on a table."""
        try:
            result = self.connection.fetchone(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.triggers 
                    WHERE trigger_schema = %s 
                    AND trigger_name = %s 
                    AND event_object_table = %s
                )
            """,
                (schema_name, trigger_name, table_name),
            )
            return result[0] if result else False
        except Exception as e:
            self.logger.error(f"Error checking trigger existence: {e}")
            return False

    def extension_exists(self, extension_name: str) -> bool:
        """Check if a PostgreSQL extension is installed."""
        try:
            result = self.connection.fetchone(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension 
                    WHERE extname = %s
                )
            """,
                (extension_name,),
            )
            return result[0] if result else False
        except Exception as e:
            self.logger.error(f"Error checking extension existence: {e}")
            return False

    def create_extension(
        self, extension_name: str, if_not_exists: bool = True
    ):
        """Create a PostgreSQL extension."""
        try:
            if_not_exists_clause = "IF NOT EXISTS" if if_not_exists else ""
            query = (
                f"CREATE EXTENSION {if_not_exists_clause} {extension_name}"
            )
            self.connection.execute(query)
            self.logger.info(f"Extension '{extension_name}' created/verified")
        except Exception as e:
            self.logger.error(
                f"Error creating extension '{extension_name}': {e}"
            )
            raise

    def get_table_row_count(
        self, table_name: str, schema_name: str = "public"
    ) -> int:
        """Get approximate row count for a table."""
        try:
            result = self.connection.fetchone(
                """
                SELECT n_tup_ins - n_tup_del as row_count
                FROM pg_stat_user_tables 
                WHERE schemaname = %s AND relname = %s
            """,
                (schema_name, table_name),
            )
            return result[0] if result and result[0] is not None else 0
        except Exception as e:
            self.logger.error(f"Error getting row count: {e}")
            return 0


class Migration:
    """Database migration class."""

    def __init__(self, name: str, version: str, plugin_name: str):
        self.name = name
        self.version = version
        self.plugin_name = plugin_name
        self.logger = logging.getLogger(__name__)

    @abstractmethod
    def up(self, db_manager: DatabaseManager):
        """Apply the migration."""
        pass

    @abstractmethod
    def down(self, db_manager: DatabaseManager):
        """Rollback the migration."""
        pass

    def __str__(self):
        return f"{self.plugin_name}_{self.version}_{self.name}"


class MigrationManager:
    """Manages database migrations for plugins."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        self._ensure_migration_table()

    def _ensure_migration_table(self):
        """Ensure the migrations tracking table exists."""
        try:
            if not self.db_manager.table_exists(
                "plugin_migrations", "public"
            ):
                self.db_manager.connection.execute("""
                    CREATE TABLE plugin_migrations (
                        id SERIAL PRIMARY KEY,
                        plugin_name VARCHAR(255) NOT NULL,
                        migration_name VARCHAR(255) NOT NULL,
                        version VARCHAR(50) NOT NULL,
                        applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        UNIQUE(plugin_name, migration_name, version)
                    )
                """)
                self.logger.info("Created plugin_migrations table")
        except Exception as e:
            self.logger.error(f"Error creating migration table: {e}")
            raise

    def is_migration_applied(self, migration: Migration) -> bool:
        """Check if a migration has been applied."""
        try:
            result = self.db_manager.connection.fetchone(
                """
                SELECT EXISTS (
                    SELECT 1 FROM plugin_migrations 
                    WHERE plugin_name = %s 
                    AND migration_name = %s 
                    AND version = %s
                )
            """,
                (migration.plugin_name, migration.name, migration.version),
            )
            return result[0] if result else False
        except Exception as e:
            self.logger.error(f"Error checking migration status: {e}")
            return False

    def apply_migration(self, migration: Migration):
        """Apply a migration if it hasn't been applied yet."""
        if self.is_migration_applied(migration):
            self.logger.info(
                f"Migration {migration} already applied, skipping"
            )
            return

        try:
            self.logger.info(f"Applying migration: {migration}")
            migration.up(self.db_manager)

            # Record the migration as applied
            self.db_manager.connection.execute(
                """
                INSERT INTO plugin_migrations (plugin_name, migration_name, version)
                VALUES (%s, %s, %s)
            """,
                (migration.plugin_name, migration.name, migration.version),
            )

            self.logger.info(f"Migration {migration} applied successfully")
        except Exception as e:
            self.logger.error(f"Error applying migration {migration}: {e}")
            self.db_manager.connection.rollback()
            raise

    def rollback_migration(self, migration: Migration):
        """Rollback a migration if it has been applied."""
        if not self.is_migration_applied(migration):
            self.logger.info(
                f"Migration {migration} not applied, nothing to rollback"
            )
            return

        try:
            self.logger.info(f"Rolling back migration: {migration}")
            migration.down(self.db_manager)

            # Remove the migration record
            self.db_manager.connection.execute(
                """
                DELETE FROM plugin_migrations 
                WHERE plugin_name = %s 
                AND migration_name = %s 
                AND version = %s
            """,
                (migration.plugin_name, migration.name, migration.version),
            )

            self.logger.info(
                f"Migration {migration} rolled back successfully"
            )
        except Exception as e:
            self.logger.error(
                f"Error rolling back migration {migration}: {e}"
            )
            self.db_manager.connection.rollback()
            raise

    def get_applied_migrations(
        self, plugin_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get list of applied migrations."""
        try:
            if plugin_name:
                results = self.db_manager.connection.fetchall(
                    """
                    SELECT plugin_name, migration_name, version, applied_at
                    FROM plugin_migrations 
                    WHERE plugin_name = %s
                    ORDER BY applied_at
                """,
                    (plugin_name,),
                )
            else:
                results = self.db_manager.connection.fetchall("""
                    SELECT plugin_name, migration_name, version, applied_at
                    FROM plugin_migrations 
                    ORDER BY applied_at
                """)

            return [
                {
                    "plugin_name": row[0],
                    "migration_name": row[1],
                    "version": row[2],
                    "applied_at": row[3],
                }
                for row in results
            ]
        except Exception as e:
            self.logger.error(f"Error getting applied migrations: {e}")
            return []


def create_database_connection(
    db_type: str = "postgresql",
) -> DatabaseConnection:
    """Factory function to create database connections."""
    if db_type.lower() == "postgresql":
        return PostgreSQLConnection()
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


def get_database_manager(
    config: Dict[str, Any], db_type: str = "postgresql"
) -> DatabaseManager:
    """Factory function to create a database manager."""
    connection = create_database_connection(db_type)
    connection.connect(config)
    return DatabaseManager(connection)
