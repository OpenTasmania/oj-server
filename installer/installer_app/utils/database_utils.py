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
    """
    Abstract base class for database connection.

    This class is designed to define a common interface for interacting with
    various database systems. It enforces the implementation of key database
    operations such as connecting, executing queries, and handling transactions
    in derived classes.
    """

    @abstractmethod
    def connect(self, config: Dict[str, Any]):
        """
        Represents an abstract method to define connection implementations.

        The `connect` method is designed to be implemented by subclasses.
        It establishes a connection using the provided configuration details.

        Parameters
        ----------
        config : Dict[str, Any]
            A dictionary containing configuration details required to establish a
            connection. The exact keys and values depend on the implementation in
            the subclass.

        Raises
        ------
        NotImplementedError
            If the method is not implemented by a subclass.
        """
        pass

    @abstractmethod
    def close(self):
        """
        An abstract method to allow subclasses to implement specific behavior for closing
        operations. Subclasses must provide their own implementation of this method.

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        pass

    @abstractmethod
    def execute(self, query: str, params: Optional[tuple] = None):
        """
        Represents an abstract method to execute a database query with optional parameters.

        This method should be implemented by subclasses to perform the
        actual execution of a query against a database. It is expected
        to handle variable query parameters securely and efficiently.

        Parameters:
            query: str
                The SQL query string to be executed.
            params: Optional[tuple], optional
                A tuple of parameters to be substituted into the SQL query,
                if required. Defaults to None.

        Returns:
            None: The concrete implementation may choose to return specific
            output based on the executed query, such as query results or
            operation success status.

        Raises:
            Implementation of this method may define and handle specific
            exceptions related to database operations.
        """
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
        """
        Fetches a single row from the result of the query execution.

        This method should be implemented by a subclass to execute a given query
        against a database or data source and fetch exactly one row from the
        result set. If the query does not return any rows, the method should
        return None. This is intended for fetching specific, single results from
        queries such as fetch by unique identifier or specific criteria.

        Parameters:
            query (str): The SQL query to be executed.
            params (Optional[tuple]): Optional parameters to be substituted into the query.

        Returns:
            Optional[tuple]: A tuple representing a single row from the query result,
                or None if no rows are returned.

        Raises:
            NotImplementedError: This method must be implemented in a concrete subclass.
        """
        pass

    @abstractmethod
    def commit(self):
        """
        Defines an abstract method `commit` that must be implemented in subclasses.
        This method is meant to be overridden and provides functionality related
        to committing changes or performing commit-specific operations
        within a subclass context.

        Methods:
            commit: An abstract method that must be implemented in a derived class.

        """
        pass

    @abstractmethod
    def rollback(self):
        """
        An abstract base method that defines the rollback functionality, which must
        be implemented by subclasses. This method is intended to revert or undo
        changes or actions performed, restoring a previous state.

        This is a placeholder method and it does not include any concrete
        implementation.

        Raises:
            NotImplementedError: If the method is called on an instance and not
            implemented in a subclass.
        """
        pass


class PostgreSQLConnection(DatabaseConnection):
    """
    Defines a PostgreSQL database connection class that provides methods for
    connecting to, executing queries on, and managing transactions within a
    PostgreSQL database.

    This class is built on top of the psycopg2 library to handle PostgreSQL
    operations. It includes functionalities such as opening and closing a
    database connection, executing queries, fetching results, committing
    transactions, and rolling back changes. It also leverages logging to
    capture and report on operational events and errors.
    """

    def __init__(self):
        self.connection = None
        self.logger = logging.getLogger(__name__)

    def connect(self, config: Dict[str, Any]):
        """
        Connects to a PostgreSQL database using the provided configuration dictionary.
        The method utilizes the psycopg2 library to establish a connection and log
        the outcome. If psycopg2 is not installed, an ImportError is raised. Any other
        errors encountered during the connection process are logged and re-raised.

        Args:
            config (Dict[str, Any]): A dictionary containing the database connection
            details. The "database" key should have a nested dictionary with the
            following keys:
                - "host" (str): The database host. Default is "localhost".
                - "port" (int): The port for the database connection. Default is 5432.
                - "database" (str): The name of the database to connect to. Default is
                  "openjourney".
                - "user" (str): The username for the database connection. Default is
                  "postgres".
                - "password" (str): The password for the database connection. Default
                  is an empty string.

        Raises:
            ImportError: If psycopg2 is not installed.
            Exception: For any other errors encountered during the connection
            process.
        """
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
        """
        Closes the active PostgreSQL connection, if any.

        Ensures that the database connection is properly closed. Logs messages
        regarding the success or failure of the connection closing process.

        Raises:
            Exception: If an error occurs while closing the PostgreSQL connection.
        """
        if self.connection:
            try:
                self.connection.close()
                self.connection = None
                self.logger.info("PostgreSQL connection closed")
            except Exception as e:
                self.logger.error(f"Error closing PostgreSQL connection: {e}")

    def execute(self, query: str, params: Optional[tuple] = None):
        """
        Executes a database query with optional parameters and ensures the integrity
        of the connection by committing the transaction on success or rolling back
        on failure. Logs any errors encountered during execution.

        Args:
            query (str): The SQL query string to be executed.
            params (Optional[tuple]): A tuple of parameters to be used with the SQL
                query (default is None).

        Raises:
            RuntimeError: If the database connection has not been established.
            Exception: If an error occurs during query execution.
        """
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
        """
        Fetches all rows resulting from executing a SQL query.

        Executes the given SQL query with the provided parameters and retrieves all
        matching records. If no records are found, an empty list is returned.

        Parameters:
            query: str
                The SQL query to be executed.
            params: Optional[tuple]
                A tuple of parameters to substitute into the SQL query. This
                argument is optional and can be left empty if the query requires
                no parameters.

        Returns:
            List[tuple]
                A list of tuples where each tuple represents a row retrieved from
                the database. If no rows are found, an empty list is returned.

        Raises:
            RuntimeError
                If the database connection has not been established.
            Exception
                If an error occurs during the execution of the query or fetching
                of results.
        """
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
        """
        Fetches a single row from the database based on the provided SQL query and parameters.

        This method executes the provided SQL query using the active database connection
        and retrieves one row of the result set. If the result is empty, it will return None.

        Parameters:
        query: str
            The SQL query string to execute.
        params: Optional[tuple], optional
            A tuple containing parameters to bind to the SQL query. Defaults to None.

        Returns:
        Optional[tuple]
            A single row from the query result as a tuple, or None if no rows are returned.

        Raises:
        RuntimeError
            If the database connection is not established.
        Exception
            If an error occurs during query execution.
        """
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
        """
        Commits the current transaction to the database. This method finalizes all
        operations performed in the current transaction and makes changes
        persistent in the database.

        Raises
        ------
        Exception
            If no active database connection exists.
        """
        if self.connection:
            self.connection.commit()

    def rollback(self):
        """
        Reverts the changes made during the active transaction if a connection exists.

        The `rollback` method undoes any changes made to the database during the current
        transaction when it is called. It is particularly useful when an error occurs
        during a transaction, and the changes need to be reverted to maintain data
        consistency. This method requires an active database connection.

        Raises:
            AttributeError: If `self.connection` does not exist or is not valid.
        """
        if self.connection:
            self.connection.rollback()


class DatabaseManager:
    """
    Manage database operations including checking existence and creation of schemas, tables, indexes,
    functions, triggers, extensions, etc., primarily for PostgreSQL databases.

    The DatabaseManager class acts as an abstraction layer for performing common database operations
    to ensure the existence of database objects or retrieve metadata, using a provided
    DatabaseConnection instance for executing queries.

    Attributes:
        connection: The database connection interface used to execute SQL commands.
    """

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
        """
        Creates a new database schema or verifies its existence if it already exists.

        This method constructs and executes an SQL statement to create a database schema.
        If `if_not_exists` is set to True, it ensures the schema is only created if it does
        not already exist.

        Parameters:
            schema_name: str
                The name of the schema to be created.
            if_not_exists: bool
                A flag that determines whether the schema creation should only proceed
                if the schema does not exist. Defaults to True.

        Raises:
            Exception
                If there is an error during schema creation, it will be logged and re-raised
                for the caller to handle.
        """
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
        """
        Checks if a table exists in a given schema within the database.

        This method queries the database to determine whether a table with the given name exists
        in the specified schema. If an error occurs during the execution of the query, the method
        logs the error and returns False.

        Args:
            table_name: Name of the table to check existence.
            schema_name: Name of the schema wherein the table is expected to be located. Defaults to "public".

        Returns:
            bool: True if the table exists, False otherwise.
        """
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
        """
        Check if a specified index exists in the PostgreSQL database schema.

        This method determines whether a given index name exists within a specified
        schema of a PostgreSQL database. It queries the PostgreSQL system catalog
        to verify the existence of the index.

        Parameters:
            index_name: The name of the index to check for existence.
            schema_name: The name of the schema to look in. Defaults to "public".

        Returns:
            bool: True if the index exists, False otherwise.

        Raises:
            Exception: Logs an error in case of any failure during database query
            execution and returns False as the resultant value.
        """
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
        """
        Checks if a database function exists within a specific schema.

        Tries to determine whether a given function exists within a specified schema
        in the database. Returns a boolean indicating the existence of the function.
        Logs an error if an exception occurs while querying the database.

        Parameters:
            function_name (str): Name of the database function to check.
            schema_name (str): Name of the database schema to look for the function.
                               Defaults to "public".

        Returns:
            bool: True if the function exists, False otherwise.
        """
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
        """
        Checks if a trigger exists in the database for a specified table and schema.

        This method queries the information schema to verify whether a trigger with the
        specified name is associated with a given table and schema. It returns a boolean
        indicating the existence of the trigger in the database.

        Args:
            trigger_name (str): The name of the trigger to check.
            table_name (str): The name of the table associated with the trigger.
            schema_name (str): The name of the schema where the trigger is expected
                to exist. Defaults to "public".

        Returns:
            bool: True if the trigger exists, False otherwise.
        """
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
        """
        Checks if a PostgreSQL extension exists in the database.

        The method verifies whether a specific extension is installed in the
        PostgreSQL database by querying the `pg_extension` system catalog.

        Parameters:
        extension_name: str
            The name of the extension to check for existence.

        Returns:
        bool
            True if the extension exists, False otherwise.

        Raises:
        Exception
            An error is raised when there is any issue executing the query or
            accessing the database connection.

        """
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
        """
        Creates a database extension with the given name.

        This method attempts to create a PostgreSQL extension by executing a
        corresponding SQL statement. If the `if_not_exists` flag is set to True,
        it includes the "IF NOT EXISTS" clause to avoid errors if the extension
        already exists. Logs information about the success or failure of the
        operation.

        Parameters:
            extension_name (str): The name of the extension to create.
            if_not_exists (bool): A flag to determine whether to include the "IF
                NOT EXISTS" clause in the SQL statement. Defaults to True.

        Raises:
            Exception: If an error occurs during the creation of the extension.
        """
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
        """
        Retrieves the row count of a specified table in a given schema. This method executes a query
        to fetch the number of rows by calculating the difference between inserted tuples and deleted
        tuples in PostgreSQL's statistics system. If the query fails or there is an error, it logs the
        error message and returns 0.

        Args:
            table_name (str): Name of the table for which row count is to be retrieved.
            schema_name (str): Name of the schema where the table resides. Defaults to "public".

        Returns:
            int: The number of rows in the specified table. If an error occurs, the method
            returns 0.
        """
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
    """
    Represents a base class for defining database migrations.

    This class serves as a blueprint for creating database migration tasks that can move
    a database schema and/or data forward (`up`) or revert it to a previous state (`down`).
    It is designed to be subclassed by specific migrations, each providing its own
    implementation of the abstract methods `up` and `down`. The purpose of this class
    is to standardize migration logic and ensure consistent handling of database changes.
    """

    def __init__(self, name: str, version: str, plugin_name: str):
        self.name = name
        self.version = version
        self.plugin_name = plugin_name
        self.logger = logging.getLogger(__name__)

    @abstractmethod
    def up(self, db_manager: DatabaseManager):
        """
        An abstract method that defines a database migration step to be implemented
        by subclasses. The `up` method is intended to apply changes to the database
        schema, data, or structure using the provided `DatabaseManager`.

        Parameters:
            db_manager (DatabaseManager): The object responsible for managing database
            operations such as executing queries, creating tables, and managing transactions.

        Raises:
            NotImplementedError: Always raised unless the method is overridden by a
            concrete subclass implementation.
        """
        pass

    @abstractmethod
    def down(self, db_manager: DatabaseManager):
        """
        An abstract method to define the downward migration of a database to revert changes or rollback
        specific operations. This must be implemented in subclasses. It allows for precise control over
        destructive operations when altering the database schema.

        Parameters
        ----------
        db_manager : DatabaseManager
            An instance of the DatabaseManager class that abstracts the database operations
            required for the migration.

        Raises
        ------
        NotImplementedError
            If the method is not overridden in the subclass.
        """
        pass

    def __str__(self):
        return f"{self.plugin_name}_{self.version}_{self.name}"


class MigrationManager:
    """
    Manages migrations for plugins, ensuring proper application and tracking.

    The MigrationManager class facilitates database migrations for plugins, providing
    methods to apply, rollback, and track migrations. It ensures that migrations are
    applied in a consistent manner with safeguards against duplicate applications. It
    interacts with a 'plugin_migrations' database table to track the state of migrations.

    Attributes:
        db_manager: DatabaseManager instance used to interact with the database.
        logger: Logger instance used to log messages for tracking the migration process.

    Methods:
        is_migration_applied(migration: Migration) -> bool:
            Check if a specific migration has been applied.

        apply_migration(migration: Migration):
            Apply a migration if it hasn't already been applied.

        rollback_migration(migration: Migration):
            Rollback a migration if it has been applied.

        get_applied_migrations(plugin_name: Optional[str] = None) -> List[Dict[str, Any]]:
            Retrieve a list of applied migrations, optionally filtered by the plugin name.
    """

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        self._ensure_migration_table()

    def _ensure_migration_table(self):
        """
        Ensures that the migration table `plugin_migrations` exists in the database.
        If the table does not exist, it is created with the relevant structure. This
        method logs the creation of the table or any errors encountered during the
        process.

        Raises:
            Exception: If an error occurs while creating the migration table.
        """
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
        """
        Checks if a specific migration has already been applied to the database.

        This method queries the database to determine whether a given migration,
        identified by its plugin name, migration name, and version, exists in the
        plugin migrations table. If the migration exists, it indicates that the
        migration has already been applied.

        Args:
            migration (Migration): The migration instance containing the
            plugin name, migration name, and version used for the query.

        Returns:
            bool: True if the migration has been applied, False otherwise.
        """
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
        """
        Apply a migration to the database if it has not already been applied.

        This method checks whether the given migration has already been applied
        to the database. If it has not been applied, the method attempts to apply
        the migration and records it in the database as having been applied. If an
        error occurs during the application of the migration, the transaction is
        rolled back and the error is re-raised.

        Args:
            migration (Migration): The migration object to be applied.

        Raises:
            Exception: If an error occurs during the application of the migration.
        """
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
        """
        Rollbacks a given migration by applying the migration's 'down' method and
        removing its record from the database.

        If the migration has not been applied, logs an informational message and
        exits early without performing any operations.

        Logs the status of the rollback process, including successful rollback or
        any errors encountered while rolling back.

        Parameters:
            migration (Migration): The migration instance to roll back.

        Raises:
            Exception: Propagates the original exception if an error occurs during
            the rollback process.
        """
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
        """
        Fetches the list of migrations that have been applied to plugins in the system.

        If a specific plugin name is provided, filters the applied migrations for the
        given plugin. Otherwise, retrieves migrations applied across all plugins. The
        results are ordered by the time of application.

        Args:
            plugin_name (Optional[str]): The name of the plugin for which applied
            migrations should be retrieved. If None, retrieves migrations for all
            plugins.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries where each dictionary contains
            the following keys:
                - plugin_name (str): The name of the plugin.
                - migration_name (str): The name of the migration.
                - version (str): The version of the migration.
                - applied_at (datetime): The timestamp when the migration was applied.
        """
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
    """
    Establishes a database connection based on the specified database type.

    This function allows creating a database connection object tailored to
    the specified database type. Currently, it supports only PostgreSQL
    connections. If an unsupported database type is provided, it raises an
    appropriate error.

    Args:
        db_type: The type of the database to connect to. Default is
            "postgresql".

    Returns:
        A DatabaseConnection instance corresponding to the specified
        database type.

    Raises:
        ValueError: If the database type provided is unsupported.
    """
    if db_type.lower() == "postgresql":
        return PostgreSQLConnection()
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


def get_database_manager(
    config: Dict[str, Any], db_type: str = "postgresql"
) -> DatabaseManager:
    """
    Fetches a database manager instance for the given database type and configuration.

    This function establishes a connection to the specified database type using the
    provided configuration and returns a `DatabaseManager` instance that can manage
    database operations. The function defaults to using a PostgreSQL database if no
    specific database type is provided.

    Args:
        config (Dict[str, Any]): A dictionary containing the configuration details
            required to establish a database connection.
        db_type (str): The type of the database to connect to. Defaults to "postgresql".

    Returns:
        DatabaseManager: An instance of the `DatabaseManager` class initialized
            with the established database connection.
    """
    connection = create_database_connection(db_type)
    connection.connect(config)
    return DatabaseManager(connection)
