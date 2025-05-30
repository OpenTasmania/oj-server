#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Handles data transformation for GTFS (General Transit Feed Specification) files,
primarily for aligning with database schema and converting geometries.
"""

import logging
from typing import Any, Dict, Optional

import pandas as pd

module_logger = logging.getLogger(__name__)


def clean_string_field(value: Any) -> Optional[str]:
    """
    Clean a string field by stripping whitespace.

    Converts None, NaN, pd.NA or empty strings (after stripping) to None.
    If the input is not a string, it's converted to a string before processing.

    Args:
        value: The value to clean.

    Returns:
        The cleaned string if it's not empty, otherwise None.
    """
    if pd.isna(value):
        return None
    if isinstance(value, str):
        stripped_value = value.strip()
        return stripped_value if stripped_value else None
    try:
        stripped_value = str(value).strip()
        return stripped_value if stripped_value else None
    except Exception:
        module_logger.warning(
            f"Could not convert value to string for cleaning: {type(value)}"
        )
        return None


def create_point_wkt(lon: Any, lat: Any, srid: int = 4326) -> Optional[str]:
    """
    Create a WKT (Well-Known Text) string for a PostGIS Point geometry.
    This function might be less used if gtfs-kit pre-computes geometries.

    Args:
        lon: Longitude value.
        lat: Latitude value.
        srid: The Spatial Reference System Identifier. Defaults to 4326 (WGS 84).

    Returns:
        A WKT string "SRID=srid;POINT(lon lat)" or None if inputs are invalid.
    """
    try:
        if pd.isna(lat) or (isinstance(lat, str) and not str(lat).strip()):
            return None
        if pd.isna(lon) or (isinstance(lon, str) and not str(lon).strip()):
            return None

        lat_float = float(lat)
        lon_float = float(lon)

        if not (-90 <= lat_float <= 90 and -180 <= lon_float <= 180):
            module_logger.warning(
                f"Invalid latitude/longitude for WKT: lat={lat_float}, lon={lon_float}."
            )
            return None
        return f"SRID={srid};POINT({lon_float} {lat_float})"
    except (ValueError, TypeError) as e:
        module_logger.warning(
            f"Could not create POINT WKT from lat='{lat}', lon='{lon}': {e}"
        )
        return None


def transform_dataframe(
        df: pd.DataFrame, file_schema_info: Dict[str, Any]
) -> pd.DataFrame:
    """
    Transform a DataFrame to align with a database schema definition.

    This function handles geometry conversion (if a 'geometry' column with
    Shapely objects exists, it's converted to WKT for the target 'geom_col'),
    ensures all columns defined in `file_schema_info['columns']` exist
    (adding them with None if missing), and orders columns according to the schema.

    Args:
        df: Pandas DataFrame (potentially from gtfs-kit, may include Shapely geometries).
        file_schema_info: Schema definition for the target database table.
                          It should contain 'columns' (dictionary of column names to their
                          definitions/types) and optionally 'geom_config' (dictionary
                          specifying 'geom_col' as target DB geometry column name and 'srid').

    Returns:
        A Pandas DataFrame transformed and aligned for database loading.
    """
    table_name_for_log = file_schema_info.get("db_table_name", "unknown table")
    if df.empty:
        module_logger.info(f"DataFrame for {table_name_for_log} is empty. No transformation.")
        expected_cols = list(file_schema_info.get("columns", {}).keys())
        geom_col_name_from_config = file_schema_info.get("geom_config", {}).get("geom_col")
        if geom_col_name_from_config and geom_col_name_from_config not in expected_cols:
            expected_cols.append(geom_col_name_from_config)
        return pd.DataFrame(columns=expected_cols)

    module_logger.debug(
        f"Transforming DataFrame for {table_name_for_log}. Initial columns: {df.columns.tolist()}"
    )
    transformed_df = df.copy()

    expected_db_columns_ordered = list(file_schema_info.get("columns", {}).keys())
    if not expected_db_columns_ordered:
        module_logger.warning(f"No columns defined in schema for {table_name_for_log}. Returning as is.")
        return transformed_df

    geom_config = file_schema_info.get("geom_config")
    db_geom_col_name: Optional[str] = None

    if geom_config:
        db_geom_col_name = geom_config.get("geom_col")
        if db_geom_col_name:
            if db_geom_col_name not in expected_db_columns_ordered:
                expected_db_columns_ordered.append(db_geom_col_name)

            srid = geom_config.get("srid", 4326)

            if 'geometry' in transformed_df.columns:  # Source column from gtfs-kit often named 'geometry'
                module_logger.debug(
                    f"Converting 'geometry' (Shapely objects) to WKT for target column '{db_geom_col_name}' in {table_name_for_log}")
                transformed_df[db_geom_col_name] = transformed_df['geometry'].apply(
                    lambda geom_obj: f"SRID={srid};{geom_obj.wkt}" if geom_obj and not pd.isna(geom_obj) else None
                )
            elif db_geom_col_name in transformed_df.columns and transformed_df[db_geom_col_name].dtype == 'object':
                module_logger.debug(
                    f"Target geometry column '{db_geom_col_name}' already exists in DataFrame for {table_name_for_log}, assuming it's WKT.")
            elif geom_config.get("lat_col") and geom_config.get("lon_col"):  # Fallback if no pre-computed geometry
                lat_col = geom_config["lat_col"]
                lon_col = geom_config["lon_col"]
                if lat_col in transformed_df.columns and lon_col in transformed_df.columns:
                    module_logger.info(
                        f"Creating WKT for '{db_geom_col_name}' from source columns '{lat_col}' and '{lon_col}' in {table_name_for_log}.")
                    transformed_df[db_geom_col_name] = transformed_df.apply(
                        lambda row: create_point_wkt(row.get(lon_col), row.get(lat_col), srid), axis=1
                    )
                else:
                    module_logger.warning(
                        f"Source lat/lon columns ('{lat_col}', '{lon_col}') for geometry missing in {table_name_for_log}. Target column '{db_geom_col_name}' will be None.")
                    transformed_df[db_geom_col_name] = None
            elif db_geom_col_name not in transformed_df.columns:  # If no geometry source, ensure column exists
                module_logger.debug(
                    f"No source identified for geometry column '{db_geom_col_name}' in {table_name_for_log}. Column will be added with None values.")
                transformed_df[db_geom_col_name] = None
        else:
            module_logger.warning(
                f"geom_config was provided for {table_name_for_log} but it is missing the 'geom_col' key to specify target DB geometry column name.")

    output_df = pd.DataFrame()
    for col_name in expected_db_columns_ordered:
        if col_name in transformed_df.columns:
            output_df[col_name] = transformed_df[col_name]
        else:
            module_logger.debug(
                f"Database schema column '{col_name}' not found in transformed DataFrame for {table_name_for_log}; adding it with None values.")
            output_df[col_name] = pd.Series([None] * len(transformed_df), dtype='object')

    module_logger.debug(
        f"Transformation complete for {table_name_for_log}. Final columns for DB load: {output_df.columns.tolist()}")
    return output_df