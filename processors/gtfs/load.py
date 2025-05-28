#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Handles loading GTFS (General Transit Feed Specification) data into a
PostgreSQL database.

This module provides functions to load Pandas DataFrames, transformed from GTFS
files, into corresponding database tables. It includes functionality for
batch inserts, handling potential geometry data (WKT format), and logging
failed records to a Dead-Letter Queue (DLQ) table.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import connection as PgConnection
from psycopg2.extensions import cursor as PgCursor
from psycopg2.extras import execute_values

module_logger = logging.getLogger(__name__)


def get_table_columns(
    cursor: PgCursor,
    table_name: str,
    schema: str = "public",
) -> Optional[List[str]]:
    """
    Fetch column names for a given table from the information_schema.

    Args:
        cursor: Active psycopg2 cursor object.
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
    except psycopg2.Error as e:
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
    Load a Pandas DataFrame into a specified PostgreSQL table.

    This function assumes the input DataFrame has been validated and transformed
    according to the `schema_definition`. It truncates the target table before
    loading new data. It uses `execute_values` for efficient batch inserts.
    Geometry data, if present, is expected as WKT strings and will be
    converted using `ST_SetSRID(ST_GeomFromText(...))`.

    Args:
        conn: Active psycopg2 connection object.
        df: Pandas DataFrame to load. Its columns should align with the
            keys in `schema_definition['columns']` plus any geometry column
            defined in `schema_definition['geom_config']`.
        table_name: Name of the target database table.
        schema_definition: Schema details for the table (e.g., from
                           `schema_definitions.GTFS_FILE_SCHEMAS`). Expected
                           to contain 'columns' (a dict) and optionally
                           'geom_config'.
        dlq_table_name: Optional name of the Dead-Letter Queue (DLQ) table
                        for logging records that fail during this load process.
                        Currently, DLQ logging here is basic for batch failures.

    Returns:
        A tuple (successful_loads, dlq_inserts):
            - successful_loads: Number of records successfully loaded.
            - dlq_inserts: Number of records sent to DLQ (currently basic,
                           primarily for indicating batch failures).
    """
    if df.empty:
        module_logger.info(
            f"DataFrame for table '{table_name}' is empty. Nothing to load."
        )
        return 0, 0

    successful_loads = 0
    dlq_inserts = 0  # Currently minimal DLQ usage in this batch function.

    # Determine columns for insertion based on the schema definition.
    # These are the keys of the 'columns' dictionary in file_schema_info.
    target_db_cols_from_schema = list(
        schema_definition.get("columns", {}).keys()
    )
    # Include geometry column if defined in schema_definition's geom_config.
    geom_config = schema_definition.get("geom_config")
    geom_col_name: Optional[str] = None
    if geom_config:
        geom_col_name = geom_config.get("geom_col")
        if geom_col_name and geom_col_name not in target_db_cols_from_schema:
            # Typically, the geom_col is generated and not part of the
            # original GTFS file's direct columns.
            target_db_cols_from_schema.append(geom_col_name)

    # Filter DataFrame columns to only those expected by the schema.
    # The order in df_cols_for_db_insert will match target_db_cols_from_schema.
    df_cols_for_db_insert: List[str] = []
    for col_name in target_db_cols_from_schema:
        if col_name in df.columns:
            df_cols_for_db_insert.append(col_name)
        # If a schema column is missing in df, it won't be included.
        # The transform step should ensure all necessary columns are present.

    if not df_cols_for_db_insert:
        module_logger.error(
            f"No matching columns found between DataFrame and schema for "
            f"table '{table_name}'. Cannot load."
        )
        return 0, 0

    # Create a new DataFrame with only the selected columns in the correct order.
    # Use a copy to avoid modifying the original DataFrame.
    df_to_load_final = df[df_cols_for_db_insert].copy()

    # Convert DataFrame to list of tuples for `execute_values`.
    # Pandas NA/NaN values are converted to None for PostgreSQL NULL.
    try:
        data_tuples = [
            tuple(x)
            for x in df_to_load_final.replace({
                pd.NA: None,
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
        return 0, 0  # Cannot proceed if data conversion fails.

    with conn.cursor() as cursor:  # Ensure cursor is closed
        # Truncate production table before loading new data.
        try:
            module_logger.info(f"Truncating table: {table_name}...")
            cursor.execute(
                sql.SQL("TRUNCATE TABLE {} CASCADE;").format(
                    sql.Identifier(table_name)
                )
            )
            module_logger.info(f"Table {table_name} truncated.")
        except psycopg2.Error as e:
            module_logger.error(
                f"Error truncating table {table_name}: {e}", exc_info=True
            )
            conn.rollback()  # Rollback on error
            return 0, 0  # Cannot proceed if truncate fails.

        # Prepare INSERT statement components.
        quoted_db_cols = [
            sql.Identifier(col) for col in df_cols_for_db_insert
        ]
        cols_sql_segment = sql.SQL(", ").join(quoted_db_cols)
        placeholders_list = [sql.Placeholder()] * len(df_cols_for_db_insert)

        # Handle geometry column specifically: wrap with ST_GeomFromText.
        if (
            geom_col_name
            and geom_col_name in df_cols_for_db_insert
            and geom_config
        ):
            srid = geom_config.get(
                "srid", 4326
            )  # Default SRID if not specified
            try:
                geom_col_idx = df_cols_for_db_insert.index(geom_col_name)
                placeholders_list[geom_col_idx] = sql.SQL(
                    "ST_SetSRID(ST_GeomFromText({}), {})"
                ).format(sql.Placeholder(), sql.Literal(srid))
            except ValueError:
                module_logger.error(
                    f"Geometry column '{geom_col_name}' defined in schema but "
                    f"not found in DataFrame columns being loaded for "
                    f"'{table_name}'. This should not happen if transform step is correct."
                )
                conn.rollback()
                return 0, 0

        placeholders_sql_segment = sql.SQL(", ").join(placeholders_list)
        insert_stmt = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(table_name),
            cols_sql_segment,
            placeholders_sql_segment,
        )
        module_logger.debug(
            f"Insert statement for {table_name}: {insert_stmt.as_string(conn)}"
        )

        module_logger.info(
            f"Attempting to load {len(data_tuples)} records into {table_name}..."
        )
        try:
            execute_values(
                cursor,
                insert_stmt.as_string(
                    conn
                ),  # Get raw SQL string for execute_values
                data_tuples,
                page_size=1000,  # Tunable batch size for execute_values
            )
            successful_loads = (
                cursor.rowcount
                if cursor.rowcount is not None
                else len(data_tuples)
            )
            conn.commit()  # Commit after successful batch insert.
            module_logger.info(
                f"Successfully loaded {successful_loads} records into {table_name}."
            )
        except psycopg2.Error as e_db_insert:
            conn.rollback()  # Rollback on batch insert error.
            module_logger.error(
                f"Error during bulk insert into {table_name}: {e_db_insert}. "
                "No records loaded into production table for this batch.",
                exc_info=True,
            )
            # Basic DLQ for the entire failed batch.
            # Granular DLQ should happen at validation/transform stages.
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
                    dlq_inserts = 1  # Indicate one DLQ entry for the batch
                except Exception as e_dlq_log:
                    module_logger.error(
                        f"Failed to log batch failure to DLQ: {e_dlq_log}"
                    )
        except Exception as e_unexpected:
            conn.rollback()
            module_logger.error(
                f"Unexpected error during data load for {table_name}: {e_unexpected}",
                exc_info=True,
            )

    return successful_loads, dlq_inserts


def log_to_dlq(
    conn: PgConnection,
    dlq_table_name: str,
    failed_record_data: Dict,  # Original record data or batch summary
    error_reason: str,
    source_info: str,  # e.g., filename, specific error context
) -> None:
    """
    Log a failed record or batch failure information to a Dead-Letter Queue (DLQ) table.

    Assumes the DLQ table has at least the following columns:
    - `original_data` (TEXT or JSONB): Stores the problematic data.
    - `error_reason` (TEXT): Description of why the record failed.
    - `source_info` (TEXT): Context about the source of the data (e.g., filename).
    - `processed_at` (TIMESTAMP WITH TIME ZONE): Timestamp of logging.

    Args:
        conn: Active psycopg2 connection object.
        dlq_table_name: Name of the DLQ table.
        failed_record_data: Dictionary containing the data of the failed record
                            or a summary if it's a batch failure.
        error_reason: String describing the reason for failure.
        source_info: String providing context about the data's origin or the
                     nature of the failure (e.g., "stops.txt", "Batch insert error").
    """
    dlq_insert_stmt = sql.SQL(
        """
        INSERT INTO {} (original_data, error_reason, source_info, processed_at)
        VALUES (%s, %s, %s, %s);
        """
    ).format(sql.Identifier(dlq_table_name))

    try:
        # Convert record data to JSON string to store in TEXT or JSONB column.
        # Use default=str for non-serializable types like datetime.
        record_json = json.dumps(failed_record_data, default=str)
        timestamp_now = datetime.now()

        with conn.cursor() as cursor:
            cursor.execute(
                dlq_insert_stmt,
                (record_json, error_reason, source_info, timestamp_now),
            )
        conn.commit()  # Commit DLQ insert immediately or batch them if preferred.
        module_logger.debug(
            f"Record/Info logged to DLQ table '{dlq_table_name}' "
            f"for source: {source_info}"
        )
    except psycopg2.Error as e_db_dlq:
        conn.rollback()  # Rollback if DLQ insert fails.
        module_logger.error(
            f"Database error inserting record into DLQ table "
            f"'{dlq_table_name}': {e_db_dlq}",
            exc_info=True,
        )
    except Exception as e_unexpected_dlq:
        conn.rollback()
        module_logger.error(
            f"Unexpected error logging to DLQ table '{dlq_table_name}': "
            f"{e_unexpected_dlq}",
            exc_info=True,
        )
