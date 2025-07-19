# OpenJourney Database Implementation

This document describes the implementation of the OpenJourney specification as the main database in the PostGIS section
of the Kubernetes stack.

## Overview

The OpenJourney specification has been implemented as a comprehensive PostgreSQL/PostGIS database schema that supports
the complete OpenJourney data model. This implementation provides:

- **Spatial Data Support**: Full PostGIS integration for geographical data
- **Complete Schema**: All OpenJourney core components and extensions
- **Performance Optimization**: Proper indexing and spatial indexes
- **Data Integrity**: Foreign key constraints and validation
- **Automatic Timestamps**: Created/updated timestamp tracking
- **Tile Serving**: Integration with pg_tileserv for vector tile serving

## Database Schema

The OpenJourney database schema is organized under the `openjourney` schema and includes the following tables:

### Core Tables

#### 1. Data Sources (`openjourney.data_sources`)

Stores information about data sources and transit agencies.

```sql
CREATE TABLE openjourney.data_sources
(
    source_id       TEXT PRIMARY KEY,
    source_name     TEXT,
    source_type     TEXT,
    source_url      TEXT,
    source_timezone TEXT,
    source_lang     TEXT,
    source_email    TEXT,
    source_phone    TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 2. Routes (`openjourney.routes`)

Defines transit routes and services.

```sql
CREATE TABLE openjourney.routes
(
    route_id        TEXT PRIMARY KEY,
    route_name      TEXT,
    agency_id       TEXT,
    agency_route_id TEXT,
    transit_mode    TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 3. Segments (`openjourney.segments`)

Individual route segments between stops.

```sql
CREATE TABLE openjourney.segments
(
    segment_id     TEXT PRIMARY KEY,
    route_id       TEXT REFERENCES openjourney.routes (route_id),
    start_stop_id  TEXT,
    end_stop_id    TEXT,
    distance       REAL,
    duration       INTEGER,
    transport_mode TEXT,
    accessibility  TEXT,
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 4. Path Geometry (`openjourney.path_geometry`)

Spatial path data with PostGIS geometry support.

```sql
CREATE TABLE openjourney.path_geometry
(
    point_id   SERIAL PRIMARY KEY,
    segment_id TEXT REFERENCES openjourney.segments (segment_id),
    geom       GEOMETRY(POINT, 4326),
    latitude   REAL,
    longitude  REAL,
    sequence   INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 5. Stops (`openjourney.stops`)

Transit stops and stations with spatial data.

```sql
CREATE TABLE openjourney.stops
(
    stop_id             TEXT PRIMARY KEY,
    stop_name           TEXT,
    geom                GEOMETRY(POINT, 4326),
    stop_lat            REAL,
    stop_lon            REAL,
    location_type       INTEGER,
    parent_station      TEXT,
    wheelchair_boarding INTEGER,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Supporting Tables

#### 6. Fares (`openjourney.fares`)

Fare information and pricing.

#### 7. Fare Rules (`openjourney.fare_rules`)

Rules governing fare application.

#### 8. Transfers (`openjourney.transfers`)

Transfer information between routes/stops.

#### 9. Vehicle Profiles (`openjourney.vehicle_profiles`)

Vehicle characteristics and capabilities (stored as JSONB).

#### 10. Navigation Instructions (`openjourney.navigation_instructions`)

Turn-by-turn navigation instructions.

#### 11. Cargo Data (`openjourney.cargo_data`)

Cargo and freight information.

#### 12. Temporal Data (`openjourney.temporal_data`)

Service calendars and scheduling information.

## Spatial Features

### PostGIS Integration

- **SRID 4326**: All geometry data uses WGS84 coordinate system
- **Spatial Indexes**: GIST indexes on all geometry columns for fast spatial queries
- **Geometry Types**: POINT geometry for stops and path points

### Spatial Queries Examples

```sql
-- Find stops within 1km of a point
SELECT stop_id, stop_name
FROM openjourney.stops
WHERE ST_DWithin(geom, ST_SetSRID(ST_MakePoint(-73.9857, 40.7484), 4326), 1000);

-- Get path geometry for a segment as GeoJSON
SELECT ST_AsGeoJSON(geom)
FROM openjourney.path_geometry
WHERE segment_id = 'segment_1'
ORDER BY sequence;
```

## Vector Tile Serving

The OpenJourney schema is integrated with pg_tileserv for serving vector tiles:

- **Schema Publishing**: The `openjourney` schema is included in pg_tileserv configuration
- **Tile Endpoint**: Vector tiles available at `/vector/openjourney.{table}/{z}/{x}/{y}.pbf`
- **Spatial Tables**: All tables with geometry columns are automatically served as vector tiles

### Example Tile URLs

```
/vector/openjourney.stops/{z}/{x}/{y}.pbf
/vector/openjourney.path_geometry/{z}/{x}/{y}.pbf
```

## Performance Features

### Indexes

- **Primary Keys**: All tables have appropriate primary keys
- **Foreign Keys**: Referential integrity maintained with foreign key constraints
- **Spatial Indexes**: GIST indexes on all geometry columns
- **Performance Indexes**: Additional indexes on frequently queried columns

### Triggers

- **Automatic Timestamps**: `updated_at` columns automatically updated on record changes
- **Data Validation**: Triggers can be added for data validation and business rules

## Data Import and Export

### Importing OpenJourney Data

```python
import psycopg2
from datetime import date

# Connect to database
conn = psycopg2.connect(
    host='localhost',
    database='openjourney',
    user='postgres',
    password='password'
)

# Insert route data
with conn.cursor() as cur:
    cur.execute("""
        INSERT INTO openjourney.routes 
        (route_id, route_name, agency_id, transit_mode)
        VALUES (%s, %s, %s, %s)
    """, ('route_1', 'Main Street Bus', 'metro_transit', 'bus'))

    # Insert stop with geometry
    cur.execute("""
        INSERT INTO openjourney.stops 
        (stop_id, stop_name, geom, stop_lat, stop_lon)
        VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s)
    """, ('stop_1', 'Main St & 1st Ave', -73.9857, 40.7484, 40.7484, -73.9857))

conn.commit()
```

### Exporting to GeoJSON

```sql
-- Export stops as GeoJSON
SELECT jsonb_build_object(
               'type', 'FeatureCollection',
               'features', jsonb_agg(
                       jsonb_build_object(
                               'type', 'Feature',
                               'geometry', ST_AsGeoJSON(geom)::jsonb,
                               'properties', jsonb_build_object(
                                       'stop_id', stop_id,
                                       'stop_name', stop_name,
                                       'wheelchair_boarding', wheelchair_boarding
                                             )
                       )
                           )
       )
FROM openjourney.stops;
```

## Testing

A comprehensive test suite is available at `tests/test_openjourney_schema.py` that verifies:

- Schema and table creation
- PostGIS extension installation
- Spatial indexes and geometry columns
- Data insertion and foreign key constraints
- Trigger functionality
- Sample data operations

### Running Tests

```bash
# Set environment variables
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=openjourney
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=password

# Run tests
python tests/test_openjourney_schema.py
```

## Kubernetes Deployment

The OpenJourney schema is automatically created when the PostgreSQL container starts in Kubernetes:

1. **Initialization Script**: `kubernetes/components/postgres/init-postgis.sh` creates the schema
2. **Configuration**: pg_tileserv is configured to serve the openjourney schema
3. **Persistence**: Data is persisted using Kubernetes PersistentVolumeClaims

### Deployment Commands

```bash
# Deploy the stack
kubectl apply -k kubernetes/overlays/production/

# Check database status
kubectl exec -it deployment/postgres-deployment -- psql -U postgres -d openjourney -c "\dt openjourney.*"
```

## Integration with Existing Systems

### GTFS Integration

The OpenJourney schema can coexist with existing GTFS data:

- GTFS data remains in the `gtfs` schema
- OpenJourney data in the `openjourney` schema
- Both schemas served by pg_tileserv

### Data Conversion

Tools and scripts can be developed to convert between:

- GTFS → OpenJourney format
- OpenJourney → GeoJSON
- OpenJourney → Vector tiles

## Future Enhancements

### Planned Features

1. **Advanced Spatial Queries**: More sophisticated spatial analysis functions
2. **Data Validation**: Enhanced validation rules and constraints
3. **Performance Monitoring**: Query performance tracking and optimization
4. **API Integration**: REST API for OpenJourney data access

### Extension Points

- Custom functions for OpenJourney-specific calculations
- Additional indexes for specific use cases
- Integration with other transit data standards
- Machine learning features for route optimization

## Support and Maintenance

### Monitoring

- Database performance metrics
- Spatial query performance
- Vector tile serving performance
- Data quality checks

### Backup and Recovery

- Regular database backups
- Point-in-time recovery capability
- Schema migration procedures
- Data integrity verification

## Conclusion

The OpenJourney database implementation provides a robust, scalable foundation for transit data management with full
spatial capabilities. The integration with PostGIS and pg_tileserv enables powerful spatial analysis and efficient
vector tile serving for web applications.

For questions or support, please refer to the project documentation or contact the development team.