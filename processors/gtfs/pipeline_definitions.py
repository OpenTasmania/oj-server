# processors/gtfs/pipeline_definitions.py
# -*- coding: utf-8 -*-
"""
Static definitions for the GTFS processing pipeline, including table load order
and foreign key relationships.
"""
from typing import List, Tuple

GTFS_LOAD_ORDER: List[str] = [
    "agency.txt", "stops.txt", "routes.txt", "calendar.txt",
    "calendar_dates.txt", "shapes.txt",
    "trips.txt", "stop_times.txt",
    "frequencies.txt", "transfers.txt", "feed_info.txt",
    "gtfs_shapes_lines.txt"  # Conceptual entry for processing shape lines
]

GTFS_FOREIGN_KEYS: List[Tuple[str, List[str], str, List[str], str]] = [
    ("gtfs_routes", ["agency_id"], "gtfs_agency", ["agency_id"], "fk_routes_agency_id"),
    ("gtfs_trips", ["route_id"], "gtfs_routes", ["route_id"], "fk_trips_route_id"),
    ("gtfs_trips", ["shape_id"], "gtfs_shapes_lines", ["shape_id"], "fk_trips_shape_id_lines"),
    ("gtfs_stop_times", ["trip_id"], "gtfs_trips", ["trip_id"], "fk_stop_times_trip_id"),
    ("gtfs_stop_times", ["stop_id"], "gtfs_stops", ["stop_id"], "fk_stop_times_stop_id"),
    ("gtfs_stops", ["parent_station"], "gtfs_stops", ["stop_id"], "fk_stops_parent_station"),
]