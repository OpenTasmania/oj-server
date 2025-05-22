#!/usr/bin/env python3
import logging
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values

logger = logging.getLogger(__name__)


def get_table_columns(cursor: psycopg2.extensions.cursor, table_name: str, schema: str = 'public') -> Optional[
    List[str]]:
    """Fetches column names for a given table."""
    try:
        cursor.execute(sql.SQL("""
                               SELECT column_name
                               FROM information_schema.columns
                               WHERE table_schema = %s
                                 AND table_name = %s
                               ORDER BY ordinal_position;
                               """), (schema, table_name))
        columns = [row[0] for row in cursor.fetchall()]
        if not columns:
            logger.warning(f"No columns found for table {schema}.{table_name}. Does the table exist?")
            return None
        return columns
    except psycopg2.Error as e:
        logger.error(f"Error fetching columns for table {schema}.{table_name}: {e}")
        return None


def load_dataframe_to_db(
        conn: psycopg2.extensions.connection,
        df: pd.DataFrame,
        table_name: str,
        schema_definition: Dict[str, Any],  # From schema_definitions.py
        dlq_table_name: Optional[str] = None
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
    target_table_cols_from_schema = list(schema_definition.get("columns", {}).keys())

    # Add geometry column if it's part of the schema definition (e.g., for stops)
    # The DataFrame should have this column pre-calculated as WKT by the transform step.
    geom_config = schema_definition.get("geom_config")
    if geom_config and geom_config.get("geom_col") not in target_table_cols_from_schema:
        target_table_cols_from_schema.append(geom_config.get("geom_col"))

    # Ensure DataFrame columns match and are in the order of target_table_cols_from_schema
    # This is crucial for execute_values or COPY.
    # For simplicity, this example assumes the transform step already prepared the DataFrame
    # with columns matching schema_definition['columns'] plus the geom_col if applicable.
    # A more robust version would reorder/select df columns based on target_table_cols_from_schema.

    # Select only columns that are expected in the target table based on schema_definition
    # and are present in the DataFrame
    df_cols_to_load = [col for col in target_table_cols_from_schema if col in df.columns]

    if not df_cols_to_load:
        logger.error(f"No matching columns found between DataFrame and schema for table {table_name}. Cannot load.")
        return 0, 0

    df_to_load_final = df[df_cols_to_load].copy()  # Use a copy to avoid modifying original df

    # Convert DataFrame to list of tuples for execute_values
    # NaNs should be converted to None for PostgreSQL NULL.
    # The transform step should ideally handle type conversions to strings suitable for DB.
    # For geometry, it should be WKT string.
    try:
        data_tuples = [tuple(x) for x in df_to_load_final.replace({pd.NA: None, float('nan'): None}).to_numpy()]
    except Exception as e:
        logger.error(f"Error converting DataFrame for {table_name} to tuples: {e}")
        return 0, 0

    # Truncate production table before loading new data
    try:
        logger.info(f"Truncating production table: {table_name}...")
        cursor.execute(sql.SQL("TRUNCATE TABLE {} CASCADE;").format(sql.Identifier(table_name)))
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
    placeholders = sql.SQL(", ").join([sql.Placeholder()] * len(df_cols_to_load))

    insert_stmt = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table_name),
        cols_sql_str,
        placeholders
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
                f"Geometry column '{geom_col_name}' defined in schema but not found in DataFrame columns for {table_name}.")
            return 0, 0

        # Rebuild placeholders to wrap geom column with ST_GeomFromText
        ph_list = [sql.Placeholder()] * len(df_cols_to_load)
        ph_list[geom_col_idx] = sql.SQL("ST_SetSRID(ST_GeomFromText({}), {})").format(sql.Placeholder(),
                                                                                      sql.Literal(srid))
        placeholders = sql.SQL(", ").join(ph_list)

        insert_stmt = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(table_name),
            cols_sql_str,
            placeholders
        )

    logger.info(f"Attempting to load {len(data_tuples)} records into {table_name}...")
    try:
        # Using execute_values for batch insert
        # Page size can be tuned
        execute_values(cursor, insert_stmt.as_string(conn), data_tuples, page_size=1000)
        successful_loads = cursor.rowcount if cursor.rowcount is not None else len(
            data_tuples)  # execute_values might not set rowcount directly
        conn.commit()
        logger.info(f"Successfully loaded {successful_loads} records into {table_name}.")
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"Error during bulk insert into {table_name}: {e}. No records loaded into production table.")
        # If bulk insert fails, we could attempt row-by-row insert with DLQ,
        # but that's much slower and more complex.
        # For now, if bulk fails, all are considered failed for this table.
        # A more granular DLQ would happen at the validation/transform stage before this function.
        # This load function assumes data is already validated and transformed.
        # If dlq_table_name is provided, we might log failed batch to a general log.
        if dlq_table_name:
            logger.error(
                f"Batch failed for {table_name}. Consider routing original DataFrame to {dlq_table_name} if this was due to data issues not caught earlier.")
            # Simple DLQ for entire failed batch (example, may need more context)
            # for row_tuple in data_tuples:
            #     log_to_dlq(conn, dlq_table_name, dict(zip(df_cols_to_load, row_tuple)), "Batch insert failed", "Entire batch")

    except Exception as e:
        conn.rollback()
        logger.error(f"Unexpected error during data load for {table_name}: {e}", exc_info=True)

    cursor.close()
    return successful_loads, dlq_inserts  # dlq_inserts is 0 for now with this batch approach


def log_to_dlq(
        conn: psycopg2.extensions.connection,
        dlq_table_name: str,
        failed_record: Dict,  # Original record (or as dict)
        error_reason: str,
        source_info: str  # e.g., filename, line number
):
    """
    Logs a failed record to the specified Dead-Letter Queue table.
    Assumes DLQ table has columns: original_data (JSONB/TEXT), error_reason (TEXT),
                                   source_info (TEXT), processed_at (TIMESTAMP).
    """
    cursor = conn.cursor()
    dlq_insert_stmt = sql.SQL("""
                              INSERT INTO {} (original_data, error_reason, source_info, processed_at)
                              VALUES (%s, %s, %s, %s);
                              """).format(sql.Identifier(dlq_table_name))

    try:
        # Convert record to JSON string to store in TEXT or JSONB column
        import json
        record_json = json.dumps(failed_record, default=str)  # default=str for non-serializable types

        cursor.execute(dlq_insert_stmt, (record_json, error_reason, source_info, datetime.now()))
        conn.commit()  # Commit DLQ insert immediately or batch them
        logger.debug(f"Record logged to DLQ {dlq_table_name}: {source_info}")
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"Error inserting record into DLQ table {dlq_table_name}: {e}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Unexpected error logging to DLQ {dlq_table_name}: {e}", exc_info=True)
    finally:
        cursor.close()


# Example usage within a larger pipeline (called by main_pipeline.py)
if __name__ == "__main__":
    # This module is intended to be imported, but here's a conceptual test.
    # You would need a database connection and a sample DataFrame.

    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
    logger.info("--- Testing load.py conceptually ---")

    # Dummy connection and data for testing
    try:
        conn_test = psycopg2.connect(**DB_PARAMS)  # Ensure DB_PARAMS is correctly set
        cursor_test = conn_test.cursor()

        # Example: Create a dummy stops table and DLQ table for testing
        dummy_stops_schema = {
            "table_name": "test_gtfs_stops",
            "columns": {
                "stop_id": "TEXT PRIMARY KEY", "stop_name": "TEXT",
                "stop_lat": "DOUBLE PRECISION", "stop_lon": "DOUBLE PRECISION"
            },
            "pk": "stop_id",
            "geom_config": {"lat_col": "stop_lat", "lon_col": "stop_lon", "geom_col": "geom", "srid": 4326}
        }
        dummy_dlq_stops_table = "dlq_test_gtfs_stops"

        cursor_test.execute(sql.SQL("DROP TABLE IF EXISTS {};").format(sql.Identifier(dummy_dlq_stops_table)))
        cursor_test.execute(
            sql.SQL("DROP TABLE IF EXISTS {};").format(sql.Identifier(dummy_stops_schema["table_name"])))

        # Create main table
        cols_def_test = [f"\"{k}\" {v}" for k, v in dummy_stops_schema["columns"].items()]
        cols_def_test.append(
            f"\"{dummy_stops_schema['geom_config']['geom_col']}\" GEOMETRY(Point, {dummy_stops_schema['geom_config']['srid']})")
        pk_test = f", PRIMARY KEY (\"{dummy_stops_schema['pk']}\")" if dummy_stops_schema['pk'] else ""
        cursor_test.execute(sql.SQL("CREATE TABLE {} ({}{});").format(
            sql.Identifier(dummy_stops_schema["table_name"]),
            sql.SQL(", ".join(cols_def_test)),
            sql.SQL(pk_test)
        ))

        # Create DLQ table
        cursor_test.execute(sql.SQL("""
                                    CREATE TABLE IF NOT EXISTS {}
                                    (
                                        id
                                        SERIAL
                                        PRIMARY
                                        KEY,
                                        original_data
                                        JSONB,
                                        error_reason
                                        TEXT,
                                        source_info
                                        TEXT,
                                        processed_at
                                        TIMESTAMP
                                        WITH
                                        TIME
                                        ZONE
                                        DEFAULT
                                        CURRENT_TIMESTAMP
                                    );
                                    """).format(sql.Identifier(dummy_dlq_stops_table)))
        conn_test.commit()

        # Sample DataFrame (assuming it has been validated and transformed)
        # The transform step should produce WKT for geometry if using ST_GeomFromText
        sample_data = {
            'stop_id': ['s1', 's2', 's3_bad_geom'],
            'stop_name': ['Stop 1', 'Stop 2', 'Stop 3 Bad'],
            'stop_lat': [40.71, 40.72, None],  # Valid, Valid, Invalid for geom
            'stop_lon': [-74.00, -74.01, -74.02],  # Valid, Valid, Valid
            'geom': ["POINT(-74.00 40.71)", "POINT(-74.01 40.72)", None]  # Pre-transformed WKT
        }
        sample_df = pd.DataFrame(sample_data)
        # Ensure all columns expected by schema are present or handle missing ones
        # For this test, the DataFrame must match the columns used by load_dataframe_to_db

        # Test loading (DLQ logic in load_dataframe_to_db is currently basic for batch failures)
        # The more granular DLQ happens *before* calling load_dataframe_to_db, in the transform/validate stage.
        # This function primarily loads "good" data.
        logger.info(f"Test loading sample_df into {dummy_stops_schema['table_name']}")

        # Simulate that 'geom' column is used for ST_GeomFromText
        # The df should have the WKT string for the geom column.

        # Re-create DataFrame ensuring order and content match `target_table_cols_from_schema`
        # target_table_cols_from_schema = ['stop_id', 'stop_name', 'stop_lat', 'stop_lon', 'geom']
        test_df_for_load = pd.DataFrame({
            'stop_id': ['s1', 's2'],
            'stop_name': ['Stop 1', 'Stop 2'],
            'stop_lat': [40.71, 40.72],  # These would be used by transform to create WKT
            'stop_lon': [-74.00, -74.01],
            'geom': ["POINT(-74.00 40.71)", "POINT(-74.01 40.72)"]  # WKT string
        })

        loaded, dlq_count = load_dataframe_to_db(conn_test, test_df_for_load, dummy_stops_schema["table_name"],
                                                 dummy_stops_schema, dummy_dlq_stops_table)
        logger.info(f"Test Load: {loaded} records loaded, {dlq_count} sent to DLQ (expected 0 from this function).")

        cursor_test.execute(
            sql.SQL("SELECT COUNT(*) FROM {};").format(sql.Identifier(dummy_stops_schema["table_name"])))
        logger.info(f"Count in {dummy_stops_schema['table_name']}: {cursor_test.fetchone()[0]}")

        # Test the DLQ logging function (this would typically be called from validate.py or transform.py)
        bad_record_example = {'stop_id': 's4_bad', 'stop_name': 'Bad Stop Record', 'stop_lat': 'INVALID_LAT'}
        log_to_dlq(conn_test, dummy_dlq_stops_table, bad_record_example, "Invalid latitude value", "stops.txt line X")
        cursor_test.execute(sql.SQL("SELECT COUNT(*) FROM {};").format(sql.Identifier(dummy_dlq_stops_table)))
        logger.info(f"Count in {dummy_dlq_stops_table}: {cursor_test.fetchone()[0]}")


    except psycopg2.Error as db_err:
        logger.error(f"Test database error: {db_err}")
    except Exception as ex:
        logger.error(f"Test general error: {ex}", exc_info=True)
    finally:
        if 'conn_test' in locals() and conn_test:
            # Clean up test tables
            # cursor_test.execute(sql.SQL("DROP TABLE IF EXISTS {};").format(sql.Identifier(dummy_dlq_stops_table)))
            # cursor_test.execute(sql.SQL("DROP TABLE IF EXISTS {};").format(sql.Identifier(dummy_stops_schema["table_name"])))
            # conn_test.commit()
            cursor_test.close()
            conn_test.close()
            logger.info("Test database connection closed.")

    logger.info("--- load.py test finished ---")
