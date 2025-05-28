# setup/services/nginx.py
# -*- coding: utf-8 -*-
"""
Handles the setup and configuration of Nginx as a reverse proxy.

This module configures Nginx to act as a reverse proxy for various backend
map services (pg_tileserv, Apache/mod_tile for raster tiles, OSRM).
It creates a test page, sets up the Nginx site configuration, enables the
site, disables the default Nginx site, tests the configuration, and
restarts the Nginx service.
"""

import logging
import os
import subprocess  # For CalledProcessError
from typing import Optional

from setup import config
from setup.command_utils import (
    command_exists,
    log_map_server,
    run_elevated_command,
)
from setup.helpers import (
    systemd_reload,  # For reloading systemd after service changes
)
from setup.state_manager import get_current_script_hash

module_logger = logging.getLogger(__name__)


def nginx_setup(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Set up Nginx as a reverse proxy for map services.

    - Checks if Nginx is installed.
    - Creates a simple HTML test page.
    - Creates an Nginx site configuration file (`transit_proxy`) to proxy
      requests to pg_tileserv, Apache/mod_tile (raster), and OSRM.
    - Enables the new Nginx site and disables the default site.
    - Tests the Nginx configuration for syntax errors.
    - Restarts and enables the Nginx service.

    Args:
        current_logger: Optional logger instance to use. If None,
                        the module's default logger is used.

    Raises:
        subprocess.CalledProcessError: If `nginx -t` (configuration test)
                                     fails, or if critical Nginx service
                                     management commands fail.
        Exception: For other unexpected errors during setup.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Setting up Nginx as a reverse proxy...",
        "info",
        logger_to_use,
    )
    script_hash_for_comments = (
        get_current_script_hash(logger_instance=logger_to_use) or "UNKNOWN_HASH"
    )

    if not command_exists("nginx"):
        log_map_server(
            f"{config.SYMBOLS['warning']} Nginx not found. Skipping Nginx setup.",
            "warning",
            logger_to_use,
        )
        return

    # Create a directory for a simple test page.
    test_page_base_dir = "/var/www/html"  # Base for www-data user.
    test_page_dir = os.path.join(test_page_base_dir, "map_test_page")
    run_elevated_command(
        ["mkdir", "-p", test_page_dir], current_logger=logger_to_use
    )

    # Content for the simple index.html test page.
    simple_index_html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Nginx Map Proxy Test</title>
</head>
<body>
    <h1>Nginx is Active!</h1>
    <p>Map services should be available via Nginx proxy if correctly configured.</p>
    <p>VM IP/Domain for access: {config.VM_IP_OR_DOMAIN}</p>
    <ul>
        <li>Raster Tiles (OSM Base):
            <a href="/raster/hot/0/0/0.png">/raster/hot/0/0/0.png</a>
            (if renderd is working)
        </li>
        <li>Vector Tiles (pg_tileserv - e.g., stops):
            <a href="/vector/public.gtfs_stops/0/0/0.pbf">/vector/public.gtfs_stops/0/0/0.pbf</a>
            (if pg_tileserv & data exist)
        </li>
        <li>OSRM Route (example, needs OSRM data):
            <a href="/route/v1/driving/-34,151;-35,150?overview=false">Example OSRM Route Query</a>
        </li>
        <li>This Test Page: /index.html or /</li>
    </ul>
</body>
</html>
"""
    index_html_path = os.path.join(test_page_dir, "index.html")
    run_elevated_command(
        ["tee", index_html_path],  # Overwrites or creates
        cmd_input=simple_index_html_content,
        current_logger=logger_to_use,
    )

    # Set correct ownership and permissions for the test page directory.
    run_elevated_command(
        ["chown", "-R", "www-data:www-data", test_page_dir],
        current_logger=logger_to_use,
    )
    run_elevated_command(
        ["chmod", "-R", "755", test_page_dir], current_logger=logger_to_use
    )

    # Nginx site configuration for the reverse proxy.
    nginx_conf_available_path = "/etc/nginx/sites-available/transit_proxy"
    # Nginx variables ($variable_name) need to be escaped with '$$' in
    # Python f-strings to be interpreted literally by Nginx.
    nginx_transit_proxy_conf_content = f"""\
# {nginx_conf_available_path}
# Configured by script V{script_hash_for_comments}
# This Nginx server block listens on port 80 and acts as a reverse proxy
# for various backend map services.

server {{
    listen 80 default_server;
    listen [::]:80 default_server; # For IPv6

    # Use the configured VM_IP_OR_DOMAIN or '_' as a catch-all.
    server_name {config.VM_IP_OR_DOMAIN if config.VM_IP_OR_DOMAIN != config.VM_IP_OR_DOMAIN_DEFAULT else "_"};

    access_log /var/log/nginx/transit_proxy.access.log;
    error_log /var/log/nginx/transit_proxy.error.log;

    # Standard proxy headers
    proxy_http_version 1.1;
    proxy_set_header Upgrade $$http_upgrade; # Note: Nginx vars use $$
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $$host;
    proxy_set_header X-Real-IP $$remote_addr;
    proxy_set_header X-Forwarded-For $$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $$scheme;
    proxy_buffering off; # Useful for streaming services

    # Proxy to pg_tileserv (typically on localhost:7800)
    location /vector/ {{
        proxy_pass http://localhost:7800/;
        # Add any specific headers for pg_tileserv if needed
    }}

    # Proxy to Apache/mod_tile/renderd for raster tiles (typically on localhost:8080)
    # The '/hot/' path segment should match Apache's AddTileConfig and Renderd's URI.
    location /raster/hot/ {{
        proxy_pass http://localhost:8080/hot/;
    }}

    # Proxy to OSRM backend (typically on localhost:5000)
    location /route/v1/ {{
        proxy_pass http://localhost:5000/route/v1/;
    }}

    # Serve the simple test page from the root location.
    location / {{
        root {test_page_dir};
        index index.html index.htm;
        try_files $$uri $$uri/ /index.html; # Fallback to index.html
    }}
}}
"""
    # Note: The f-string interpolation for Nginx variables ($$) is handled above.
    # If any $variable was missed, it would need manual escaping here.

    run_elevated_command(
        ["tee", nginx_conf_available_path],  # Overwrites or creates
        cmd_input=nginx_transit_proxy_conf_content,
        current_logger=logger_to_use,
    )
    log_map_server(
        f"{config.SYMBOLS['success']} Created Nginx site configuration: "
        f"{nginx_conf_available_path}",
        "success",
        logger_to_use,
    )

    # Enable the new Nginx site by creating a symlink.
    nginx_conf_enabled_path = (
        f"/etc/nginx/sites-enabled/"
        f"{os.path.basename(nginx_conf_available_path)}"
    )
    # Ensure the target for symlink exists before creating it.
    # run_elevated_command with 'ln -sf' will overwrite if symlink exists
    # or create it. It will fail if source does not exist.
    run_elevated_command(
        ["ln", "-sf", nginx_conf_available_path, nginx_conf_enabled_path],
        current_logger=logger_to_use,
    )
    log_map_server(
        f"{config.SYMBOLS['info']} Enabled Nginx site by symlinking to "
        f"{nginx_conf_enabled_path}.",
        "info",
        logger_to_use,
    )

    # Disable the default Nginx site if it's enabled.
    default_nginx_symlink = "/etc/nginx/sites-enabled/default"
    # Check if it's a symlink and exists before trying to remove.
    is_link_check = run_elevated_command(
        ["test", "-L", default_nginx_symlink],  # -L tests if it's a symlink
        check=False, capture_output=True, current_logger=logger_to_use,
    )
    if is_link_check.returncode == 0:  # Symlink exists, so site is enabled.
        run_elevated_command(
            ["rm", default_nginx_symlink], current_logger=logger_to_use
        )
        log_map_server(
            f"{config.SYMBOLS['info']} Disabled default Nginx site by "
            "removing symlink.",
            "info",
            logger_to_use,
        )

    # Test Nginx configuration and restart the service.
    log_map_server(
        f"{config.SYMBOLS['gear']} Testing Nginx configuration...",
        "info",
        logger_to_use,
    )
    try:
        # `nginx -t` will raise CalledProcessError if config test fails.
        run_elevated_command(["nginx", "-t"], current_logger=logger_to_use)
        log_map_server(
            f"{config.SYMBOLS['success']} Nginx configuration test successful.",
            "success",
            logger_to_use,
        )

        systemd_reload(current_logger=logger_to_use)
        run_elevated_command(
            ["systemctl", "enable", "nginx.service"],
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["systemctl", "restart", "nginx.service"],
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['info']} Nginx service status:",
            "info",
            logger_to_use,
        )
        run_elevated_command(
            ["systemctl", "status", "nginx.service", "--no-pager", "-l"],
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Nginx setup completed.",
            "success",
            logger_to_use,
        )
    except subprocess.CalledProcessError:
        # Error details are already logged by run_elevated_command.
        log_map_server(
            f"{config.SYMBOLS['error']} Nginx configuration test failed or "
            "service restart issue. Please check Nginx error logs (e.g., "
            "journalctl -u nginx or /var/log/nginx/error.log).",
            "error",
            logger_to_use,
        )
        raise  # Propagate failure for this critical step.
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} An unexpected error occurred during "
            f"Nginx finalization: {e}",
            "error",
            logger_to_use,
        )
        raise