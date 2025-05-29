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
    if pd.isna(value):  # Handles None, NaN, NaT, and pd.NA introduced in Pandas 2
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
        module_logger.warning(
            f"Could not convert value to string for cleaning: {type(value)}"
        )
        return None


def create_point_wkt(lon: Any, lat: Any, srid: int = 4326) -> Optional[str]:
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
        # Using pd.isna to robustly handle None, np.nan, and pd.NA (from Pandas 2+)
        if pd.isna(lat) or (isinstance(lat, str) and not str(lat).strip()):
            module_logger.debug(
                f"Missing or invalid latitude for WKT creation: lat='{lat}'"
            )
            return None
        if pd.isna(lon) or (isinstance(lon, str) and not str(lon).strip()):
            module_logger.debug(
                f"Missing or invalid longitude for WKT creation: lon='{lon}'"
            )
            return None

        lat_float = float(lat)
        lon_float = float(lon)

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
            f"Could not create POINT WKT due to invalid latitude/longitude "
            f"conversion: lat='{lat}', lon='{lon}'. Error: {e}"
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
    table_name_for_log = file_schema_info.get(
        "db_table_name", "unknown table"
    )
    if df.empty:
        module_logger.info(
            f"DataFrame for {table_name_for_log} is empty. "
            "No transformation needed."
        )
        expected_cols = list(file_schema_info.get("columns", {}).keys())
        geom_col_name = file_schema_info.get("geom_config", {}).get(
            "geom_col"
        )
        if geom_col_name and geom_col_name not in expected_cols:
            expected_cols.append(geom_col_name)
        return pd.DataFrame(columns=expected_cols)

    module_logger.debug(
        f"Starting transformation for {table_name_for_log}. "
        f"Initial columns: {df.columns.tolist()}"
    )

    transformed_df = df.copy()

    expected_db_columns = list(file_schema_info.get("columns", {}).keys())
    if not expected_db_columns:
        module_logger.warning(
            f"No columns defined in schema for {table_name_for_log}. "
            "Returning raw DataFrame (or its copy)."
        )
        return transformed_df

    geom_config = file_schema_info.get("geom_config")
    final_columns_ordered = list(expected_db_columns)

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
        elif (
            lat_col in transformed_df.columns
            and lon_col in transformed_df.columns
        ):
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
            if geom_col_name and geom_col_name not in transformed_df.columns:
                transformed_df[geom_col_name] = None
            if geom_col_name and geom_col_name not in final_columns_ordered:
                final_columns_ordered.append(geom_col_name)

    output_df = pd.DataFrame()
    for col_name in final_columns_ordered:
        if col_name not in transformed_df.columns:
            module_logger.debug(
                f"Column '{col_name}' from schema not in DataFrame for "
                f"{table_name_for_log}; adding as None."
            )
            output_df[col_name] = None
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
        "shape_id",
        "shape_pt_lon",
        "shape_pt_lat",
        "shape_pt_sequence",
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

    working_df = shapes_points_df[required_cols].copy()

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

    # Pandas 2: inplace=True is generally discouraged.
    working_df = working_df.dropna(
        subset=required_cols
    )
    if working_df.empty:
        module_logger.warning(
            "No valid shape points remaining after data type "
            "conversion and NaN/pd.NA drop. Returning empty LineString DataFrame."
        )
        return pd.DataFrame(columns=["shape_id", "geom"])

    sorted_shapes = working_df.sort_values(
        by=["shape_id", "shape_pt_sequence"]
    )

    lines_data = []
    for shape_id, group in sorted_shapes.groupby("shape_id"):
        if len(group) < 2:
            module_logger.debug(
                f"Shape_id '{shape_id}' has fewer than 2 valid, ordered "
                "points. Skipping LineString creation for this shape."
            )
            continue

        coords_str = ", ".join(
            f"{row.shape_pt_lon} {row.shape_pt_lat}"
            for _, row in group.iterrows()
        )
        wkt_linestring = f"SRID=4326;LINESTRING({coords_str})"
        lines_data.append({"shape_id": shape_id, "geom": wkt_linestring})

    lines_df = pd.DataFrame(lines_data)
    module_logger.info(
        f"Aggregated shape points into {len(lines_df)} LineStrings."
    )
    return lines_df


# Example Usage (for testing this module directly)
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(message)s",
    )
    module_logger.info("--- Testing osm.processors.gtfs.transform.py ---")

    mock_stop_schema = {
        "db_table_name": "gtfs_stops",
        "columns": {
            "stop_id": {"type": "TEXT", "pk": True},
            "stop_name": {"type": "TEXT"},
            "stop_lat": {"type": "DOUBLE PRECISION"},
            "stop_lon": {"type": "DOUBLE PRECISION"},
            "location_type": {"type": "INTEGER"},
        },
        "geom_config": {
            "lat_col": "stop_lat",
            "lon_col": "stop_lon",
            "geom_col": "geom",
            "srid": 4326,
        },
    }

    raw_stop_data = {
        "stop_id": ["s1", "s2", "s3", "s4", "s5", "s6", "s7"],
        "stop_name": [
            " Stop One ",
            "Stop Two",
            "Stop Three (No Coords)",
            "Stop Four (Bad Coords)",
            "Stop Five ",
            None,
            pd.NA
        ],
        "stop_lat": ["40.7128 ", "40.7321", None, "95.0", " ", "40.0", pd.NA],
        "stop_lon": [
            " -74.0060",
            "-74.0001",
            "-74.0010",
            "-74.0020",
            "-74.0030 ",
            pd.NA,
            "-74.0050"
        ],
        "extra_column": ["a", "b", "c", "d", "e", "f", "g"],
        "location_type": [0, 1, None, 0, 2, 1, 0],
    }
    raw_stops_df = pd.DataFrame(raw_stop_data)
    raw_stops_df['stop_name'] = raw_stops_df['stop_name'].astype(pd.StringDtype())
    raw_stops_df['stop_lat'] = raw_stops_df['stop_lat'].astype(pd.StringDtype())
    raw_stops_df['stop_lon'] = raw_stops_df['stop_lon'].astype(pd.StringDtype())


    module_logger.info(f"Raw stops DataFrame:\n{raw_stops_df}")
    module_logger.info(f"Raw stops DataFrame dtypes:\n{raw_stops_df.dtypes}")


    transformed_stops_df = transform_dataframe(raw_stops_df, mock_stop_schema)
    module_logger.info(
        f"\nTransformed stops DataFrame:\n{transformed_stops_df}"
    )
    module_logger.info(
        "Transformed stops DataFrame columns: "
        f"{transformed_stops_df.columns.tolist()}"
    )
    module_logger.info(
        f"Transformed stops dtypes:\n{transformed_stops_df.dtypes}"
    )

    mock_shapes_points_data = {
        "shape_id": [
            "shp1", "shp1", "shp1", "shp2", "shp2_bad_seq", "shp3_one_pt", "shp1",
            "shp4_good", "shp4_good", "shp5_all_na", "shp5_all_na",
        ],
        "shape_pt_lat": [40.0, 40.1, 40.2, 39.0, "invalid_lat", 38.0, 39.9, 41.0, 41.1, pd.NA, pd.NA],
        "shape_pt_lon": [-74.0, -74.1, -74.2, -73.0, -73.1, -72.0, -73.9, -75.0, -75.1, pd.NA, pd.NA],
        "shape_pt_sequence": [
            1, 3, 2, 1, "not_a_num", 1, 0, 0, 1, 0, 1,
        ],
    }
    raw_shapes_df = pd.DataFrame(mock_shapes_points_data)
    raw_shapes_df['shape_pt_lat'] = raw_shapes_df['shape_pt_lat']
    raw_shapes_df['shape_pt_lon'] = raw_shapes_df['shape_pt_lon']
    raw_shapes_df['shape_pt_sequence'] = raw_shapes_df['shape_pt_sequence']

    module_logger.info(f"\nRaw shapes points DataFrame:\n{raw_shapes_df}")
    module_logger.info(f"Raw shapes dtypes:\n{raw_shapes_df.dtypes}")


    shapes_lines_df = transform_shape_points_to_lines_df(raw_shapes_df)
    module_logger.info(
        f"\nTransformed shapes lines DataFrame:\n{shapes_lines_df}"
    )

    module_logger.info(
        "--- osm.processors.gtfs.transform.py test finished ---"
    )