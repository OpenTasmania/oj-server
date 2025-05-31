# setup/website_content_deployer.py
# -*- coding: utf-8 -*-
"""
Handles deployment of the static test website page.
"""
import logging
import os
import re
from typing import Optional

from common.command_utils import log_map_server, run_elevated_command
from setup import config  # For config vars and SYMBOLS
from setup.state_manager import get_current_script_hash

module_logger = logging.getLogger(__name__)

# Directory where the Nginx root location points for the test page
# This should match the 'root' directive in the Nginx site config.
WEBSITE_DEPLOY_DIR = "/var/www/html/map_test_page"
WEBSITE_HTML_FILENAME = "index.html"

# Standard web server user/group
WEB_USER = "www-data"
WEB_GROUP = "www-data"


def deploy_test_website_content(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Creates the test website directory and deploys the index.html file
    with appropriate content and permissions.
    """
    logger_to_use = current_logger if current_logger else module_logger
    script_hash = get_current_script_hash(logger_instance=logger_to_use) or "UNKNOWN_HASH"
    log_map_server(
        f"{config.SYMBOLS['step']} Deploying test website content to {WEBSITE_DEPLOY_DIR}...",
        "info",
        logger_to_use,
    )

    # Create the deployment directory
    run_elevated_command(["mkdir", "-p", WEBSITE_DEPLOY_DIR], current_logger=logger_to_use)

    vm_ip_or_domain = config.VM_IP_OR_DOMAIN
    is_ip = bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", vm_ip_or_domain))
    is_default_domain = vm_ip_or_domain == config.VM_IP_OR_DOMAIN_DEFAULT
    is_localhost = vm_ip_or_domain.lower() == "localhost"
    scheme = "http" if is_ip or is_default_domain or is_localhost else "https"

    website_html_page_path = os.path.join(WEBSITE_DEPLOY_DIR, WEBSITE_HTML_FILENAME)

    webpage_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Transit System Map Test - V{script_hash[:7]}</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="{scheme}://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin=""/>
    <script src="{scheme}://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>
    <link href='{scheme}://unpkg.com/maplibre-gl@4.1.0/dist/maplibre-gl.css' rel='stylesheet'/>
    <script src='{scheme}://unpkg.com/maplibre-gl@4.1.0/dist/maplibre-gl.js'></script>
    <style>
        body {{ margin: 0; padding: 0; font-family: sans-serif; }}
        .map-container {{ position: relative; width: 100%; height: 45vh; border: 1px solid #ccc; margin-bottom: 10px; }}
        .info {{ padding: 10px; background: #f4f4f4; border-bottom: 1px solid #ddd; margin-bottom:10px; }}
        h2, h3 {{ margin-top: 0; }}
    </style>
</head>
<body>

<div class="info">
    <h2>Map Test Page</h2>
    <p>Testing Raster Tiles (Leaflet) and Vector Tiles (MapLibre GL JS).</p>
    <p>Server Host: <strong>{vm_ip_or_domain}</strong> (Scheme: {scheme}://)</p>
    <p><i>Access URLs assume Nginx proxy is correctly configured.</i></p>
</div>

<h3>Raster Tiles (Leaflet) - OSM Base</h3>
<div id="map-raster" class="map-container"></div>

<h3>Vector Tiles (MapLibre GL JS) - GTFS Stops & Shapes</h3>
<div id="map-vector" class="map-container"></div>

<script>
    // --- Raster Map (Leaflet) ---
    try {{
        var rasterMap = L.map('map-raster').setView([-42.8826, 147.3257], 13); // Hobart default
        L.tileLayer('{scheme}://{vm_ip_or_domain}/raster/hot/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, Tiles by Local Server'
        }}).addTo(rasterMap);
        L.marker([-42.8826, 147.3257]).addTo(rasterMap).bindPopup('Hobart (Raster View)');
    }} catch(e) {{ console.error("Leaflet map error: ", e); document.getElementById('map-raster').innerHTML = "Error initializing raster map."; }}

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
                    'pgtileserv_shapes': {{
                        'type': 'vector',
                        'tiles': ['{scheme}://{vm_ip_or_domain}/vector/public.gtfs_shapes_lines/{{z}}/{{x}}/{{y}}.pbf'],
                        'maxzoom': 16
                    }}
                }},
                'layers': [
                    {{ 'id': 'background', 'type': 'background', 'paint': {{ 'background-color': '#f0f2f5' }} }},
                    {{
                        'id': 'routes-lines', 'type': 'line', 'source': 'pgtileserv_shapes',
                        'source-layer': 'public.gtfs_shapes_lines',
                        'layout': {{ 'line-join': 'round', 'line-cap': 'round' }},
                        'paint': {{ 'line-color': '#e3342f', 'line-width': 2.5, 'line-opacity': 0.8 }}
                    }},
                    {{
                        'id': 'stops-circles', 'type': 'circle', 'source': 'pgtileserv_stops',
                        'source-layer': 'public.gtfs_stops',
                        'paint': {{
                            'circle-radius': 4, 'circle-color': '#3490dc',
                            'circle-stroke-width': 1, 'circle-stroke-color': '#ffffff'
                        }}
                    }}
                ]
            }},
            center: [147.3257, -42.8826], // Hobart default (lng, lat)
            zoom: 12
        }});
        vectorMap.addControl(new maplibregl.NavigationControl());
    }} catch (e) {{
        console.error("MapLibre GL map error:", e);
        document.getElementById('map-vector').innerHTML = "Error initializing vector map. Check console.";
    }}
</script>
</body>
</html>
"""
    try:
        run_elevated_command(
            ["tee", website_html_page_path],
            cmd_input=webpage_content,
            current_logger=logger_to_use
        )
        # Set ownership and permissions for web server access
        run_elevated_command(["chown", "-R", f"{WEB_USER}:{WEB_GROUP}", WEBSITE_DEPLOY_DIR],
                             current_logger=logger_to_use)
        run_elevated_command(["chmod", "-R", "g+rX,o+rX", WEBSITE_DEPLOY_DIR],
                             current_logger=logger_to_use)  # Read/Execute for group/others
        run_elevated_command(["find", WEBSITE_DEPLOY_DIR, "-type", "f", "-exec", "chmod", "g+r,o+r", "{}", ";"],
                             current_logger=logger_to_use)  # Read for files

        log_map_server(f"{config.SYMBOLS['success']} Deployed and permissioned {website_html_page_path}", "success",
                       logger_to_use)

        test_page_url = f"{scheme}://{vm_ip_or_domain}/"
        # If Nginx root is /var/www/html, then it would be /map_test_page/
        # The Nginx config previously set root to /var/www/html/map_test_page for location /
        log_map_server(f"{config.SYMBOLS['info']} Test website page should be accessible at: {test_page_url}", "info",
                       logger_to_use)

    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to deploy test website content to {website_html_page_path}: {e}",
            "error", logger_to_use)
        raise