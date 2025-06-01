# processors/gtfs/db_setup.py
# -*- coding: utf-8 -*-
"""
Handles database schema setup for GTFS processing, including table creation
and foreign key management.
"""
import logging
from typing import List  # Added Tuple

import psycopg  # Keep psycopg for PgConnection
from psycopg import Connection as PgConnection  # Keep specific import
from psycopg import sql

# Import definitions from other GTFS modules
from . import schema_definitions as schemas  # For GTFS_FILE_SCHEMAS
from .pipeline_definitions import GTFS_FOREIGN_KEYS, GTFS_LOAD_ORDER

module_logger = logging.getLogger(__name__)


# REMOVE sanitize_identifier function as it will no longer be used.
# def sanitize_identifier(name: str) -> str:
#     """Sanitize SQL identifiers (table/column names) by quoting them."""
#     return '"' + name.replace('"', '""').strip() + '"'


def create_tables_from_schema(conn: PgConnection) -> None:
    """
    Create database tables based on schema_definitions.GTFS_FILE_SCHEMAS.
    Primary keys are added using ALTER TABLE based on 'pk_cols' in the schema.
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
            # Changed from List[str] to List[sql.Composed]
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

                # Start building the column definition with name and type
                # sql.Identifier handles quoting for col_name
                # sql.SQL treats col_type_str as a literal SQL snippet (e.g., a type)
                column_definition_parts = [
                    sql.Identifier(col_name),
                    sql.SQL(col_type_str),
                ]

                # Example: Add other constraints if defined in col_props
                # This part depends on how you might extend schema_definitions.py
                # For instance, if you had a 'constraints' key in col_props:
                # if "constraints" in col_props and col_props["constraints"]:
                #     column_definition_parts.append(sql.SQL(col_props["constraints"]))

                # Join parts for this column definition (e.g., "column_name TEXT")
                cols_defs_sql_list.append(
                    sql.SQL(" ").join(column_definition_parts)
                )

            if not cols_defs_sql_list:  # pragma: no cover
                module_logger.warning(
                    f"No columns to define for table {table_name}. Skipping creation."
                )
                continue

            # Join all column definitions with a comma
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
            # Not raising, as DLQ might be non-critical

    module_logger.info("Database schema setup/verification complete.")


def add_foreign_keys_from_schema(
        conn: PgConnection,
) -> None:  # pragma: no cover
    """
    Add foreign keys based on GTFS_FOREIGN_KEYS definitions.
    This function expects to be run within an existing transaction.
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
                if not cursor.fetchone()[0]:
                    module_logger.warning(
                        f"Source Table {from_table} for FK {fk_name} does not exist. Skipping FK creation."
                    )
                    continue
                cursor.execute(
                    "SELECT to_regclass(%s);", (f"public.{to_table}",)
                )
                if not cursor.fetchone()[0]:
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
                    "ALTER TABLE {} ADD CONSTRAINT {} FOREIGN KEY ({}) "
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
    """Drop all defined GTFS foreign keys using Psycopg 3."""
    module_logger.info("Dropping existing GTFS foreign keys...")
    with conn.cursor() as cursor:
        for from_table, _, _, _, fk_name in reversed(GTFS_FOREIGN_KEYS):
            try:
                cursor.execute(
                    "SELECT to_regclass(%s);", (f"public.{from_table}",)
                )
                if not cursor.fetchone()[0]:
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
