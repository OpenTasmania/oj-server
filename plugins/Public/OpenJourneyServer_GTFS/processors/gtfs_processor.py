# -*- coding: utf-8 -*-
"""
GTFS Processor - Implements ProcessorInterface for GTFS data

This processor handles GTFS (General Transit Feed Specification) data and converts it
to the canonical database schema.
"""

import zipfile
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd
import gtfs_kit as gk
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from datetime import datetime

# Import the ProcessorInterface from common
import sys

sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from common.processor_interface import ProcessorInterface, ProcessorError
from common.logging_config import (
    setup_service_logging,
    get_logger,
    log_database_operation,
    log_performance,
)


class GTFSDatabaseWriter:
    """
    Writes GTFS data converted to canonical format directly to PostgreSQL database.
    """

    def __init__(self, db_config: Dict):
        """Initialize with database configuration."""
        self.db_config = db_config
        # Set up centralized logging for GTFS database writer
        setup_service_logging("gtfs-database-writer")
        self.logger = get_logger("GTFSDatabaseWriter")

    def get_connection(self):
        """Get database connection."""
        return psycopg2.connect(
            host=self.db_config["host"],
            port=self.db_config["port"],
            database=self.db_config["database"],
            user=self.db_config["user"],
            password=self.db_config["password"],
        )

    def write_agencies(self, conn, agencies_data: List[Dict]):
        """Write agencies data to canonical.transport_agencies."""
        self.logger.info(f"Writing {len(agencies_data)} agencies to database")
        log_database_operation(
            "INSERT", "transport_agencies", len(agencies_data)
        )

        with conn.cursor() as cur:
            for agency in agencies_data:
                cur.execute(
                    """
                    INSERT INTO canonical.transport_agencies 
                    (agency_id, agency_name, agency_url, agency_timezone, agency_lang, agency_phone, agency_fare_url, agency_email)
                    VALUES (%(agency_id)s, %(agency_name)s, %(agency_url)s, %(agency_timezone)s, %(agency_lang)s, %(agency_phone)s, %(agency_fare_url)s, %(agency_email)s)
                    ON CONFLICT (agency_id) DO UPDATE SET
                        agency_name = EXCLUDED.agency_name,
                        agency_url = EXCLUDED.agency_url,
                        agency_timezone = EXCLUDED.agency_timezone,
                        agency_lang = EXCLUDED.agency_lang,
                        agency_phone = EXCLUDED.agency_phone,
                        agency_fare_url = EXCLUDED.agency_fare_url,
                        agency_email = EXCLUDED.agency_email,
                        updated_at = NOW()
                """,
                    agency,
                )

    def write_routes(self, conn, routes_data: List[Dict]):
        """Write routes data to canonical.transport_routes."""
        with conn.cursor() as cur:
            for route in routes_data:
                cur.execute(
                    """
                    INSERT INTO canonical.transport_routes 
                    (route_id, agency_id, route_short_name, route_long_name, route_description, route_type, 
                     route_url, route_color, route_text_color, route_sort_order, continuous_pickup, continuous_drop_off)
                    VALUES (%(route_id)s, %(agency_id)s, %(route_short_name)s, %(route_long_name)s, %(route_description)s, 
                            %(route_type)s, %(route_url)s, %(route_color)s, %(route_text_color)s, %(route_sort_order)s, 
                            %(continuous_pickup)s, %(continuous_drop_off)s)
                    ON CONFLICT (route_id) DO UPDATE SET
                        agency_id = EXCLUDED.agency_id,
                        route_short_name = EXCLUDED.route_short_name,
                        route_long_name = EXCLUDED.route_long_name,
                        route_description = EXCLUDED.route_description,
                        route_type = EXCLUDED.route_type,
                        route_url = EXCLUDED.route_url,
                        route_color = EXCLUDED.route_color,
                        route_text_color = EXCLUDED.route_text_color,
                        route_sort_order = EXCLUDED.route_sort_order,
                        continuous_pickup = EXCLUDED.continuous_pickup,
                        continuous_drop_off = EXCLUDED.continuous_drop_off,
                        updated_at = NOW()
                """,
                    route,
                )

    def write_stops(self, conn, stops_data: List[Dict]):
        """Write stops data to canonical.transport_stops."""
        with conn.cursor() as cur:
            for stop in stops_data:
                cur.execute(
                    """
                    INSERT INTO canonical.transport_stops 
                    (stop_id, stop_name, stop_description, stop_lat, stop_lon, zone_id, stop_url, location_type, 
                     parent_station, stop_timezone, wheelchair_boarding, level_id, platform_code, geom)
                    VALUES (%(stop_id)s, %(stop_name)s, %(stop_description)s, %(stop_lat)s, %(stop_lon)s, %(zone_id)s, 
                            %(stop_url)s, %(location_type)s, %(parent_station)s, %(stop_timezone)s, %(wheelchair_boarding)s, 
                            %(level_id)s, %(platform_code)s, ST_SetSRID(ST_MakePoint(%(stop_lon)s, %(stop_lat)s), 4326))
                    ON CONFLICT (stop_id) DO UPDATE SET
                        stop_name = EXCLUDED.stop_name,
                        stop_description = EXCLUDED.stop_description,
                        stop_lat = EXCLUDED.stop_lat,
                        stop_lon = EXCLUDED.stop_lon,
                        zone_id = EXCLUDED.zone_id,
                        stop_url = EXCLUDED.stop_url,
                        location_type = EXCLUDED.location_type,
                        parent_station = EXCLUDED.parent_station,
                        stop_timezone = EXCLUDED.stop_timezone,
                        wheelchair_boarding = EXCLUDED.wheelchair_boarding,
                        level_id = EXCLUDED.level_id,
                        platform_code = EXCLUDED.platform_code,
                        geom = EXCLUDED.geom,
                        updated_at = NOW()
                """,
                    stop,
                )

    def write_trips(self, conn, trips_data: List[Dict]):
        """Write trips data to canonical.transport_trips."""
        with conn.cursor() as cur:
            for trip in trips_data:
                cur.execute(
                    """
                    INSERT INTO canonical.transport_trips 
                    (trip_id, route_id, service_id, trip_headsign, trip_short_name, direction_id, 
                     block_id, shape_id, wheelchair_accessible, bikes_allowed)
                    VALUES (%(trip_id)s, %(route_id)s, %(service_id)s, %(trip_headsign)s, %(trip_short_name)s, 
                            %(direction_id)s, %(block_id)s, %(shape_id)s, %(wheelchair_accessible)s, %(bikes_allowed)s)
                    ON CONFLICT (trip_id) DO UPDATE SET
                        route_id = EXCLUDED.route_id,
                        service_id = EXCLUDED.service_id,
                        trip_headsign = EXCLUDED.trip_headsign,
                        trip_short_name = EXCLUDED.trip_short_name,
                        direction_id = EXCLUDED.direction_id,
                        block_id = EXCLUDED.block_id,
                        shape_id = EXCLUDED.shape_id,
                        wheelchair_accessible = EXCLUDED.wheelchair_accessible,
                        bikes_allowed = EXCLUDED.bikes_allowed,
                        updated_at = NOW()
                """,
                    trip,
                )

    def write_schedule(self, conn, schedule_data: List[Dict]):
        """Write schedule data to canonical.transport_schedule."""
        with conn.cursor() as cur:
            for schedule in schedule_data:
                cur.execute(
                    """
                    INSERT INTO canonical.transport_schedule 
                    (trip_id, arrival_time, departure_time, stop_id, stop_sequence, stop_headsign, 
                     pickup_type, drop_off_type, continuous_pickup, continuous_drop_off, shape_dist_traveled, timepoint)
                    VALUES (%(trip_id)s, %(arrival_time)s, %(departure_time)s, %(stop_id)s, %(stop_sequence)s, 
                            %(stop_headsign)s, %(pickup_type)s, %(drop_off_type)s, %(continuous_pickup)s, 
                            %(continuous_drop_off)s, %(shape_dist_traveled)s, %(timepoint)s)
                    ON CONFLICT (trip_id, stop_sequence) DO UPDATE SET
                        arrival_time = EXCLUDED.arrival_time,
                        departure_time = EXCLUDED.departure_time,
                        stop_id = EXCLUDED.stop_id,
                        stop_headsign = EXCLUDED.stop_headsign,
                        pickup_type = EXCLUDED.pickup_type,
                        drop_off_type = EXCLUDED.drop_off_type,
                        continuous_pickup = EXCLUDED.continuous_pickup,
                        continuous_drop_off = EXCLUDED.continuous_drop_off,
                        shape_dist_traveled = EXCLUDED.shape_dist_traveled,
                        timepoint = EXCLUDED.timepoint,
                        updated_at = NOW()
                """,
                    schedule,
                )

    def write_shapes(self, conn, shapes_data: List[Dict]):
        """Write shapes data to canonical.transport_shapes."""
        with conn.cursor() as cur:
            for shape in shapes_data:
                cur.execute(
                    """
                    INSERT INTO canonical.transport_shapes 
                    (shape_id, shape_pt_lat, shape_pt_lon, shape_pt_sequence, shape_dist_traveled)
                    VALUES (%(shape_id)s, %(shape_pt_lat)s, %(shape_pt_lon)s, %(shape_pt_sequence)s, %(shape_dist_traveled)s)
                    ON CONFLICT (shape_id, shape_pt_sequence) DO UPDATE SET
                        shape_pt_lat = EXCLUDED.shape_pt_lat,
                        shape_pt_lon = EXCLUDED.shape_pt_lon,
                        shape_dist_traveled = EXCLUDED.shape_dist_traveled,
                        updated_at = NOW()
                """,
                    shape,
                )

    def write_calendar(self, conn, calendar_data: List[Dict]):
        """Write calendar data to canonical.transport_calendar."""
        with conn.cursor() as cur:
            for calendar in calendar_data:
                cur.execute(
                    """
                    INSERT INTO canonical.transport_calendar 
                    (service_id, monday, tuesday, wednesday, thursday, friday, saturday, sunday, start_date, end_date)
                    VALUES (%(service_id)s, %(monday)s, %(tuesday)s, %(wednesday)s, %(thursday)s, %(friday)s, 
                            %(saturday)s, %(sunday)s, %(start_date)s, %(end_date)s)
                    ON CONFLICT (service_id) DO UPDATE SET
                        monday = EXCLUDED.monday,
                        tuesday = EXCLUDED.tuesday,
                        wednesday = EXCLUDED.wednesday,
                        thursday = EXCLUDED.thursday,
                        friday = EXCLUDED.friday,
                        saturday = EXCLUDED.saturday,
                        sunday = EXCLUDED.sunday,
                        start_date = EXCLUDED.start_date,
                        end_date = EXCLUDED.end_date,
                        updated_at = NOW()
                """,
                    calendar,
                )

    def write_calendar_dates(self, conn, calendar_dates_data: List[Dict]):
        """Write calendar dates data to canonical.transport_calendar_dates."""
        with conn.cursor() as cur:
            for calendar_date in calendar_dates_data:
                cur.execute(
                    """
                    INSERT INTO canonical.transport_calendar_dates 
                    (service_id, date, exception_type)
                    VALUES (%(service_id)s, %(date)s, %(exception_type)s)
                    ON CONFLICT (service_id, date) DO UPDATE SET
                        exception_type = EXCLUDED.exception_type,
                        updated_at = NOW()
                """,
                    calendar_date,
                )


class GTFSProcessor(ProcessorInterface):
    """
    GTFS Processor implementing ProcessorInterface.

    Processes GTFS data and loads it into the canonical database schema.
    """

    def __init__(self, db_config: Dict[str, Any]):
        super().__init__(db_config)
        self.writer = GTFSDatabaseWriter(db_config)
        self.temp_files: List[Path] = []

    @property
    def processor_name(self) -> str:
        return "GTFS"

    @property
    def supported_formats(self) -> List[str]:
        return [".zip", ".txt"]

    def validate_source(self, source_path: Path) -> bool:
        """
        Validate that the source is a valid GTFS feed.

        Args:
            source_path: Path to the GTFS source

        Returns:
            True if valid GTFS feed, False otherwise
        """
        try:
            if source_path.suffix.lower() == ".zip":
                with zipfile.ZipFile(source_path, "r") as zip_file:
                    files = zip_file.namelist()
                    # Check for required GTFS files
                    required_files = [
                        "agency.txt",
                        "routes.txt",
                        "trips.txt",
                        "stops.txt",
                        "stop_times.txt",
                    ]
                    return all(f in files for f in required_files)
            elif source_path.is_dir():
                # Check for required GTFS files in directory
                required_files = [
                    "agency.txt",
                    "routes.txt",
                    "trips.txt",
                    "stops.txt",
                    "stop_times.txt",
                ]
                return all((source_path / f).exists() for f in required_files)
            return False
        except Exception as e:
            self.logger.error(
                f"Error validating GTFS source {source_path}: {str(e)}"
            )
            return False

    def extract(self, source_path: Path, **kwargs) -> Dict[str, Any]:
        """
        Extract GTFS data from zip file or directory.

        Args:
            source_path: Path to GTFS zip file or directory
            **kwargs: Additional parameters (e.g., url for downloading)

        Returns:
            Dictionary containing extracted GTFS feed data
        """
        try:
            # Handle URL download if provided
            if "url" in kwargs:
                source_path = self._download_from_url(kwargs["url"])
                self.temp_files.append(source_path)

            # Extract GTFS feed using gtfs_kit
            if source_path.suffix.lower() == ".zip":
                # Extract zip to temporary directory
                temp_dir = Path(tempfile.mkdtemp())
                self.temp_files.append(temp_dir)

                with zipfile.ZipFile(source_path, "r") as zip_file:
                    zip_file.extractall(temp_dir)

                feed = gk.read_feed(temp_dir, dist_units="km")
            else:
                feed = gk.read_feed(source_path, dist_units="km")

            return {"feed": feed, "source_path": source_path}

        except Exception as e:
            raise ProcessorError(
                f"Failed to extract GTFS data: {str(e)}",
                self.processor_name,
                e,
            )

    def transform(
        self, raw_data: Dict[str, Any], source_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform GTFS data to canonical format.

        Args:
            raw_data: Raw GTFS feed data from extract phase
            source_info: Information about the data source

        Returns:
            Dictionary containing transformed data for canonical schema
        """
        try:
            feed = raw_data["feed"]
            transformed_data = {}

            # Transform agencies
            if hasattr(feed, "agency") and feed.agency is not None:
                agencies = []
                for _, agency in feed.agency.iterrows():
                    agencies.append({
                        "agency_id": agency.get("agency_id", ""),
                        "agency_name": agency.get("agency_name", ""),
                        "agency_url": agency.get("agency_url", ""),
                        "agency_timezone": agency.get("agency_timezone", ""),
                        "agency_lang": agency.get("agency_lang"),
                        "agency_phone": agency.get("agency_phone"),
                        "agency_fare_url": agency.get("agency_fare_url"),
                        "agency_email": agency.get("agency_email"),
                    })
                transformed_data["agencies"] = agencies

            # Transform routes
            if hasattr(feed, "routes") and feed.routes is not None:
                routes = []
                for _, route in feed.routes.iterrows():
                    routes.append({
                        "route_id": route.get("route_id"),
                        "agency_id": route.get("agency_id", ""),
                        "route_short_name": route.get("route_short_name"),
                        "route_long_name": route.get("route_long_name"),
                        "route_description": route.get("route_desc"),
                        "route_type": int(route.get("route_type", 0)),
                        "route_url": route.get("route_url"),
                        "route_color": route.get("route_color", "FFFFFF"),
                        "route_text_color": route.get(
                            "route_text_color", "000000"
                        ),
                        "route_sort_order": route.get("route_sort_order"),
                        "continuous_pickup": route.get(
                            "continuous_pickup", 1
                        ),
                        "continuous_drop_off": route.get(
                            "continuous_drop_off", 1
                        ),
                    })
                transformed_data["routes"] = routes

            # Transform stops
            if hasattr(feed, "stops") and feed.stops is not None:
                stops = []
                for _, stop in feed.stops.iterrows():
                    stops.append({
                        "stop_id": stop.get("stop_id"),
                        "stop_name": stop.get("stop_name", ""),
                        "stop_description": stop.get("stop_desc"),
                        "stop_lat": float(stop.get("stop_lat", 0)),
                        "stop_lon": float(stop.get("stop_lon", 0)),
                        "zone_id": stop.get("zone_id"),
                        "stop_url": stop.get("stop_url"),
                        "location_type": int(stop.get("location_type", 0)),
                        "parent_station": stop.get("parent_station"),
                        "stop_timezone": stop.get("stop_timezone"),
                        "wheelchair_boarding": int(
                            stop.get("wheelchair_boarding", 0)
                        ),
                        "level_id": stop.get("level_id"),
                        "platform_code": stop.get("platform_code"),
                    })
                transformed_data["stops"] = stops

            # Transform trips
            if hasattr(feed, "trips") and feed.trips is not None:
                trips = []
                for _, trip in feed.trips.iterrows():
                    trips.append({
                        "trip_id": trip.get("trip_id"),
                        "route_id": trip.get("route_id"),
                        "service_id": trip.get("service_id"),
                        "trip_headsign": trip.get("trip_headsign"),
                        "trip_short_name": trip.get("trip_short_name"),
                        "direction_id": trip.get("direction_id"),
                        "block_id": trip.get("block_id"),
                        "shape_id": trip.get("shape_id"),
                        "wheelchair_accessible": int(
                            trip.get("wheelchair_accessible", 0)
                        ),
                        "bikes_allowed": int(trip.get("bikes_allowed", 0)),
                    })
                transformed_data["trips"] = trips

            # Transform stop_times to schedule
            if hasattr(feed, "stop_times") and feed.stop_times is not None:
                schedule = []
                for _, stop_time in feed.stop_times.iterrows():
                    schedule.append({
                        "trip_id": stop_time.get("trip_id"),
                        "arrival_time": stop_time.get("arrival_time"),
                        "departure_time": stop_time.get("departure_time"),
                        "stop_id": stop_time.get("stop_id"),
                        "stop_sequence": int(
                            stop_time.get("stop_sequence", 0)
                        ),
                        "stop_headsign": stop_time.get("stop_headsign"),
                        "pickup_type": int(stop_time.get("pickup_type", 0)),
                        "drop_off_type": int(
                            stop_time.get("drop_off_type", 0)
                        ),
                        "continuous_pickup": stop_time.get(
                            "continuous_pickup"
                        ),
                        "continuous_drop_off": stop_time.get(
                            "continuous_drop_off"
                        ),
                        "shape_dist_traveled": stop_time.get(
                            "shape_dist_traveled"
                        ),
                        "timepoint": int(stop_time.get("timepoint", 1)),
                    })
                transformed_data["schedule"] = schedule

            # Transform shapes
            if hasattr(feed, "shapes") and feed.shapes is not None:
                shapes = []
                for _, shape in feed.shapes.iterrows():
                    shapes.append({
                        "shape_id": shape.get("shape_id"),
                        "shape_pt_lat": float(shape.get("shape_pt_lat", 0)),
                        "shape_pt_lon": float(shape.get("shape_pt_lon", 0)),
                        "shape_pt_sequence": int(
                            shape.get("shape_pt_sequence", 0)
                        ),
                        "shape_dist_traveled": shape.get(
                            "shape_dist_traveled"
                        ),
                    })
                transformed_data["shapes"] = shapes

            # Transform calendar
            if hasattr(feed, "calendar") and feed.calendar is not None:
                calendar = []
                for _, cal in feed.calendar.iterrows():
                    calendar.append({
                        "service_id": cal.get("service_id"),
                        "monday": bool(cal.get("monday", 0)),
                        "tuesday": bool(cal.get("tuesday", 0)),
                        "wednesday": bool(cal.get("wednesday", 0)),
                        "thursday": bool(cal.get("thursday", 0)),
                        "friday": bool(cal.get("friday", 0)),
                        "saturday": bool(cal.get("saturday", 0)),
                        "sunday": bool(cal.get("sunday", 0)),
                        "start_date": cal.get("start_date"),
                        "end_date": cal.get("end_date"),
                    })
                transformed_data["calendar"] = calendar

            # Transform calendar_dates
            if (
                hasattr(feed, "calendar_dates")
                and feed.calendar_dates is not None
            ):
                calendar_dates = []
                for _, cal_date in feed.calendar_dates.iterrows():
                    calendar_dates.append({
                        "service_id": cal_date.get("service_id"),
                        "date": cal_date.get("date"),
                        "exception_type": int(
                            cal_date.get("exception_type", 1)
                        ),
                    })
                transformed_data["calendar_dates"] = calendar_dates

            return transformed_data

        except Exception as e:
            raise ProcessorError(
                f"Failed to transform GTFS data: {str(e)}",
                self.processor_name,
                e,
            )

    def load(self, transformed_data: Dict[str, Any]) -> bool:
        """
        Load transformed data into canonical database schema.

        Args:
            transformed_data: Transformed data from transform phase

        Returns:
            True if load was successful, False otherwise
        """
        try:
            with self.writer.get_connection() as conn:
                # Load data in dependency order
                if "agencies" in transformed_data:
                    self.writer.write_agencies(
                        conn, transformed_data["agencies"]
                    )
                    self.logger.info(
                        f"Loaded {len(transformed_data['agencies'])} agencies"
                    )

                if "routes" in transformed_data:
                    self.writer.write_routes(conn, transformed_data["routes"])
                    self.logger.info(
                        f"Loaded {len(transformed_data['routes'])} routes"
                    )

                if "stops" in transformed_data:
                    self.writer.write_stops(conn, transformed_data["stops"])
                    self.logger.info(
                        f"Loaded {len(transformed_data['stops'])} stops"
                    )

                if "calendar" in transformed_data:
                    self.writer.write_calendar(
                        conn, transformed_data["calendar"]
                    )
                    self.logger.info(
                        f"Loaded {len(transformed_data['calendar'])} calendar entries"
                    )

                if "calendar_dates" in transformed_data:
                    self.writer.write_calendar_dates(
                        conn, transformed_data["calendar_dates"]
                    )
                    self.logger.info(
                        f"Loaded {len(transformed_data['calendar_dates'])} calendar date exceptions"
                    )

                if "shapes" in transformed_data:
                    self.writer.write_shapes(conn, transformed_data["shapes"])
                    self.logger.info(
                        f"Loaded {len(transformed_data['shapes'])} shape points"
                    )

                if "trips" in transformed_data:
                    self.writer.write_trips(conn, transformed_data["trips"])
                    self.logger.info(
                        f"Loaded {len(transformed_data['trips'])} trips"
                    )

                if "schedule" in transformed_data:
                    self.writer.write_schedule(
                        conn, transformed_data["schedule"]
                    )
                    self.logger.info(
                        f"Loaded {len(transformed_data['schedule'])} schedule entries"
                    )

                conn.commit()
                return True

        except Exception as e:
            self.logger.error(f"Failed to load GTFS data: {str(e)}")
            return False
        finally:
            # Clean up temporary files
            self.cleanup(self.temp_files)
            self.temp_files.clear()

    def _download_from_url(self, url: str) -> Path:
        """Download GTFS feed from URL."""
        temp_dir = Path(tempfile.mkdtemp())
        temp_path = temp_dir / "gtfs_feed.zip"

        self.logger.info(f"Downloading GTFS feed from {url}")
        response = requests.get(url, stream=True)
        response.raise_for_status()

        with open(temp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return temp_path
