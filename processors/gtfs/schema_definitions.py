#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Defines schema information for mapping GTFS concepts to database tables.

This module provides the `GTFS_FILE_SCHEMAS` dictionary, which maps GTFS
filenames (or conceptual table names like 'gtfs_shapes_lines.txt') to
their corresponding database table name, column definitions (name and target type),
primary key columns, and geometry configuration. This is used by data loading
and processing components to interact with the PostgreSQL database.
"""

from typing import Any, Dict

GTFS_FILE_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "agency.txt": {
        "db_table_name": "gtfs_agency",
        "columns": {
            "agency_id": {"type": "TEXT", "pk": True},  # Added "pk": True
            "agency_name": {"type": "TEXT"},
            "agency_url": {"type": "TEXT"},
            "agency_timezone": {"type": "TEXT"},
            "agency_lang": {"type": "TEXT"},
            "agency_phone": {"type": "TEXT"},
            "agency_fare_url": {"type": "TEXT"},
            "agency_email": {"type": "TEXT"},
        },
        "pk_cols": ["agency_id"],  # Retained for other potential uses
    },
    "stops.txt": {
        "db_table_name": "gtfs_stops",
        "columns": {
            "stop_id": {"type": "TEXT", "pk": True},  # Added "pk": True
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
            "route_id": {"type": "TEXT", "pk": True},  # Added "pk": True
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
            "trip_id": {"type": "TEXT", "pk": True},  # Added "pk": True
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
            "trip_id": {"type": "TEXT"},  # Part of composite PK
            "arrival_time": {"type": "TEXT"},
            "departure_time": {"type": "TEXT"},
            "stop_id": {"type": "TEXT"},  # Part of composite PK
            "stop_sequence": {
                "type": "INTEGER"
            },  # Part of composite PK, pk handling for composite is different
            "stop_headsign": {"type": "TEXT"},
            "pickup_type": {"type": "INTEGER"},
            "drop_off_type": {"type": "INTEGER"},
            "continuous_pickup": {"type": "INTEGER"},
            "continuous_drop_off": {"type": "INTEGER"},
            "shape_dist_traveled": {"type": "DOUBLE PRECISION"},
            "timepoint": {"type": "INTEGER"},
        },
        # For composite PKs like stop_times, the create_tables_from_schema
        # currently doesn't set them inline. This would typically be handled
        # by an ALTER TABLE ADD PRIMARY KEY statement after table creation if needed.
        # However, stop_times is referenced BY other tables, it doesn't reference others
        # via these columns directly in the provided GTFS_FOREIGN_KEYS.
        # The existing code adds `col_constraints += " PRIMARY KEY"` only if col_props.get("pk") is true.
        # For composite keys, a separate mechanism is needed. The current `create_tables_from_schema`
        # only supports single column PKs this way.
        # Since `stop_times` isn't a target in the provided GTFS_FOREIGN_KEYS, this might be less critical
        # for *this specific error*, but good to note.
        # If pk_cols is intended to define primary keys, then create_tables_from_schema needs modification
        # to handle composite keys from pk_cols, or these should be added separately.
        # For now, no "pk": True is added here as it's a composite key.
        "pk_cols": ["trip_id", "stop_sequence"],
    },
    "calendar.txt": {
        "db_table_name": "gtfs_calendar",
        "columns": {
            "service_id": {"type": "TEXT", "pk": True},  # Added "pk": True
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
            "service_id": {"type": "TEXT"},  # Part of composite PK
            "date": {"type": "TEXT"},  # Part of composite PK
            "exception_type": {"type": "INTEGER"},
        },
        "pk_cols": ["service_id", "date"],  # Composite PK
    },
    "shapes.txt": {  # This is for the points that make up shapes
        "db_table_name": "gtfs_shapes_points",
        "columns": {
            "shape_id": {"type": "TEXT"},  # Part of composite PK
            "shape_pt_lat": {"type": "DOUBLE PRECISION"},
            "shape_pt_lon": {"type": "DOUBLE PRECISION"},
            "shape_pt_sequence": {"type": "INTEGER"},  # Part of composite PK
            "shape_dist_traveled": {"type": "DOUBLE PRECISION"},
        },
        "pk_cols": ["shape_id", "shape_pt_sequence"],  # Composite PK
    },
    "gtfs_shapes_lines.txt": {  # This is a conceptual name for the table holding LineString geometries
        "db_table_name": "gtfs_shapes_lines",  # This table is created with an EXPLICIT PK in update_gtfs.py
        "columns": {
            "shape_id": {
                "type": "TEXT",
                "pk": True,
            },  # "pk": True added for consistency, though creation is separate
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
            "trip_id": {"type": "TEXT"},  # Part of composite PK
            "start_time": {"type": "TEXT"},  # Part of composite PK
            "end_time": {"type": "TEXT"},
            "headway_secs": {"type": "INTEGER"},
            "exact_times": {"type": "INTEGER"},
        },
        "pk_cols": ["trip_id", "start_time"],  # Composite PK
    },
    "transfers.txt": {
        "db_table_name": "gtfs_transfers",
        "columns": {
            "from_stop_id": {"type": "TEXT"},  # Part of composite PK
            "to_stop_id": {"type": "TEXT"},  # Part of composite PK
            "transfer_type": {"type": "INTEGER"},  # Part of composite PK
            "min_transfer_time": {"type": "INTEGER"},
        },
        "pk_cols": [
            "from_stop_id",
            "to_stop_id",
            "transfer_type",
        ],  # Composite PK
    },
    "feed_info.txt": {
        "db_table_name": "gtfs_feed_info",
        "columns": {  # feed_info often doesn't have a single PK, sometimes composite, sometimes none if only one row
            "feed_publisher_name": {
                "type": "TEXT"
            },  # Part of composite PK (as defined in pk_cols)
            "feed_publisher_url": {"type": "TEXT"},
            "feed_lang": {"type": "TEXT"},
            "default_lang": {"type": "TEXT"},
            "feed_start_date": {"type": "TEXT"},
            "feed_end_date": {"type": "TEXT"},
            "feed_version": {"type": "TEXT"},  # Part of composite PK
            "feed_contact_email": {"type": "TEXT"},
            "feed_contact_url": {"type": "TEXT"},
        },
        "pk_cols": ["feed_publisher_name", "feed_version"],  # Composite PK
    },
}
