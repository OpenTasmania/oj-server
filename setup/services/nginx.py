# setup/services/nginx.py
"""
Handles setup of Nginx as a reverse proxy.
"""
import logging
import os
from typing import Optional

from setup import config
from setup.command_utils import (
    run_elevated_command,
    log_map_server,
    command_exists,
)
from ..helpers import systemd_reload  # Import systemd_reload
import subprocess

module_logger = logging.getLogger(__name__)


def nginx_setup(current_logger: Optional[logging.Logger] = None) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Setting up Nginx as a reverse proxy...",
        "info",
        logger_to_use,
    )

    if not command_exists("nginx"):
        log_map_server(
            f"{config.SYMBOLS['warning']} Nginx not found. Skipping Nginx setup.",
            "warning",
            logger_to_use,
        )
        return

    test_page_base_dir = "/var/www/html"  # Base for www-data
    test_page_dir = os.path.join(
        test_page_base_dir, "map_test_page"
    )  # Specific subdir
    run_elevated_command(
        ["mkdir", "-p", test_page_dir], current_logger=logger_to_use
    )

    simple_index_html_content = f"""<!DOCTYPE html>
<html><head><title>Nginx Map Proxy Test</title></head>
<body><h1>Nginx is Active!</h1>
<p>Map services should be available via Nginx proxy if correctly configured.</p>
<p>VM IP/Domain for access: {config.VM_IP_OR_DOMAIN}</p>
<ul>
    <li>Raster Tiles (OSM Base): <a href="/raster/hot/0/0/0.png">/raster/hot/0/0/0.png</a> (if renderd is working)</li>
    <li>Vector Tiles (pg_tileserv - e.g., stops): <a href="/vector/public.gtfs_stops/0/0/0.pbf">/vector/public.gtfs_stops/0/0/0.pbf</a> (if pg_tileserv & data exist)</li>
    <li>OSRM Route (example, needs OSRM data): <a href="/route/v1/driving/-34,151;-35,150?overview=false">Example OSRM Route Query</a></li>
    <li>This Test Page: /index.html or /</li>
</ul>
</body></html>
"""
    index_html_path = os.path.join(test_page_dir, "index.html")
    run_elevated_command(
        ["tee", index_html_path],
        cmd_input=simple_index_html_content,
        current_logger=logger_to_use,
    )

    run_elevated_command(
        ["chown", "-R", "www-data:www-data", test_page_dir],
        current_logger=logger_to_use,
    )
    run_elevated_command(
        ["chmod", "-R", "755", test_page_dir], current_logger=logger_to_use
    )

    nginx_conf_available_path = "/etc/nginx/sites-available/transit_proxy"
    # IMPORTANT: In f-strings, Nginx's own $variables need to be escaped as $$.
    # Python variables like {config.VM_IP_OR_DOMAIN} are interpolated correctly by the f-string.
    nginx_transit_proxy_conf_content = f"""# /etc/nginx/sites-available/transit_proxy
# Configured by script V{config.SCRIPT_VERSION}
server {{
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name {config.VM_IP_OR_DOMAIN if config.VM_IP_OR_DOMAIN != config.VM_IP_OR_DOMAIN_DEFAULT else "_"}; # Underscore for default catch-all if needed

    access_log /var/log/nginx/transit_proxy.access.log;
    error_log /var/log/nginx/transit_proxy.error.log;

    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade; # Note: Nginx vars need $$ in Python f-string
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;             # $$host
    proxy_set_header X-Real-IP $remote_addr; # $$remote_addr
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; # $$proxy_add_x_forwarded_for
    proxy_set_header X-Forwarded-Proto $scheme; # $$scheme
    proxy_buffering off;

    location /vector/ {{ # pg_tileserv (usually on localhost:7800)
        proxy_pass http://localhost:7800/;
    }}

    location /raster/hot/ {{ # Apache/mod_tile/renderd (usually on localhost:8080)
        proxy_pass http://localhost:8080/hot/;
    }}

    location /route/v1/ {{ # OSRM (usually on localhost:5000)
        proxy_pass http://localhost:5000/route/v1/;
    }}

    location / {{
        root {test_page_dir};
        index index.html index.htm;
        try_files $uri $uri/ /index.html; # $$uri $$uri/
    }}
}}
"""
    # Perform $ -> $$ replacement for Nginx variables if they were not already escaped
    nginx_transit_proxy_conf_content = (
        nginx_transit_proxy_conf_content.replace(
            "$http_upgrade", "$$http_upgrade"
        )
    )
    nginx_transit_proxy_conf_content = (
        nginx_transit_proxy_conf_content.replace("$host", "$$host")
    )
    nginx_transit_proxy_conf_content = (
        nginx_transit_proxy_conf_content.replace(
            "$remote_addr", "$$remote_addr"
        )
    )
    nginx_transit_proxy_conf_content = (
        nginx_transit_proxy_conf_content.replace(
            "$proxy_add_x_forwarded_for", "$$proxy_add_x_forwarded_for"
        )
    )
    nginx_transit_proxy_conf_content = (
        nginx_transit_proxy_conf_content.replace("$scheme", "$$scheme")
    )
    nginx_transit_proxy_conf_content = (
        nginx_transit_proxy_conf_content.replace("$uri", "$$uri")
    )

    run_elevated_command(
        ["tee", nginx_conf_available_path],
        cmd_input=nginx_transit_proxy_conf_content,
        current_logger=logger_to_use,
    )
    log_map_server(
        f"{config.SYMBOLS['success']} Created Nginx site configuration: {nginx_conf_available_path}",
        "success",
        logger_to_use,
    )

    nginx_conf_enabled_path = f"/etc/nginx/sites-enabled/{os.path.basename(nginx_conf_available_path)}"
    # Ensure target for symlink exists before creating it
    if os.path.isfile(
        nginx_conf_available_path
    ):  # This check is as current user, might not see root-owned file
        # Better to rely on ln -sf to overwrite if it exists, or fail if source is missing
        run_elevated_command(
            ["ln", "-sf", nginx_conf_available_path, nginx_conf_enabled_path],
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['info']} Enabled Nginx site by symlinking to {nginx_conf_enabled_path}.",
            "info",
            logger_to_use,
        )
    else:
        # This case should ideally not be reached if tee command above succeeded
        log_map_server(
            f"{config.SYMBOLS['error']} Source Nginx config {nginx_conf_available_path} not found. Cannot enable site.",
            "error",
            logger_to_use,
        )
        # Consider raising an error here to stop the Nginx setup.

    default_nginx_symlink = "/etc/nginx/sites-enabled/default"
    # Check if it's a symlink and exists before trying to remove
    is_link_check = run_elevated_command(
        ["test", "-L", default_nginx_symlink],
        check=False,
        capture_output=True,
        current_logger=logger_to_use,
    )
    if is_link_check.returncode == 0:  # Symlink exists
        run_elevated_command(
            ["rm", default_nginx_symlink], current_logger=logger_to_use
        )
        log_map_server(
            f"{config.SYMBOLS['info']} Disabled default Nginx site by removing symlink.",
            "info",
            logger_to_use,
        )

    log_map_server(
        f"{config.SYMBOLS['gear']} Testing Nginx configuration...",
        "info",
        logger_to_use,
    )
    try:
        run_elevated_command(
            ["nginx", "-t"], current_logger=logger_to_use
        )  # Will raise CalledProcessError if nginx -t fails
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
        # Error already logged by run_elevated_command -> run_command
        log_map_server(
            f"{config.SYMBOLS['error']} Nginx configuration test failed or service restart issue. Please check Nginx error logs (e.g., journalctl -u nginx or /var/log/nginx/error.log).",
            "error",
            logger_to_use,
        )
        raise  # Fail the step
