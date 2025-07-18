# Apache HTTP Server Plugin

This plugin provides Apache HTTP server with mod_tile integration for serving map tiles and static web content.

## Features

- **HTTP Server**: Apache HTTP server for serving web content and API endpoints
- **Tile Serving**: mod_tile integration for efficient map tile delivery
- **CORS Support**: Cross-Origin Resource Sharing configuration for web applications
- **Kubernetes Deployment**: Complete containerized deployment with configuration management
- **Renderd Integration**: Socket-based communication with renderd for tile generation

## What This Plugin Does

The Apache plugin sets up and configures an Apache HTTP server specifically optimized for serving map tiles and web
content. It integrates with the mod_tile module to provide efficient tile serving capabilities and connects to renderd
for on-demand tile generation.

Key capabilities:

- Serves map tiles at `/osm_tiles/{z}/{x}/{y}.png` endpoint
- Provides static web content hosting
- Handles CORS headers for cross-domain requests
- Manages tile caching and delivery optimization
- Integrates with renderd via Unix socket communication

## Implementation

### Core Components

- **Apache HTTP Server**: Main web server process
- **mod_tile Module**: Apache module for tile serving optimization
- **Configuration Management**: Dynamic configuration generation based on settings
- **Socket Communication**: Integration with renderd tile generation service

### Architecture

```
Client Request → Apache HTTP Server → mod_tile → renderd → Tile Generation
                      ↓
                 Static Content / Cached Tiles
```

### Configuration

The plugin accepts the following configuration parameters:

```yaml
apache:
  enabled: true
  listen_port: 8080
  server_name: "localhost"
  document_root: "/var/www/html"
  mod_tile_enabled: true
  tile_dir: "/var/cache/renderd/tiles"
  renderd_socket: "/var/run/renderd/renderd.sock"
  max_zoom: 18
  min_zoom: 0
  cors_enabled: true
  tile_server:
    uri: "/osm_tiles/"
    xml: "/home/renderer/src/openstreetmap-carto/mapnik.xml"
    host: "tile.openstreetmap.org"
    htcp_host: "proxy.openstreetmap.org"
```

## How to Use

### Kubernetes Deployment

The plugin automatically deploys when the container orchestration system is set up:

```bash
# The plugin deploys the following Kubernetes resources:
# - Deployment: Apache HTTP server pods
# - Service: Load balancer for HTTP traffic
# - ConfigMap: Apache and mod_tile configuration
# - NetworkPolicy: Traffic rules and security
```

### Accessing Tiles

Once deployed, map tiles are available at:

```
http://your-server:8080/osm_tiles/{z}/{x}/{y}.png
```

Where:

- `{z}` is the zoom level (0-18)
- `{x}` is the tile X coordinate
- `{y}` is the tile Y coordinate

### Static Content

Static web content can be served from the configured document root:

```
http://your-server:8080/your-content.html
```

### Integration with Web Applications

Use with mapping libraries like Leaflet:

```javascript
L.tileLayer('http://your-server:8080/osm_tiles/{z}/{x}/{y}.png', {
    attribution: '© Map contributors',
    maxZoom: 18,
    minZoom: 0
}).addTo(map);
```

## Container Configuration

The plugin includes a complete Docker container setup:

- **Base Image**: Apache HTTP server with mod_tile
- **Configuration**: Dynamic configuration file generation
- **Volumes**: Persistent storage for tile cache and content
- **Networking**: Exposed ports and service discovery

## Performance Considerations

- **Tile Caching**: Tiles are cached to reduce renderd load
- **Concurrent Requests**: Apache handles multiple simultaneous tile requests
- **Memory Usage**: Configure based on expected tile cache size
- **Socket Performance**: Unix socket communication with renderd for optimal performance

## Troubleshooting

### Common Issues

1. **Tiles Not Loading**
    - Check renderd socket permissions and connectivity
    - Verify tile directory permissions
    - Review Apache error logs

2. **Configuration Errors**
    - Validate Apache configuration syntax
    - Check mod_tile module loading
    - Verify file paths and permissions

3. **Performance Issues**
    - Monitor tile cache hit rates
    - Check renderd response times
    - Review Apache access patterns

### Debugging

Check container logs:

```bash
kubectl logs -l app=apache
```

Verify service connectivity:

```bash
kubectl get services apache-service
```

Test tile endpoint:

```bash
curl http://your-server:8080/osm_tiles/10/512/512.png
```

## Dependencies

- Apache HTTP Server
- mod_tile module
- renderd service (for tile generation)
- Persistent storage for tile cache
- Network connectivity to renderd socket

## File Structure

```
plugins/Public/OpenJourneyServer_Apache/
├── plugin.py                  # Main plugin implementation
├── kubernetes/               # Kubernetes deployment manifests
│   ├── deployment.yaml      # Apache deployment configuration
│   ├── service.yaml         # Service definition
│   ├── configmap.yaml       # Apache configuration
│   ├── network-policy.yaml  # Network security rules
│   ├── Dockerfile           # Container image definition
│   └── kustomization.yaml   # Kustomize configuration
└── README.md                # This documentation
```