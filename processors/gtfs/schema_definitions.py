#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Defines Pydantic models for validating GTFS (General Transit Feed Specification)
data files.

This module provides a base model `GTFSBaseModel` with common configurations
and specific Pydantic models for each GTFS file type (e.g., Agency, Stop,
Route). These models are used to validate the structure and data types of
records read from GTFS text files.

The main schema dictionary `GTFS_FILE_SCHEMAS` maps GTFS filenames to their
corresponding Pydantic model, database table name, and primary key columns.
"""

import logging
from datetime import datetime
from typing import Optional, Literal, Annotated, Dict, Type, List, Any

from pydantic import (
    BaseModel,
    Field,
    conint,
    confloat,
    model_validator,
    field_validator,
    ValidationError,
    StringConstraints,  # Explicitly import if needed, often part of Annotated
)

# --- Pydantic Model Configuration ---
class GTFSBaseModel(BaseModel):
    """
    Base Pydantic model for all GTFS entities.

    Includes common configuration options:
    - `extra = "ignore"`: Ignores extra fields not defined in the model.
    - `str_strip_whitespace = True`: Strips leading/trailing whitespace from
                                     string fields.
    - `validate_assignment = True`: Validates fields on assignment after
                                    initialization.
    """
    class Config:
        extra = "ignore"
        str_strip_whitespace = True
        validate_assignment = True


# --- GTFS File Specific Models ---

class Agency(GTFSBaseModel):
    """
    Represents an agency from `agency.txt`.

    Attributes:
        agency_id: Conditionally required. Uniquely identifies a transit agency.
        agency_name: Required. Full name of the transit agency.
        agency_url: Required. URL of the transit agency.
        agency_timezone: Required. Timezone where the agency is located.
        agency_lang: Optional. Two-letter ISO 639-1 code for the primary
                     language used by this agency.
        agency_phone: Optional. Voice telephone number for the agency.
        agency_fare_url: Optional. URL for purchasing fares online.
        agency_email: Optional. Email address for contacting the agency.
    """
    agency_id: Optional[Annotated[str, StringConstraints(min_length=1)]] = None
    agency_name: Annotated[str, StringConstraints(min_length=1)]
    agency_url: Annotated[str, StringConstraints(pattern=r"^https?://.+")]
    agency_timezone: Annotated[str, StringConstraints(min_length=1)]
    agency_lang: Optional[
        Annotated[str, StringConstraints(min_length=2, max_length=2)]
    ] = None
    agency_phone: Optional[str] = None
    agency_fare_url: Optional[
        Annotated[str, StringConstraints(pattern=r"^https?://.+")]
    ] = None
    agency_email: Optional[
        Annotated[str, StringConstraints(
            pattern=r"[^@ \t\r\n]+@[^@ \t\r\n]+\.[^@ \t\r\n]+"
        )]
    ] = None


class Stop(GTFSBaseModel):
    """
    Represents a stop or station from `stops.txt`.

    Attributes:
        stop_id: Required. Uniquely identifies a stop, station, or entrance.
        stop_code: Optional. Short text or number uniquely identifying the stop.
        stop_name: Optional. Name of the stop or station.
        stop_desc: Optional. Description of the stop.
        stop_lat: Required. Latitude of the stop or station.
        stop_lon: Required. Longitude of the stop or station.
        zone_id: Optional. Fare zone for the stop.
        stop_url: Optional. URL of a web page about the stop.
        location_type: Optional. Identifies whether this stop represents a
                       stop, station, entrance/exit, generic node, or boarding area.
                       (0 or blank: Stop, 1: Station, 2: Entrance/Exit,
                       3: Generic Node, 4: Boarding Area). Defaults to 0.
        parent_station: Optional. The `stop_id` of the parent station, if any.
        stop_timezone: Optional. Timezone of the stop.
        wheelchair_boarding: Optional. Indicates wheelchair accessibility.
                             (0: No info, 1: Accessible, 2: Not accessible).
        level_id: Optional. Level of the platform.
        platform_code: Optional. Platform identifier for the stop.
    """
    stop_id: Annotated[str, StringConstraints(min_length=1)]
    stop_code: Optional[str] = None
    stop_name: Optional[Annotated[str, StringConstraints(min_length=1)]] = None
    stop_desc: Optional[str] = None
    stop_lat: confloat(ge=-90, le=90)
    stop_lon: confloat(ge=-180, le=180)
    zone_id: Optional[str] = None
    stop_url: Optional[
        Annotated[str, StringConstraints(pattern=r"^https?://.+")]
    ] = None
    location_type: Optional[conint(ge=0, le=4)] = Field(0)
    parent_station: Optional[str] = None
    stop_timezone: Optional[str] = None
    wheelchair_boarding: Optional[conint(ge=0, le=2)] = None
    level_id: Optional[str] = None
    platform_code: Optional[str] = None


class Route(GTFSBaseModel):
    """
    Represents a route from `routes.txt`.

    Attributes:
        route_id: Required. Uniquely identifies a route.
        agency_id: Optional. Agency for the route.
        route_short_name: Optional. Short name for the route (e.g., "10").
        route_long_name: Optional. Long name for the route.
        route_desc: Optional. Description of the route.
        route_type: Required. Type of route (e.g., 0: Tram, 3: Bus).
        route_url: Optional. URL for the route.
        route_color: Optional. Route color in hex format (e.g., "FFFFFF").
        route_text_color: Optional. Route text color in hex format.
        route_sort_order: Optional. Order for displaying routes.
        continuous_pickup: Optional. Indicates continuous pickup policy.
        continuous_drop_off: Optional. Indicates continuous drop-off policy.
    """
    route_id: Annotated[str, StringConstraints(min_length=1)]
    agency_id: Optional[str] = None
    route_short_name: Optional[str] = Field("", max_length=50)
    route_long_name: Optional[str] = Field("", max_length=255)
    route_desc: Optional[str] = None
    route_type: conint(ge=0, le=7) # GTFS standard route types
    route_url: Optional[
        Annotated[str, StringConstraints(pattern=r"^https?://.+")]
    ] = None
    route_color: Optional[
        Annotated[str, StringConstraints(pattern=r"^[0-9a-fA-F]{6}$")]
    ] = None
    route_text_color: Optional[
        Annotated[str, StringConstraints(pattern=r"^[0-9a-fA-F]{6}$")]
    ] = None
    route_sort_order: Optional[conint(ge=0)] = None
    # Continuous pickup/drop-off: 0=Continuous, 1=Not available,
    # 2=Phone agency, 3=Coordinate with driver
    continuous_pickup: Optional[conint(ge=0, le=3)] = Field(None)
    continuous_drop_off: Optional[conint(ge=0, le=3)] = Field(None)


class Trip(GTFSBaseModel):
    """
    Represents a trip from `trips.txt`.

    Attributes:
        route_id: Required. ID of the route this trip belongs to.
        service_id: Required. ID of the service pattern for this trip.
        trip_id: Required. Uniquely identifies a trip.
        trip_headsign: Optional. Text that appears on signage for the trip.
        trip_short_name: Optional. Short name for the trip.
        direction_id: Optional. Indicates direction of travel (0 or 1).
        block_id: Optional. ID of the block of trips this trip belongs to.
        shape_id: Optional. ID of the shape for this trip.
        wheelchair_accessible: Optional. Wheelchair accessibility for the trip.
        bikes_allowed: Optional. Indicates if bikes are allowed on this trip.
    """
    route_id: Annotated[str, StringConstraints(min_length=1)]
    service_id: Annotated[str, StringConstraints(min_length=1)]
    trip_id: Annotated[str, StringConstraints(min_length=1)]
    trip_headsign: Optional[str] = None
    trip_short_name: Optional[str] = None
    direction_id: Optional[Literal[0, 1]] = None
    block_id: Optional[str] = None
    shape_id: Optional[str] = None
    wheelchair_accessible: Optional[Literal[0, 1, 2]] = Field(None)
    bikes_allowed: Optional[Literal[0, 1, 2]] = Field(None)


class StopTime(GTFSBaseModel):
    """
    Represents a stop time event from `stop_times.txt`.

    Attributes:
        trip_id: Required. ID of the trip this stop time belongs to.
        arrival_time: Optional. Arrival time at the stop (HH:MM:SS).
        departure_time: Optional. Departure time from the stop (HH:MM:SS).
        stop_id: Required. ID of the stop.
        stop_sequence: Required. Order of stops for a trip.
        stop_headsign: Optional. Headsign for this stop on this trip.
        pickup_type: Optional. How passengers are picked up.
        drop_off_type: Optional. How passengers are dropped off.
        continuous_pickup: Optional. Continuous pickup policy for this stop time.
        continuous_drop_off: Optional. Continuous drop-off policy.
        shape_dist_traveled: Optional. Distance from first shape point.
        timepoint: Optional. Indicates if this stop is a timepoint.
    """
    trip_id: Annotated[str, StringConstraints(min_length=1)]
    arrival_time: Optional[
        Annotated[str, StringConstraints(
            pattern=r"^[0-9]{1,2}:[0-5][0-9]:[0-5][0-9]$"
        )]
    ] = None
    departure_time: Optional[
        Annotated[str, StringConstraints(
            pattern=r"^[0-9]{1,2}:[0-5][0-9]:[0-5][0-9]$"
        )]
    ] = None
    stop_id: Annotated[str, StringConstraints(min_length=1)]
    stop_sequence: conint(ge=0)
    stop_headsign: Optional[str] = None
    pickup_type: Optional[conint(ge=0, le=3)] = Field(None)
    drop_off_type: Optional[conint(ge=0, le=3)] = Field(None)
    continuous_pickup: Optional[conint(ge=0, le=3)] = Field(None)
    continuous_drop_off: Optional[conint(ge=0, le=3)] = Field(None)
    shape_dist_traveled: Optional[confloat(ge=0)] = None
    timepoint: Optional[Literal[0, 1]] = Field(None)

    @model_validator(mode="after")
    def check_arrival_departure_times(cls, model: "StopTime") -> "StopTime":
        """Validate that at least one of arrival_time or departure_time is provided."""
        # GTFS spec: "arrival_time and departure_time are required for timepoints."
        # "For non-timepoints, both can be empty if it's a pass-through."
        # This validator currently allows both to be None, which is valid for
        # some non-timepoint scenarios. If strict timepoint validation is needed,
        # this logic would need to consider the `timepoint` field.
        if model.arrival_time is None and model.departure_time is None:
            # Depending on strictness, could raise ValueError here.
            # For now, allowing this as per some interpretations of optionality.
            pass
        return model


class Calendar(GTFSBaseModel):
    """
    Represents a service availability pattern from `calendar.txt`.

    Attributes:
        service_id: Required. Uniquely identifies a set of dates when service
                    is available for one or more routes.
        monday: Required. Indicates if service is available on Mondays (1) or not (0).
        tuesday: Required. Tuesday availability.
        wednesday: Required. Wednesday availability.
        thursday: Required. Thursday availability.
        friday: Required. Friday availability.
        saturday: Required. Saturday availability.
        sunday: Required. Sunday availability.
        start_date: Required. Start date for the service (YYYYMMDD).
        end_date: Required. End date for the service (YYYYMMDD).
    """
    service_id: Annotated[str, StringConstraints(min_length=1)]
    monday: Literal[0, 1]
    tuesday: Literal[0, 1]
    wednesday: Literal[0, 1]
    thursday: Literal[0, 1]
    friday: Literal[0, 1]
    saturday: Literal[0, 1]
    sunday: Literal[0, 1]
    start_date: Annotated[str, StringConstraints(pattern=r"^[0-9]{8}$")]
    end_date: Annotated[str, StringConstraints(pattern=r"^[0-9]{8}$")]

    @field_validator("start_date", "end_date")
    @classmethod
    def check_date_format(cls, v: str) -> str:
        """Validate that date strings are in YYYYMMDD format."""
        try:
            datetime.strptime(v, "%Y%m%d").date()
        except ValueError as e:
            raise ValueError(f"Date {v} is not a valid YYYYMMDD date.") from e
        return v


class CalendarDate(GTFSBaseModel):
    """
    Represents exceptions to service availability from `calendar_dates.txt`.

    Attributes:
        service_id: Required. ID of the service affected by this exception.
        date: Required. Date of the exception (YYYYMMDD).
        exception_type: Required. Type of exception (1: Service added,
                        2: Service removed).
    """
    service_id: Annotated[str, StringConstraints(min_length=1)]
    date: Annotated[str, StringConstraints(pattern=r"^[0-9]{8}$")]
    exception_type: Literal[1, 2]

    @field_validator("date")
    @classmethod
    def check_date_format(cls, v: str) -> str:
        """Validate that the date string is in YYYYMMDD format."""
        try:
            datetime.strptime(v, "%Y%m%d").date()
        except ValueError as e:
            raise ValueError(f"Date {v} is not a valid YYYYMMDD date.") from e
        return v


class ShapePoint(GTFSBaseModel):
    """
    Represents a point in a vehicle's path from `shapes.txt`.

    Attributes:
        shape_id: Required. ID of the shape this point belongs to.
        shape_pt_lat: Required. Latitude of the shape point.
        shape_pt_lon: Required. Longitude of the shape point.
        shape_pt_sequence: Required. Sequence of this point in the shape.
        shape_dist_traveled: Optional. Distance traveled along the shape
                             from the first point.
    """
    shape_id: Annotated[str, StringConstraints(min_length=1)]
    shape_pt_lat: confloat(ge=-90, le=90)
    shape_pt_lon: confloat(ge=-180, le=180)
    shape_pt_sequence: conint(ge=0)
    shape_dist_traveled: Optional[confloat(ge=0)] = None


class Frequency(GTFSBaseModel):
    """
    Represents service frequency for a trip from `frequencies.txt`.

    Attributes:
        trip_id: Required. ID of the trip this frequency applies to.
        start_time: Required. Start time for this frequency period (HH:MM:SS).
        end_time: Required. End time for this frequency period (HH:MM:SS).
        headway_secs: Required. Time in seconds between departures.
        exact_times: Optional. Indicates if service is frequency-based (0) or
                     schedule-based (1) for this period.
    """
    trip_id: Annotated[str, StringConstraints(min_length=1)]
    start_time: Annotated[
        str, StringConstraints(pattern=r"^[0-9]{1,2}:[0-5][0-9]:[0-5][0-9]$")
    ]
    end_time: Annotated[
        str, StringConstraints(pattern=r"^[0-9]{1,2}:[0-5][0-9]:[0-5][0-9]$")
    ]
    headway_secs: conint(gt=0) # Headway must be positive
    exact_times: Optional[Literal[0, 1]] = Field(None)


class Transfer(GTFSBaseModel):
    """
    Represents a transfer rule between stops from `transfers.txt`.

    Attributes:
        from_stop_id: Required. ID of the stop where transfer originates.
        to_stop_id: Required. ID of the stop where transfer terminates.
        transfer_type: Required. Type of transfer.
                       (0: Recommended, 1: Timed, 2: Min time, 3: Not possible)
        min_transfer_time: Optional. Minimum time for the transfer (seconds).
                           Required if `transfer_type` is 2.
    """
    from_stop_id: Annotated[str, StringConstraints(min_length=1)]
    to_stop_id: Annotated[str, StringConstraints(min_length=1)]
    transfer_type: conint(ge=0, le=3)
    min_transfer_time: Optional[conint(ge=0)] = None

    @model_validator(mode="after")
    def check_min_transfer_time_logic(cls, model: "Transfer") -> "Transfer":
        """Validate min_transfer_time based on transfer_type."""
        if model.transfer_type == 2 and model.min_transfer_time is None:
            raise ValueError(
                "min_transfer_time is required when transfer_type is 2 "
                "(min_time transfer)."
            )
        return model


class FeedInfo(GTFSBaseModel):
    """
    Represents feed metadata from `feed_info.txt`.

    Attributes:
        feed_publisher_name: Required. Name of the organization publishing the feed.
        feed_publisher_url: Required. URL of the feed publisher.
        feed_lang: Required. Language of the feed (IETF BCP 47 language code).
        default_lang: Optional. Default language for text in this feed.
        feed_start_date: Optional. Start date of feed validity (YYYYMMDD).
        feed_end_date: Optional. End date of feed validity (YYYYMMDD).
        feed_version: Optional. Version of the feed.
        feed_contact_email: Optional. Contact email for the feed.
        feed_contact_url: Optional. Contact URL for the feed.
    """
    feed_publisher_name: Annotated[str, StringConstraints(min_length=1)]
    feed_publisher_url: Annotated[str, StringConstraints(pattern=r"^https?://.+")]
    feed_lang: Annotated[str, StringConstraints(min_length=2)] # e.g., 'en', 'fr-CA'
    default_lang: Optional[Annotated[str, StringConstraints(min_length=2)]] = None
    feed_start_date: Optional[
        Annotated[str, StringConstraints(pattern=r"^[0-9]{8}$")]
    ] = None
    feed_end_date: Optional[
        Annotated[str, StringConstraints(pattern=r"^[0-9]{8}$")]
    ] = None
    feed_version: Optional[str] = None
    feed_contact_email: Optional[
        Annotated[str, StringConstraints(
            pattern=r"[^@ \t\r\n]+@[^@ \t\r\n]+\.[^@ \t\r\n]+"
        )]
    ] = None
    feed_contact_url: Optional[
        Annotated[str, StringConstraints(pattern=r"^https?://.+")]
    ] = None

    @field_validator("feed_start_date", "feed_end_date", mode="before")
    @classmethod
    def check_date_format_optional(cls, v: Optional[str]) -> Optional[str]:
        """Validate optional date strings (YYYYMMDD) if provided."""
        if v is not None and str(v).strip() != "": # Process if not None or empty
            try:
                datetime.strptime(v, "%Y%m%d").date()
            except ValueError as e:
                raise ValueError(
                    f"Date {v} is not a valid YYYYMMDD date."
                ) from e
            return v
        return None # Return None if input was None or empty string


# --- Main Schema Dictionary ---
# Maps GTFS filenames to their Pydantic model, database table name,
# and primary key column(s). This is used by data loading and processing
# components.
GTFS_FILE_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "agency.txt": {
        "model": Agency,
        "db_table_name": "gtfs_agency",
        "pk_cols": ["agency_id"], # Assuming agency_id becomes required for DB
    },
    "stops.txt": {
        "model": Stop,
        "db_table_name": "gtfs_stops",
        "pk_cols": ["stop_id"],
    },
    "routes.txt": {
        "model": Route,
        "db_table_name": "gtfs_routes",
        "pk_cols": ["route_id"],
    },
    "trips.txt": {
        "model": Trip,
        "db_table_name": "gtfs_trips",
        "pk_cols": ["trip_id"],
    },
    "stop_times.txt": {
        "model": StopTime,
        "db_table_name": "gtfs_stop_times",
        "pk_cols": ["trip_id", "stop_sequence"], # Composite PK
    },
    "calendar.txt": {
        "model": Calendar,
        "db_table_name": "gtfs_calendar",
        "pk_cols": ["service_id"],
    },
    "calendar_dates.txt": {
        "model": CalendarDate,
        "db_table_name": "gtfs_calendar_dates",
        "pk_cols": ["service_id", "date"], # Composite PK
    },
    "shapes.txt": { # Describes points that make up a shape
        "model": ShapePoint,
        "db_table_name": "gtfs_shapes_points", # Staging table for points
        "pk_cols": ["shape_id", "shape_pt_sequence"], # Composite PK
    },
    "frequencies.txt": {
        "model": Frequency,
        "db_table_name": "gtfs_frequencies",
        "pk_cols": ["trip_id", "start_time"], # Composite PK
    },
    "transfers.txt": {
        "model": Transfer,
        "db_table_name": "gtfs_transfers",
        # PK can be complex, often (from_stop_id, to_stop_id) if unique,
        # or might need to include transfer_type or even be a generated ID.
        # For simplicity, assuming from/to is usually unique enough for some feeds.
        # The GTFS spec does not mandate a PK for transfers.txt itself.
        # If multiple transfer types can exist between same pair of stops, this PK is insufficient.
        "pk_cols": ["from_stop_id", "to_stop_id", "transfer_type"],
    },
    "feed_info.txt": {
        "model": FeedInfo,
        "db_table_name": "gtfs_feed_info",
        # feed_publisher_name and feed_version often form a natural key
        "pk_cols": ["feed_publisher_name", "feed_version"],
    },
}

if __name__ == "__main__":
    # This block is for basic testing of the Pydantic models when the
    # script is run directly.
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)
    logger.info("--- Testing GTFS Schema Definitions (Pydantic Models) ---")

    test_results: Dict[str, List[str]] = {"valid": [], "invalid": []}

    def _test_model(ModelClass: Type[BaseModel], data: Dict, is_valid_expected: bool):
        model_name = ModelClass.__name__
        try:
            instance = ModelClass(**data)
            if is_valid_expected:
                logger.info(
                    f"VALID {model_name}: {instance.model_dump_json(indent=2)}"
                )
                test_results["valid"].append(model_name)
            else:
                logger.error(
                    f"UNEXPECTEDLY VALID {model_name} for data: {data}"
                )
                test_results["invalid"].append(f"{model_name} (unexpectedly valid)")
        except ValidationError as e_val:
            if is_valid_expected:
                logger.error(
                    f"UNEXPECTEDLY INVALID {model_name} for data {data}: "
                    f"{e_val.errors()}"
                )
                test_results["invalid"].append(f"{model_name} (unexpectedly invalid)")
            else:
                logger.info(
                    f"Caught EXPECTED validation error for {model_name}: "
                    f"{e_val.errors()}"
                )
                test_results["valid"].append(f"{model_name} (expected error)")
        except Exception as e_other:
            logger.error(
                f"UNEXPECTED Exception during {model_name} test with {data}: {e_other}"
            )
            test_results["invalid"].append(f"{model_name} (unexpected exception)")


    # Agency tests
    _test_model(Agency, {
        "agency_id": "MBTA", "agency_name": "MBTA",
        "agency_url": "http://mbta.com", "agency_timezone": "America/New_York"
    }, True)
    _test_model(Agency, {
        "agency_name": "Test", "agency_url": "badurl",
        "agency_timezone": "Test/Zone"
    }, False) # Expect agency_url to fail

    # Stop tests
    _test_model(Stop, {
        "stop_id": "place-north", "stop_name": "North Station",
        "stop_lat": 42.365577, "stop_lon": -71.06129, "location_type": 1
    }, True)
    _test_model(Stop, {
        "stop_id": "bad-lat", "stop_lat": 95.0, "stop_lon": -70.0
    }, False) # Expect stop_lat > 90 to fail

    # StopTime tests
    _test_model(StopTime, {
        "trip_id": "t1", "stop_id": "s1", "stop_sequence": 1,
        "arrival_time": "08:00:00"
    }, True)
    _test_model(StopTime, { # Both times None is currently allowed by validator
        "trip_id": "t2", "stop_id": "s2", "stop_sequence": 1,
        "arrival_time": None, "departure_time": None
    }, True) # If validator changes to disallow, this becomes False

    # Transfer tests
    _test_model(Transfer, {
        "from_stop_id": "s1", "to_stop_id": "s2", "transfer_type": 0
    }, True)
    _test_model(Transfer, {
        "from_stop_id": "s3", "to_stop_id": "s4", "transfer_type": 2,
        "min_transfer_time": 120
    }, True)
    _test_model(Transfer, { # transfer_type 2 requires min_transfer_time
        "from_stop_id": "s5", "to_stop_id": "s6", "transfer_type": 2,
        "min_transfer_time": None
    }, False)

    logger.info("\n--- Schema Definition Test Summary ---")
    logger.info(f"Models behaving as expected: {len(test_results['valid'])}")
    for item in test_results["valid"]:
        logger.info(f"  - {item}")
    if test_results["invalid"]:
        logger.error(f"Models NOT behaving as expected: {len(test_results['invalid'])}")
        for item in test_results["invalid"]:
            logger.error(f"  - {item}")
    logger.info("--- Schema definition tests finished. ---")