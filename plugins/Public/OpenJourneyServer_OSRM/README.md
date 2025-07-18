# OSRM Routing Plugin

This plugin provides OSRM (Open Source Routing Machine) routing services with enhanced algorithms and multi-modal
routing capabilities.

## Features

- **Multi-Modal Routing**: Support for driving, walking, cycling, and public transport routing
- **Enhanced Algorithms**: Advanced routing algorithms including Contraction Hierarchies (CH) and Multi-Level Dijkstra (
  MLD)
- **Traffic Integration**: Real-time traffic data integration for dynamic routing
- **Custom Profiles**: Configurable routing profiles for different transportation modes
- **Performance Optimization**: Shared memory, caching, and multi-threading support
- **Database Integration**: PostgreSQL integration for routing analytics and caching
- **Kubernetes Deployment**: Containerized OSRM services with scalable deployment

## What This Plugin Does

The OSRM plugin provides comprehensive routing services using the Open Source Routing Machine engine. It offers
multi-modal routing capabilities with support for various transportation modes and advanced routing algorithms optimized
for performance and accuracy.

Key capabilities:

- Calculates optimal routes for different transportation modes
- Provides turn-by-turn navigation instructions
- Supports route optimization and alternative route calculation
- Integrates with traffic data for dynamic routing
- Offers distance matrix calculations for multiple origins/destinations
- Provides map matching services for GPS traces
- Supports isochrone (reachability) analysis

## Implementation

### Core Components

- **OSRM Backend**: Core routing engine with algorithm implementations
- **Routing Profiles**: Transportation mode-specific routing configurations
- **Database Integration**: PostgreSQL schema for routing data and analytics
- **Performance Layer**: Caching and memory optimization components
- **API Interface**: RESTful API for routing requests

### Architecture

```
Client Request → OSRM API → Routing Engine → Algorithm (CH/MLD) → Route Response
                     ↓
              Database Cache / Analytics
```

### Routing Profiles

The plugin supports multiple routing profiles:

#### Driving Profile

- **Algorithm**: Contraction Hierarchies (CH)
- **Max Speed**: 130 km/h
- **Features**: Traffic integration, road restrictions, vehicle-specific routing

#### Walking Profile

- **Algorithm**: Multi-Level Dijkstra (MLD)
- **Max Speed**: 6 km/h
- **Features**: Pedestrian paths, accessibility considerations, safety routing

#### Cycling Profile

- **Algorithm**: Contraction Hierarchies (CH)
- **Max Speed**: 25 km/h
- **Features**: Bike lanes, elevation consideration, safety routing

#### Public Transport Profile

- **Algorithm**: Multi-Level Dijkstra (MLD)
- **Features**: GTFS integration, schedule-based routing, multi-modal connections

## How to Use

### Configuration

Configure OSRM settings in your YAML configuration:

```yaml
osrm:
  enabled: true
  image_tag: "osrm/osrm-backend:latest"
  listen_port: 5000
  max_table_size: 8000
  max_matching_size: 5000
  max_viaroute_size: 10000
  max_trip_size: 1000

  private_features:
    enhanced_algorithms: true
    traffic_integration: true
    custom_profiles: true
    analytics_tracking: true
    route_optimization: true
    multi_modal_routing: true

  profiles:
    driving:
      enabled: true
      data_file: "/data/driving.osrm"
      algorithm: "CH"
      max_speed: 130

    walking:
      enabled: true
      data_file: "/data/walking.osrm"
      algorithm: "MLD"
      max_speed: 6

    cycling:
      enabled: true
      data_file: "/data/cycling.osrm"
      algorithm: "CH"
      max_speed: 25

    public_transport:
      enabled: true
      data_file: "/data/transit.osrm"
      algorithm: "MLD"
      gtfs_integration: true

  performance:
    threads: 4
    shared_memory: true
    cache_size: "2G"
    mmap_memory: true
```

### Kubernetes Deployment

The plugin automatically deploys OSRM services:

```bash
# Deploy OSRM routing services
kubectl apply -f kubernetes/

# Check deployment status
kubectl get pods -l app=osrm
kubectl get services osrm-service
```

### API Usage

#### Route Calculation

```bash
# Get driving route between two points
curl "http://osrm-service:5000/route/v1/driving/13.388860,52.517037;13.397634,52.529407?overview=full&geometries=geojson"

# Get walking route with steps
curl "http://osrm-service:5000/route/v1/walking/13.388860,52.517037;13.397634,52.529407?steps=true"

# Get cycling route with alternatives
curl "http://osrm-service:5000/route/v1/cycling/13.388860,52.517037;13.397634,52.529407?alternatives=true"
```

#### Distance Matrix

```bash
# Calculate distance matrix for multiple points
curl "http://osrm-service:5000/table/v1/driving/13.388860,52.517037;13.397634,52.529407;13.428555,52.523219"
```

#### Map Matching

```bash
# Match GPS trace to road network
curl -X POST "http://osrm-service:5000/match/v1/driving" \
  -H "Content-Type: application/json" \
  -d '{"coordinates":[[13.388860,52.517037],[13.397634,52.529407]]}'
```

#### Isochrone Analysis

```bash
# Get 10-minute reachability area
curl "http://osrm-service:5000/isochrone/v1/driving/13.388860,52.517037?contours_minutes=10"
```

## Database Schema

The plugin creates tables in the `routing` schema:

### Core Tables

- `routing.routing_profiles` - Routing profile configurations
- `routing.routing_cache` - Cached routing results for performance
- `routing.routing_analytics` - Usage analytics and performance metrics

### Analytics Tables

- `routing.route_requests` - Request logging and analysis
- `routing.performance_metrics` - Algorithm performance tracking
- `routing.traffic_data` - Traffic integration data

## Performance Optimization

### Memory Management

- **Shared Memory**: Enables memory sharing between OSRM processes
- **Memory Mapping**: Uses mmap for efficient data access
- **Cache Size**: Configurable cache size for routing data

### Algorithm Selection

- **Contraction Hierarchies (CH)**: Fast preprocessing, excellent query performance
- **Multi-Level Dijkstra (MLD)**: Flexible, good for dynamic scenarios
- **Customizable**: Profile-specific algorithm selection

### Scaling

- **Multi-threading**: Configurable thread count for concurrent requests
- **Horizontal Scaling**: Kubernetes-based scaling for high availability
- **Load Balancing**: Service-level load distribution

## Data Preparation

### OSM Data Processing

```bash
# Download OpenStreetMap data
wget https://download.geofabrik.de/australia-oceania/australia-latest.osm.pbf

# Extract and prepare routing data
osrm-extract australia-latest.osm.pbf -p profiles/driving.lua
osrm-partition australia-latest.osrm
osrm-customize australia-latest.osrm

# Start OSRM service
osrm-routed --algorithm=CH australia-latest.osrm
```

### Profile Customization

Create custom routing profiles by modifying Lua scripts:

```lua
-- Custom driving profile
api_version = 4

function setup()
  return {
    properties = {
      max_speed_for_map_matching = 180/3.6,
      use_turn_restrictions = true,
      continue_straight_at_waypoint = true,
      weight_name = 'routability'
    }
  }
end

function process_way(profile, way, result)
  -- Custom way processing logic
  local highway = way:get_value_by_key("highway")
  local maxspeed = way:get_value_by_key("maxspeed")
  
  -- Apply custom routing rules
  if highway == "motorway" then
    result.forward_speed = 110
    result.backward_speed = 110
  end
end
```

## Troubleshooting

### Common Issues

1. **Service Unavailable**
    - Check OSRM container status: `kubectl get pods -l app=osrm`
    - Verify data files are properly mounted
    - Review container logs: `kubectl logs -l app=osrm`

2. **Slow Routing Performance**
    - Increase cache size in configuration
    - Enable shared memory for better performance
    - Consider using Contraction Hierarchies algorithm
    - Check thread configuration

3. **Route Quality Issues**
    - Verify OSM data quality and coverage
    - Review routing profile configuration
    - Check for proper data preprocessing
    - Validate coordinate formats (longitude, latitude)

4. **Memory Issues**
    - Monitor memory usage: `kubectl top pods -l app=osrm`
    - Adjust cache size and memory limits
    - Consider data file optimization
    - Review shared memory configuration

### Debugging

#### Service Health Check

```bash
# Check OSRM service health
curl "http://osrm-service:5000/health"

# Test basic routing functionality
curl "http://osrm-service:5000/route/v1/driving/0,0;1,1"
```

#### Performance Monitoring

```bash
# Monitor routing performance
kubectl logs -l app=osrm | grep "request"

# Check resource usage
kubectl top pods -l app=osrm
```

## Dependencies

- **OSRM Backend**: Core routing engine
- **OpenStreetMap Data**: Road network data in PBF format
- **PostgreSQL**: Database for analytics and caching
- **PostGIS**: Geospatial extensions for PostgreSQL
- **Kubernetes**: Container orchestration platform
- **Persistent Storage**: For OSM data and routing files

## File Structure

```
plugins/Public/OpenJourneyServer_OSRM/
├── plugin.py                  # Main plugin implementation
├── config.yaml               # Plugin-specific configuration
├── kubernetes/               # Kubernetes deployment manifests
│   ├── deployment.yaml      # OSRM service deployment
│   ├── service.yaml         # Service definition
│   ├── configmap.yaml       # Configuration management
│   ├── pvc.yaml             # Persistent volume claims
│   ├── network-policy.yaml  # Network security rules
│   └── kustomization.yaml   # Kustomize configuration
└── README.md                # This documentation
```

## Integration Examples

### Route Planning Application

```javascript
// JavaScript integration example
async function calculateRoute(start, end, profile = 'driving') {
    const response = await fetch(
        `http://osrm-service:5000/route/v1/${profile}/${start.lng},${start.lat};${end.lng},${end.lat}?overview=full&geometries=geojson`
    );
    const data = await response.json();
    return data.routes[0];
}
```

### Distance Matrix Calculation

```python
# Python integration example
import requests


def get_distance_matrix(coordinates, profile='driving'):
    coords_str = ';'.join([f"{lng},{lat}" for lng, lat in coordinates])
    url = f"http://osrm-service:5000/table/v1/{profile}/{coords_str}"
    response = requests.get(url)
    return response.json()
```

### Map Matching Service

```bash
# GPS trace matching
curl -X POST "http://osrm-service:5000/match/v1/driving" \
  -H "Content-Type: application/json" \
  -d '{
    "coordinates": [
      [13.388860, 52.517037],
      [13.397634, 52.529407],
      [13.428555, 52.523219]
    ],
    "radiuses": [10, 10, 10]
  }'
```