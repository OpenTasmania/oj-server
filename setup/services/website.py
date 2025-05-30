# setup/services/website.py
# -*- coding: utf-8 -*-
"""
Setup an example website page
"""

import logging
import re  # Import re for IP address matching
from typing import Optional  # Literal removed

from setup import config  # Import config to access VM_IP_OR_DOMAIN
from setup.command_utils import (
    log_map_server,
    run_elevated_command,
)

module_logger = logging.getLogger(__name__)


# Removed uri: Literal["http","https"] parameter
def website_setup(current_logger: Optional[logging.Logger] = None) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Setting up example website page...",
        "info",
        logger_to_use,
    )

    # Get VM_IP_OR_DOMAIN from the global config
    vm_ip_or_domain = config.VM_IP_OR_DOMAIN

    # Determine scheme (http or https)
    is_ip = bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", vm_ip_or_domain))
    is_default_domain = vm_ip_or_domain == config.VM_IP_OR_DOMAIN_DEFAULT  # "example.com"
    is_localhost = vm_ip_or_domain.lower() == "localhost"

    # Use http for IPs, localhost, or the default "example.com" domain, https otherwise
    scheme = "http" if is_ip or is_default_domain or is_localhost else "https"

    log_map_server(
        f"{config.SYMBOLS['info']} Using scheme '{scheme}://' for website URLs with domain/IP: {vm_ip_or_domain}",
        "info",
        logger_to_use,
    )

    website_html_page_path = "/var/www/html/map_test_page/index.html"

    # Corrected HTML content to use the determined scheme and vm_ip_or_domain
    webpage_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Transit System Map Test</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="{scheme}://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
          integrity="sha256-p4NxAoJBhuIN20f8X7/iB3g4T7bFMPjR/f0_vL+aU5Q=" 
          crossorigin=""/>
    <script src="{scheme}://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
            integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
    <link href='{scheme}://unpkg.com/maplibre-gl@4.1.0/dist/maplibre-gl.css' rel='stylesheet'/>
    <script src='{scheme}://unpkg.com/maplibre-gl@4.1.0/dist/maplibre-gl.js'></script>
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
            height: 50vh; /* Adjusted for two maps */
        }}

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
    </strong> (Used in URLs below)
    </p>
</div>

<h3>Raster Tiles (Leaflet)</h3>
<div id="map-raster" class="map-container"></div>

<h3>Vector Tiles (MapLibre GL JS - showing stops and routes)</h3>
<div id="map-vector" class="map-container"></div>


<script>
    // --- Raster Map (Leaflet) ---
    var rasterMap = L.map('map-raster').setView([-42.8826, 147.3257], 13); // Hobart
    L.tileLayer('{scheme}://{vm_ip_or_domain}/raster/hot/{{z}}/{{x}}/{{y}}.png', {{
        maxZoom: 19,
        attribution: '&copy; <a href="{scheme}://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, Tiles by Local Server'
    }}).addTo(rasterMap);
    L.marker([-42.8826, 147.3257]).addTo(rasterMap).bindPopup('Hobart (Raster)');

    // --- Vector Map (MapLibre GL JS) ---
    try {{
        var vectorMap = new maplibregl.Map({{
            container: 'map-vector',
            style: {{
                'version': 8,
                'sources': {{
                    'pgtileserv_stops': {{
                        'type': 'vector',
                        'tiles': ['{scheme}://{vm_ip_or_domain}/vector/public.gtfs_stops/{{z}}/{{x}}/{{y}}.pbf'],
                        'maxzoom': 16
                    }},
                    'pgtileserv_routes': {{
                        'type': 'vector',
                        'tiles': ['{scheme}://{vm_ip_or_domain}/vector/public.gtfs_shapes_lines/{{z}}/{{x}}/{{y}}.pbf'],
                        'maxzoom': 16
                    }}
                }},
                'layers': [
                    {{
                        'id': 'background', // Added a simple background layer
                        'type': 'background',
                        'paint': {{
                            'background-color': '#f0f0f0' // Light grey background
                        }}
                    }},
                    {{
                        'id': 'stops-circles',
                        'type': 'circle',
                        'source': 'pgtileserv_stops',
                        'source-layer': 'public.gtfs_stops',
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
        # Ensure parent directory exists
        run_elevated_command(["mkdir", "-p", "/var/www/html/map_test_page"], current_logger=logger_to_use)
        run_elevated_command(
            ["tee", website_html_page_path],
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