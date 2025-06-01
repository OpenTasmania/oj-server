# actions/website_setup_actions.py
# -*- coding: utf-8 -*-
"""
Handles deployment of the static test website page.
"""
import logging
import os
import re  # For IP check
from pathlib import Path  # For path handling
from typing import Optional

from common.command_utils import log_map_server, run_elevated_command
from setup.config_models import AppSettings  # For type hinting
from setup import config as static_config  # For SCRIPT_VERSION if used in {script_version_short}
from setup.state_manager import get_current_script_hash  # For {script_hash} if preferred

module_logger = logging.getLogger(__name__)

# WEBSITE_DEPLOY_DIR, WEBSITE_HTML_FILENAME are now from app_settings.webapp
# WEB_USER, WEB_GROUP are system constants, can remain here or move to a shared constants if used elsewhere
WEB_SERVER_USER = "www-data"  # Standard web server user
WEB_SERVER_GROUP = "www-data"


def deploy_test_website_content(
        app_settings: AppSettings,
        current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Creates the test website directory and deploys the index.html file
    using templates and paths from app_settings.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    webapp_cfg = app_settings.webapp

    deploy_dir = Path(webapp_cfg.root_dir)
    index_filename = webapp_cfg.index_filename
    website_html_page_path = deploy_dir / index_filename

    log_map_server(
        f"{symbols.get('step', '➡️')} Deploying test website content to {deploy_dir}...",
        "info", logger_to_use, app_settings)

    # Create the deployment directory
    run_elevated_command(["mkdir", "-p", str(deploy_dir)], app_settings, current_logger=logger_to_use)

    # Determine scheme and Nginx port for URLs in HTML
    # Certbot step modifies Nginx to HTTPS. We need to know if HTTPS is active.
    # For simplicity, webapp.default_scheme can be "http" and change to "https" if certbot ran successfully.
    # Or, an AppSettings field like `app_settings.nginx.is_https_enabled` could be set by certbot step.
    # For now, using configured default_scheme and nginx_external_port.
    scheme = webapp_cfg.default_scheme
    nginx_port = webapp_cfg.nginx_external_port  # 80 for http, 443 for https by default

    # If Certbot has run and Nginx is configured for SSL, scheme should be https
    # This is a simplified check; a more robust way is needed if Certbot state isn't directly in AppSettings
    if not (app_settings.vm_ip_or_domain == VM_IP_OR_DOMAIN_DEFAULT or \
            bool(re.fullmatch(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", app_settings.vm_ip_or_domain)) or \
            app_settings.vm_ip_or_domain.lower() == "localhost"):
        # If it's a proper domain, assume Certbot might have run or will run
        # A better way would be to check if Nginx is listening on 443 or if certs exist
        # For now, if default_scheme is 'http' but it's a real domain, let's prefer 'https'
        # This is heuristic. A shared state or specific config from Certbot step would be better.
        # For this example, let's assume if it's not a local/default IP/domain, https is intended after certbot
        if scheme == "http":  # If default is http, but looks like a public domain
            # A more robust check: is Nginx configured for SSL for this domain?
            # This is hard to check here easily. For now, assume if it's a proper domain, https might be active via certbot.
            # Let's assume for now that the user sets webapp.default_scheme to https in config.yaml if certbot is used.
            pass

    # Get script hash or version for the V{...} tag in HTML
    # Using short script hash for brevity in title
    script_hash_full = get_current_script_hash(static_config.OSM_PROJECT_ROOT, app_settings, logger_to_use)
    script_version_short = script_hash_full[:7] if script_hash_full else static_config.SCRIPT_VERSION

    html_template_str = webapp_cfg.index_html_template
    format_vars = {
        "script_version_short": script_version_short,
        "scheme": scheme,
        "vm_ip_or_domain": app_settings.vm_ip_or_domain,
        "nginx_port": nginx_port,  # Port Nginx is externally listening on
        "renderd_uri_path_segment": app_settings.renderd.uri_path_segment,
        "pg_tileserv_uri_prefix": app_settings.pg_tileserv.uri_prefix,
        # Add other placeholders if your HTML template needs them
    }

    try:
        webpage_content_final = html_template_str.format(**format_vars)

        run_elevated_command(
            ["tee", str(website_html_page_path)], app_settings,
            cmd_input=webpage_content_final, current_logger=logger_to_use
        )
        # Set ownership and permissions for web server access
        run_elevated_command(["chown", "-R", f"{WEB_SERVER_USER}:{WEB_SERVER_GROUP}", str(deploy_dir)], app_settings,
                             current_logger=logger_to_use)
        run_elevated_command(["chmod", "-R", "g+rX,o+rX", str(deploy_dir)], app_settings, current_logger=logger_to_use)
        run_elevated_command(["find", str(deploy_dir), "-type", "f", "-exec", "chmod", "g+r,o+r", "{}", ";"],
                             app_settings, current_logger=logger_to_use)

        log_map_server(f"{symbols.get('success', '✅')} Deployed and permissioned {website_html_page_path}", "success",
                       logger_to_use, app_settings)

        # Construct URL for user info, considering if port is standard for scheme
        port_str = f":{nginx_port}" if (scheme == "http" and nginx_port != 80) or \
                                       (scheme == "https" and nginx_port != 443) else ""
        test_page_url = f"{scheme}://{app_settings.vm_ip_or_domain}{port_str}/"
        log_map_server(f"{symbols.get('info', 'ℹ️')} Test website page should be accessible at: {test_page_url}",
                       "info", logger_to_use, app_settings)

    except KeyError as e_key:
        log_map_server(
            f"{symbols.get('error', '❌')} Missing placeholder key '{e_key}' for website HTML template. Check config.yaml/models.",
            "error", logger_to_use, app_settings)
        raise
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to deploy test website content to {website_html_page_path}: {e}",
            "error", logger_to_use, app_settings, exc_info=True)
        raise