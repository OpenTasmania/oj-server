# pg_tileserv Vector Tile Server Plugin

This plugin provides pg_tileserv for serving vector tiles directly from PostgreSQL/PostGIS spatial tables.

## Features

- **Vector Tile Server**: High-performance vector tile serving from PostGIS
- **Automatic Discovery**: Automatically discovers and serves spatial tables
- **REST API**: RESTful API for vector tile access and metadata
- **Performance Optimization**: Connection pooling and caching for high throughput
- **CORS Support**: Cross-Origin Resource Sharing for web applications
- **Multiple Formats**: Support for MVT (Mapbox Vector Tiles) and JSON formats
- **Kubernetes Deployment**: Containerized deployment with scalable architecture

## What This Plugin Does

The pg_tileserv plugin provides a lightweight, fast vector tile server that serves tiles directly from PostGIS spatial tables. It automatically discovers spatial tables in the database and exposes them as vector tile endpoints, enabling efficient rendering of geographic data in web mapping applications.

Key capabilities:
- Serves vector tiles in Mapbox Vector Tile (MVT) format
- Automatically discovers PostGIS spatial tables
- Provides metadata and collection information via REST API
- Supports dynamic tile generation with configurable parameters
- Handles large datasets efficiently with spatial indexing
- Offers flexible styling and filtering options
- Provides health monitoring and status endpoints

## Implementation

### Core Components

- **Tile Server**: Core pg_tileserv application serving vector tiles
- **PostGIS Integration**: Direct connection to PostGIS spatial tables
- **REST API**: HTTP endpoints for tiles and metadata
- **Connection Pool**: Database connection management for performance
- **Cache Layer**: HTTP caching for improved response times

### Architecture

```
Web Client → pg_tileserv API → PostGIS Database → Vector Tiles
                    ↓
              Metadata / Collections
```

## How to Use

### Configuration

Configure pg_tileserv settings in your YAML configuration:

```yaml
pg_tileserv:
  enabled: true
  http_port: 7800
  db_host: "postgres-service"
  db_port: 5432
  db_name: "openjourney"
  db_user: "postgres"
  pool_size: 4
  pool_size_max: 16
  listen_address: "0.0.0.0"
  cors_origins: ["*"]
  default_resolution: 4096
  default_buffer: 256
  max_features_per_tile: 10000
  
  tile_config:
    cache_control: "public, max-age=3600"
    gzip: true
    debug: false
    pretty: false
```

### Kubernetes Deployment

The plugin automatically deploys pg_tileserv when the system is set up:

```bash
# Deploy pg_tileserv service
kubectl apply -f kubernetes/

# Check deployment status
kubectl get pods -l app=pg-tileserv
kubectl get services pg-tileserv-service
```

### Database Requirements

The plugin requires PostGIS extension and spatial tables:

```sql
-- PostGIS extension (created automatically)
CREATE EXTENSION IF NOT EXISTS postgis;

-- Example spatial table
CREATE TABLE transit_stops (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    geom GEOMETRY(POINT, 4326)
);

-- Create spatial index
CREATE INDEX idx_transit_stops_geom ON transit_stops USING GIST (geom);
```

## API Endpoints

### Collections and Metadata

#### List Available Collections
```bash
# Get all available spatial tables
curl "http://pg-tileserv-service:7800/collections.json"

# Response includes table metadata and tile URLs
{
  "collections": [
    {
      "id": "public.transit_stops",
      "title": "Transit Stops",
      "extent": {...},
      "links": [
        {
          "rel": "tiles",
          "href": "http://pg-tileserv-service:7800/collections/public.transit_stops/items/{z}/{x}/{y}.mvt"
        }
      ]
    }
  ]
}
```

#### Collection Details
```bash
# Get specific collection information
curl "http://pg-tileserv-service:7800/collections/public.transit_stops.json"
```

### Vector Tiles

#### Tile Access
```bash
# Get vector tile for specific zoom/x/y
curl "http://pg-tileserv-service:7800/collections/public.transit_stops/items/10/512/512.mvt"

# With query parameters
curl "http://pg-tileserv-service:7800/collections/public.transit_stops/items/10/512/512.mvt?properties=name,type&filter=type='bus_stop'"
```

#### Tile Parameters

- **properties**: Comma-separated list of properties to include
- **filter**: SQL WHERE clause for filtering features
- **resolution**: Tile resolution (default: 4096)
- **buffer**: Tile buffer in pixels (default: 256)
- **limit**: Maximum features per tile

### Health and Status

#### Health Check
```bash
# Check service health
curl "http://pg-tileserv-service:7800/health"

# Response
{
  "status": "ok",
  "database": "connected",
  "version": "1.0.0"
}
```

## Web Mapping Integration

### Mapbox GL JS

```javascript
// Add pg_tileserv source to Mapbox GL JS map
map.addSource('transit-stops', {
  type: 'vector',
  tiles: ['http://pg-tileserv-service:7800/collections/public.transit_stops/items/{z}/{x}/{y}.mvt'],
  maxzoom: 16
});

// Add layer
map.addLayer({
  id: 'stops-layer',
  type: 'circle',
  source: 'transit-stops',
  'source-layer': 'public.transit_stops',
  paint: {
    'circle-radius': 6,
    'circle-color': '#3490dc',
    'circle-stroke-width': 2,
    'circle-stroke-color': '#ffffff'
  }
});
```

### Leaflet with Vector Tiles

```javascript
// Using Leaflet.VectorGrid plugin
var vectorTileOptions = {
  vectorTileLayerStyles: {
    'public.transit_stops': {
      radius: 6,
      fillColor: '#3490dc',
      color: '#ffffff',
      weight: 2,
      fillOpacity: 0.8
    }
  }
};

var vectorLayer = L.vectorGrid.protobuf(
  'http://pg-tileserv-service:7800/collections/public.transit_stops/items/{z}/{x}/{y}.mvt',
  vectorTileOptions
).addTo(map);
```

### OpenLayers

```javascript
// OpenLayers vector tile layer
var vectorSource = new ol.source.VectorTile({
  format: new ol.format.MVT(),
  url: 'http://pg-tileserv-service:7800/collections/public.transit_stops/items/{z}/{x}/{y}.mvt'
});

var vectorLayer = new ol.layer.VectorTile({
  source: vectorSource,
  style: new ol.style.Style({
    image: new ol.style.Circle({
      radius: 6,
      fill: new ol.style.Fill({color: '#3490dc'}),
      stroke: new ol.style.Stroke({color: '#ffffff', width: 2})
    })
  })
});

map.addLayer(vectorLayer);
```

## Spatial Table Optimization

### Indexing

```sql
-- Create spatial index for performance
CREATE INDEX idx_table_geom ON spatial_table USING GIST (geom);

-- Create attribute indexes for filtering
CREATE INDEX idx_table_type ON spatial_table (type);
CREATE INDEX idx_table_name ON spatial_table (name);
```

### Table Structure

```sql
-- Optimized table structure for vector tiles
CREATE TABLE optimized_spatial_table (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,
    properties JSONB,
    geom GEOMETRY(POINT, 4326) NOT NULL
);

-- Indexes
CREATE INDEX idx_optimized_geom ON optimized_spatial_table USING GIST (geom);
CREATE INDEX idx_optimized_type ON optimized_spatial_table (type);
CREATE INDEX idx_optimized_properties ON optimized_spatial_table USING GIN (properties);
```

### Data Preparation

```sql
-- Simplify geometries for better performance
UPDATE spatial_table 
SET geom = ST_Simplify(geom, 0.0001) 
WHERE ST_GeometryType(geom) IN ('ST_Polygon', 'ST_MultiPolygon');

-- Ensure valid geometries
UPDATE spatial_table 
SET geom = ST_MakeValid(geom) 
WHERE NOT ST_IsValid(geom);
```

## Performance Tuning

### Database Configuration

```sql
-- PostgreSQL configuration for spatial queries
-- In postgresql.conf:
shared_buffers = 256MB
work_mem = 64MB
maintenance_work_mem = 256MB
effective_cache_size = 1GB

-- PostGIS specific
max_locks_per_transaction = 256
```

### Connection Pooling

```yaml
pg_tileserv:
  pool_size: 4          # Initial connections
  pool_size_max: 16     # Maximum connections
  pool_timeout: 30      # Connection timeout (seconds)
```

### Caching Strategy

```yaml
pg_tileserv:
  tile_config:
    cache_control: "public, max-age=3600"  # 1 hour cache
    gzip: true                             # Enable compression
```

## Troubleshooting

### Common Issues

1. **No Spatial Tables Found**
   - Verify PostGIS extension is installed: `SELECT * FROM pg_extension WHERE extname = 'postgis'`
   - Check for spatial tables: `SELECT * FROM geometry_columns`
   - Ensure tables have spatial indexes
   - Verify table permissions for pg_tileserv user

2. **Slow Tile Generation**
   - Check spatial indexes: `EXPLAIN ANALYZE SELECT * FROM table WHERE ST_Intersects(geom, bbox)`
   - Monitor connection pool usage
   - Review tile resolution and buffer settings
   - Consider geometry simplification

3. **Service Unavailable**
   - Check pg_tileserv pod status: `kubectl get pods -l app=pg-tileserv`
   - Verify database connectivity: `kubectl logs -l app=pg-tileserv`
   - Check service endpoints: `kubectl get services pg-tileserv-service`
   - Review configuration parameters

4. **CORS Issues**
   - Verify CORS origins configuration
   - Check browser developer tools for CORS errors
   - Ensure proper HTTP headers are set
   - Test with curl to isolate client-side issues

### Debugging

#### Service Health Check
```bash
# Check pg_tileserv health
curl "http://pg-tileserv-service:7800/health"

# List available collections
curl "http://pg-tileserv-service:7800/collections.json"

# Test specific tile
curl -I "http://pg-tileserv-service:7800/collections/public.transit_stops/items/10/512/512.mvt"
```

#### Database Diagnostics
```sql
-- Check PostGIS installation
SELECT PostGIS_Version();

-- List spatial tables
SELECT schemaname, tablename, attname, type 
FROM geometry_columns 
WHERE schemaname = 'public';

-- Check spatial indexes
SELECT schemaname, tablename, indexname 
FROM pg_indexes 
WHERE indexdef LIKE '%gist%';

-- Analyze table statistics
ANALYZE spatial_table;
```

#### Performance Monitoring
```bash
# Monitor pg_tileserv logs
kubectl logs -f -l app=pg-tileserv

# Check resource usage
kubectl top pods -l app=pg-tileserv

# Monitor database connections
kubectl exec -it postgres-pod -- psql -c "SELECT count(*) FROM pg_stat_activity WHERE application_name LIKE '%pg_tileserv%'"
```

## Security Considerations

### Database Access
- **Limited Permissions**: Grant only SELECT permissions to pg_tileserv user
- **Schema Restrictions**: Limit access to specific schemas containing spatial data
- **Connection Security**: Use SSL connections for database access

### API Security
- **CORS Configuration**: Configure appropriate CORS origins for production
- **Rate Limiting**: Implement rate limiting to prevent abuse
- **Authentication**: Consider adding authentication for sensitive data

### Network Security
- **Internal Access**: Keep pg_tileserv internal to cluster when possible
- **Firewall Rules**: Restrict network access to authorized clients
- **HTTPS**: Use HTTPS for external access

## Dependencies

- **PostgreSQL**: Database server with spatial data
- **PostGIS**: PostgreSQL extension for spatial data types and functions
- **Kubernetes**: Container orchestration platform
- **Spatial Data**: PostGIS tables with geometry columns and spatial indexes

## File Structure

```
plugins/Public/OpenJourneyServer_pg_tileserv/
├── plugin.py                  # Main plugin implementation
├── kubernetes/               # Kubernetes deployment manifests
│   ├── deployment.yaml      # pg_tileserv deployment configuration
│   ├── service.yaml         # Service definition
│   ├── configmap.yaml       # Configuration management
│   └── kustomization.yaml   # Kustomize configuration
└── README.md                # This documentation
```

## Integration Examples

### Dynamic Styling
```javascript
// Dynamic styling based on properties
map.addLayer({
  id: 'transit-routes',
  type: 'line',
  source: 'transit-routes',
  'source-layer': 'public.transit_routes',
  paint: {
    'line-color': [
      'match',
      ['get', 'route_type'],
      'bus', '#ff6b6b',
      'rail', '#4ecdc4',
      'ferry', '#45b7d1',
      '#95a5a6'  // default color
    ],
    'line-width': 3
  }
});
```

### Filtered Tiles
```javascript
// Request tiles with server-side filtering
var filteredSource = {
  type: 'vector',
  tiles: ['http://pg-tileserv-service:7800/collections/public.transit_stops/items/{z}/{x}/{y}.mvt?filter=type=\'bus_stop\''],
  maxzoom: 16
};
```

### Custom Properties
```javascript
// Request specific properties only
var optimizedSource = {
  type: 'vector',
  tiles: ['http://pg-tileserv-service:7800/collections/public.transit_stops/items/{z}/{x}/{y}.mvt?properties=name,type,route_id'],
  maxzoom: 16
};
```