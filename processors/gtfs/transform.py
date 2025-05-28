#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Handles data transformation for GTFS (General Transit Feed Specification) files.

This module provides functions to clean and transform GTFS data, typically
after it has been read into a Pandas DataFrame and validated. Transformations
include string cleaning, creation of WKT (Well-Known Text) geometry strings
from latitude/longitude, and ensuring DataFrame columns align with a defined
schema. It also includes a function to aggregate GTFS shapes.txt point data
into LineString geometries.
"""

import logging
from typing import Any, Dict, Optional

import pandas as pd

# Import Pydantic models and schema definitions if needed for reference
# or type hints.
# from . import schema_definitions as schemas

module_logger = logging.getLogger(__name__)


def clean_string_field(value: Any) -> Optional[str]:
    """
    Clean a string field by stripping whitespace.

    Converts None or empty strings (after stripping) to None. If the input
    is not a string, it's converted to a string before processing.

    Args:
        value: The value to clean. Can be of any type that can be
               converted to a string.

    Returns:
        The cleaned string if it's not empty, otherwise None.
    """
    if pd.isna(value):  # Handles None, NaN, NaT
        return None
    if isinstance(value, str):
        stripped_value = value.strip()
        return stripped_value if stripped_value else None

    # For non-string types (e.g., numbers), convert to string, strip, and check.
    # This ensures consistency if a field unexpectedly contains non-string data
    # that should be treated as a string.
    try:
        stripped_value = str(value).strip()
        return stripped_value if stripped_value else None
    except Exception:
        # In case str(value) fails for some unusual object.
        module_logger.warning(f"Could not convert value to string for cleaning: {type(value)}")
        return None


def create_point_wkt(
    lon: Any, lat: Any, srid: int = 4326
) -> Optional[str]:
    """
    Create a WKT (Well-Known Text) string for a PostGIS Point geometry.

    Args:
        lon: Longitude value.
        lat: Latitude value.
        srid: The Spatial Reference System Identifier. Defaults to 4326 (WGS 84).

    Returns:
        A WKT string in the format "SRID=srid;POINT(lon lat)" if latitude and
        longitude are valid, otherwise None.
    """
    try:
        # Ensure lon and lat can be converted to float and are not None or empty.
        if (lon is None or str(lon).strip() == "" or
                lat is None or str(lat).strip() == ""):
            module_logger.debug(
                f"Missing latitude or longitude for WKT creation: "
                f"lat='{lat}', lon='{lon}'"
            )
            return None

        lon_float = float(lon)
        lat_float = float(lat)

        # Basic range check for latitude and longitude.
        # Pydantic models used in validation should enforce stricter checks earlier.
        if not (-90 <= lat_float <= 90 and -180 <= lon_float <= 180):
            module_logger.warning(
                f"Invalid latitude/longitude values for WKT: "
                f"lat={lat_float}, lon={lon_float}. Must be within "
                "lat [-90, 90] and lon [-180, 180]."
            )
            return None

        return f"SRID={srid};POINT({lon_float} {lat_float})"
    except (ValueError, TypeError) as e:
        module_logger.warning(
            f"Could not create POINT WKT due to invalid latitude/longitude: "
            f"lat='{lat}', lon='{lon}'. Error: {e}"
        )
        return None


def transform_dataframe(
    df: pd.DataFrame, file_schema_info: Dict[str, Any]
) -> pd.DataFrame:
    """
    Transform a DataFrame based on GTFS schema information.

    This function applies generic cleaning (e.g., string stripping via Pydantic
    models usually handles this during validation), creates geometry WKT strings
    if 'geom_config' is present in the schema, and ensures all columns defined
    in `file_schema_info['columns']` exist, adding them with None if missing.
    The output DataFrame will only contain columns defined in the schema.

    Args:
        df: Pandas DataFrame of raw or Pydantic-validated GTFS data for a
            single file.
        file_schema_info: The schema definition for this GTFS file (e.g., from
                          `schema_definitions.GTFS_FILE_SCHEMAS`). It should
                          contain 'columns' (a dictionary of column names to
                          their definitions) and optionally 'geom_config'.

    Returns:
        A Pandas DataFrame with transformed data, ready for loading. Columns
        will match those specified in the schema and be in the defined order.
    """
    table_name_for_log = file_schema_info.get('db_table_name', 'unknown table')
    if df.empty:
        module_logger.info(
            f"DataFrame for {table_name_for_log} is empty. "
            "No transformation needed."
        )
        # Return an empty DataFrame with columns matching the schema.
        expected_cols = list(file_schema_info.get("columns", {}).keys())
        geom_col_name = file_schema_info.get("geom_config", {}).get("geom_col")
        if geom_col_name and geom_col_name not in expected_cols:
            expected_cols.append(geom_col_name)
        return pd.DataFrame(columns=expected_cols)

    module_logger.debug(
        f"Starting transformation for {table_name_for_log}. "
        f"Initial columns: {df.columns.tolist()}"
    )

    transformed_df = df.copy()

    # Get expected column names from the schema definition.
    # These are the keys of the 'columns' dictionary in file_schema_info.
    expected_db_columns = list(file_schema_info.get("columns", {}).keys())
    if not expected_db_columns:
        module_logger.warning(
            f"No columns defined in schema for {table_name_for_log}. "
            "Returning raw DataFrame (or its copy)."
        )
        return transformed_df

    # String cleaning:
    # Pydantic models (used in a prior validation step) typically handle
    # string stripping (e.g., via GTFSBaseModel's Config).
    # If data comes directly from CSV without Pydantic parsing, explicit
    # cleaning here would be more critical.
    # Example if needed:
    # for col in transformed_df.columns:
    #     if col in expected_db_columns and transformed_df[col].dtype == "object":
    #         transformed_df[col] = transformed_df[col].apply(clean_string_field)

    # Create PostGIS geometry WKT string if configured in the schema.
    geom_config = file_schema_info.get("geom_config")
    final_columns_ordered = list(expected_db_columns)  # Start with DB columns

    if geom_config:
        lat_col = geom_config.get("lat_col")
        lon_col = geom_config.get("lon_col")
        geom_col_name = geom_config.get("geom_col")
        srid = geom_config.get("srid", 4326)

        if not geom_col_name:
            module_logger.warning(
                f"geom_config provided for {table_name_for_log} but "
                f"'geom_col' name is missing. Cannot create geometry column."
            )
        elif lat_col in transformed_df.columns and lon_col in transformed_df.columns:
            module_logger.debug(
                f"Creating WKT for geometry column '{geom_col_name}' from "
                f"'{lat_col}' and '{lon_col}' for {table_name_for_log}."
            )
            transformed_df[geom_col_name] = transformed_df.apply(
                lambda row: create_point_wkt(
                    row.get(lon_col), row.get(lat_col), srid
                ),
                axis=1,
            )
            if geom_col_name not in final_columns_ordered:
                # Add geom_col to the list of columns if it's generated
                # and not already part of the main DB columns (it usually isn't).
                final_columns_ordered.append(geom_col_name)
        else:
            missing_geo_cols = []
            if lat_col not in transformed_df.columns:
                missing_geo_cols.append(lat_col)
            if lon_col not in transformed_df.columns:
                missing_geo_cols.append(lon_col)
            module_logger.warning(
                f"Latitude ('{lat_col}') or Longitude ('{lon_col}') columns "
                f"(missing: {missing_geo_cols}) not found in DataFrame for "
                f"{table_name_for_log}. Skipping geometry creation for '{geom_col_name}'."
            )
            # Ensure geom_col exists if expected by schema, even if null.
            if geom_col_name not in transformed_df.columns:
                transformed_df[geom_col_name] = None
            if geom_col_name not in final_columns_ordered:
                final_columns_ordered.append(geom_col_name)

    # Ensure all columns defined in the schema exist in the DataFrame,
    # adding missing ones with None.
    # Also, select and reorder columns to match the schema definition order.
    output_df = pd.DataFrame()
    for col_name in final_columns_ordered:
        if col_name not in transformed_df.columns:
            module_logger.debug(
                f"Column '{col_name}' from schema not in DataFrame for "
                f"{table_name_for_log}; adding as None."
            )
            output_df[col_name] = None  # Creates a column of NaNs/Nones
        else:
            output_df[col_name] = transformed_df[col_name]

    module_logger.debug(
        f"Transformation complete for {table_name_for_log}. "
        f"Final columns: {output_df.columns.tolist()}"
    )
    return output_df


def transform_shape_points_to_lines_df(
    shapes_points_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Transform a DataFrame of GTFS shapes.txt points into LineString geometries.

    This function aggregates points belonging to the same `shape_id` into
    WKT LineString geometries, suitable for tables like `gtfs_shapes_lines`.
    It assumes that the input DataFrame has already undergone Pydantic
    validation and type coercion for relevant fields.

    Args:
        shapes_points_df: DataFrame corresponding to `shapes.txt` data.
                          Must contain `shape_id`, `shape_pt_lon`,
                          `shape_pt_lat`, and `shape_pt_sequence`.

    Returns:
        A new DataFrame with columns 'shape_id' and 'geom' (WKT LineString).
        Returns an empty DataFrame if input is empty or essential columns
        are missing.
    """
    if shapes_points_df.empty:
        module_logger.info(
            "Shapes points DataFrame is empty. No lines to transform."
        )
        return pd.DataFrame(columns=["shape_id", "geom"])

    required_cols = [
        "shape_id", "shape_pt_lon", "shape_pt_lat", "shape_pt_sequence",
    ]
    missing_cols = [
        col for col in required_cols if col not in shapes_points_df.columns
    ]
    if missing_cols:
        module_logger.error(
            f"Shapes points DataFrame is missing required columns: {missing_cols}. "
            "Cannot create linestrings."
        )
        return pd.DataFrame(columns=["shape_id", "geom"])

    module_logger.info(
        f"Aggregating {len(shapes_points_df)} shape points into LineStrings..."
    )

    # Create a working copy
    working_df = shapes_points_df[required_cols].copy()

    # Ensure correct data types for sorting and geometry creation.
    # Pydantic validation should have handled most of this, but explicit
    # conversion here provides robustness.
    try:
        working_df["shape_pt_lon"] = pd.to_numeric(
            working_df["shape_pt_lon"], errors="coerce"
        )
        working_df["shape_pt_lat"] = pd.to_numeric(
            working_df["shape_pt_lat"], errors="coerce"
        )
        working_df["shape_pt_sequence"] = pd.to_numeric(
            working_df["shape_pt_sequence"], errors="coerce"
        )
    except Exception as e:
        module_logger.error(
            f"Error converting shape point columns to numeric: {e}. "
            "LineString creation may be affected."
        )
        # Depending on severity, could return empty DataFrame here.
        # For now, proceed and let dropna handle issues.

    # Drop rows where essential geo-data or sequence is missing after coercion.
    working_df.dropna(
        subset=required_cols,  # Check all required columns for NaN after coercion
        inplace=True,
    )
    if working_df.empty:
        module_logger.warning(
            "No valid shape points remaining after data type "
            "conversion and NaN drop. Returning empty LineString DataFrame."
        )
        return pd.DataFrame(columns=["shape_id", "geom"])

    # Sort by shape_id and then by sequence to ensure correct line ordering.
    sorted_shapes = working_df.sort_values(
        by=["shape_id", "shape_pt_sequence"]
    )

    lines_data = []
    for shape_id, group in sorted_shapes.groupby("shape_id"):
        if len(group) < 2:  # Need at least two points to make a line.
            module_logger.debug(
                f"Shape_id '{shape_id}' has fewer than 2 valid, ordered "
                "points. Skipping LineString creation for this shape."
            )
            continue

        # Create coordinate pairs (lon, lat) for the WKT string.
        coords_str = ", ".join(
            f"{row.shape_pt_lon} {row.shape_pt_lat}"
            for _, row in group.iterrows()  # Iterate over sorted points in group
        )
        wkt_linestring = f"SRID=4326;LINESTRING({coords_str})"
        lines_data.append({"shape_id": shape_id, "geom": wkt_linestring})

    lines_df = pd.DataFrame(lines_data)
    module_logger.info(f"Aggregated shape points into {len(lines_df)} LineStrings.")
    return lines_df


# Example Usage (for testing this module directly)
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(message)s",
    )
    module_logger.info("--- Testing osm.processors.gtfs.transform.py ---")

    # Mock schema definition for stops.txt
    mock_stop_schema = {
        "db_table_name": "gtfs_stops",  # Changed from table_name for consistency
        "columns": {  # Simulates structure from schema_definitions.py
            "stop_id": {"type": "TEXT", "pk": True},  # Example type/pk info
            "stop_name": {"type": "TEXT"},
            "stop_lat": {"type": "DOUBLE PRECISION"},
            "stop_lon": {"type": "DOUBLE PRECISION"},
            "location_type": {"type": "INTEGER"},
            # "geom" is not in 'columns' but defined by 'geom_config'
        },
        "geom_config": {
            "lat_col": "stop_lat",
            "lon_col": "stop_lon",
            "geom_col": "geom",  # This is the target column name for WKT
            "srid": 4326,
        },
    }

    # Sample raw DataFrame (as if read from CSV or after Pydantic validation)
    raw_stop_data = {
        "stop_id": ["s1", "s2", "s3", "s4", "s5"],
        "stop_name": [
            " Stop One ", "Stop Two", "Stop Three (No Coords)",
            "Stop Four (Bad Coords)", "Stop Five "
        ],
        "stop_lat": ["40.7128 ", "40.7321", None, "95.0", " "],
        "stop_lon": [" -74.0060", "-74.0001", "-74.0010", "-74.0020", "-74.0030 "],
        "extra_column": ["a", "b", "c", "d", "e"],  # This should be dropped
        "location_type": [0, 1, None, 0, 2],  # Added for schema completeness
    }
    raw_stops_df = pd.DataFrame(raw_stop_data)
    module_logger.info(f"Raw stops DataFrame:\n{raw_stops_df}")

    transformed_stops_df = transform_dataframe(raw_stops_df, mock_stop_schema)
    module_logger.info(f"\nTransformed stops DataFrame:\n{transformed_stops_df}")
    module_logger.info(
        "Transformed stops DataFrame columns: "
        f"{transformed_stops_df.columns.tolist()}"
    )
    module_logger.info(f"Transformed stops dtypes:\n{transformed_stops_df.dtypes}")
    # Expected columns based on mock_stop_schema:
    # ['stop_id', 'stop_name', 'stop_lat', 'stop_lon', 'location_type', 'geom']

    # Test shape points to lines transformation
    mock_shapes_points_data = {
        "shape_id": ["shp1", "shp1", "shp1", "shp2", "shp2_bad", "shp3", "shp1"],  # Unordered point for shp1
        "shape_pt_lat": [40.0, 40.1, 40.2, 39.0, "invalid", 38.0, 39.9],
        "shape_pt_lon": [-74.0, -74.1, -74.2, -73.0, -73.1, -72.0, -73.9],
        "shape_pt_sequence": [1, 3, 2, 1, "nan", 1, 0],  # Unordered sequence for shp1, bad seq
    }
    raw_shapes_df = pd.DataFrame(mock_shapes_points_data)
    module_logger.info(f"\nRaw shapes points DataFrame:\n{raw_shapes_df}")

    shapes_lines_df = transform_shape_points_to_lines_df(raw_shapes_df)
    module_logger.info(f"\nTransformed shapes lines DataFrame:\n{shapes_lines_df}")
    # Expected: shp1 should be ordered by sequence (0,1,2,3),
    # shp2 should be skipped (invalid lat), shp3 skipped (1 point)

    module_logger.info("--- osm.processors.gtfs.transform.py test finished ---")