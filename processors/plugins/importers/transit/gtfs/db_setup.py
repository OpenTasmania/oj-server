# processors/gtfs/db_setup.py
# -*- coding: utf-8 -*-
"""
Handles database schema setup for GTFS processing, including table creation
and foreign key management.
"""

import logging
from typing import List

import psycopg
from psycopg import Connection as PgConnection
from psycopg import sql

from . import schema_definitions as schemas
from .pipeline_definitions import GTFS_FOREIGN_KEYS, GTFS_LOAD_ORDER

module_logger = logging.getLogger(__name__)


def create_tables_from_schema(conn: PgConnection) -> None:
    """
    Sets up the database schema for GTFS-related data.

    This function creates tables in the database as defined by GTFS_FILE_SCHEMAS.
    It ensures the necessary tables exist with the appropriate columns and, where
    applicable, adds primary key constraints. A generic dead letter queue (DLQ)
    table and a table for 'gtfs_shapes_lines' are also created or ensured.

    Parameters:
    conn : PgConnection
        An active PostgreSQL database connection.

    Raises:
    psycopg.Error
        If errors occur during table creation or primary key setup.
    """
    module_logger.info(
        "Setting up database schema based on schema_definitions.GTFS_FILE_SCHEMAS..."
    )
    with conn.cursor() as cursor:
        for filename_key in GTFS_LOAD_ORDER:
            details = schemas.GTFS_FILE_SCHEMAS.get(filename_key)
            if not details:
                if filename_key not in [
                    "gtfs_shapes_lines.txt"
                ]:  # pragma: no cover
                    module_logger.debug(
                        f"No schema definition for '{filename_key}', skipping table creation in this loop."
                    )
                continue

            table_name = details["db_table_name"]
            cols_defs_sql_list: List[sql.Composed] = []

            db_columns_def = details.get("columns", {})
            if not isinstance(db_columns_def, dict):  # pragma: no cover
                module_logger.error(
                    f"Columns definition for {table_name} is not a dictionary. Skipping."
                )
                continue

            for col_name, col_props in db_columns_def.items():
                col_type_str = col_props.get(
                    "type", "TEXT"
                )  # e.g., "TEXT", "INTEGER", "GEOMETRY(Point, 4326)"

                column_definition_parts = [
                    sql.Identifier(col_name),
                    sql.SQL(col_type_str),
                ]

                cols_defs_sql_list.append(
                    sql.SQL(" ").join(column_definition_parts)
                )

            if not cols_defs_sql_list:  # pragma: no cover
                module_logger.warning(
                    f"No columns to define for table {table_name}. Skipping creation."
                )
                continue

            cols_sql_segment = sql.SQL(", ").join(cols_defs_sql_list)

            create_sql = sql.SQL(
                "CREATE TABLE IF NOT EXISTS {} ({});"
            ).format(
                sql.Identifier(table_name),
                cols_sql_segment,
            )
            try:
                module_logger.debug(
                    f"Executing SQL for table {table_name}: {create_sql.as_string(conn)}"
                )
                cursor.execute(create_sql)
            except psycopg.Error as e:  # pragma: no cover
                module_logger.error(
                    f"Error creating table {table_name}: {e.diag.message_primary if e.diag else str(e)}"
                )
                raise

            pk_column_names = details.get("pk_cols")
            if (
                pk_column_names
                and isinstance(pk_column_names, list)
                and len(pk_column_names) > 0
            ):
                sanitized_pk_cols = [
                    sql.Identifier(col) for col in pk_column_names
                ]
                pk_cols_sql_segment = sql.SQL(", ").join(sanitized_pk_cols)
                constraint_name_str = f"pk_{table_name.replace('gtfs_', '')}"
                if len(constraint_name_str) > 63:  # pragma: no cover
                    constraint_name_str = constraint_name_str[:63]
                pk_constraint_name = sql.Identifier(constraint_name_str)

                alter_pk_sql = sql.SQL(
                    "ALTER TABLE {} ADD CONSTRAINT {} PRIMARY KEY ({});"
                ).format(
                    sql.Identifier(table_name),
                    pk_constraint_name,
                    pk_cols_sql_segment,
                )
                try:
                    module_logger.debug(
                        f"Attempting to add PRIMARY KEY to {table_name} on ({', '.join(pk_column_names)})"
                    )
                    cursor.execute(alter_pk_sql)
                    module_logger.info(
                        f"Added PRIMARY KEY to {table_name} on ({', '.join(pk_column_names)})."
                    )
                except psycopg.Error as e_pk:  # pragma: no cover
                    module_logger.error(
                        f"Failed to add PRIMARY KEY to {table_name}: {e_pk.diag.message_primary if e_pk.diag else str(e_pk)}"
                    )
                    raise e_pk

        try:
            cursor.execute(
                sql.SQL(
                    """
                    CREATE TABLE IF NOT EXISTS gtfs_shapes_lines
                    (
                        shape_id
                        TEXT
                        PRIMARY
                        KEY,
                        geom
                        GEOMETRY
                    (
                        LineString,
                        4326
                    ));
                    """
                )
            )
            module_logger.info("Table 'gtfs_shapes_lines' ensured.")
        except psycopg.Error as e:  # pragma: no cover
            module_logger.error(
                f"Error creating table gtfs_shapes_lines: {e.diag.message_primary if e.diag else str(e)}"
            )
            raise

        try:
            cursor.execute(
                sql.SQL(
                    """
                    CREATE TABLE IF NOT EXISTS gtfs_dlq
                    (
                        id
                        SERIAL
                        PRIMARY
                        KEY,
                        gtfs_filename
                        TEXT,
                        original_row_data
                        TEXT,
                        error_timestamp
                        TIMESTAMP
                        WITH
                        TIME
                        ZONE
                        DEFAULT
                        CURRENT_TIMESTAMP,
                        error_reason
                        TEXT,
                        notes
                        TEXT
                    );
                    """
                )
            )
            module_logger.info("Generic DLQ table 'gtfs_dlq' ensured.")
        except psycopg.Error as e:  # pragma: no cover
            module_logger.error(
                f"Error creating generic DLQ table gtfs_dlq: {e.diag.message_primary if e.diag else str(e)}"
            )
            # TODO: Check non-raising
            # Not raising, as DLQ might be non-critical

    module_logger.info("Database schema setup/verification complete.")


def add_foreign_keys_from_schema(
    conn: PgConnection,
) -> None:  # pragma: no cover
    """
    Add foreign keys to the database schema after data loading.

    This function attempts to add foreign key constraints to tables in a PostgreSQL
    database using the connection provided. It iterates through a list of predefined
    foreign key definitions and applies each constraint if both the source and target
    tables of the foreign key relationship exist. Foreign key constraints are added
    in a deferred mode, thus delaying their enforcement until the transaction is
    committed. Detailed logs are produced throughout the process to track success
    and failure for each foreign key operation.

    Arguments:
        conn: A connection object to a PostgreSQL database.

    Raises:
        psycopg.Error: If any database error occurs during the process of adding
            foreign keys, such as an invalid SQL statement or database state.
        Exception: For any unexpected error encountered during execution.

    Notes:
        - The foreign key constraints are applied in a deferred mode, meaning their
          enforcement is postponed until the transaction in which they are created
          is committed.
        - If any of the source or target tables for a foreign key does not exist, the
          corresponding foreign key creation is skipped and a warning is logged.
        - The function assumes the existence of a predefined list of foreign key
          metadata (GTFS_FOREIGN_KEYS) containing tuples with information about each
          constraint to be added.
    """
    module_logger.info("Attempting to add foreign keys post-data load...")
    with conn.cursor() as cursor:
        for (
            from_table,
            from_cols_list,
            to_table,
            to_cols_list,
            fk_name,
        ) in GTFS_FOREIGN_KEYS:
            try:
                cursor.execute(
                    "SELECT to_regclass(%s);", (f"public.{from_table}",)
                )
                source_table_exists_row = cursor.fetchone()
                if (
                    not source_table_exists_row
                    or not source_table_exists_row[0]
                ):
                    module_logger.warning(
                        f"Source Table {from_table} for FK {fk_name} does not exist. Skipping FK creation."
                    )
                    continue
                cursor.execute(
                    "SELECT to_regclass(%s);", (f"public.{to_table}",)
                )
                target_table_exists_row = cursor.fetchone()
                if (
                    not target_table_exists_row
                    or not target_table_exists_row[0]
                ):
                    module_logger.warning(
                        f"Target Table {to_table} for FK {fk_name} does not exist. Skipping FK creation."
                    )
                    continue

                from_cols_sql = sql.SQL(", ").join(
                    map(sql.Identifier, from_cols_list)
                )
                to_cols_sql = sql.SQL(", ").join(
                    map(sql.Identifier, to_cols_list)
                )

                alter_sql = sql.SQL(
                    "ALTER TABLE {} ADD CONSTRAINT {} FOREIGN KEY ({}) "  # type: ignore[misc] # psycoph3 linter confusion
                    "REFERENCES {} ({}) DEFERRABLE INITIALLY DEFERRED;"
                ).format(
                    sql.Identifier(from_table),
                    sql.Identifier(fk_name),
                    from_cols_sql,
                    sql.Identifier(to_table),
                    to_cols_sql,
                )

                module_logger.info(
                    f"Preparing to add FK {fk_name} on {from_table}({', '.join(from_cols_list)})"
                    f" -> {to_table}({', '.join(to_cols_list)})"
                )
                cursor.execute(alter_sql)
                module_logger.info(
                    f"Successfully prepared FK {fk_name} for commit."
                )
            except psycopg.Error as e:
                module_logger.error(
                    f"Could not prepare foreign key {fk_name} for commit: {e.diag.message_primary if e.diag else str(e)}"
                )
                raise
            except Exception as ex:
                module_logger.error(
                    f"Unexpected error preparing foreign key {fk_name}: {ex}",
                    exc_info=True,
                )
                raise
    module_logger.info(
        "Foreign key application process finished (pending commit of parent transaction)."
    )


def drop_all_gtfs_foreign_keys(
    conn: PgConnection,
) -> None:  # pragma: no cover
    """
    Drops all existing GTFS foreign keys from the specified PostgreSQL database connection.

    This function iterates through a predefined list of GTFS foreign key constraints,
    represented by GTFS_FOREIGN_KEYS, and attempts to drop each of them from their
    respective tables. It ensures the operations are performed only if the corresponding
    table exists within the database. Logs messages are generated for executed actions
    and any failures encountered during the process, including warnings for cases where
    foreign keys cannot be dropped.

    Parameters:
        conn (PgConnection): Active PostgreSQL connection object used to communicate
            with the target database.

    Raises:
        This function does not explicitly raise exceptions but logs them instead. Errors
        encountered when attempting to drop foreign keys will be logged and handled
        gracefully.
    """
    module_logger.info("Dropping existing GTFS foreign keys...")
    with conn.cursor() as cursor:
        for from_table, _, _, _, fk_name in reversed(GTFS_FOREIGN_KEYS):
            try:
                cursor.execute(
                    "SELECT to_regclass(%s);", (f"public.{from_table}",)
                )
                table_exists_row = cursor.fetchone()
                if not table_exists_row or not table_exists_row[0]:
                    module_logger.debug(
                        f"Table {from_table} for FK {fk_name} does not exist. Skipping FK drop."
                    )
                    continue
                cursor.execute(
                    sql.SQL(
                        "ALTER TABLE {} DROP CONSTRAINT IF EXISTS {};"
                    ).format(
                        sql.Identifier(from_table), sql.Identifier(fk_name)
                    )
                )
                module_logger.info(
                    f"Dropped foreign key {fk_name} from {from_table} (if existed)."
                )
            except psycopg.Error as e:
                module_logger.warning(
                    f"Could not drop foreign key {fk_name} from {from_table}: {e.diag.message_primary if e.diag else str(e)}."
                )
    module_logger.info("Finished attempting to drop GTFS foreign keys.")
