# setup/services/certbot.py
"""
Handles setup of SSL certificates using Certbot with the Nginx plugin.
"""
import logging
import re  # For IP address check
from typing import Optional
import subprocess
from .. import config
from ..command_utils import (
    run_elevated_command,
    log_map_server,
)  # Removed command_exists as not used here

module_logger = logging.getLogger(__name__)


def certbot_setup(current_logger: Optional[logging.Logger] = None) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Setting up SSL certificates using Certbot with Nginx plugin...",
        "info",
        logger_to_use,
    )

    # Validate VM_IP_OR_DOMAIN before proceeding
    domain_to_certify = config.VM_IP_OR_DOMAIN
    is_default_domain = domain_to_certify == config.VM_IP_OR_DOMAIN_DEFAULT
    # Regex to check if it's likely an IP address
    is_ip_address = bool(
        re.fullmatch(
            r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", domain_to_certify
        )
    )
    is_localhost = domain_to_certify.lower() == "localhost"

    if (
        is_default_domain
        or is_ip_address
        or is_localhost
        or "." not in domain_to_certify
    ):
        log_map_server(
            f"{config.SYMBOLS['warning']} Skipping Certbot: VM_IP_OR_DOMAIN ('{domain_to_certify}') is default, an IP address, localhost, or not a Fully Qualified Domain Name (FQDN). Certbot requires a public FQDN.",
            "warning",
            logger_to_use,
        )
        log_map_server(
            f"   Ensure DNS records for '{domain_to_certify}' point to this server's public IP and that Nginx (port 80/443) is accessible externally.",
            "info",
            logger_to_use,
        )
        return

    log_map_server(
        f"{config.SYMBOLS['package']} Installing Certbot and Nginx plugin...",
        "info",
        logger_to_use,
    )
    try:
        # It's good practice to update apt cache before installing new packages
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
        raise  # Critical for this step

    admin_email = (
        f"admin@{domain_to_certify}"  # Generate a plausible admin email
    )
    log_map_server(
        f"{config.SYMBOLS['gear']} Running Certbot for domain: {domain_to_certify} with registration email {admin_email}...",
        "info",
        logger_to_use,
    )

    certbot_cmd = [
        "certbot",
        "--nginx",  # Use the Nginx plugin
        "-d",
        domain_to_certify,  # Domain to certify
        "--non-interactive",  # Run without interactive prompts
        "--agree-tos",  # Agree to Let's Encrypt Terms of Service
        "--email",
        admin_email,  # Email for registration and renewal notices
        "--redirect",  # Automatically redirect HTTP to HTTPS
        # Consider "--hsts" and "--staple-ocsp" for enhanced security if appropriate
        # "--hsts",
        # "--staple-ocsp",
        # "--uir" # Uncomment if you want to handle insecure redirects manually (less common)
    ]
    try:
        # Certbot can be verbose, capture_output might be useful if you only want to log summary
        run_elevated_command(
            certbot_cmd, capture_output=True, current_logger=logger_to_use
        )  # capture_output helps to see certbot's own summary
        log_map_server(
            f"{config.SYMBOLS['success']} Certbot SSL certificate obtained and Nginx configured for {domain_to_certify}.",
            "success",
            logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['info']} Certbot auto-renewal timer should be active. Check with: sudo systemctl list-timers | grep certbot",
            "info",
            logger_to_use,
        )
    except subprocess.CalledProcessError:
        # run_elevated_command (via run_command) already logs e.cmd, e.stdout, e.stderr
        log_map_server(
            f"{config.SYMBOLS['error']} Certbot command failed. Please check Certbot logs (usually in /var/log/letsencrypt/) for detailed error messages.",
            "error",
            logger_to_use,
        )
        # This failure might be non-critical for some dev setups, so not re-raising by default.
        # If SSL is mandatory, you might want to 'raise' here.
    except Exception as e_unexp:
        log_map_server(
            f"{config.SYMBOLS['error']} An unexpected error occurred during Certbot setup: {e_unexp}",
            "error",
            logger_to_use,
        )
        # raise e_unexp # If critical
