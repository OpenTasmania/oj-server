#!/usr/bin/env python3
import logging
from typing import Dict, Any, Optional

import pandas as pd

# Import Pydantic models and schema definitions if needed for reference or type hints
# from . import schema_definitions as schemas

logger = logging.getLogger(__name__)


def clean_string_field(value: Any) -> Optional[str]:
    """
    Cleans a string field: strips whitespace. Converts None or empty strings to None.
    """
    if isinstance(value, str):
        stripped_value = value.strip()
        return stripped_value if stripped_value else None
    elif value is None:
        return None
    # If it's a number or other type, Pydantic should have caught it earlier if schema expects str.
    # For robustness, convert to string and strip, then check if empty.
    stripped_value = str(value).strip()
    return stripped_value if stripped_value else None


def create_point_wkt(lon: Any, lat: Any, srid: int = 4326) -> Optional[str]:
    """
    Creates a WKT string for a PostGIS Point geometry if lat/lon are valid.
    Returns None if lat or lon are invalid or cannot be converted to float.
    """
    try:
        # Ensure lon and lat can be converted to float and are not None or empty strings
        if (
            lon is None
            or lat is None
            or str(lon).strip() == ""
            or str(lat).strip() == ""
        ):
            logger.debug(
                f"Missing lat or lon for WKT creation: lat='{lat}', lon='{lon}'"
            )
            return None

        lon_float = float(lon)
        lat_float = float(lat)

        # Basic range check (Pydantic models should enforce this more strictly)
        if not (-90 <= lat_float <= 90 and -180 <= lon_float <= 180):
            logger.warning(
                f"Invalid lat/lon values for WKT: lat={lat_float}, lon={lon_float}"
            )
            return None

        return f"SRID={srid};POINT({lon_float} {lat_float})"
    except (ValueError, TypeError) as e:
        logger.warning(
            f"Could not create POINT WKT due to invalid lat/lon: lat='{lat}', lon='{lon}'. Error: {e}"
        )
        return None


def transform_dataframe(
    df: pd.DataFrame, file_schema_info: Dict[str, Any]
) -> pd.DataFrame:
    """
    Transforms a DataFrame based on GTFS schema info.
    - Applies generic cleaning (e.g., string stripping).
    - Creates geometry WKT strings if 'geom_config' is present in schema.
    - Ensures all columns defined in schema_info['columns'] exist, adding them with None if missing.

    Args:
        df: Pandas DataFrame of raw GTFS data for a single file.
        file_schema_info: The schema definition for this GTFS file from GTFS_FILE_SCHEMAS.

    Returns:
        Pandas DataFrame with transformed data, ready for loading.
        It will only contain columns defined in the schema.
    """
    if df.empty:
        logger.info(
            f"DataFrame for {file_schema_info.get('table_name', 'unknown table')} is empty. No transformation needed."
        )
        return df

    logger.debug(
        f"Starting transformation for {file_schema_info.get('table_name', 'unknown table')}. Initial columns: {df.columns.tolist()}"
    )

    transformed_df = df.copy()

    # Get expected columns from the schema definition
    expected_cols = list(file_schema_info.get("columns", {}).keys())
    if not expected_cols:
        logger.warning(
            f"No columns defined in schema for {file_schema_info.get('table_name')}. Returning raw DataFrame."
        )
        return transformed_df

    # String cleaning for all columns that are expected to be strings (or objects by pandas)
    for col in transformed_df.columns:
        if (
            col in file_schema_info.get("columns", {})
            and transformed_df[col].dtype == "object"
        ):
            # Pydantic models handle stripping via anystr_strip_whitespace.
            # This is a fallback or general cleaner if Pydantic validation is done separately.
            # For now, we assume Pydantic models are the primary validator.
            # If data comes directly from CSV without Pydantic parsing first, this is useful:
            # transformed_df[col] = transformed_df[col].apply(clean_string_field)
            pass  # Assuming Pydantic models (used in validate.py) handle string cleaning.

    # Create PostGIS geometry WKT string if configured in schema
    geom_config = file_schema_info.get("geom_config")
    if geom_config:
        lat_col = geom_config.get("lat_col")
        lon_col = geom_config.get("lon_col")
        geom_col = geom_config.get("geom_col")
        srid = geom_config.get("srid", 4326)

        if (
            lat_col in transformed_df.columns
            and lon_col in transformed_df.columns
            and geom_col
        ):
            logger.debug(
                f"Creating WKT for geometry column '{geom_col}' from '{lat_col}' and '{lon_col}'."
            )
            transformed_df[geom_col] = transformed_df.apply(
                lambda row: create_point_wkt(
                    row.get(lon_col), row.get(lat_col), srid
                ),
                axis=1,
            )
            if (
                geom_col not in expected_cols
            ):  # Add geom_col to expected if generated
                expected_cols.append(geom_col)
        else:
            logger.warning(
                f"Latitude ('{lat_col}') or Longitude ('{lon_col}') columns not found in DataFrame for geometry creation. Skipping '{geom_col}'."
            )
            if (
                geom_col and geom_col not in transformed_df.columns
            ):  # Ensure geom col exists if expected, even if null
                transformed_df[geom_col] = None

    # Ensure all columns defined in the schema exist in the DataFrame, adding missing ones with None.
    # Also reorders/selects columns to match the schema definition order for loading.
    final_columns = []
    for col_name in expected_cols:
        if col_name not in transformed_df.columns:
            logger.debug(
                f"Column '{col_name}' not in DataFrame for {file_schema_info.get('table_name')}, adding as None."
            )
            transformed_df[col_name] = None
        final_columns.append(col_name)

    # Select and reorder columns to match schema definition for consistency
    try:
        transformed_df = transformed_df[final_columns]
    except KeyError as e:
        logger.error(
            f"KeyError during column selection/reordering for {file_schema_info.get('table_name')}: {e}. This might indicate a mismatch between DataFrame columns and schema definition after processing."
        )
        logger.error(f"DataFrame columns: {transformed_df.columns.tolist()}")
        logger.error(f"Expected columns (final_columns): {final_columns}")
        # Potentially return original df or raise error
        return df  # Or an empty df of expected structure to avoid load errors

    logger.debug(
        f"Transformation complete for {file_schema_info.get('table_name', 'unknown table')}. Final columns: {transformed_df.columns.tolist()}"
    )
    return transformed_df


def transform_shape_points_to_lines_df(
    shapes_points_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Transforms a DataFrame of GTFS shapes.txt points into a DataFrame of LineString geometries,
    one per shape_id. This is for preparing data for the gtfs_shapes_lines table.

    Args:
        shapes_points_df: DataFrame corresponding to shapes.txt, must contain
                          shape_id, shape_pt_lon, shape_pt_lat, shape_pt_sequence.
                          Assumes Pydantic validation/coercion has occurred.

    Returns:
        A DataFrame with columns 'shape_id' and 'geom' (WKT LineString).
    """
    if shapes_points_df.empty:
        logger.info(
            "Shapes points DataFrame is empty. No lines to transform."
        )
        return pd.DataFrame(columns=["shape_id", "geom"])

    required_cols = [
        "shape_id",
        "shape_pt_lon",
        "shape_pt_lat",
        "shape_pt_sequence",
    ]
    if not all(col in shapes_points_df.columns for col in required_cols):
        logger.error(
            f"Shapes points DataFrame is missing one or more required columns: {required_cols}"
        )
        return pd.DataFrame(columns=["shape_id", "geom"])

    logger.info(
        f"Aggregating {len(shapes_points_df)} shape points into LineStrings..."
    )

    # Ensure correct data types for sorting and geometry creation
    try:
        shapes_points_df["shape_pt_lon"] = pd.to_numeric(
            shapes_points_df["shape_pt_lon"], errors="coerce"
        )
        shapes_points_df["shape_pt_lat"] = pd.to_numeric(
            shapes_points_df["shape_pt_lat"], errors="coerce"
        )
        shapes_points_df["shape_pt_sequence"] = pd.to_numeric(
            shapes_points_df["shape_pt_sequence"], errors="coerce"
        )
    except Exception as e:
        logger.error(f"Error converting shape point columns to numeric: {e}")
        return pd.DataFrame(columns=["shape_id", "geom"])

    # Drop rows where essential geo-data is missing after coercion
    shapes_points_df.dropna(
        subset=[
            "shape_id",
            "shape_pt_lon",
            "shape_pt_lat",
            "shape_pt_sequence",
        ],
        inplace=True,
    )

    # Sort by shape_id and then by sequence
    sorted_shapes = shapes_points_df.sort_values(
        by=["shape_id", "shape_pt_sequence"]
    )

    lines = []
    for shape_id, group in sorted_shapes.groupby("shape_id"):
        if len(group) < 2:  # Need at least two points to make a line
            logger.debug(
                f"Shape_id '{shape_id}' has fewer than 2 valid points. Skipping LineString creation."
            )
            continue

        # Create coordinate pairs (lon, lat)
        coords = [
            f"{row.shape_pt_lon} {row.shape_pt_lat}"
            for _, row in group.iterrows()
        ]
        wkt_linestring = f"SRID=4326;LINESTRING({', '.join(coords)})"
        lines.append({"shape_id": shape_id, "geom": wkt_linestring})

    lines_df = pd.DataFrame(lines)
    logger.info(f"Aggregated into {len(lines_df)} LineStrings.")
    return lines_df


# Example Usage (for testing this module directly)
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(module)s - %(message)s",
    )
    logger.info("--- Testing transform.py ---")

    # Mock schema definition for stops.txt (subset from schema_definitions.py)
    mock_stop_schema = {
        "table_name": "gtfs_stops",
        "columns": {
            "stop_id": "TEXT PRIMARY KEY",
            "stop_name": "TEXT",
            "stop_lat": "DOUBLE PRECISION",
            "stop_lon": "DOUBLE PRECISION",
            "location_type": "INTEGER",
        },
        "geom_config": {
            "lat_col": "stop_lat",
            "lon_col": "stop_lon",
            "geom_col": "geom",
            "srid": 4326,
        },
    }

    # Sample raw DataFrame (as if read from CSV)
    raw_stop_data = {
        "stop_id": ["s1", "s2", "s3", "s4", "s5"],
        "stop_name": [
            " Stop One ",
            "Stop Two",
            "Stop Three (No Coords)",
            "Stop Four (Bad Coords)",
            "Stop Five ",
        ],
        "stop_lat": [
            "40.7128 ",
            "40.7321",
            None,
            "95.0",
            " ",
        ],  # Note spaces, None, bad value, empty string
        "stop_lon": [
            " -74.0060",
            "-74.0001",
            "-74.0010",
            "-74.0020",
            "-74.0030 ",
        ],
        "extra_column": ["a", "b", "c", "d", "e"],  # This should be ignored
    }
    raw_stops_df = pd.DataFrame(raw_stop_data)
    logger.info(f"Raw stops DataFrame:\n{raw_stops_df}")

    transformed_stops_df = transform_dataframe(raw_stops_df, mock_stop_schema)
    logger.info(f"Transformed stops DataFrame:\n{transformed_stops_df}")
    logger.info(
        f"Transformed stops DataFrame columns: {transformed_stops_df.columns.tolist()}"
    )
    logger.info(f"Transformed stops dtypes:\n{transformed_stops_df.dtypes}")

    # Test shape points to lines transformation
    mock_shapes_points_data = {
        "shape_id": ["shp1", "shp1", "shp1", "shp2", "shp2_bad", "shp3"],
        "shape_pt_lat": [40.0, 40.1, 40.2, 39.0, "invalid", 38.0],
        "shape_pt_lon": [-74.0, -74.1, -74.2, -73.0, -73.1, -72.0],
        "shape_pt_sequence": [
            1,
            2,
            3,
            1,
            1,
            1,
        ],  # shp2_bad has only one point effectively after bad lat
        # shp3 has only one point
        "shape_dist_traveled": [0.0, 1.0, 2.0, 0.0, 0.0, 0.0],
    }
    raw_shapes_df = pd.DataFrame(mock_shapes_points_data)
    logger.info(f"\nRaw shapes points DataFrame:\n{raw_shapes_df}")

    shapes_lines_df = transform_shape_points_to_lines_df(raw_shapes_df)
    logger.info(f"Transformed shapes lines DataFrame:\n{shapes_lines_df}")

    logger.info("--- transform.py test finished ---")
