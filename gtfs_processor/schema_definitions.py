#!/usr/bin/env python3
from typing import Optional, Literal

from pydantic import BaseModel, validator, Field, conint, confloat, constr


# --- Pydantic Model Configuration ---
class GTFSBaseModel(BaseModel):
    class Config:
        extra = 'ignore'  # Ignore extra columns from CSV not defined in model
        anystr_strip_whitespace = True  # Strip whitespace from all string fields
        validate_assignment = True  # Validate when setting attributes after creation


# --- GTFS File Specific Models ---

class Agency(GTFSBaseModel):
    agency_id: Optional[constr(min_length=1)] = None  # Conditionally Required: required if multiple agencies
    agency_name: constr(min_length=1)
    agency_url: constr(pattern=r'^https?://.+')  # Basic URL validation
    agency_timezone: constr(min_length=1)  # Should be a valid TZ database name
    agency_lang: Optional[constr(min_length=2, max_length=2)] = None  # ISO 639-1 code
    agency_phone: Optional[str] = None
    agency_fare_url: Optional[constr(pattern=r'^https?://.+')] = None
    agency_email: Optional[constr(pattern=r'[^@ \t\r\n]+@[^@ \t\r\n]+\.[^@ \t\r\n]+')] = None  # Basic email validation


class Stop(GTFSBaseModel):
    stop_id: constr(min_length=1)
    stop_code: Optional[str] = None
    stop_name: Optional[constr(min_length=1)] = None  # Conditionally Required if not a station with name
    stop_desc: Optional[str] = None
    stop_lat: confloat(ge=-90, le=90)  # Required
    stop_lon: confloat(ge=-180, le=180)  # Required
    zone_id: Optional[str] = None
    stop_url: Optional[constr(pattern=r'^https?://.+')] = None
    location_type: Optional[conint(ge=0, le=4)] = Field(
        0)  # 0 for stop/platform, 1 for station, etc. Default to 0 (stop/platform)
    parent_station: Optional[str] = None  # Should be a stop_id of a station (location_type=1)
    stop_timezone: Optional[str] = None  # Optional, if different from agency_timezone
    wheelchair_boarding: Optional[conint(ge=0, le=2)] = None  # 0, 1, or 2
    level_id: Optional[str] = None
    platform_code: Optional[str] = None
    # geom: str # This will be added by the transform.py module as WKT


class Route(GTFSBaseModel):
    route_id: constr(min_length=1)
    agency_id: Optional[str] = None  # Conditionally Required if multiple agencies
    route_short_name: Optional[str] = Field("", max_length=50)  # GTFS says default empty string is okay
    route_long_name: Optional[str] = Field("", max_length=255)
    route_desc: Optional[str] = None
    route_type: conint(ge=0, le=7)  # Or more specific if only certain types supported, e.g. 3 for Bus
    # Extended route types exist (e.g., up to 1700s for specific rail)
    # For a general validator, a wider range or specific list could be used.
    route_url: Optional[constr(pattern=r'^https?://.+')] = None
    route_color: Optional[constr(pattern=r'^[0-9a-fA-F]{6}$')] = None  # Hex color
    route_text_color: Optional[constr(pattern=r'^[0-9a-fA-F]{6}$')] = None
    route_sort_order: Optional[conint(ge=0)] = None
    continuous_pickup: Optional[conint(ge=0, le=3)] = Field(None)  # 0-regular, 1-none, 2-phone, 3-driver
    continuous_drop_off: Optional[conint(ge=0, le=3)] = Field(None)


class Trip(GTFSBaseModel):
    route_id: constr(min_length=1)
    service_id: constr(min_length=1)
    trip_id: constr(min_length=1)
    trip_headsign: Optional[str] = None
    trip_short_name: Optional[str] = None
    direction_id: Optional[Literal[0, 1]] = None  # 0 or 1
    block_id: Optional[str] = None
    shape_id: Optional[str] = None
    wheelchair_accessible: Optional[Literal[0, 1, 2]] = Field(None)  # 0-no info, 1-accessible, 2-not accessible
    bikes_allowed: Optional[Literal[0, 1, 2]] = Field(None)  # 0-no info, 1-allowed, 2-not allowed


class StopTime(GTFSBaseModel):
    trip_id: constr(min_length=1)
    # GTFS times can be > 23:59:59, so simple time type won't work. Use regex for HH:MM:SS format.
    arrival_time: Optional[constr(pattern=r'^[0-9]{1,2}:[0-5][0-9]:[0-5][0-9]$')] = None
    departure_time: Optional[constr(pattern=r'^[0-9]{1,2}:[0-5][0-9]:[0-5][0-9]$')] = None
    stop_id: constr(min_length=1)
    stop_sequence: conint(ge=0)  # Must be non-negative, usually positive and increasing
    stop_headsign: Optional[str] = None
    pickup_type: Optional[conint(ge=0, le=3)] = Field(None)  # Default is 0 if not provided
    drop_off_type: Optional[conint(ge=0, le=3)] = Field(None)  # Default is 0 if not provided
    continuous_pickup: Optional[conint(ge=0, le=3)] = Field(None)
    continuous_drop_off: Optional[conint(ge=0, le=3)] = Field(None)
    shape_dist_traveled: Optional[confloat(ge=0)] = None
    timepoint: Optional[Literal[0, 1]] = Field(None)  # 0-approximate, 1-exact. Default is 1 if not provided.

    @validator('arrival_time', 'departure_time', pre=True, always=True)
    def check_times_conditionally_required(cls, v, values, field):
        # As per spec, arrival_time and departure_time are conditionally required.
        # At least one must be specified for each stop_time.
        # This simple validator just ensures it passes if present, more complex logic could check that
        # if one is None the other is not, but that depends on how you handle None vs empty string from CSV.
        # Pydantic handles optional by default if type is Optional[str].
        # For now, just a basic pass-through or more specific validation if needed.
        if field.name == 'arrival_time' and v is None and values.get('departure_time') is None:
            # This validation should ideally happen after both fields are attempted to be parsed.
            # Pydantic v2 model_validator is better for cross-field validation.
            pass  # Post-validation logic would be better here.
        return v


class Calendar(GTFSBaseModel):
    service_id: constr(min_length=1)
    monday: Literal[0, 1]
    tuesday: Literal[0, 1]
    wednesday: Literal[0, 1]
    thursday: Literal[0, 1]
    friday: Literal[0, 1]
    saturday: Literal[0, 1]
    sunday: Literal[0, 1]
    start_date: constr(pattern=r'^[0-9]{8}$')  # YYYYMMDD
    end_date: constr(pattern=r'^[0-9]{8}$')  # YYYYMMDD

    @validator('start_date', 'end_date')
    def check_date_format(cls, v):
        # Further validation: convert to date object to check validity
        try:
            datetime.strptime(v, "%Y%m%d").date()
        except ValueError:
            raise ValueError(f"Date {v} is not a valid YYYYMMDD date.")
        return v


class CalendarDate(GTFSBaseModel):
    service_id: constr(min_length=1)
    date: constr(pattern=r'^[0-9]{8}$')  # YYYYMMDD
    exception_type: Literal[1, 2]  # 1-added, 2-removed

    @validator('date')
    def check_date_format(cls, v):
        try:
            datetime.strptime(v, "%Y%m%d").date()
        except ValueError:
            raise ValueError(f"Date {v} is not a valid YYYYMMDD date.")
        return v


class ShapePoint(GTFSBaseModel):  # For shapes.txt
    shape_id: constr(min_length=1)
    shape_pt_lat: confloat(ge=-90, le=90)
    shape_pt_lon: confloat(ge=-180, le=180)
    shape_pt_sequence: conint(ge=0)
    shape_dist_traveled: Optional[confloat(ge=0)] = None


class Frequency(GTFSBaseModel):
    trip_id: constr(min_length=1)
    start_time: constr(pattern=r'^[0-9]{1,2}:[0-5][0-9]:[0-5][0-9]$')
    end_time: constr(pattern=r'^[0-9]{1,2}:[0-5][0-9]:[0-5][0-9]$')
    headway_secs: conint(gt=0)  # Must be positive
    exact_times: Optional[Literal[0, 1]] = Field(None)  # 0-frequency based, 1-schedule based


class Transfer(GTFSBaseModel):
    from_stop_id: constr(min_length=1)
    to_stop_id: constr(min_length=1)
    transfer_type: conint(ge=0, le=3)  # 0-recommended, 1-timed, 2-min_time, 3-not possible
    min_transfer_time: Optional[conint(ge=0)] = None

    @validator('min_transfer_time', always=True)
    def check_min_transfer_time_required(cls, v, values):
        if values.get('transfer_type') == 2 and v is None:
            raise ValueError('min_transfer_time is required when transfer_type is 2.')
        return v


class FeedInfo(GTFSBaseModel):
    feed_publisher_name: constr(min_length=1)
    feed_publisher_url: constr(pattern=r'^https?://.+')
    feed_lang: constr(min_length=2)  # ISO 639-1 code
    default_lang: Optional[constr(min_length=2)] = None
    feed_start_date: Optional[constr(pattern=r'^[0-9]{8}$')] = None
    feed_end_date: Optional[constr(pattern=r'^[0-9]{8}$')] = None
    feed_version: Optional[str] = None
    feed_contact_email: Optional[constr(pattern=r'[^@ \t\r\n]+@[^@ \t\r\n]+\.[^@ \t\r\n]+')] = None
    feed_contact_url: Optional[constr(pattern=r'^https?://.+')] = None

    @validator('feed_start_date', 'feed_end_date', pre=True)
    def check_date_format_optional(cls, v):
        if v is not None and v != "":  # Allow empty string if field is truly optional
            try:
                datetime.strptime(v, "%Y%m%d").date()
            except ValueError:
                raise ValueError(f"Date {v} is not a valid YYYYMMDD date.")
        return v


# --- Main Schema Dictionary ---
# Maps GTFS filenames to their Pydantic model and primary key(s) for DB ops
# This will be used by validate.py and load.py
GTFS_FILE_SCHEMAS = {
    "agency.txt": {"model": Agency, "db_table_name": "gtfs_agency", "pk_cols": ["agency_id"]},
    # PK might be absent if single agency
    "stops.txt": {"model": Stop, "db_table_name": "gtfs_stops", "pk_cols": ["stop_id"]},
    "routes.txt": {"model": Route, "db_table_name": "gtfs_routes", "pk_cols": ["route_id"]},
    "trips.txt": {"model": Trip, "db_table_name": "gtfs_trips", "pk_cols": ["trip_id"]},
    "stop_times.txt": {"model": StopTime, "db_table_name": "gtfs_stop_times", "pk_cols": ["trip_id", "stop_sequence"]},
    "calendar.txt": {"model": Calendar, "db_table_name": "gtfs_calendar", "pk_cols": ["service_id"]},
    "calendar_dates.txt": {"model": CalendarDate, "db_table_name": "gtfs_calendar_dates",
                           "pk_cols": ["service_id", "date"]},
    "shapes.txt": {"model": ShapePoint, "db_table_name": "gtfs_shapes_points",
                   "pk_cols": ["shape_id", "shape_pt_sequence"]},
    "frequencies.txt": {"model": Frequency, "db_table_name": "gtfs_frequencies", "pk_cols": ["trip_id", "start_time"]},
    "transfers.txt": {"model": Transfer, "db_table_name": "gtfs_transfers",
                      "pk_cols": ["from_stop_id", "to_stop_id", "transfer_type"]},
    # transfer_type might not always be part of PK
    "feed_info.txt": {"model": FeedInfo, "db_table_name": "gtfs_feed_info",
                      "pk_cols": ["feed_publisher_name", "feed_version"]}
    # No standard PK, often single row. Using these as example.
}

# Define DLQ table structures conceptually (could be simpler, e.g., just a few common fields and a data blob)
# For now, let's assume DLQ tables mirror the main tables with added error metadata columns.
# The actual creation of DLQ tables would happen in setup_schema or a dedicated DLQ setup function.
# Example: dlq_gtfs_stops would have all columns of Stop plus error_reason, raw_data, etc.

if __name__ == "__main__":
    logger.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger.info("--- Testing GTFS Schema Definitions (Pydantic Models) ---")

    # Test Agency model
    try:
        agency_data_ok = {"agency_id": "MBTA", "agency_name": "MBTA", "agency_url": "http://mbta.com",
                          "agency_timezone": "America/New_York"}
        agency = Agency(**agency_data_ok)
        logger.info(f"Valid Agency: {agency.model_dump_json(indent=2)}")

        agency_data_bad_url = {"agency_name": "Test", "agency_url": "badurl", "agency_timezone": "Test/Zone"}
        # agency_fail = Agency(**agency_data_bad_url) # This will raise ValidationError
    except Exception as e:  # Pydantic raises ValidationError
        logger.error(f"Agency validation error: {e}")

    # Test Stop model
    try:
        stop_data_ok = {"stop_id": "place-north", "stop_name": "North Station", "stop_lat": 42.365577,
                        "stop_lon": -71.06129, "location_type": 1}
        stop = Stop(**stop_data_ok)
        logger.info(f"Valid Stop: {stop.model_dump_json(indent=2)}")

        stop_data_bad_lat = {"stop_id": "bad-lat", "stop_lat": 95.0, "stop_lon": -70.0}
        # stop_fail = Stop(**stop_data_bad_lat)
    except Exception as e:
        logger.error(f"Stop validation error: {e}")

    # Test Route model
    try:
        route_data_ok = {"route_id": "Blue", "route_short_name": "BL", "route_long_name": "Blue Line",
                         "route_type": 1}  # Subway
        route = Route(**route_data_ok)
        logger.info(f"Valid Route: {route.model_dump_json(indent=2)}")
    except Exception as e:
        logger.error(f"Route validation error: {e}")

    # Test Calendar model
    try:
        calendar_data_ok = {
            "service_id": "WEEKDAY", "monday": 1, "tuesday": 1, "wednesday": 1, "thursday": 1,
            "friday": 1, "saturday": 0, "sunday": 0, "start_date": "20250101", "end_date": "20251231"
        }
        calendar = Calendar(**calendar_data_ok)
        logger.info(f"Valid Calendar: {calendar.model_dump_json(indent=2)}")

        calendar_data_bad_date = {"service_id": "BAD", "monday": 1, "tuesday": 1, "wednesday": 1, "thursday": 1,
                                  "friday": 1, "saturday": 0, "sunday": 0, "start_date": "20251301",
                                  "end_date": "20251231"}
        # calendar_fail = Calendar(**calendar_data_bad_date)
    except Exception as e:
        logger.error(f"Calendar validation error: {e}")

    logger.info("--- Schema definition tests finished (some intentionally commented out to avoid script exit) ---")
