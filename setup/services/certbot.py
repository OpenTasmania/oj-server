# setup/services/certbot.py
# -*- coding: utf-8 -*-
"""
Handles setup of SSL certificates using Certbot with the Nginx plugin.

This module automates the installation of Certbot and its Nginx plugin,
then attempts to obtain and install an SSL certificate for the configured
domain if it's a valid FQDN.
"""

import logging
import re  # For IP address and FQDN validation
import subprocess  # For CalledProcessError
from typing import Optional

from setup import config
from configure.command_utils import log_map_server, run_elevated_command

# `command_exists` was removed from imports in the original as not used;
# keeping it out unless a need arises.

module_logger = logging.getLogger(__name__)


def certbot_setup(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Set up SSL certificates using Certbot with the Nginx plugin.

    - Validates `VM_IP_OR_DOMAIN` from config to ensure it's suitable for
      Certbot (i.e., a Fully Qualified Domain Name, not an IP or localhost).
    - Installs Certbot and the `python3-certbot-nginx` plugin via apt.
    - Runs Certbot to obtain and install an SSL certificate for the domain,
      configuring Nginx automatically.
    - Uses non-interactive mode and agrees to terms of service automatically.
    - Sets up HTTP to HTTPS redirection.

    Args:
        current_logger: Optional logger instance to use. If None,
                        the module's default logger is used.

    Raises:
        Exception: If critical steps like Certbot package installation fail.
                   Certbot command failures are logged but may not always
                   be re-raised, depending on script's overall error strategy.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Setting up SSL certificates using Certbot "
        "with Nginx plugin...",
        "info",
        logger_to_use,
    )

    # Validate VM_IP_OR_DOMAIN before proceeding.
    domain_to_certify = config.VM_IP_OR_DOMAIN
    is_default_domain = domain_to_certify == config.VM_IP_OR_DOMAIN_DEFAULT
    # Regex to check if it's likely an IP address (IPv4).
    is_ip_address = bool(
        re.fullmatch(
            r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", domain_to_certify
        )
    )
    is_localhost = domain_to_certify.lower() == "localhost"
    # Basic FQDN check: must contain at least one dot and not be an IP.
    is_fqdn_like = (
        "." in domain_to_certify and not is_ip_address and not is_localhost
    )

    if is_default_domain or is_ip_address or is_localhost or not is_fqdn_like:
        log_map_server(
            f"{config.SYMBOLS['warning']} Skipping Certbot: VM_IP_OR_DOMAIN "
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
            "info",  # Informational, not a warning for the skip itself
            logger_to_use,
        )
        return  # Skip Certbot setup.

    log_map_server(
        f"{config.SYMBOLS['package']} Installing Certbot and Nginx plugin...",
        "info",
        logger_to_use,
    )
    try:
        # It's good practice to update apt cache before installing new packages.
        run_elevated_command(["apt", "update"], current_logger=logger_to_use)
        run_elevated_command(
            ["apt", "install", "-y", "certbot", "python3-certbot-nginx"],
            current_logger=logger_to_use,
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to install Certbot packages: {e}",
            "error",
            logger_to_use,
        )
        raise  # Certbot packages are critical for this step.

    # Generate a plausible admin email based on the domain.
    # Assumes the domain has at least one part before the TLD, e.g., example.com
    # For very short domains like `co.uk` this might not be ideal, but generally works.
    domain_parts = domain_to_certify.split(".")
    if len(domain_parts) >= 2:
        # Use the last two parts for a generic email, e.g., admin@example.com
        email_domain_part = f"{domain_parts[-2]}.{domain_parts[-1]}"
    else:
        # Fallback if domain is very simple (e.g. 'internaldomain')
        email_domain_part = domain_to_certify
    admin_email = f"admin@{email_domain_part}"

    log_map_server(
        f"{config.SYMBOLS['gear']} Running Certbot for domain: "
        f"{domain_to_certify} with registration email {admin_email}...",
        "info",
        logger_to_use,
    )

    certbot_cmd = [
        "certbot",
        "--nginx",  # Use the Nginx plugin.
        "-d",
        domain_to_certify,  # Domain to certify.
        "--non-interactive",  # Run without interactive prompts.
        "--agree-tos",  # Agree to Let's Encrypt Terms of Service.
        "--email",
        admin_email,  # Email for registration and renewal notices.
        "--redirect",  # Automatically redirect HTTP to HTTPS.
        # Consider these for enhanced security if appropriate for your setup:
        # "--hsts", # HTTP Strict Transport Security
        # "--staple-ocsp", # OCSP Stapling
        # "--uir" # Uncomment if you want to handle insecure redirects manually.
    ]
    try:
        # Certbot can be verbose; capture_output helps see its summary.
        run_elevated_command(
            certbot_cmd, capture_output=True, current_logger=logger_to_use
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Certbot SSL certificate obtained and "
            f"Nginx configured for {domain_to_certify}.",
            "success",
            logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['info']} Certbot auto-renewal timer should be "
            "active. Check with: sudo systemctl list-timers | grep certbot",
            "info",
            logger_to_use,
        )
    except subprocess.CalledProcessError:
        # run_elevated_command (via run_command) already logs e.cmd, e.stdout, e.stderr.
        log_map_server(
            f"{config.SYMBOLS['error']} Certbot command failed. Please check "
            "Certbot logs (usually in /var/log/letsencrypt/) for detailed "
            "error messages.",
            "error",
            logger_to_use,
        )
        # This failure might be non-critical for some dev setups, so not
        # re-raising by default. If SSL is mandatory, you might 'raise' here.
    except Exception as e_unexp:
        log_map_server(
            f"{config.SYMBOLS['error']} An unexpected error occurred during "
            f"Certbot setup: {e_unexp}",
            "error",
            logger_to_use,
        )
        # Consider re-raising if this step is critical:
        # raise e_unexp
