# configure/nginx_configurator.py
# -*- coding: utf-8 -*-
"""
Handles configuration of Nginx as a reverse proxy for map services.
"""
import logging
import os
import subprocess  # For CalledProcessError
from typing import Optional

from common.command_utils import log_map_server, run_elevated_command
from common.system_utils import systemd_reload
from setup import config  # For SYMBOLS, VM_IP_OR_DOMAIN etc.
from setup.state_manager import get_current_script_hash

module_logger = logging.getLogger(__name__)

NGINX_SITES_AVAILABLE_DIR = "/etc/nginx/sites-available"
NGINX_SITES_ENABLED_DIR = "/etc/nginx/sites-enabled"
PROXY_CONF_NAME = "transit_proxy"  # Name of our Nginx site config file

# This directory is set up by setup/services/website.py
WEBSITE_ROOT_DIR = "/var/www/html/map_test_page"


def create_nginx_proxy_site_config(current_logger: Optional[logging.Logger] = None) -> None:
    """Creates the Nginx site configuration file for reverse proxying."""
    logger_to_use = current_logger if current_logger else module_logger
    script_hash = get_current_script_hash(logger_instance=logger_to_use) or "UNKNOWN_HASH"

    nginx_conf_path = os.path.join(NGINX_SITES_AVAILABLE_DIR, PROXY_CONF_NAME)
    log_map_server(f"{config.SYMBOLS['step']} Creating Nginx site configuration: {nginx_conf_path}...", "info",
                   logger_to_use)

    server_name_config = config.VM_IP_OR_DOMAIN
    if config.VM_IP_OR_DOMAIN == config.VM_IP_OR_DOMAIN_DEFAULT:
        server_name_config = "_"  # Catch-all if default example.com is used

    # Nginx variables ($variable_name) need to be escaped with '$$' in
    # Python f-strings to be interpreted literally by Nginx.
    nginx_transit_proxy_conf_content = f"""\
# {nginx_conf_path}
# Configured by script V{script_hash}
# Nginx server block as a reverse proxy for map services.

server {{
    listen 80 default_server;
    listen [::]:80 default_server;

    server_name {server_name_config};

    access_log /var/log/nginx/{PROXY_CONF_NAME}.access.log;
    error_log /var/log/nginx/{PROXY_CONF_NAME}.error.log;

    # Standard proxy headers
    proxy_http_version 1.1;
    proxy_set_header Upgrade $$http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $$host;
    proxy_set_header X-Real-IP $$remote_addr;
    proxy_set_header X-Forwarded-For $$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $$scheme;
    proxy_buffering off;

    # Proxy to pg_tileserv (default port 7800)
    location /vector/ {{
        proxy_pass http://localhost:7800/;
        # Add specific headers for pg_tileserv if needed later
    }}

    # Proxy to Apache/mod_tile/renderd for raster tiles (default port 8080)
    # The '/hot/' path segment must match Apache's AddTileConfig and Renderd's URI.
    location /raster/hot/ {{
        proxy_pass http://localhost:8080/hot/;
    }}

    # Proxy to OSRM backend (default port 5000)
    # This assumes OSRM is running and listening on localhost:5000.
    # If multiple OSRM regions run on different ports, this needs adjustment
    # or multiple location blocks.
    location /route/v1/ {{
        proxy_pass http://localhost:5000/route/v1/;
    }}

    # Serve the test website page from the root location.
    # The WEBSITE_ROOT_DIR is prepared by the website_setup step.
    location / {{
        root {WEBSITE_ROOT_DIR};
        index index.html index.htm;
        try_files $$uri $$uri/ /index.html =404; # Fallback to index.html or 404
    }}
}}
"""
    try:
        run_elevated_command(
            ["tee", nginx_conf_path],
            cmd_input=nginx_transit_proxy_conf_content, current_logger=logger_to_use
        )
        log_map_server(f"{config.SYMBOLS['success']} Created Nginx site configuration: {nginx_conf_path}", "success",
                       logger_to_use)
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['error']} Failed to write Nginx site configuration {nginx_conf_path}: {e}",
                       "error", logger_to_use)
        raise


def manage_nginx_sites(current_logger: Optional[logging.Logger] = None) -> None:
    """Enables the new Nginx proxy site and disables the default site."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Managing Nginx sites (enabling {PROXY_CONF_NAME}, disabling default)...",
                   "info", logger_to_use)

    source_conf_path = os.path.join(NGINX_SITES_AVAILABLE_DIR, PROXY_CONF_NAME)
    symlink_path = os.path.join(NGINX_SITES_ENABLED_DIR, PROXY_CONF_NAME)

    # Ensure source file exists before trying to symlink
    if not os.path.exists(source_conf_path):
        # Try elevated check
        try:
            run_elevated_command(["test", "-f", source_conf_path], check=True, current_logger=logger_to_use)
        except Exception:
            log_map_server(
                f"{config.SYMBOLS['error']} Nginx site file {source_conf_path} does not exist. Cannot enable.", "error",
                logger_to_use)
            raise FileNotFoundError(f"{source_conf_path} not found.")

    run_elevated_command(["ln", "-sf", source_conf_path, symlink_path], current_logger=logger_to_use)
    log_map_server(f"{config.SYMBOLS['success']} Enabled Nginx site '{PROXY_CONF_NAME}'.", "success", logger_to_use)

    # Disable default Nginx site
    default_nginx_symlink = os.path.join(NGINX_SITES_ENABLED_DIR, "default")
    try:
        # Check if it's a symlink and exists
        test_result = run_elevated_command(["test", "-L", default_nginx_symlink], check=False, capture_output=True,
                                           current_logger=logger_to_use)
        if test_result.returncode == 0:  # Symlink exists
            run_elevated_command(["rm", default_nginx_symlink], current_logger=logger_to_use)
            log_map_server(f"{config.SYMBOLS['info']} Disabled default Nginx site.", "info", logger_to_use)
        else:
            log_map_server(
                f"{config.SYMBOLS['info']} Default Nginx site not enabled or symlink not found at {default_nginx_symlink}. Skipping disable.",
                "info", logger_to_use)
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['warning']} Could not disable default Nginx site (error: {e}). This might be okay if it wasn't enabled.",
            "warning", logger_to_use)


def test_nginx_configuration(current_logger: Optional[logging.Logger] = None) -> None:
    """Tests the Nginx configuration for syntax errors."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Testing Nginx configuration (nginx -t)...", "info", logger_to_use)
    try:
        run_elevated_command(["nginx", "-t"], current_logger=logger_to_use,
                             check=True)  # check=True will raise on error
        log_map_server(f"{config.SYMBOLS['success']} Nginx configuration test successful.", "success", logger_to_use)
    except subprocess.CalledProcessError as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Nginx configuration test FAILED. Command: '{e.cmd}'. Output: {e.stderr or e.stdout}",
            "error", logger_to_use)
        raise  # Propagate failure, this is critical


def activate_nginx_service(current_logger: Optional[logging.Logger] = None) -> None:
    """Reloads systemd, restarts and enables the Nginx service."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Activating Nginx service...", "info", logger_to_use)

    systemd_reload(current_logger=logger_to_use)
    run_elevated_command(["systemctl", "restart", "nginx.service"], current_logger=logger_to_use)
    run_elevated_command(["systemctl", "enable", "nginx.service"], current_logger=logger_to_use)

    log_map_server(f"{config.SYMBOLS['info']} Nginx service status:", "info", logger_to_use)
    run_elevated_command(["systemctl", "status", "nginx.service", "--no-pager", "-l"], current_logger=logger_to_use)
    log_map_server(f"{config.SYMBOLS['success']} Nginx service activated.", "success", logger_to_use)