# OpenStreetMap Tile Rendering Plugin

This plugin provides OpenStreetMap tile rendering capabilities through the renderd service. It manages tile caching and integration with the mapping stack including Mapnik, mod_tile, and Apache for serving raster tiles.

## Features

- **Tile Rendering**: Complete renderd service for generating raster tiles from OpenStreetMap data
- **PostgreSQL Integration**: Stores OSM data in PostgreSQL with PostGIS extension
- **Kubernetes Deployment**: Full Kubernetes integration with deployments, services, and persistent volumes
- **Mapnik Integration**: Uses Mapnik for high-quality map rendering with OpenStreetMap Carto styles
- **Tile Caching**: Efficient tile caching with mod_tile integration
- **Plugin Architecture**: Modular plugin-based architecture

## Database Schema

The plugin creates the following tables in the `osm` schema:

### Required Tables
- `osm.planet_osm_point` - Point features (POIs, nodes with tags)
- `osm.planet_osm_line` - Linear features (roads, rivers, boundaries)
- `osm.planet_osm_polygon` - Polygon features (buildings, areas, landuse)
- `osm.planet_osm_roads` - Road network (optimized for routing)

### Optional Tables
- `osm.planet_osm_ways` - Way metadata and node references
- `osm.planet_osm_rels` - Relation metadata and member references
- `osm.planet_osm_nodes` - Node metadata (usually not needed for rendering)

## Installation

The plugin is automatically installed when the OpenJourney server is deployed with the plugin system enabled.

### Prerequisites

- PostgreSQL with PostGIS and hstore extensions
- Kubernetes cluster
- Docker for container builds
- OSM data file (PBF format)

### Manual Installation

```bash
# The plugin is located at:
plugins/Public/OpenJourneyServer-OpenStreetMap/

# Required components:
# - plugin.py: Main plugin implementation
# - kubernetes/: Kubernetes manifests for renderd
# - carto/: OpenJourneyServer-OpenStreetMap Carto style files
```

## Configuration

The plugin uses the following configuration parameters:

```yaml
openstreetmap:
  enable_ways_table: true
  enable_relations_table: true
  enable_nodes_table: false  # Usually not needed for rendering

renderd:
  num_threads_multiplier: 1
  tile_cache_dir: "/var/lib/mod_tile"
  run_dir: "/var/run/renderd"
  socket_path: "/var/run/renderd/renderd.sock"
  mapnik_xml_stylesheet_path: "/usr/local/share/maps/style/openstreetmap-carto/mapnik.xml"
  mapnik_plugins_dir_override: "/usr/lib/x86_64-linux-gnu/mapnik/4.0/input/"
  uri_path_segment: "hot"

database:
  host: localhost
  port: 5432
  database: openjourney
  user: postgres
  password: your_password
```

## Usage

### Data Import

Import OpenStreetMap data using osm2pgsql:

```bash
# Download OSM data (example for Australia)
wget https://download.geofabrik.de/australia-oceania/australia-latest.osm.pbf

# Import data using osm2pgsql
osm2pgsql -d openjourney -U postgres -H localhost \
  --create --slim --drop \
  --cache 2000 --number-processes 4 \
  --hstore --style /path/to/openstreetmap-carto.style \
  --tag-transform-script /path/to/openstreetmap-carto.lua \
  australia-latest.osm.pbf
```

### Tile Rendering

The renderd service automatically generates tiles on demand:

- **Tile URL Format**: `http://your-server/raster/hot/{z}/{x}/{y}.png`
- **Zoom Levels**: 0-18 (configurable)
- **Tile Size**: 256x256 pixels
- **Format**: PNG

### Kubernetes Deployment

The plugin includes complete Kubernetes manifests:

```bash
# Deploy renderd service
kubectl apply -f plugins/Public/OpenJourneyServer-OpenStreetMap/kubernetes/

# Check deployment status
kubectl get pods -l app=renderd
kubectl get services renderd-service
```

## Components

### Renderd Service
- **Purpose**: Tile rendering daemon
- **Technology**: C++ application with Mapnik integration
- **Configuration**: Generated from template in config.yaml
- **Performance**: Multi-threaded rendering with configurable thread count

### Mapnik Stylesheets
- **Style**: OpenStreetMap Carto (standard OSM style)
- **Format**: Mapnik XML with CartoCSS source
- **Customization**: Supports style modifications and extensions
- **Data Sources**: PostgreSQL/PostGIS queries

### Tile Cache
- **Technology**: mod_tile with Apache integration
- **Storage**: Persistent volume for tile cache
- **Expiry**: Configurable tile expiration policies
- **Performance**: Efficient tile serving with HTTP caching headers

## API Integration

### Tile Access

Access rendered tiles through the web interface:

```javascript
// Leaflet integration
L.tileLayer('http://your-server/raster/hot/{z}/{x}/{y}.png', {
    attribution: '© OpenJourneyServer-OpenStreetMap contributors',
    maxZoom: 18
}).addTo(map);
```

### Database Queries

Query OSM data directly from PostgreSQL:

```sql
-- Find all restaurants in a bounding box
SELECT name, amenity, ST_AsText(way) as location
FROM osm.planet_osm_point
WHERE amenity = 'restaurant'
AND way && ST_MakeEnvelope(xmin, ymin, xmax, ymax, 3857);

-- Get road network for routing
SELECT osm_id, name, highway, ST_AsText(way) as geometry
FROM osm.planet_osm_line
WHERE highway IS NOT NULL
AND highway IN ('primary', 'secondary', 'tertiary', 'residential');
```

## Monitoring and Performance

### Key Metrics
- Tile rendering performance (tiles/second)
- Cache hit ratio
- Database query performance
- Memory and CPU usage

### Log Files
- Renderd logs: Available through Kubernetes logs
- Apache access logs: Tile request patterns
- Database logs: Query performance analysis

### Performance Tuning
- **Thread Count**: Adjust `num_threads_multiplier` based on CPU cores
- **Cache Size**: Configure tile cache size based on available storage
- **Database**: Optimize PostgreSQL settings for spatial queries
- **Memory**: Ensure sufficient memory for Mapnik rendering

## Troubleshooting

### Common Issues

1. **Tile Rendering Errors**
   - Check Mapnik XML stylesheet path
   - Verify database connectivity
   - Review renderd configuration

2. **Database Connection Issues**
   - Verify PostgreSQL connection parameters
   - Check PostGIS extension installation
   - Ensure proper database permissions

3. **Performance Issues**
   - Monitor database query performance
   - Adjust renderd thread count
   - Check tile cache configuration
   - Review system resource usage

4. **Style Issues**
   - Verify OpenStreetMap Carto installation
   - Check Mapnik plugin directory
   - Review stylesheet XML generation

### Debug Mode

Enable debug logging in renderd configuration:

```yaml
renderd:
  log_level: debug
  stats_file: /var/run/renderd/renderd.stats
```

## Development

### Plugin Structure
```
plugins/Public/OpenStreetMap/
├── __init__.py                 # Plugin package initialization
├── plugin.py                   # Main plugin class and database schema
├── README.md                   # This documentation
├── kubernetes/                 # Kubernetes manifests
│   ├── deployment.yaml        # Renderd deployment
│   ├── service.yaml           # Renderd service
│   ├── configmap.yaml         # Renderd configuration
│   ├── pvc.yaml               # Persistent volume claims
│   └── network-policy.yaml    # Network policies
└── carto/                     # OpenStreetMap Carto styles
    ├── openstreetmap-carto.lua
    ├── openstreetmap-carto-flex.lua
    └── scripts/
        └── get-external-data.py
```

### Extending the Plugin

1. **Custom Styles**: Modify Mapnik XML or add new stylesheets
2. **Additional Tables**: Extend database schema for custom data
3. **Performance Optimization**: Add custom indexes or views
4. **Integration**: Connect with other OpenJourney plugins

### Testing

```bash
# Test plugin loading
python -c "from plugins.OpenStreetMap import OpenStreetMapPlugin; print('Plugin loaded successfully')"

# Test database schema
# (Requires proper database configuration)

# Test tile rendering
curl http://localhost/raster/hot/10/512/512.png
```

## Integration Examples

The OpenStreetMap plugin can be integrated with various mapping applications:

- **Transit Data Overlay**: Overlay public transit data on base maps
- **Routing Applications**: Use OSM road network for routing calculations
- **Web Mapping**: Provide base map tiles for web applications
- **API Integration**: Expose tile endpoints through REST API

## License

This plugin is part of the OpenJourney project and follows the same licensing terms.

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review log files for error details
3. Consult the OpenJourney documentation
4. Report issues through the project's issue tracking system

## References

- [OpenStreetMap](https://www.openstreetmap.org/)
- [OpenStreetMap Carto](https://github.com/gravitystorm/openstreetmap-carto)
- [Mapnik](https://mapnik.org/)
- [osm2pgsql](https://osm2pgsql.org/)
- [PostGIS](https://postgis.net/)