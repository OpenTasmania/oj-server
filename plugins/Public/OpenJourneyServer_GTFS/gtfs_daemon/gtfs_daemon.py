#!/usr/bin/env python3
"""
GTFS to OpenJourney Daemon for Kubernetes
==========================================

A containerized daemon that regularly downloads GTFS feeds from configured URLs
and imports them into the OpenJourney PostgreSQL database.

This is adapted from the original gtfs_daemon.py to work with PostgreSQL
and the OpenJourney database schema in a Kubernetes environment.
"""

import argparse
import json
import logging
import os
import sys
import time
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import gtfs_kit as gk


class PostgreSQLOpenJourneyWriter:
    """
    Writes GTFS data converted to OpenJourney format directly to PostgreSQL database.
    """

    def __init__(self, db_config: Dict):
        """Initialize with database configuration."""
        self.db_config = db_config
        self.logger = logging.getLogger("PostgreSQLOpenJourneyWriter")

    def get_connection(self):
        """Get database connection."""
        return psycopg2.connect(
            host=self.db_config["host"],
            port=self.db_config["port"],
            database=self.db_config["database"],
            user=self.db_config["user"],
            password=self.db_config["password"],
        )

    def write_data_source(self, conn, source_data: Dict):
        """Write data source information."""
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO openjourney.data_sources 
                (source_id, source_name, source_type, source_url, source_timezone, source_lang, source_email, source_phone)
                VALUES (%(source_id)s, %(source_name)s, %(source_type)s, %(source_url)s, %(source_timezone)s, %(source_lang)s, %(source_email)s, %(source_phone)s)
                ON CONFLICT (source_id) DO UPDATE SET
                    source_name = EXCLUDED.source_name,
                    source_type = EXCLUDED.source_type,
                    source_url = EXCLUDED.source_url,
                    source_timezone = EXCLUDED.source_timezone,
                    source_lang = EXCLUDED.source_lang,
                    source_email = EXCLUDED.source_email,
                    source_phone = EXCLUDED.source_phone,
                    updated_at = NOW()
            """,
                source_data,
            )

    def write_routes(self, conn, routes_data: List[Dict]):
        """Write routes data."""
        with conn.cursor() as cur:
            for route in routes_data:
                cur.execute(
                    """
                    INSERT INTO openjourney.routes 
                    (route_id, route_name, agency_id, agency_route_id, transit_mode)
                    VALUES (%(route_id)s, %(route_name)s, %(agency_id)s, %(agency_route_id)s, %(transit_mode)s)
                    ON CONFLICT (route_id) DO UPDATE SET
                        route_name = EXCLUDED.route_name,
                        agency_id = EXCLUDED.agency_id,
                        agency_route_id = EXCLUDED.agency_route_id,
                        transit_mode = EXCLUDED.transit_mode,
                        updated_at = NOW()
                """,
                    route,
                )

    def write_stops(self, conn, stops_data: List[Dict]):
        """Write stops data with geometry."""
        with conn.cursor() as cur:
            for stop in stops_data:
                cur.execute(
                    """
                    INSERT INTO openjourney.stops 
                    (stop_id, stop_name, geom, stop_lat, stop_lon, location_type, parent_station, wheelchair_boarding)
                    VALUES (%(stop_id)s, %(stop_name)s, ST_SetSRID(ST_MakePoint(%(stop_lon)s, %(stop_lat)s), 4326), 
                            %(stop_lat)s, %(stop_lon)s, %(location_type)s, %(parent_station)s, %(wheelchair_boarding)s)
                    ON CONFLICT (stop_id) DO UPDATE SET
                        stop_name = EXCLUDED.stop_name,
                        geom = EXCLUDED.geom,
                        stop_lat = EXCLUDED.stop_lat,
                        stop_lon = EXCLUDED.stop_lon,
                        location_type = EXCLUDED.location_type,
                        parent_station = EXCLUDED.parent_station,
                        wheelchair_boarding = EXCLUDED.wheelchair_boarding,
                        updated_at = NOW()
                """,
                    stop,
                )

    def write_segments(self, conn, segments_data: List[Dict]):
        """Write segments data."""
        with conn.cursor() as cur:
            for segment in segments_data:
                cur.execute(
                    """
                    INSERT INTO openjourney.segments 
                    (segment_id, route_id, start_stop_id, end_stop_id, distance, duration, transport_mode, accessibility)
                    VALUES (%(segment_id)s, %(route_id)s, %(start_stop_id)s, %(end_stop_id)s, %(distance)s, %(duration)s, %(transport_mode)s, %(accessibility)s)
                    ON CONFLICT (segment_id) DO UPDATE SET
                        route_id = EXCLUDED.route_id,
                        start_stop_id = EXCLUDED.start_stop_id,
                        end_stop_id = EXCLUDED.end_stop_id,
                        distance = EXCLUDED.distance,
                        duration = EXCLUDED.duration,
                        transport_mode = EXCLUDED.transport_mode,
                        accessibility = EXCLUDED.accessibility,
                        updated_at = NOW()
                """,
                    segment,
                )

    def write_temporal_data(self, conn, temporal_data: List[Dict]):
        """Write temporal/calendar data."""
        with conn.cursor() as cur:
            for temporal in temporal_data:
                cur.execute(
                    """
                    INSERT INTO openjourney.temporal_data 
                    (service_id, start_date, end_date, monday, tuesday, wednesday, thursday, friday, saturday, sunday)
                    VALUES (%(service_id)s, %(start_date)s, %(end_date)s, %(monday)s, %(tuesday)s, %(wednesday)s, %(thursday)s, %(friday)s, %(saturday)s, %(sunday)s)
                    ON CONFLICT (service_id) DO UPDATE SET
                        start_date = EXCLUDED.start_date,
                        end_date = EXCLUDED.end_date,
                        monday = EXCLUDED.monday,
                        tuesday = EXCLUDED.tuesday,
                        wednesday = EXCLUDED.wednesday,
                        thursday = EXCLUDED.thursday,
                        friday = EXCLUDED.friday,
                        saturday = EXCLUDED.saturday,
                        sunday = EXCLUDED.sunday,
                        updated_at = NOW()
                """,
                    temporal,
                )

    def write_journey_data(self, journey_data: Dict):
        """Write complete journey data to PostgreSQL."""
        try:
            with self.get_connection() as conn:
                self.logger.info(
                    "Writing data to OpenJourney PostgreSQL database..."
                )

                # Write data sources
                if journey_data.get("data_sources"):
                    for source in journey_data["data_sources"]:
                        self.write_data_source(conn, source)
                    self.logger.info(
                        f"Wrote {len(journey_data['data_sources'])} data sources"
                    )

                # Write routes
                if journey_data.get("routes"):
                    self.write_routes(conn, journey_data["routes"])
                    self.logger.info(
                        f"Wrote {len(journey_data['routes'])} routes"
                    )

                # Write stops
                if journey_data.get("stops"):
                    self.write_stops(conn, journey_data["stops"])
                    self.logger.info(
                        f"Wrote {len(journey_data['stops'])} stops"
                    )

                # Write segments
                if journey_data.get("segments"):
                    self.write_segments(conn, journey_data["segments"])
                    self.logger.info(
                        f"Wrote {len(journey_data['segments'])} segments"
                    )

                # Write temporal data
                if journey_data.get("temporal_data"):
                    self.write_temporal_data(
                        conn, journey_data["temporal_data"]
                    )
                    self.logger.info(
                        f"Wrote {len(journey_data['temporal_data'])} temporal records"
                    )

                conn.commit()
                self.logger.info("Successfully wrote all data to PostgreSQL")

        except Exception as e:
            self.logger.error(f"Error writing to PostgreSQL: {str(e)}")
            raise


class GTFSToOpenJourneyConverter:
    """
    Converts GTFS data to OpenJourney format for PostgreSQL storage.
    """

    def __init__(self):
        self.logger = logging.getLogger("GTFSToOpenJourneyConverter")

    def convert_gtfs_to_openjourney(
        self, gtfs_path: Path, source_info: Dict
    ) -> Dict:
        """Convert GTFS data to OpenJourney format."""
        self.logger.info(f"Converting GTFS data from {gtfs_path}")

        # Load GTFS feed
        feed = gk.read_feed(gtfs_path, dist_units="km")

        journey_data: Dict[str, List[Dict[str, Any]]] = {
            "data_sources": [],
            "routes": [],
            "stops": [],
            "segments": [],
            "temporal_data": [],
        }

        # Convert data sources (agencies)
        if hasattr(feed, "agency") and feed.agency is not None:
            for _, agency in feed.agency.iterrows():
                journey_data["data_sources"].append({
                    "source_id": agency.get("agency_id", "default"),
                    "source_name": agency.get("agency_name", ""),
                    "source_type": "GTFS",
                    "source_url": source_info.get("url", ""),
                    "source_timezone": agency.get("agency_timezone", ""),
                    "source_lang": agency.get("agency_lang", ""),
                    "source_email": agency.get("agency_email", ""),
                    "source_phone": agency.get("agency_phone", ""),
                })

        # Convert routes
        if hasattr(feed, "routes") and feed.routes is not None:
            for _, route in feed.routes.iterrows():
                journey_data["routes"].append({
                    "route_id": route["route_id"],
                    "route_name": route.get("route_short_name", "")
                    + " "
                    + route.get("route_long_name", ""),
                    "agency_id": route.get("agency_id", ""),
                    "agency_route_id": route["route_id"],
                    "transit_mode": self._map_gtfs_route_type(
                        route.get("route_type", 3)
                    ),
                })

        # Convert stops
        if hasattr(feed, "stops") and feed.stops is not None:
            for _, stop in feed.stops.iterrows():
                journey_data["stops"].append({
                    "stop_id": stop["stop_id"],
                    "stop_name": stop.get("stop_name", ""),
                    "stop_lat": float(stop.get("stop_lat", 0)),
                    "stop_lon": float(stop.get("stop_lon", 0)),
                    "location_type": int(stop.get("location_type", 0)),
                    "parent_station": stop.get("parent_station", None),
                    "wheelchair_boarding": int(
                        stop.get("wheelchair_boarding", 0)
                    ),
                })

        # Convert calendar data to temporal data
        if hasattr(feed, "calendar") and feed.calendar is not None:
            for _, calendar in feed.calendar.iterrows():
                journey_data["temporal_data"].append({
                    "service_id": calendar["service_id"],
                    "start_date": calendar["start_date"],
                    "end_date": calendar["end_date"],
                    "monday": bool(calendar.get("monday", 0)),
                    "tuesday": bool(calendar.get("tuesday", 0)),
                    "wednesday": bool(calendar.get("wednesday", 0)),
                    "thursday": bool(calendar.get("thursday", 0)),
                    "friday": bool(calendar.get("friday", 0)),
                    "saturday": bool(calendar.get("saturday", 0)),
                    "sunday": bool(calendar.get("sunday", 0)),
                })

        # Generate segments from stop_times and trips
        self._generate_segments(feed, journey_data)

        return journey_data

    def _map_gtfs_route_type(self, route_type: int) -> str:
        """Map GTFS route type to OpenJourney transit mode."""
        mapping = {
            0: "tram",
            1: "subway",
            2: "rail",
            3: "bus",
            4: "ferry",
            5: "cable_tram",
            6: "aerial_lift",
            7: "funicular",
            11: "trolleybus",
            12: "monorail",
        }
        return mapping.get(route_type, "bus")

    def _generate_segments(self, feed, journey_data: Dict):
        """Generate segments from GTFS trips and stop_times."""
        if not (hasattr(feed, "trips") and hasattr(feed, "stop_times")):
            return

        segments = []

        # Group stop_times by trip_id
        if feed.stop_times is not None:
            stop_times_grouped = feed.stop_times.groupby("trip_id")

            for trip_id, trip_stops in stop_times_grouped:
                trip_stops = trip_stops.sort_values("stop_sequence")
                trip_stops_list = trip_stops.to_dict("records")

                # Get route_id for this trip
                trip_info = feed.trips[feed.trips["trip_id"] == trip_id]
                if trip_info.empty:
                    continue
                route_id = trip_info.iloc[0]["route_id"]

                # Create segments between consecutive stops
                for i in range(len(trip_stops_list) - 1):
                    current_stop = trip_stops_list[i]
                    next_stop = trip_stops_list[i + 1]

                    segment_id = f"{trip_id}_{current_stop['stop_sequence']}_{next_stop['stop_sequence']}"

                    # Calculate duration if times are available
                    duration = None
                    if current_stop.get("departure_time") and next_stop.get(
                        "arrival_time"
                    ):
                        try:
                            # Simple time difference calculation (this is simplified)
                            duration = 300  # Default 5 minutes, should be calculated properly
                        except:
                            duration = None

                    segments.append({
                        "segment_id": segment_id,
                        "route_id": route_id,
                        "start_stop_id": current_stop["stop_id"],
                        "end_stop_id": next_stop["stop_id"],
                        "distance": None,  # Could be calculated from stop coordinates
                        "duration": duration,
                        "transport_mode": "bus",  # Default, should map from route
                        "accessibility": None,
                    })

        journey_data["segments"] = segments


class GTFSDaemon:
    """
    GTFS Daemon for Kubernetes that processes GTFS feeds and stores them in PostgreSQL.
    """

    def __init__(self, config: Dict):
        """Initialize the GTFS daemon."""
        self.config = config
        self.feeds = config.get("feeds", [])
        self.db_config = config.get("database", {})
        self.max_retries = config.get("max_retries", 3)
        self.retry_delay = config.get("retry_delay", 60)

        # Setup logging
        self.setup_logging()

        # Initialize components
        self.converter = GTFSToOpenJourneyConverter()
        self.db_writer = PostgreSQLOpenJourneyWriter(self.db_config)

    def setup_logging(self):
        """Setup logging configuration."""
        log_level = self.config.get("log_level", "INFO")
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format=log_format,
            handlers=[logging.StreamHandler(sys.stdout)],
        )

        self.logger = logging.getLogger("GTFSDaemon")

    def download_gtfs_from_url(
        self, url: str, temp_dir: str
    ) -> Optional[Path]:
        """Download GTFS feed from URL."""
        try:
            self.logger.info(f"Downloading GTFS feed from {url}")
            response = requests.get(url, timeout=300)
            response.raise_for_status()

            # Save to temporary file
            temp_path = Path(temp_dir) / "gtfs_feed.zip"
            with open(temp_path, "wb") as f:
                f.write(response.content)

            self.logger.info(f"Downloaded GTFS feed to {temp_path}")
            return temp_path

        except Exception as e:
            self.logger.error(
                f"Error downloading GTFS feed from {url}: {str(e)}"
            )
            return None

    def process_feed(self, feed_config: Dict) -> bool:
        """Process a single GTFS feed."""
        feed_url = feed_config["url"]
        feed_name = feed_config.get("name", feed_url)

        self.logger.info(f"Processing feed: {feed_name}")

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Download GTFS feed
                gtfs_path = self.download_gtfs_from_url(feed_url, temp_dir)
                if not gtfs_path:
                    return False

                # Convert to OpenJourney format
                journey_data = self.converter.convert_gtfs_to_openjourney(
                    gtfs_path, feed_config
                )

                # Write to PostgreSQL
                self.db_writer.write_journey_data(journey_data)

                self.logger.info(f"Successfully processed feed: {feed_name}")
                return True

        except Exception as e:
            self.logger.error(f"Error processing feed {feed_name}: {str(e)}")
            return False

    def process_feed_with_retry(self, feed_config: Dict):
        """Process feed with retry logic."""
        feed_name = feed_config.get("name", feed_config["url"])

        for attempt in range(self.max_retries):
            try:
                if self.process_feed(feed_config):
                    return  # Success
            except Exception as e:
                self.logger.error(
                    f"Attempt {attempt + 1} failed for feed {feed_name}: {str(e)}"
                )

            if attempt < self.max_retries - 1:
                delay = self.retry_delay * (2**attempt)
                self.logger.info(
                    f"Retrying feed {feed_name} in {delay} seconds..."
                )
                time.sleep(delay)

    def run_once(self):
        """Run the daemon once (process all feeds)."""
        self.logger.info("Starting GTFS daemon run...")

        for feed_config in self.feeds:
            self.process_feed_with_retry(feed_config)

        self.logger.info("GTFS daemon run completed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="GTFS to OpenJourney Daemon")
    parser.add_argument(
        "--config", default="/app/config.json", help="Configuration file path"
    )
    args = parser.parse_args()

    # Load configuration
    try:
        with open(args.config, "r") as f:
            config = json.load(f)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)

    # Create and run daemon
    daemon = GTFSDaemon(config)
    daemon.run_once()


if __name__ == "__main__":
    main()
