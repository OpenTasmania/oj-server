# configure/certbot_configurator.py
# -*- coding: utf-8 -*-
"""
Handles configuration of SSL certificates using Certbot with the Nginx plugin.
"""

import logging
import re
import subprocess
from typing import Optional

from common.command_utils import log_map_server, run_elevated_command
from setup.config_models import (  # For type hinting & default comparison
    VM_IP_OR_DOMAIN_DEFAULT,
    AppSettings,
)

# from setup import config as static_config # Not needed if symbols come from app_settings

module_logger = logging.getLogger(__name__)


def run_certbot_nginx(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Runs Certbot to obtain and install SSL certificate for the configured domain.

    This function uses the Certbot tool with the Nginx plugin to obtain and install
    an SSL certificate for the domain specified in app_settings. It performs validation
    checks on the domain to ensure it's suitable for SSL certification (must be a valid
    FQDN, not an IP address or localhost). If the domain is valid, it runs Certbot with
    appropriate options based on the certbot configuration in app_settings.

    Args:
        app_settings (AppSettings): Configuration object containing application settings
            including the domain to certify and Certbot configuration options.
        current_logger (Optional[logging.Logger]): Logger instance to use for logging
            messages. If None, a module-wide default logger is used.

    Raises:
        RuntimeError: If the Certbot command fails during execution.
        Exception: For any other unexpected errors during Certbot execution.

    Note:
        If the domain is not valid for SSL certification (e.g., it's an IP address or
        localhost), the function will log a warning and return without attempting to
        obtain a certificate, as this is often intentional for local development.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    certbot_cfg = app_settings.certbot

    log_map_server(
        f"{symbols.get('step', '➡️')} Running Certbot with Nginx plugin...",
        "info",
        logger_to_use,
        app_settings,
    )

    domain_to_certify = app_settings.vm_ip_or_domain
    is_default_domain = (
        domain_to_certify == VM_IP_OR_DOMAIN_DEFAULT
    )  # Imported default
    is_ip_address = bool(
        re.fullmatch(
            r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", domain_to_certify
        )
    )
    is_localhost = domain_to_certify.lower() == "localhost"
    is_fqdn_like = (
        "." in domain_to_certify and not is_ip_address and not is_localhost
    )

    if is_default_domain or is_ip_address or is_localhost or not is_fqdn_like:
        log_map_server(
            f"{symbols.get('warning', '!')} Skipping Certbot: VM_IP_OR_DOMAIN ('{domain_to_certify}') "
            "is default, an IP, localhost, or not an FQDN. Certbot requires a public FQDN.",
            "warning",
            logger_to_use,
            app_settings,
        )
        log_map_server(
            f"   Ensure DNS for '{domain_to_certify}' points to this server and Nginx (80/443) is accessible externally.",
            "info",
            logger_to_use,
            app_settings,
        )
        return  # Not raising an error, as this might be intentional for local dev.

    # Derive admin email if not explicitly set in a future CertbotSettings field
    admin_email = getattr(
        certbot_cfg, "admin_email", None
    )  # Check if admin_email is in CertbotSettings
    if not admin_email:
        domain_parts = domain_to_certify.split(".")
        email_domain_part = domain_to_certify
        if len(domain_parts) >= 2:
            email_domain_part = f"{domain_parts[-2]}.{domain_parts[-1]}"
        admin_email = f"admin@{email_domain_part}"  # Default derivation
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Using derived admin email for Certbot: {admin_email}",
            "info",
            logger_to_use,
            app_settings,
        )
    else:
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Using configured admin email for Certbot: {admin_email}",
            "info",
            logger_to_use,
            app_settings,
        )

    log_map_server(
        f"{symbols.get('info', 'ℹ️')} Attempting SSL certificate for domain: {domain_to_certify} with email {admin_email}...",
        "info",
        logger_to_use,
        app_settings,
    )

    certbot_cmd = [
        "certbot",
        "--nginx",
        "-d",
        domain_to_certify,
        "--non-interactive",
        "--agree-tos",
        "--email",
        admin_email,
        "--redirect",  # Default: redirect HTTP to HTTPS
    ]

    if certbot_cfg.use_hsts:
        certbot_cmd.append("--hsts")
    if certbot_cfg.use_staple_ocsp:
        certbot_cmd.append("--staple-ocsp")
    if certbot_cfg.use_uir:
        certbot_cmd.append("--uir")

    try:
        run_elevated_command(
            certbot_cmd,
            app_settings,
            capture_output=True,
            current_logger=logger_to_use,
            check=True,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} Certbot SSL certificate obtained and Nginx configured for {domain_to_certify}.",
            "success",
            logger_to_use,
            app_settings,
        )
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Certbot auto-renewal timer should be active. Check with: sudo systemctl list-timers | grep certbot",
            "info",
            logger_to_use,
            app_settings,
        )
    except subprocess.CalledProcessError as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Certbot command FAILED. Check Certbot logs (usually /var/log/letsencrypt/).",
            "error",
            logger_to_use,
            app_settings,
        )
        # Output from run_elevated_command already includes stderr/stdout from the failed command
        raise RuntimeError(
            f"Certbot execution failed for domain {domain_to_certify}."
        ) from e
    except Exception as e_unexp:
        log_map_server(
            f"{symbols.get('error', '❌')} An unexpected error occurred during Certbot execution: {e_unexp}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        raise
