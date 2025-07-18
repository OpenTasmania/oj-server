-- Canonical Database Schema for OpenJourney
-- This script creates the final transport_* tables as specified in Task 1
-- These tables replace the legacy gtfs_* tables and serve as the canonical data model

-- Create the canonical schema
CREATE SCHEMA IF NOT EXISTS canonical;
GRANT CREATE, USAGE ON SCHEMA canonical TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA canonical GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA canonical GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA canonical GRANT EXECUTE ON FUNCTIONS TO postgres;

-- Transport Stops: Canonical representation of all transit stops/stations
CREATE TABLE IF NOT EXISTS canonical.transport_stops (
    stop_id TEXT PRIMARY KEY,
    stop_name TEXT NOT NULL,
    stop_description TEXT,
    stop_lat DECIMAL(10, 8) NOT NULL,
    stop_lon DECIMAL(11, 8) NOT NULL,
    zone_id TEXT,
    stop_url TEXT,
    location_type INTEGER DEFAULT 0,
    parent_station TEXT,
    stop_timezone TEXT,
    wheelchair_boarding INTEGER DEFAULT 0,
    level_id TEXT,
    platform_code TEXT,
    geom GEOMETRY(POINT, 4326),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Foreign key constraints
    CONSTRAINT fk_parent_station FOREIGN KEY (parent_station) REFERENCES canonical.transport_stops(stop_id)
);

-- Transport Routes: Canonical representation of transit routes
CREATE TABLE IF NOT EXISTS canonical.transport_routes (
    route_id TEXT PRIMARY KEY,
    agency_id TEXT NOT NULL,
    route_short_name TEXT,
    route_long_name TEXT,
    route_description TEXT,
    route_type INTEGER NOT NULL,
    route_url TEXT,
    route_color TEXT DEFAULT 'FFFFFF',
    route_text_color TEXT DEFAULT '000000',
    route_sort_order INTEGER,
    continuous_pickup INTEGER DEFAULT 1,
    continuous_drop_off INTEGER DEFAULT 1,
    network_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Transport Trips: Canonical representation of individual transit trips/journeys
CREATE TABLE IF NOT EXISTS canonical.transport_trips (
    trip_id TEXT PRIMARY KEY,
    route_id TEXT NOT NULL,
    service_id TEXT NOT NULL,
    trip_headsign TEXT,
    trip_short_name TEXT,
    direction_id INTEGER, -- 0 or 1 for direction
    block_id TEXT,
    shape_id TEXT,
    wheelchair_accessible INTEGER DEFAULT 0,
    bikes_allowed INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Foreign key constraints
    CONSTRAINT fk_trip_route FOREIGN KEY (route_id) REFERENCES canonical.transport_routes(route_id),
    CONSTRAINT fk_trip_shape FOREIGN KEY (shape_id) REFERENCES canonical.transport_shapes(shape_id)
);

-- Transport Schedule: Canonical representation of stop times and scheduling
CREATE TABLE IF NOT EXISTS canonical.transport_schedule (
    schedule_id SERIAL PRIMARY KEY,
    trip_id TEXT NOT NULL,
    arrival_time TIME,
    departure_time TIME,
    stop_id TEXT NOT NULL,
    stop_sequence INTEGER NOT NULL,
    stop_headsign TEXT,
    pickup_type INTEGER DEFAULT 0,
    drop_off_type INTEGER DEFAULT 0,
    continuous_pickup INTEGER,
    continuous_drop_off INTEGER,
    shape_dist_traveled DECIMAL(10, 2),
    timepoint INTEGER DEFAULT 1, -- 0=approximate, 1=exact
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Foreign key constraints
    CONSTRAINT fk_schedule_trip FOREIGN KEY (trip_id) REFERENCES canonical.transport_trips(trip_id),
    CONSTRAINT fk_schedule_stop FOREIGN KEY (stop_id) REFERENCES canonical.transport_stops(stop_id),
    
    -- Unique constraint to prevent duplicate stop times
    CONSTRAINT uk_trip_stop_sequence UNIQUE (trip_id, stop_sequence)
);

-- Transport Shapes: Canonical representation of route geometries
CREATE TABLE IF NOT EXISTS canonical.transport_shapes (
    shape_id TEXT NOT NULL,
    shape_pt_lat DECIMAL(10, 8) NOT NULL,
    shape_pt_lon DECIMAL(11, 8) NOT NULL,
    shape_pt_sequence INTEGER NOT NULL,
    shape_dist_traveled DECIMAL(10, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Primary key on shape_id and sequence
    PRIMARY KEY (shape_id, shape_pt_sequence)
);

-- Transport Calendar: Service calendar information
CREATE TABLE IF NOT EXISTS canonical.transport_calendar (
    service_id TEXT PRIMARY KEY,
    monday BOOLEAN DEFAULT FALSE,
    tuesday BOOLEAN DEFAULT FALSE,
    wednesday BOOLEAN DEFAULT FALSE,
    thursday BOOLEAN DEFAULT FALSE,
    friday BOOLEAN DEFAULT FALSE,
    saturday BOOLEAN DEFAULT FALSE,
    sunday BOOLEAN DEFAULT FALSE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Transport Calendar Dates: Service exceptions
CREATE TABLE IF NOT EXISTS canonical.transport_calendar_dates (
    service_id TEXT NOT NULL,
    date DATE NOT NULL,
    exception_type INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Primary key on service and date
    PRIMARY KEY (service_id, date)
);

-- Transport Agencies: Transit agency information
CREATE TABLE IF NOT EXISTS canonical.transport_agencies (
    agency_id TEXT PRIMARY KEY,
    agency_name TEXT NOT NULL,
    agency_url TEXT NOT NULL,
    agency_timezone TEXT NOT NULL,
    agency_lang TEXT,
    agency_phone TEXT,
    agency_fare_url TEXT,
    agency_email TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add foreign key constraint for routes to agencies
ALTER TABLE canonical.transport_routes 
ADD CONSTRAINT fk_route_agency 
FOREIGN KEY (agency_id) REFERENCES canonical.transport_agencies(agency_id);

-- Add foreign key constraint for trips to calendar
ALTER TABLE canonical.transport_trips 
ADD CONSTRAINT fk_trip_service 
FOREIGN KEY (service_id) REFERENCES canonical.transport_calendar(service_id);

-- Create essential indexes for performance
CREATE INDEX IF NOT EXISTS idx_transport_stops_geom ON canonical.transport_stops USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_transport_stops_location ON canonical.transport_stops (stop_lat, stop_lon);
CREATE INDEX IF NOT EXISTS idx_transport_stops_parent ON canonical.transport_stops (parent_station);

CREATE INDEX IF NOT EXISTS idx_transport_routes_agency ON canonical.transport_routes (agency_id);
CREATE INDEX IF NOT EXISTS idx_transport_routes_type ON canonical.transport_routes (route_type);

CREATE INDEX IF NOT EXISTS idx_transport_trips_route ON canonical.transport_trips (route_id);
CREATE INDEX IF NOT EXISTS idx_transport_trips_service ON canonical.transport_trips (service_id);
CREATE INDEX IF NOT EXISTS idx_transport_trips_shape ON canonical.transport_trips (shape_id);

CREATE INDEX IF NOT EXISTS idx_transport_schedule_trip ON canonical.transport_schedule (trip_id);
CREATE INDEX IF NOT EXISTS idx_transport_schedule_stop ON canonical.transport_schedule (stop_id);
CREATE INDEX IF NOT EXISTS idx_transport_schedule_sequence ON canonical.transport_schedule (trip_id, stop_sequence);
CREATE INDEX IF NOT EXISTS idx_transport_schedule_times ON canonical.transport_schedule (arrival_time, departure_time);

CREATE INDEX IF NOT EXISTS idx_transport_shapes_id ON canonical.transport_shapes (shape_id);
CREATE INDEX IF NOT EXISTS idx_transport_shapes_sequence ON canonical.transport_shapes (shape_id, shape_pt_sequence);

CREATE INDEX IF NOT EXISTS idx_transport_calendar_dates ON canonical.transport_calendar (start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_transport_calendar_service ON canonical.transport_calendar_dates (service_id);
CREATE INDEX IF NOT EXISTS idx_transport_calendar_date ON canonical.transport_calendar_dates (date);

-- Create triggers to update the updated_at timestamp
CREATE OR REPLACE FUNCTION canonical.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers to all tables
CREATE TRIGGER update_transport_stops_updated_at BEFORE UPDATE ON canonical.transport_stops FOR EACH ROW EXECUTE FUNCTION canonical.update_updated_at_column();
CREATE TRIGGER update_transport_routes_updated_at BEFORE UPDATE ON canonical.transport_routes FOR EACH ROW EXECUTE FUNCTION canonical.update_updated_at_column();
CREATE TRIGGER update_transport_trips_updated_at BEFORE UPDATE ON canonical.transport_trips FOR EACH ROW EXECUTE FUNCTION canonical.update_updated_at_column();
CREATE TRIGGER update_transport_schedule_updated_at BEFORE UPDATE ON canonical.transport_schedule FOR EACH ROW EXECUTE FUNCTION canonical.update_updated_at_column();
CREATE TRIGGER update_transport_shapes_updated_at BEFORE UPDATE ON canonical.transport_shapes FOR EACH ROW EXECUTE FUNCTION canonical.update_updated_at_column();
CREATE TRIGGER update_transport_calendar_updated_at BEFORE UPDATE ON canonical.transport_calendar FOR EACH ROW EXECUTE FUNCTION canonical.update_updated_at_column();
CREATE TRIGGER update_transport_calendar_dates_updated_at BEFORE UPDATE ON canonical.transport_calendar_dates FOR EACH ROW EXECUTE FUNCTION canonical.update_updated_at_column();
CREATE TRIGGER update_transport_agencies_updated_at BEFORE UPDATE ON canonical.transport_agencies FOR EACH ROW EXECUTE FUNCTION canonical.update_updated_at_column();

-- Grant permissions on canonical schema objects
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA canonical TO postgres;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA canonical TO postgres;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA canonical TO postgres;

-- Create views for backward compatibility and easier querying
CREATE OR REPLACE VIEW canonical.v_active_services AS
SELECT DISTINCT c.service_id, c.start_date, c.end_date
FROM canonical.transport_calendar c
WHERE c.end_date >= CURRENT_DATE
   OR EXISTS (
       SELECT 1 FROM canonical.transport_calendar_dates cd 
       WHERE cd.service_id = c.service_id 
       AND cd.date >= CURRENT_DATE 
       AND cd.exception_type = 1
   );

CREATE OR REPLACE VIEW canonical.v_route_summary AS
SELECT 
    r.route_id,
    r.route_short_name,
    r.route_long_name,
    r.route_type,
    a.agency_name,
    COUNT(DISTINCT t.trip_id) as trip_count,
    COUNT(DISTINCT s.stop_id) as stop_count
FROM canonical.transport_routes r
LEFT JOIN canonical.transport_agencies a ON r.agency_id = a.agency_id
LEFT JOIN canonical.transport_trips t ON r.route_id = t.route_id
LEFT JOIN canonical.transport_schedule s ON t.trip_id = s.trip_id
GROUP BY r.route_id, r.route_short_name, r.route_long_name, r.route_type, a.agency_name;

-- Add comments for documentation
COMMENT ON SCHEMA canonical IS 'Canonical database schema for OpenJourney transport data';
COMMENT ON TABLE canonical.transport_stops IS 'Canonical representation of all transit stops and stations';
COMMENT ON TABLE canonical.transport_routes IS 'Canonical representation of transit routes';
COMMENT ON TABLE canonical.transport_trips IS 'Canonical representation of individual transit trips/journeys';
COMMENT ON TABLE canonical.transport_schedule IS 'Canonical representation of stop times and scheduling information';
COMMENT ON TABLE canonical.transport_shapes IS 'Canonical representation of route geometries and shapes';
COMMENT ON TABLE canonical.transport_calendar IS 'Service calendar information defining when services operate';
COMMENT ON TABLE canonical.transport_calendar_dates IS 'Service exceptions (added or removed service dates)';
COMMENT ON TABLE canonical.transport_agencies IS 'Transit agency information';