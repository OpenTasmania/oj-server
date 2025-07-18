
#!/bin/sh
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
-- Create OpenJourney schema for essential GTFS tables only
-- This script creates only the minimal tables and columns needed for basic GTFS functionality
-- Optional tables (fares, transfers, shapes, etc.) are created dynamically by the plugin when needed

    CREATE SCHEMA IF NOT EXISTS openjourney;
    GRANT CREATE, USAGE ON SCHEMA openjourney TO "$POSTGRES_USER";
    ALTER DEFAULT PRIVILEGES IN SCHEMA openjourney GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON TABLES TO "$POSTGRES_USER";
    ALTER DEFAULT PRIVILEGES IN SCHEMA openjourney GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO "$POSTGRES_USER";
    ALTER DEFAULT PRIVILEGES IN SCHEMA openjourney GRANT EXECUTE ON FUNCTIONS TO "$POSTGRES_USER";

    -- Essential: Data Sources table (maps to GTFS agency.txt)
    CREATE TABLE IF NOT EXISTS openjourney.data_sources (
        source_id TEXT PRIMARY KEY,
        source_name TEXT NOT NULL,
        source_type TEXT DEFAULT 'gtfs',
        source_url TEXT,
        source_timezone TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Essential: Routes table (maps to GTFS routes.txt)
    CREATE TABLE IF NOT EXISTS openjourney.routes (
        route_id TEXT PRIMARY KEY,
        route_name TEXT NOT NULL,
        agency_id TEXT,
        route_type INTEGER,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Essential: Stops table (maps to GTFS stops.txt)
    CREATE TABLE IF NOT EXISTS openjourney.stops (
        stop_id TEXT PRIMARY KEY,
        stop_name TEXT NOT NULL,
        stop_lat REAL NOT NULL,
        stop_lon REAL NOT NULL,
        location_type INTEGER DEFAULT 0,
        parent_station TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Essential: Segments table (maps to GTFS trips.txt and stop_times.txt)
    CREATE TABLE IF NOT EXISTS openjourney.segments (
        segment_id TEXT PRIMARY KEY,
        route_id TEXT NOT NULL REFERENCES openjourney.routes(route_id),
        start_stop_id TEXT NOT NULL,
        end_stop_id TEXT NOT NULL,
        sequence_order INTEGER,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Essential: Temporal Data table (maps to GTFS calendar.txt/calendar_dates.txt)
    CREATE TABLE IF NOT EXISTS openjourney.temporal_data (
        service_id TEXT PRIMARY KEY,
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        monday BOOLEAN DEFAULT FALSE,
        tuesday BOOLEAN DEFAULT FALSE,
        wednesday BOOLEAN DEFAULT FALSE,
        thursday BOOLEAN DEFAULT FALSE,
        friday BOOLEAN DEFAULT FALSE,
        saturday BOOLEAN DEFAULT FALSE,
        sunday BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Create essential indexes for performance
    CREATE INDEX IF NOT EXISTS idx_segments_route_id ON openjourney.segments (route_id);
    CREATE INDEX IF NOT EXISTS idx_segments_stops ON openjourney.segments (start_stop_id, end_stop_id);
    CREATE INDEX IF NOT EXISTS idx_temporal_data_dates ON openjourney.temporal_data (start_date, end_date);
    CREATE INDEX IF NOT EXISTS idx_stops_location ON openjourney.stops (stop_lat, stop_lon);

    -- Create triggers to update the updated_at timestamp
    CREATE OR REPLACE FUNCTION openjourney.update_updated_at_column()
    RETURNS TRIGGER AS \$\$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    \$\$ language 'plpgsql';

    -- Apply triggers only to essential tables
    CREATE TRIGGER update_data_sources_updated_at BEFORE UPDATE ON openjourney.data_sources FOR EACH ROW EXECUTE FUNCTION openjourney.update_updated_at_column();
    CREATE TRIGGER update_routes_updated_at BEFORE UPDATE ON openjourney.routes FOR EACH ROW EXECUTE FUNCTION openjourney.update_updated_at_column();
    CREATE TRIGGER update_stops_updated_at BEFORE UPDATE ON openjourney.stops FOR EACH ROW EXECUTE FUNCTION openjourney.update_updated_at_column();
    CREATE TRIGGER update_segments_updated_at BEFORE UPDATE ON openjourney.segments FOR EACH ROW EXECUTE FUNCTION openjourney.update_updated_at_column();
    CREATE TRIGGER update_temporal_data_updated_at BEFORE UPDATE ON openjourney.temporal_data FOR EACH ROW EXECUTE FUNCTION openjourney.update_updated_at_column();

    -- Grant permissions on OpenJourney schema objects
    GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA openjourney TO "$POSTGRES_USER";
    GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA openjourney TO "$POSTGRES_USER";
    GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA openjourney TO "$POSTGRES_USER";

    -- Note: Optional tables (fares, transfers, path_geometry, etc.) will be created
    -- dynamically by the GTFS plugin when processing feeds that contain this data
EOSQL