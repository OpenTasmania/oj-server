"""
UFW configurator module.

This module provides a self-contained configurator for UFW (Uncomplicated Firewall).
"""

import logging
import subprocess
from typing import Optional

from common.command_utils import log_map_server, run_elevated_command
from common.network_utils import validate_cidr
from common.system_utils import systemd_reload
from installer.base_configurator import BaseConfigurator
from installer.config_models import AppSettings
from installer.registry import ComponentRegistry


@ComponentRegistry.register(
    name="ufw",
    metadata={
        "dependencies": [],  # UFW is a base component with no dependencies
        "description": "UFW (Uncomplicated Firewall) configuration",
    },
)
class UFWConfigurator(BaseConfigurator):
    """
    Configurator for UFW (Uncomplicated Firewall).

    This configurator ensures that UFW is properly configured with the necessary
    firewall rules and service settings to secure the server.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the UFW configurator.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)

    def configure(self) -> bool:
        """
        Configure UFW with the necessary settings.

        This method performs the following configuration tasks:
        1. Applies UFW rules
        2. Activates the UFW service

        Returns:
            True if the configuration was successful, False otherwise.
        """
        try:
            self._apply_ufw_rules()
            self._activate_ufw_service()
            return True
        except Exception as e:
            self.logger.error(f"Error configuring UFW: {str(e)}")
            return False

    def unconfigure(self) -> bool:
        """
        Unconfigure UFW settings.

        This method disables the UFW service. Note that this is a potentially
        dangerous operation as it leaves the server without firewall protection.

        Returns:
            True if the unconfiguration was successful, False otherwise.
        """
        try:
            symbols = self.app_settings.symbols

            log_map_server(
                f"{symbols.get('warning', '')} Disabling UFW. This will leave the server without firewall protection!",
                "warning",
                self.logger,
                self.app_settings,
            )

            run_elevated_command(
                ["ufw", "disable"],
                self.app_settings,
                current_logger=self.logger,
            )

            log_map_server(
                f"{symbols.get('success', '')} UFW has been disabled",
                "success",
                self.logger,
                self.app_settings,
            )

            return True
        except Exception as e:
            self.logger.error(f"Error unconfiguring UFW: {str(e)}")
            return False

    def is_configured(self) -> bool:
        """
        Check if UFW is configured.

        This method checks if the UFW service is active and properly configured.

        Returns:
            True if UFW is configured, False otherwise.
        """
        try:
            # Check if UFW is active
            result = run_elevated_command(
                ["ufw", "status"],
                self.app_settings,
                capture_output=True,
                check=False,
                current_logger=self.logger,
            )

            if result.returncode != 0:
                return False

            if result.stdout and "Status: active" in result.stdout:
                return True

            return False
        except Exception as e:
            self.logger.error(
                f"Error checking if UFW is configured: {str(e)}"
            )
            return False

    def _apply_ufw_rules(self) -> None:
        """
        Apply UFW rules.

        This method configures default policies for incoming and outgoing traffic,
        and sets up specific allow rules for administrative access and public services.

        Raises:
            ValueError: If the admin_group_ip is not in a valid CIDR format.
            subprocess.CalledProcessError: If any UFW command fails during execution.
            Exception: For any other unexpected errors during rule application.
        """
        symbols = self.app_settings.symbols
        admin_group_ip = self.app_settings.admin_group_ip

        log_map_server(
            f"{symbols.get('step', '')} Applying UFW rules...",
            "info",
            self.logger,
            self.app_settings,
        )

        if not validate_cidr(
            admin_group_ip,
            self.app_settings,
            current_logger=self.logger,
        ):
            msg = (
                f"UFW rule application aborted: Invalid ADMIN_GROUP_IP CIDR format "
                f"'{admin_group_ip}'."
            )
            log_map_server(
                f"{symbols.get('error', '')} {msg}",
                "error",
                self.logger,
                self.app_settings,
            )
            raise ValueError(msg)

        try:
            run_elevated_command(
                ["ufw", "default", "deny", "incoming"],
                self.app_settings,
                current_logger=self.logger,
            )
            run_elevated_command(
                ["ufw", "default", "allow", "outgoing"],
                self.app_settings,
                current_logger=self.logger,
            )
            run_elevated_command(
                ["ufw", "allow", "in", "on", "lo"],
                self.app_settings,
                current_logger=self.logger,
            )
            run_elevated_command(
                ["ufw", "allow", "out", "on", "lo"],
                self.app_settings,
                current_logger=self.logger,
            )

            admin_rules = [
                (
                    [
                        "ufw",
                        "allow",
                        "from",
                        admin_group_ip,
                        "to",
                        "any",
                        "port",
                        "22",
                        "proto",
                        "tcp",
                        "comment",
                        "SSH from Admin",
                    ],
                    "SSH from Admin",
                ),
                (
                    [
                        "ufw",
                        "allow",
                        "from",
                        admin_group_ip,
                        "to",
                        "any",
                        "port",
                        str(self.app_settings.pg.port),
                        "proto",
                        "tcp",
                        "comment",
                        "PostgreSQL from Admin",
                    ],
                    f"PostgreSQL from Admin on port {self.app_settings.pg.port}",
                ),
            ]
            for cmd_list, desc in admin_rules:
                log_map_server(
                    f"{symbols.get('info', '')} Allowing {desc} via UFW...",
                    "info",
                    self.logger,
                    self.app_settings,
                )
                run_elevated_command(
                    cmd_list, self.app_settings, current_logger=self.logger
                )

            public_rules = [
                (
                    ["ufw", "allow", "http", "comment", "Nginx HTTP"],
                    "HTTP (port 80)",
                ),
                (
                    ["ufw", "allow", "https", "comment", "Nginx HTTPS"],
                    "HTTPS (port 443)",
                ),
            ]
            for cmd_list, desc in public_rules:
                log_map_server(
                    f"{symbols.get('info', '')} Allowing {desc} via UFW...",
                    "info",
                    self.logger,
                    self.app_settings,
                )
                run_elevated_command(
                    cmd_list, self.app_settings, current_logger=self.logger
                )

            log_map_server(
                f"{symbols.get('success', '')} UFW rules applied successfully.",
                "success",
                self.logger,
                self.app_settings,
            )

        except subprocess.CalledProcessError as e:
            log_map_server(
                f"{symbols.get('error', '')} A UFW command failed during rule application. Command: '{e.cmd}', Error: {e.stderr or e.stdout}",
                "error",
                self.logger,
                self.app_settings,
            )
            raise
        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '')} An unexpected error occurred during UFW rule application: {e}",
                "error",
                self.logger,
                self.app_settings,
            )
            raise

    def _activate_ufw_service(self) -> None:
        """
        Activate the UFW service.

        This method checks the current status of the UFW service and enables it if
        it is inactive. It also displays the final status of the firewall with verbose
        output.

        Raises:
            subprocess.CalledProcessError: If any UFW command fails during execution.
            Exception: For any other unexpected errors during service activation.
        """
        symbols = self.app_settings.symbols

        log_map_server(
            f"{symbols.get('step', '')} Activating UFW service (enabling if inactive)...",
            "info",
            self.logger,
            self.app_settings,
        )

        try:
            status_result = run_elevated_command(
                ["ufw", "status"],
                self.app_settings,
                capture_output=True,
                check=False,
                current_logger=self.logger,
            )

            if (
                status_result.stdout
                and "inactive" in status_result.stdout.lower()
            ):
                log_map_server(
                    f"{symbols.get('warning', '')} UFW is inactive. Enabling now. "
                    "Ensure your SSH access and other essential ports are allowed by rules.",
                    "warning",
                    self.logger,
                    self.app_settings,
                )
                systemd_reload(
                    app_settings=self.app_settings, current_logger=self.logger
                )

                run_elevated_command(
                    ["ufw", "enable"],
                    self.app_settings,
                    cmd_input="y\n",
                    check=True,
                    current_logger=self.logger,
                )
                log_map_server(
                    f"{symbols.get('success', '')} UFW enabled.",
                    "success",
                    self.logger,
                    self.app_settings,
                )
            elif (
                "inactive" not in status_result.stdout.lower()
                and status_result.returncode == 0
            ):
                log_map_server(
                    f"{symbols.get('info', '')} UFW is already active.",
                    "info",
                    self.logger,
                    self.app_settings,
                )
            else:
                status_output = (
                    status_result.stdout.strip()
                    if status_result.stdout
                    else "N/A"
                )
                stderr_output = (
                    status_result.stderr.strip()
                    if status_result.stderr
                    else "N/A"
                )
                log_map_server(
                    f"{symbols.get('info', '')} UFW status not 'inactive'. Current status command output: STDOUT='{status_output}', STDERR='{stderr_output}', RC={status_result.returncode}. Assuming active or managed.",
                    "info",
                    self.logger,
                    self.app_settings,
                )

            log_map_server(
                f"{symbols.get('info', '')} Final UFW status:",
                "info",
                self.logger,
                self.app_settings,
            )
            run_elevated_command(
                ["ufw", "status", "verbose"],
                self.app_settings,
                current_logger=self.logger,
            )

        except subprocess.CalledProcessError as e:
            log_map_server(
                f"{symbols.get('error', '')} A UFW command failed during service activation. Command: '{e.cmd}', Error: {e.stderr or e.stdout}",
                "error",
                self.logger,
                self.app_settings,
            )
            raise
        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '')} An unexpected error occurred during UFW service activation: {e}",
                "error",
                self.logger,
                self.app_settings,
            )
            raise
