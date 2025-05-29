#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Handles loading GTFS (General Transit Feed Specification) data into a
PostgreSQL database using Psycopg 3.

This module provides functions to load Pandas DataFrames, transformed from GTFS
files, into corresponding database tables. It includes functionality for
batch inserts (using executemany), handling potential geometry data (WKT format),
and logging failed records to a Dead-Letter Queue (DLQ) table.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import psycopg  # Psycopg 3: Replaces psycopg2
from psycopg import sql  # Psycopg 3: Replaces psycopg2.sql
from psycopg import Connection as PgConnection, Cursor as PgCursor  # Psycopg 3: Type hints

module_logger = logging.getLogger(__name__)


def get_table_columns(
        cursor: PgCursor,  # Psycopg 3: Type hint updated
        table_name: str,
        schema: str = "public",
) -> Optional[List[str]]:
    """
    Fetch column names for a given table from the information_schema.

    Args:
        cursor: Active Psycopg 3 cursor object.
        table_name: Name of the table.
        schema: Name of the schema the table belongs to. Defaults to "public".

    Returns:
        A list of column names in their ordinal position, or None if the
        table is not found or an error occurs.
    """
    try:
        cursor.execute(
            sql.SQL(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name = %s
                ORDER BY ordinal_position;
                """
            ),
            (schema, table_name),
        )
        columns = [row[0] for row in cursor.fetchall()]
        if not columns:
            module_logger.warning(
                f"No columns found for table {schema}.{table_name}. "
                "Does the table exist?"
            )
            return None
        return columns
    except psycopg.Error as e:  # Psycopg 3: Error class changed
        module_logger.error(
            f"Error fetching columns for table {schema}.{table_name}: {e}"
        )
        return None


def load_dataframe_to_db(
        conn: PgConnection,  # Psycopg 3: Type hint updated
        df: pd.DataFrame,
        table_name: str,
        schema_definition: Dict[str, Any],
        dlq_table_name: Optional[str] = None,
) -> Tuple[int, int]:
    """
    Load a Pandas DataFrame into a specified PostgreSQL table using Psycopg 3.

    This function assumes the input DataFrame has been validated and transformed.
    It truncates the target table before loading new data using `cursor.executemany()`.
    Geometry data, if present in a column as WKT strings, is inserted as text,
    relying on PostgreSQL to cast it to the GEOMETRY type if the column is defined as such.

    Args:
        conn: Active Psycopg 3 connection object.
        df: Pandas DataFrame to load.
        table_name: Name of the target database table.
        schema_definition: Schema details for the table.
        dlq_table_name: Optional name of the Dead-Letter Queue (DLQ) table.

    Returns:
        A tuple (successful_loads, dlq_inserts).
    """
    if df.empty:
        module_logger.info(
            f"DataFrame for table '{table_name}' is empty. Nothing to load."
        )
        return 0, 0

    successful_loads = 0
    dlq_inserts = 0

    target_db_cols_from_schema = list(
        schema_definition.get("columns", {}).keys()
    )
    geom_config = schema_definition.get("geom_config")
    geom_col_name: Optional[str] = None
    if geom_config:
        geom_col_name = geom_config.get("geom_col")
        if geom_col_name and geom_col_name not in target_db_cols_from_schema:
            target_db_cols_from_schema.append(geom_col_name)

    df_cols_for_db_insert: List[str] = []
    for col_name in target_db_cols_from_schema:
        if col_name in df.columns:
            df_cols_for_db_insert.append(col_name)

    if not df_cols_for_db_insert:
        module_logger.error(
            f"No matching columns found between DataFrame and schema for "
            f"table '{table_name}'. Cannot load."
        )
        return 0, 0

    df_to_load_final = df[df_cols_for_db_insert].copy()

    try:
        data_tuples = [
            tuple(x)
            for x in df_to_load_final.replace({
                pd.NA: None,  # Pandas 2+: Ensures pd.NA is converted to None for DB
                float("nan"): None,
                float("inf"): None,
                float("-inf"): None,
            }).to_numpy()
        ]
    except Exception as e:
        module_logger.error(
            f"Error converting DataFrame for '{table_name}' to tuples: {e}",
            exc_info=True,
        )
        return 0, 0

    try:
        # Psycopg 3: Use 'with conn.transaction():' for managing transactions
        with conn.transaction():
            with conn.cursor() as cursor:
                module_logger.info(f"Truncating table: {table_name}...")
                cursor.execute(
                    sql.SQL("TRUNCATE TABLE {} CASCADE;").format(
                        sql.Identifier(table_name)
                    )
                )
                module_logger.info(f"Table {table_name} truncated.")

                if not data_tuples:
                    module_logger.info(f"No data to load into {table_name} after processing.")
                    return 0, 0

                quoted_db_cols = [
                    sql.Identifier(col) for col in df_cols_for_db_insert
                ]
                cols_sql_segment = sql.SQL(", ").join(quoted_db_cols)

                placeholders_sql_segment = sql.SQL(", ").join(
                    [sql.Placeholder()] * len(df_cols_for_db_insert)  # Psycopg 3: Placeholders for executemany
                )

                insert_stmt_template = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    sql.Identifier(table_name),
                    cols_sql_segment,
                    placeholders_sql_segment,
                )

                insert_query_string = insert_stmt_template.as_string(conn)
                module_logger.debug(
                    f"Insert statement for {table_name} (using executemany): {insert_query_string}"
                )
                module_logger.info(
                    f"Attempting to load {len(data_tuples)} records into {table_name} using executemany..."
                )

                # Psycopg 3: Use cursor.executemany
                cursor.executemany(insert_query_string, data_tuples)

                successful_loads = (
                    cursor.rowcount
                    if cursor.rowcount != -1
                    else len(data_tuples)
                )

            module_logger.info(
                f"Successfully loaded {successful_loads} records into {table_name}."
            )
    except psycopg.Error as e_db_insert:  # Psycopg 3: Error class changed
        module_logger.error(
            f"Error during bulk insert into {table_name} using Psycopg 3: {e_db_insert}. "
            "Transaction rolled back. No records loaded for this batch.",
            exc_info=True,
        )
        if dlq_table_name:
            module_logger.error(
                f"Batch insert failed for {table_name}. Logging failure info "
                f"to DLQ table '{dlq_table_name}' if possible."
            )
            try:
                log_to_dlq(
                    conn,
                    dlq_table_name,
                    {
                        "batch_summary": f"Failed to insert {len(data_tuples)} records.",
                        "first_record_example": data_tuples[0]
                        if data_tuples
                        else None,
                        "column_names": df_cols_for_db_insert,
                    },
                    str(e_db_insert),
                    f"Batch insert failure for table: {table_name}",
                )
                dlq_inserts = 1
            except Exception as e_dlq_log:
                module_logger.error(
                    f"Failed to log batch failure to DLQ: {e_dlq_log}"
                )
    except Exception as e_unexpected:
        module_logger.error(
            f"Unexpected error during data load for {table_name}: {e_unexpected}",
            exc_info=True,
        )

    return successful_loads, dlq_inserts


def log_to_dlq(
        conn: PgConnection,  # Psycopg 3: Type hint updated
        dlq_table_name: str,
        failed_record_data: Dict,
        error_reason: str,
        source_info: str,
) -> None:
    """
    Log a failed record or batch failure information to a Dead-Letter Queue (DLQ) table
    using Psycopg 3.

    Args:
        conn: Active Psycopg 3 connection object.
        dlq_table_name: Name of the DLQ table.
        failed_record_data: Dictionary containing the data of the failed record.
        error_reason: String describing the reason for failure.
        source_info: String providing context about the data's origin.
    """
    dlq_insert_stmt = sql.SQL(
        """
        INSERT INTO {} (original_data, error_reason, source_info, processed_at)
        VALUES (%s, %s, %s, %s);
        """
    ).format(sql.Identifier(dlq_table_name))

    try:
        record_json = json.dumps(failed_record_data, default=str)
        timestamp_now = datetime.now()

        # Psycopg 3: Operations are typically autocommitted unless inside an explicit transaction.
        # For a single DLQ write, autocommit is usually desired.
        with conn.cursor() as cursor:
            cursor.execute(
                dlq_insert_stmt,
                (record_json, error_reason, source_info, timestamp_now),
            )
        module_logger.debug(
            f"Record/Info logged to DLQ table '{dlq_table_name}' "
            f"for source: {source_info}"
        )
    except psycopg.Error as e_db_dlq:  # Psycopg 3: Error class changed
        module_logger.error(
            f"Database error inserting record into DLQ table "
            f"'{dlq_table_name}' using Psycopg 3: {e_db_dlq}",
            exc_info=True,
        )
    except Exception as e_unexpected_dlq:
        module_logger.error(
            f"Unexpected error logging to DLQ table '{dlq_table_name}' using Psycopg 3: "
            f"{e_unexpected_dlq}",
            exc_info=True,
        )