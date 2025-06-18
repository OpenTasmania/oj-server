"""
Certbot configurator module.

This module provides a self-contained configurator for SSL certificates
using Certbot with the Nginx plugin.
"""

import logging
import re
import subprocess
from typing import Optional

from common.command_utils import log_map_server, run_elevated_command
from installer.base_configurator import BaseConfigurator
from installer.config_models import (
    VM_IP_OR_DOMAIN_DEFAULT,
    AppSettings,
)
from installer.registry import ComponentRegistry


@ComponentRegistry.register(
    name="certbot",
    metadata={
        "dependencies": ["nginx"],  # Certbot depends on Nginx
        "description": "SSL certificate configuration using Certbot with Nginx plugin",
    },
)
class CertbotConfigurator(BaseConfigurator):
    """
    Configurator for SSL certificates using Certbot with the Nginx plugin.

    This configurator ensures that SSL certificates are properly obtained and
    installed for the configured domain using Certbot with the Nginx plugin.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Certbot configurator.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)

    def configure(self) -> bool:
        """
        Configure SSL certificates using Certbot with the Nginx plugin.

        This method runs Certbot to obtain and install SSL certificate for the
        configured domain.

        Returns:
            True if the configuration was successful, False otherwise.
        """
        try:
            self._run_certbot_nginx()
            return True
        except Exception as e:
            self.logger.error(f"Error configuring Certbot: {str(e)}")
            return False

    def unconfigure(self) -> bool:
        """
        Unconfigure SSL certificates.

        This method removes the SSL certificates obtained by Certbot.

        Returns:
            True if the unconfiguration was successful, False otherwise.
        """
        try:
            symbols = self.app_settings.symbols
            domain_to_certify = self.app_settings.vm_ip_or_domain

            # Check if the domain is valid for SSL certification
            if self._is_valid_domain_for_ssl(domain_to_certify):
                log_map_server(
                    f"{symbols.get('step', '')} Removing SSL certificates for {domain_to_certify}...",
                    "info",
                    self.logger,
                    self.app_settings,
                )

                # Run certbot delete command
                run_elevated_command(
                    [
                        "certbot",
                        "delete",
                        "--cert-name",
                        domain_to_certify,
                        "--non-interactive",
                    ],
                    self.app_settings,
                    capture_output=True,
                    current_logger=self.logger,
                    check=False,
                )

                log_map_server(
                    f"{symbols.get('success', '')} SSL certificates for {domain_to_certify} removed.",
                    "success",
                    self.logger,
                    self.app_settings,
                )

            return True
        except Exception as e:
            self.logger.error(f"Error unconfiguring Certbot: {str(e)}")
            return False

    def is_configured(self) -> bool:
        """
        Check if SSL certificates are configured.

        This method checks if SSL certificates are properly configured for the
        configured domain.

        Returns:
            True if SSL certificates are configured, False otherwise.
        """
        try:
            domain_to_certify = self.app_settings.vm_ip_or_domain

            # Check if the domain is valid for SSL certification
            if not self._is_valid_domain_for_ssl(domain_to_certify):
                return False

            # Check if the certificate exists
            result = run_elevated_command(
                ["certbot", "certificates", "--cert-name", domain_to_certify],
                self.app_settings,
                capture_output=True,
                check=False,
                current_logger=self.logger,
            )

            return (
                result.returncode == 0 and domain_to_certify in result.stdout
            )
        except Exception as e:
            self.logger.error(
                f"Error checking if Certbot is configured: {str(e)}"
            )
            return False

    def _is_valid_domain_for_ssl(self, domain: str) -> bool:
        """
        Check if the domain is valid for SSL certification.

        Args:
            domain: The domain to check.

        Returns:
            True if the domain is valid for SSL certification, False otherwise.
        """
        is_default_domain = domain == VM_IP_OR_DOMAIN_DEFAULT
        is_ip_address = bool(
            re.fullmatch(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", domain)
        )
        is_localhost = domain.lower() == "localhost"
        is_fqdn_like = (
            "." in domain and not is_ip_address and not is_localhost
        )

        return not (
            is_default_domain
            or is_ip_address
            or is_localhost
            or not is_fqdn_like
        )

    def _run_certbot_nginx(self) -> None:
        """
        Run Certbot to obtain and install SSL certificate for the configured domain.

        Raises:
            RuntimeError: If the Certbot command fails during execution.
            Exception: For any other unexpected errors during Certbot execution.
        """
        symbols = self.app_settings.symbols
        certbot_cfg = self.app_settings.certbot

        log_map_server(
            f"{symbols.get('step', '')} Running Certbot with Nginx plugin...",
            "info",
            self.logger,
            self.app_settings,
        )

        domain_to_certify = self.app_settings.vm_ip_or_domain

        if not self._is_valid_domain_for_ssl(domain_to_certify):
            log_map_server(
                f"{symbols.get('warning', '')} Skipping Certbot: VM_IP_OR_DOMAIN ('{domain_to_certify}') "
                "is default, an IP, localhost, or not an FQDN. Certbot requires a public FQDN.",
                "warning",
                self.logger,
                self.app_settings,
            )
            log_map_server(
                f"   Ensure DNS for '{domain_to_certify}' points to this server and Nginx (80/443) is accessible externally.",
                "info",
                self.logger,
                self.app_settings,
            )
            return  # Not raising an error, as this might be intentional for local dev.

        # Derive admin email if not explicitly set in a future CertbotSettings field
        admin_email = getattr(certbot_cfg, "admin_email", None)
        if not admin_email:
            domain_parts = domain_to_certify.split(".")
            email_domain_part = domain_to_certify
            if len(domain_parts) >= 2:
                email_domain_part = f"{domain_parts[-2]}.{domain_parts[-1]}"
            admin_email = f"admin@{email_domain_part}"  # Default derivation
            log_map_server(
                f"{symbols.get('info', '')} Using derived admin email for Certbot: {admin_email}",
                "info",
                self.logger,
                self.app_settings,
            )
        else:
            log_map_server(
                f"{symbols.get('info', '')} Using configured admin email for Certbot: {admin_email}",
                "info",
                self.logger,
                self.app_settings,
            )

        log_map_server(
            f"{symbols.get('info', '')} Attempting SSL certificate for domain: {domain_to_certify} with email {admin_email}...",
            "info",
            self.logger,
            self.app_settings,
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
                self.app_settings,
                capture_output=True,
                current_logger=self.logger,
                check=True,
            )
            log_map_server(
                f"{symbols.get('success', '')} Certbot SSL certificate obtained and Nginx configured for {domain_to_certify}.",
                "success",
                self.logger,
                self.app_settings,
            )
            log_map_server(
                f"{symbols.get('info', '')} Certbot auto-renewal timer should be active. Check with: sudo systemctl list-timers | grep certbot",
                "info",
                self.logger,
                self.app_settings,
            )
        except subprocess.CalledProcessError as e:
            log_map_server(
                f"{symbols.get('error', '')} Certbot command FAILED. Check Certbot logs (usually /var/log/letsencrypt/).",
                "error",
                self.logger,
                self.app_settings,
            )
            # Output from run_elevated_command already includes stderr/stdout from the failed command
            raise RuntimeError(
                f"Certbot execution failed for domain {domain_to_certify}."
            ) from e
        except Exception as e_unexp:
            log_map_server(
                f"{symbols.get('error', '')} An unexpected error occurred during Certbot execution: {e_unexp}",
                "error",
                self.logger,
                self.app_settings,
                exc_info=True,
            )
            raise
