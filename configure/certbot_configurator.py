# configure/certbot_configurator.py
# -*- coding: utf-8 -*-
"""
Handles configuration of SSL certificates using Certbot with the Nginx plugin.
"""
import logging
import re  # For IP address and FQDN validation
import subprocess  # For CalledProcessError
from typing import Optional

from common.command_utils import log_map_server, run_elevated_command
from setup import config  # For SYMBOLS, VM_IP_OR_DOMAIN etc.

module_logger = logging.getLogger(__name__)

def run_certbot_nginx(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Runs Certbot to obtain and install SSL certificate for the configured domain,
    and configures Nginx.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Running Certbot with Nginx plugin...",
        "info",
        logger_to_use,
    )

    domain_to_certify = config.VM_IP_OR_DOMAIN
    is_default_domain = domain_to_certify == config.VM_IP_OR_DOMAIN_DEFAULT
    is_ip_address = bool(re.fullmatch(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", domain_to_certify))
    is_localhost = domain_to_certify.lower() == "localhost"
    # Basic FQDN check: must contain at least one dot and not be an IP or localhost.
    is_fqdn_like = "." in domain_to_certify and not is_ip_address and not is_localhost

    if is_default_domain or is_ip_address or is_localhost or not is_fqdn_like:
        log_map_server(
            f"{config.SYMBOLS['warning']} Skipping Certbot execution: VM_IP_OR_DOMAIN "
            f"('{domain_to_certify}') is default, an IP address, localhost, "
            "or not a Fully Qualified Domain Name (FQDN). Certbot requires a "
            "public FQDN for certificate issuance.",
            "warning",
            logger_to_use,
        )
        log_map_server(
            f"   Ensure DNS records for '{domain_to_certify}' point to this "
            "server's public IP and that Nginx (ports 80/443) is "
            "accessible externally if you wish to use Certbot.",
            "info",
            logger_to_use,
        )
        # Not raising an error, as this might be an intentional skip for local dev.
        # The calling step in main_installer can decide if this is a failure or a skippable warning.
        # For state management, the step might be marked as "skipped" or "completed with warning".
        return

    # Generate a plausible admin email based on the domain.
    domain_parts = domain_to_certify.split(".")
    email_domain_part = domain_to_certify # Fallback
    if len(domain_parts) >= 2:
        # Use the last two parts for a generic email, e.g., admin@example.com
        email_domain_part = f"{domain_parts[-2]}.{domain_parts[-1]}"
    admin_email = f"admin@{email_domain_part}"

    log_map_server(
        f"{config.SYMBOLS['info']} Attempting to obtain SSL certificate for domain: "
        f"{domain_to_certify} with registration email {admin_email}...",
        "info",
        logger_to_use,
    )

    certbot_cmd = [
        "certbot",
        "--nginx",  # Use the Nginx plugin.
        "-d", domain_to_certify,  # Domain to certify.
        "--non-interactive",  # Run without interactive prompts.
        "--agree-tos",  # Agree to Let's Encrypt Terms of Service.
        "--email", admin_email,  # Email for registration and renewal notices.
        "--redirect",  # Automatically redirect HTTP to HTTPS.
        # Consider these for enhanced security if appropriate for your setup:
        # "--hsts", # HTTP Strict Transport Security
        # "--staple-ocsp", # OCSP Stapling
        # "--uir" # Uncomment if you want to handle insecure redirects manually.
    ]
    try:
        # run_elevated_command will raise CalledProcessError if certbot returns non-zero
        run_elevated_command(certbot_cmd, capture_output=True, current_logger=logger_to_use, check=True)
        log_map_server(
            f"{config.SYMBOLS['success']} Certbot SSL certificate obtained and "
            f"Nginx configured for {domain_to_certify}.",
            "success",
            logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['info']} Certbot auto-renewal timer should be active. "
            "Check with: sudo systemctl list-timers | grep certbot",
            "info",
            logger_to_use,
        )
    except subprocess.CalledProcessError as e:
        # Error details are already logged by run_elevated_command.
        log_map_server(
            f"{config.SYMBOLS['error']} Certbot command FAILED. Please check "
            "Certbot logs (usually in /var/log/letsencrypt/) for detailed "
            "error messages.",
            "error",
            logger_to_use,
        )
        # Re-raise so that execute_step in main_installer.py can catch it and mark the step as failed.
        raise RuntimeError(f"Certbot execution failed for domain {domain_to_certify}.") from e
    except Exception as e_unexp:
        log_map_server(
            f"{config.SYMBOLS['error']} An unexpected error occurred during Certbot execution: {e_unexp}",
            "error",
            logger_to_use,
        )
        raise # Re-raise for execute_step