#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Defines schema information for mapping GTFS concepts to database tables.

This module provides the `GTFS_FILE_SCHEMAS` dictionary. This dictionary is the
central authority for how GTFS files are mapped to the PostgreSQL database.

Key Structure:
- Each key in the top-level dictionary is the name of a GTFS file (e.g., "stops.txt")
  or a conceptual file for tables that are derived from GTFS data (e.g., "gtfs_shapes_lines.txt").

- `db_table_name`: The corresponding table name in the PostgreSQL database.

- `columns`: A dictionary where each key is a column name.
    - `type`: The PostgreSQL data type for the column.
    - `pk`: (boolean) If True, this column is a single-column primary key. For
            composite keys, this is handled by the `pk_cols` list.

- `pk_cols`: A list of column names that form the primary key for the table. This
             is used to add primary key constraints after the table is created,
             and it correctly handles composite keys.

- `geom_config`: For tables with spatial data, this defines the geometry column.
    - `geom_col`: The name of the geometry column.
    - `srid`: The Spatial Reference Identifier (e.g., 4326 for WGS 84).

Note on "gtfs_shapes_lines.txt":
This is a conceptual name for a table that is not directly in the GTFS feed.
It is created by processing the `shapes.txt` data to build LineString geometries
for each route shape.
"""

from typing import Any, Dict

GTFS_FILE_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "agency.txt": {
        "db_table_name": "gtfs_agency",
        "columns": {
            "agency_id": {"type": "TEXT", "pk": True},
            "agency_name": {"type": "TEXT"},
            "agency_url": {"type": "TEXT"},
            "agency_timezone": {"type": "TEXT"},
            "agency_lang": {"type": "TEXT"},
            "agency_phone": {"type": "TEXT"},
            "agency_fare_url": {"type": "TEXT"},
            "agency_email": {"type": "TEXT"},
        },
        "pk_cols": ["agency_id"],
    },
    "stops.txt": {
        "db_table_name": "gtfs_stops",
        "columns": {
            "stop_id": {"type": "TEXT", "pk": True},
            "stop_code": {"type": "TEXT"},
            "stop_name": {"type": "TEXT"},
            "stop_desc": {"type": "TEXT"},
            "stop_lat": {"type": "DOUBLE PRECISION"},
            "stop_lon": {"type": "DOUBLE PRECISION"},
            "zone_id": {"type": "TEXT"},
            "stop_url": {"type": "TEXT"},
            "location_type": {"type": "INTEGER"},
            "parent_station": {"type": "TEXT"},
            "stop_timezone": {"type": "TEXT"},
            "wheelchair_boarding": {"type": "INTEGER"},
            "level_id": {"type": "TEXT"},
            "platform_code": {"type": "TEXT"},
            "geom": {"type": "GEOMETRY(Point, 4326)"},
        },
        "pk_cols": ["stop_id"],
        "geom_config": {
            "geom_col": "geom",
            "srid": 4326,
        },
    },
    "routes.txt": {
        "db_table_name": "gtfs_routes",
        "columns": {
            "route_id": {"type": "TEXT", "pk": True},
            "agency_id": {"type": "TEXT"},
            "route_short_name": {"type": "TEXT"},
            "route_long_name": {"type": "TEXT"},
            "route_desc": {"type": "TEXT"},
            "route_type": {"type": "INTEGER"},
            "route_url": {"type": "TEXT"},
            "route_color": {"type": "TEXT"},
            "route_text_color": {"type": "TEXT"},
            "route_sort_order": {"type": "INTEGER"},
            "continuous_pickup": {"type": "INTEGER"},
            "continuous_drop_off": {"type": "INTEGER"},
        },
        "pk_cols": ["route_id"],
    },
    "trips.txt": {
        "db_table_name": "gtfs_trips",
        "columns": {
            "route_id": {"type": "TEXT"},
            "service_id": {"type": "TEXT"},
            "trip_id": {"type": "TEXT", "pk": True},
            "trip_headsign": {"type": "TEXT"},
            "trip_short_name": {"type": "TEXT"},
            "direction_id": {"type": "INTEGER"},
            "block_id": {"type": "TEXT"},
            "shape_id": {"type": "TEXT"},
            "wheelchair_accessible": {"type": "INTEGER"},
            "bikes_allowed": {"type": "INTEGER"},
        },
        "pk_cols": ["trip_id"],
    },
    "stop_times.txt": {
        "db_table_name": "gtfs_stop_times",
        "columns": {
            "trip_id": {"type": "TEXT"},
            "arrival_time": {"type": "TEXT"},
            "departure_time": {"type": "TEXT"},
            "stop_id": {"type": "TEXT"},
            "stop_sequence": {"type": "INTEGER"},
            "stop_headsign": {"type": "TEXT"},
            "pickup_type": {"type": "INTEGER"},
            "drop_off_type": {"type": "INTEGER"},
            "continuous_pickup": {"type": "INTEGER"},
            "continuous_drop_off": {"type": "INTEGER"},
            "shape_dist_traveled": {"type": "DOUBLE PRECISION"},
            "timepoint": {"type": "INTEGER"},
        },
        "pk_cols": ["trip_id", "stop_sequence"],
    },
    "calendar.txt": {
        "db_table_name": "gtfs_calendar",
        "columns": {
            "service_id": {"type": "TEXT", "pk": True},
            "monday": {"type": "INTEGER"},
            "tuesday": {"type": "INTEGER"},
            "wednesday": {"type": "INTEGER"},
            "thursday": {"type": "INTEGER"},
            "friday": {"type": "INTEGER"},
            "saturday": {"type": "INTEGER"},
            "sunday": {"type": "INTEGER"},
            "start_date": {"type": "TEXT"},
            "end_date": {"type": "TEXT"},
        },
        "pk_cols": ["service_id"],
    },
    "calendar_dates.txt": {
        "db_table_name": "gtfs_calendar_dates",
        "columns": {
            "service_id": {"type": "TEXT"},
            "date": {"type": "TEXT"},
            "exception_type": {"type": "INTEGER"},
        },
        "pk_cols": ["service_id", "date"],
    },
    "shapes.txt": {
        "db_table_name": "gtfs_shapes_points",
        "columns": {
            "shape_id": {"type": "TEXT"},
            "shape_pt_lat": {"type": "DOUBLE PRECISION"},
            "shape_pt_lon": {"type": "DOUBLE PRECISION"},
            "shape_pt_sequence": {"type": "INTEGER"},
            "shape_dist_traveled": {"type": "DOUBLE PRECISION"},
        },
        "pk_cols": ["shape_id", "shape_pt_sequence"],
    },
    "gtfs_shapes_lines.txt": {
        "db_table_name": "gtfs_shapes_lines",
        "columns": {
            "shape_id": {
                "type": "TEXT",
                "pk": True,
            },
            "geom": {"type": "GEOMETRY(LineString, 4326)"},
        },
        "pk_cols": ["shape_id"],
        "geom_config": {
            "geom_col": "geom",
            "srid": 4326,
        },
    },
    "frequencies.txt": {
        "db_table_name": "gtfs_frequencies",
        "columns": {
            "trip_id": {"type": "TEXT"},
            "start_time": {"type": "TEXT"},
            "end_time": {"type": "TEXT"},
            "headway_secs": {"type": "INTEGER"},
            "exact_times": {"type": "INTEGER"},
        },
        "pk_cols": ["trip_id", "start_time"],
    },
    "transfers.txt": {
        "db_table_name": "gtfs_transfers",
        "columns": {
            "from_stop_id": {"type": "TEXT"},
            "to_stop_id": {"type": "TEXT"},
            "transfer_type": {"type": "INTEGER"},
            "min_transfer_time": {"type": "INTEGER"},
        },
        "pk_cols": [
            "from_stop_id",
            "to_stop_id",
            "transfer_type",
        ],
    },
    "feed_info.txt": {
        "db_table_name": "gtfs_feed_info",
        "columns": {
            "feed_publisher_name": {"type": "TEXT"},
            "feed_publisher_url": {"type": "TEXT"},
            "feed_lang": {"type": "TEXT"},
            "default_lang": {"type": "TEXT"},
            "feed_start_date": {"type": "TEXT"},
            "feed_end_date": {"type": "TEXT"},
            "feed_version": {"type": "TEXT"},
            "feed_contact_email": {"type": "TEXT"},
            "feed_contact_url": {"type": "TEXT"},
        },
        "pk_cols": ["feed_publisher_name", "feed_version"],
    },
}
