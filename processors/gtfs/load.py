#!/usr/bin/env python3
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

logger = logging.getLogger(__name__)


def get_table_columns(
        cursor: psycopg2.extensions.cursor,
        table_name: str,
        schema: str = "public",
) -> Optional[List[str]]:
    """Fetches column names for a given table."""
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
            logger.warning(
                f"No columns found for table {schema}.{table_name}. Does the table exist?"
            )
            return None
        return columns
    except psycopg2.Error as e:
        logger.error(
            f"Error fetching columns for table {schema}.{table_name}: {e}"
        )
        return None


def load_dataframe_to_db(
        conn: psycopg2.extensions.connection,
        df: pd.DataFrame,
        table_name: str,
        schema_definition: Dict[str, Any],  # From schema_definitions.py
        dlq_table_name: Optional[str] = None,
) -> Tuple[int, int]:
    """
    Loads a Pandas DataFrame into a specified PostgreSQL table.
    Routes failing records to a Dead-Letter Queue (DLQ) table if specified.

    Args:
        conn: Active psycopg2 connection object.
        df: Pandas DataFrame to load.
        table_name: Name of the target production table.
        schema_definition: Schema details for the table (from GTFS_SCHEMA).
        dlq_table_name: Optional name of the DLQ table for this entity.

    Returns:
        Tuple[int, int]: Number of records successfully loaded, number of records sent to DLQ.
    """
    if df.empty:
        logger.info(f"DataFrame for {table_name} is empty. Nothing to load.")
        return 0, 0

    cursor = conn.cursor()
    successful_loads = 0
    dlq_inserts = 0

    # Get target table columns from schema_definition, not directly from DB for this load logic
    # This assumes schema_definition keys in 'columns' match DataFrame columns after transformation.
    target_table_cols_from_schema = list(
        schema_definition.get("columns", {}).keys()
    )

    # Add geometry column if it's part of the schema definition (e.g., for stops)
    # The DataFrame should have this column pre-calculated as WKT by the transform step.
    geom_config = schema_definition.get("geom_config")
    if (
            geom_config
            and geom_config.get("geom_col") not in target_table_cols_from_schema
    ):
        target_table_cols_from_schema.append(geom_config.get("geom_col"))

    # Ensure DataFrame columns match and are in the order of target_table_cols_from_schema
    # This is crucial for execute_values or COPY.
    # For simplicity, this example assumes the transform step already prepared the DataFrame
    # with columns matching schema_definition['columns'] plus the geom_col if applicable.
    # A more robust version would reorder/select df columns based on target_table_cols_from_schema.

    # Select only columns that are expected in the target table based on schema_definition
    # and are present in the DataFrame
    df_cols_to_load = [
        col for col in target_table_cols_from_schema if col in df.columns
    ]

    if not df_cols_to_load:
        logger.error(
            f"No matching columns found between DataFrame and schema for table {table_name}. Cannot load."
        )
        return 0, 0

    df_to_load_final = df[
        df_cols_to_load
    ].copy()  # Use a copy to avoid modifying original df

    # Convert DataFrame to list of tuples for execute_values
    # NaNs should be converted to None for PostgreSQL NULL.
    # The transform step should ideally handle type conversions to strings suitable for DB.
    # For geometry, it should be WKT string.
    try:
        data_tuples = [
            tuple(x)
            for x in df_to_load_final.replace(
                {pd.NA: None, float("nan"): None}
            ).to_numpy()
        ]
    except Exception as e:
        logger.error(
            f"Error converting DataFrame for {table_name} to tuples: {e}"
        )
        return 0, 0

    # Truncate production table before loading new data
    try:
        logger.info(f"Truncating production table: {table_name}...")
        cursor.execute(
            sql.SQL("TRUNCATE TABLE {} CASCADE;").format(
                sql.Identifier(table_name)
            )
        )
        logger.info(f"Table {table_name} truncated.")
    except psycopg2.Error as e:
        logger.error(f"Error truncating table {table_name}: {e}")
        conn.rollback()
        return 0, 0  # Cannot proceed if truncate fails

    # Prepare insert statement
    # Quoted column names for SQL
    quoted_cols = [sql.Identifier(col) for col in df_cols_to_load]
    cols_sql_str = sql.SQL(", ").join(quoted_cols)

    # Placeholders for values
    placeholders = sql.SQL(", ").join(
        [sql.Placeholder()] * len(df_cols_to_load)
    )

    insert_stmt = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table_name), cols_sql_str, placeholders
    )

    # If geometry column is present, it needs ST_GeomFromText wrapper
    if geom_config and geom_config.get("geom_col") in df_cols_to_load:
        geom_col_name = geom_config.get("geom_col")
        srid = geom_config.get("srid", 4326)

        # Find index of geometry column
        try:
            geom_col_idx = df_cols_to_load.index(geom_col_name)
        except ValueError:
            logger.error(
                f"Geometry column '{geom_col_name}' defined in schema but not found in DataFrame columns for {table_name}."
            )
            return 0, 0

        # Rebuild placeholders to wrap geom column with ST_GeomFromText
        ph_list = [sql.Placeholder()] * len(df_cols_to_load)
        ph_list[geom_col_idx] = sql.SQL(
            "ST_SetSRID(ST_GeomFromText({}), {})"
        ).format(sql.Placeholder(), sql.Literal(srid))
        placeholders = sql.SQL(", ").join(ph_list)

        insert_stmt = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(table_name), cols_sql_str, placeholders
        )

    logger.info(
        f"Attempting to load {len(data_tuples)} records into {table_name}..."
    )
    try:
        # Using execute_values for batch insert
        # Page size can be tuned
        execute_values(
            cursor, insert_stmt.as_string(conn), data_tuples, page_size=1000
        )
        successful_loads = (
            cursor.rowcount
            if cursor.rowcount is not None
            else len(data_tuples)
        )  # execute_values might not set rowcount directly
        conn.commit()
        logger.info(
            f"Successfully loaded {successful_loads} records into {table_name}."
        )
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(
            f"Error during bulk insert into {table_name}: {e}. No records loaded into production table."
        )
        # If bulk insert fails, we could attempt row-by-row insert with DLQ,
        # but that's much slower and more complex.
        # For now, if bulk fails, all are considered failed for this table.
        # A more granular DLQ would happen at the validation/transform stage before this function.
        # This load function assumes data is already validated and transformed.
        # If dlq_table_name is provided, we might log failed batch to a general log.
        if dlq_table_name:
            logger.error(
                f"Batch failed for {table_name}. Consider routing original DataFrame to {dlq_table_name} if this was due to data issues not caught earlier."
            )
            # Simple DLQ for entire failed batch (example, may need more context)
            # for row_tuple in data_tuples:
            #     log_to_dlq(conn, dlq_table_name, dict(zip(df_cols_to_load, row_tuple)), "Batch insert failed", "Entire batch")

    except Exception as e:
        conn.rollback()
        logger.error(
            f"Unexpected error during data load for {table_name}: {e}",
            exc_info=True,
        )

    cursor.close()
    return (
        successful_loads,
        dlq_inserts,
    )  # dlq_inserts is 0 for now with this batch approach


def log_to_dlq(
        conn: psycopg2.extensions.connection,
        dlq_table_name: str,
        failed_record: Dict,  # Original record (or as dict)
        error_reason: str,
        source_info: str,  # e.g., filename, line number
):
    """
    Logs a failed record to the specified Dead-Letter Queue table.
    Assumes DLQ table has columns: original_data (JSONB/TEXT), error_reason (TEXT),
                                   source_info (TEXT), processed_at (TIMESTAMP).
    """
    cursor = conn.cursor()
    dlq_insert_stmt = sql.SQL(
        """
        INSERT INTO {} (original_data, error_reason, source_info, processed_at)
        VALUES (%s, %s, %s, %s);
        """
    ).format(sql.Identifier(dlq_table_name))

    try:
        # Convert record to JSON string to store in TEXT or JSONB column
        import json

        record_json = json.dumps(
            failed_record, default=str
        )  # default=str for non-serializable types

        cursor.execute(
            dlq_insert_stmt,
            (record_json, error_reason, source_info, datetime.now()),
        )
        conn.commit()  # Commit DLQ insert immediately or batch them
        logger.debug(f"Record logged to DLQ {dlq_table_name}: {source_info}")
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(
            f"Error inserting record into DLQ table {dlq_table_name}: {e}"
        )
    except Exception as e:
        conn.rollback()
        logger.error(
            f"Unexpected error logging to DLQ {dlq_table_name}: {e}",
            exc_info=True,
        )
    finally:
        cursor.close()
