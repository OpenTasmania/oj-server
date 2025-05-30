# setup/services/website.py
# -*- coding: utf-8 -*-
"""
Setup an example website page


"""

import logging
from typing import Optional, Literal

from setup import config
from setup.command_utils import (
    log_map_server,
    run_elevated_command,
)

module_logger = logging.getLogger(__name__)


def website_setup(uri: Literal["http","https"], current_logger: Optional[logging.Logger] = None) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Setting up renderd for raster tiles...",
        "info",
        logger_to_use,
    )
    vm_ip_or_domain = "example"
    website_html_page_path = "/var/www/html/map_test_page/index.html"
    webpage_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Transit System Map Test</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="{uri}s://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
          integrity="sha256-p4NxAoJBhดูรายละเอียดപിൻവലിക്കാവുന്നതാണ്sha512-puBpdR0798OZvTTbP4A8bRjEnFRP বঙ্গেরFulde."
          crossorigin=""/>
    <script src="{uri}s://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
            integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
    <link href='{uri}s://unpkg.com/maplibre-gl@4.1.0/dist/maplibre-gl.css' rel='stylesheet'/>
    <script src='{uri}s://unpkg.com/maplibre-gl@4.1.0/dist/maplibre-gl.js'></script>
    <style>
        body {{
            margin: 0;
            padding: 0;
        }}

        #map {{
            position: absolute;
            top: 0;
            bottom: 0;
            width: 100%;
        }}

        .map-container {{
            position: relative;
            width: 100%;
            height: 50vh;
        }}

        /* Use two maps */
        .info {{
            padding: 10px;
            background: white;
            border: 1px solid #ccc;
        }}
    </style>
</head>
<body>

<div class="info">
    <h2>Map Test Page</h2>
    <p>Testing Raster Tiles (Leaflet) and Vector Tiles (MapLibre GL JS with basic styling).</p>
    <p>Your VM IP/Domain: <strong>
        {vm_ip_or_domain}
    </strong> (Replace this in URLs below if needed)
    </p>
</div>

<h3>Raster Tiles (Leaflet)</h3>
<div id="map-raster" class="map-container"></div>

<h3>Vector Tiles (MapLibre GL JS - showing stops)</h3>
<div id="map-vector" class="map-container"></div>


<script>
    // --- Raster Map (Leaflet) ---
    // Assuming your Nginx proxy is set up for /raster/ and renderd style URI is /hot/
    var rasterMap = L.map('map-raster').setView([-42.8826, 147.3257], 13); // Hobart
    L.tileLayer('{uri}://{vm_ip_or_domain}/raster/hot/{{z}}/{{x}}/{{y}}.png', {{ // Ensure '/hot/' matches your renderd URI
        maxZoom: 19,
        attribution: '&copy; <a href="{uri}://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, Tiles by Local Server'
    }}).addTo(rasterMap);
    L.marker([-42.8826, 147.3257]).addTo(rasterMap).bindPopup('Hobart (Raster)');

    // --- Vector Map (MapLibre GL JS) ---
    // Assuming Nginx proxy for /vector/ to pg_tileserv on localhost:7800
    // and pg_tileserv's URIPrefix is /vector
    // We'll try to display the 'public.gtfs_stops' layer from pg_tileserv.
    // The {{z}}/{{x}}/{{y}}.pbf part is handled by MapLibre.
    // The source URL should point to the pg_tileserv layer endpoint.
    // pg_tileserv lists layers like: /vector/public.gtfs_stops.json (for metadata)
    // and tiles are at /vector/public.gtfs_stops/{{z}}/{{x}}/{{y}}.pbf

    try {{
        var vectorMap = new maplibregl.Map({{
            container: 'map-vector',
            style: {{
                'version': 8,
                'sources': {{
                    'pgtileserv_stops': {{
                        'type': 'vector',
                        'tiles': ['{uri}://{vm_ip_or_domain}/vector/public.gtfs_stops/{{z}}/{{x}}/{{y}}.pbf'], // TileJSON endpoint is often auto-derived by MapLibre if base URL is given
                        'maxzoom': 16 // Adjust as appropriate for your data
                    }},
                    'pgtileserv_routes': {{ // Example for shapes if you aggregated them
                        'type': 'vector',
                        'tiles': ['{uri}://{vm_ip_or_domain}/vector/public.gtfs_shapes_lines/{{z}}/{{x}}/{{y}}.pbf'],
                        'maxzoom': 16
                    }}
                }},
                'layers': [
                    {{
                        'id': 'stops-circles',
                        'type': 'circle',
                        'source': 'pgtileserv_stops',
                        'source-layer': 'public.gtfs_stops', // Actual layer name within the PBF tile
                        'paint': {{
                            'circle-radius': 4,
                            'circle-color': '#007cbf',
                            'circle-stroke-width': 1,
                            'circle-stroke-color': '#ffffff'
                        }}
                    }},
                    {{
                        'id': 'routes-lines',
                        'type': 'line',
                        'source': 'pgtileserv_routes',
                        'source-layer': 'public.gtfs_shapes_lines',
                        'layout': {{
                            'line-join': 'round',
                            'line-cap': 'round'
                        }},
                        'paint': {{
                            'line-color': '#ff0000',
                            'line-width': 2
                        }}
                    }}
                ]
            }},
            center: [147.3257, -42.8826], // longitude, latitude for Hobart
            zoom: 12
        }});
        vectorMap.addControl(new maplibregl.NavigationControl());
    }} catch (e) {{
        console.error("Error initializing MapLibre GL map:", e);
        document.getElementById('map-vector').innerHTML = "Error initializing MapLibre GL map. Check console.";
    }}

</script>
</body>
</html>
"""
    try:
        run_elevated_command(
            ["tee", website_html_page_path],  # Overwrites or creates the file
            cmd_input=webpage_content,
            current_logger=logger_to_use
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Created/Updated {website_html_page_path}",
            "success",
            logger_to_use,
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to write {website_html_page_path}: {e}",
            "error",
            logger_to_use,
        )
        raise
