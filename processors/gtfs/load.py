#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Handles loading GTFS (General Transit Feed Specification) data into a
PostgreSQL database using Psycopg 3.

This module provides functions to load Pandas DataFrames, transformed from GTFS
files, into corresponding database tables. It includes functionality for
batch inserts (using executemany or COPY), handling potential geometry data (WKT format),
and logging failed records to a Dead-Letter Queue (DLQ) table.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import psycopg
from psycopg import Connection as PgConnection
from psycopg import Cursor as PgCursor
from psycopg import sql

module_logger = logging.getLogger(__name__)


def get_table_columns(
        cursor: PgCursor,
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
                f"No columns found for table {schema}.{table_name}. Does the table exist?"
            )
            return None
        return columns
    except psycopg.Error as e:
        module_logger.error(
            f"Error fetching columns for table {schema}.{table_name}: {e}"
        )
        return None


def load_dataframe_to_db(
        conn: PgConnection,
        df: pd.DataFrame,
        table_name: str,
        schema_definition: Dict[str, Any],
        dlq_table_name: Optional[str] = None,
) -> Tuple[int, int]:
    """
    Load a Pandas DataFrame into a specified PostgreSQL table using Psycopg 3.

    This function truncates the target table before loading new data.
    It uses `cursor.executemany()` for batch inserts. Geometry data, if present
    in a column as WKT strings, is inserted as text.

    Args:
        conn: Active Psycopg 3 connection object.
        df: Pandas DataFrame to load.
        table_name: Name of the target database table.
        schema_definition: Schema details for the table, including 'columns'
                           and optionally 'geom_config'.
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
    if geom_config:
        geom_col_name = geom_config.get("geom_col")
        if geom_col_name and geom_col_name not in target_db_cols_from_schema:
            module_logger.debug(
                f"Adding geometry column '{geom_col_name}' to target DB columns for table '{table_name}'."
            )
            target_db_cols_from_schema.append(geom_col_name)

    df_cols_for_db_insert: List[str] = [
        col for col in target_db_cols_from_schema if col in df.columns
    ]

    if not df_cols_for_db_insert:
        module_logger.error(
            f"No matching columns found between DataFrame (cols: {df.columns.tolist()}) and "
            f"schema_definition's target columns ({target_db_cols_from_schema}) for "
            f"table '{table_name}'. Cannot load."
        )
        return 0, 0

    df_to_load_final = df[df_cols_for_db_insert].copy()

    try:
        data_tuples = [
            tuple(x)
            for x in df_to_load_final.replace(
                {
                    pd.NA: None,
                    float("nan"): None,
                    float("inf"): None,
                    float("-inf"): None,
                }
            ).to_numpy()
        ]
    except Exception as e:
        module_logger.error(
            f"Error converting DataFrame for '{table_name}' to tuples: {e}",
            exc_info=True,
        )
        return 0, 0

    try:
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
                    module_logger.info(
                        f"No data to load into {table_name} after processing."
                    )
                    return 0, 0

                quoted_db_cols = [
                    sql.Identifier(col) for col in df_cols_for_db_insert
                ]
                cols_sql_segment = sql.SQL(", ").join(quoted_db_cols)
                placeholders_sql_segment = sql.SQL(", ").join(
                    [sql.Placeholder()] * len(df_cols_for_db_insert)
                )
                insert_stmt_template = sql.SQL(
                    "INSERT INTO {} ({}) VALUES ({})"
                ).format(
                    sql.Identifier(table_name),
                    cols_sql_segment,
                    placeholders_sql_segment,
                )
                insert_query_string = insert_stmt_template.as_string(conn)

                module_logger.info(
                    f"Attempting to load {len(data_tuples)} records into {table_name} using executemany..."
                )
                cursor.executemany(insert_query_string, data_tuples) # type: ignore[arg-type]
                successful_loads = (
                    cursor.rowcount
                    if cursor.rowcount != -1
                    else len(data_tuples)
                )
            module_logger.info(
                f"Successfully loaded {successful_loads} records into {table_name}."
            )
    except psycopg.Error as e_db_insert:
        module_logger.error(
            f"Error during bulk insert into {table_name} using Psycopg 3: {e_db_insert}. "
            "Transaction rolled back.",
            exc_info=True,
        )
        if dlq_table_name:
            try:
                log_to_dlq(
                    conn,  # Pass connection for DLQ logging
                    dlq_table_name,
                    {
                        "batch_summary": f"Failed to insert {len(data_tuples)} records.",
                        "first_record_example": (
                            data_tuples[0] if data_tuples else None
                        ),
                        "column_names": df_cols_for_db_insert,
                    },
                    str(e_db_insert),
                    f"Batch insert failure for table: {table_name}",
                )
                dlq_inserts = 1
            except Exception as e_dlq_log:
                module_logger.error(
                    f"Failed to log batch failure to DLQ '{dlq_table_name}': {e_dlq_log}"
                )
    except Exception as e_unexpected:
        module_logger.error(
            f"Unexpected error during data load for {table_name}: {e_unexpected}",
            exc_info=True,
        )
    return successful_loads, dlq_inserts


def log_to_dlq(
        conn: PgConnection,
        dlq_table_name: str,
        failed_record_data: Dict,
        error_reason: str,
        source_info: str,  # Renamed from 'notes' to be more descriptive of its use
) -> None:
    """
    Log a failed record or batch failure information to a Dead-Letter Queue (DLQ) table.

    Args:
        conn: Active Psycopg 3 connection object. Must be able to operate
              outside the main transaction if the main transaction failed.
        dlq_table_name: Name of the DLQ table.
        failed_record_data: Dictionary containing the data of the failed record or batch.
        error_reason: String describing the reason for failure.
        source_info: String providing context about the data's origin or process step.
    """
    # Construct DLQ table name ensuring it's a valid identifier if not already
    # This assumes dlq_table_name might not be sanitized yet.
    # If dlq_table_name is always from a trusted source, this might be overkill.

    # The original main_pipeline was creating dlq tables like dlq_gtfs_stops,
    # but the generic gtfs_dlq was also created by update_gtfs.
    # For now, this function assumes dlq_table_name is the correct, existing table name.
    # A check for table existence or dynamic creation of DLQ tables might be needed.

    dlq_insert_stmt = sql.SQL(
        "INSERT INTO {} (original_row_data, error_reason, notes, error_timestamp) " # type: ignore[misc] # psycoph3 linter confusion
        "VALUES (%s, %s, %s, %s);"
    ).format(
        sql.Identifier(dlq_table_name)
    )  # Assuming notes field exists in per-table DLQ.

    try:
        record_json = json.dumps(failed_record_data, default=str)
        timestamp_now = datetime.now()

        # DLQ logging should ideally happen in its own transaction or with autocommit.
        # Here, we use the passed connection; its transaction state depends on the caller.
        # If the main transaction was rolled back, this conn might be in an aborted state
        # unless the caller specifically handles that (e.g. by using a new cursor or conn.rollback()).

        # To ensure DLQ write happens even if main transaction failed:
        is_main_transaction_active = (
                conn.info.transaction_status
                == psycopg.pq.TransactionStatus.INTRANS
        )

        with conn.cursor() as cursor:
            if (
                    not is_main_transaction_active
                    and conn.info.transaction_status
                    != psycopg.pq.TransactionStatus.IDLE
            ):
                try:
                    conn.rollback()  # Attempt to clear failed transaction state if any
                    module_logger.debug(
                        f"Rolled back connection for DLQ insert to {dlq_table_name}"
                    )
                except psycopg.Error as rb_err:
                    module_logger.error(
                        f"Error rolling back for DLQ insert: {rb_err}"
                    )
                    # Proceeding, but insert might fail if connection is broken

            cursor.execute(
                dlq_insert_stmt,
                (record_json, error_reason, source_info, timestamp_now),
            )
            # If not in a main transaction, this cursor's operation will typically autocommit
            # or commit if conn.autocommit = True. If conn.autocommit = False and not in a tx,
            # an explicit conn.commit() would be needed for this write.
            # For simplicity, assuming default Psycopg 3 behavior or caller manages commits.
            if not is_main_transaction_active and not conn.autocommit:
                conn.commit()  # Explicit commit for DLQ if not in main transaction and no autocommit

        module_logger.debug(
            f"Record/Info logged to DLQ table '{dlq_table_name}' for source: {source_info}"
        )

    except psycopg.Error as e_db_dlq:
        module_logger.error(
            f"Database error inserting into DLQ table '{dlq_table_name}': {e_db_dlq}",
            exc_info=True,
        )
    except Exception as e_unexpected_dlq:
        module_logger.error(
            f"Unexpected error logging to DLQ table '{dlq_table_name}': {e_unexpected_dlq}",
            exc_info=True,
        )
