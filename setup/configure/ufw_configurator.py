# configure/ufw_configurator.py
# -*- coding: utf-8 -*-
"""
Handles configuration of UFW (Uncomplicated Firewall) rules and service activation.
"""

import logging
import subprocess
from typing import Optional

from common.command_utils import log_map_server, run_elevated_command
from common.network_utils import validate_cidr
from common.system_utils import systemd_reload
from setup.config_models import AppSettings

module_logger = logging.getLogger(__name__)


def apply_ufw_rules(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Applies the defined UFW (Uncomplicated Firewall) rules to secure the server.

    This function configures default policies for incoming and outgoing traffic,
    and sets up specific allow rules for administrative access and public services.
    It validates the admin group IP address format before applying rules, and logs
    the progress and results of each operation.

    Parameters:
        app_settings (AppSettings): Application settings containing configuration
            details such as admin_group_ip, PostgreSQL port, and logging symbols.
        current_logger (Optional[logging.Logger]): Logger instance to use for logging.
            If not provided, a module-level logger is used.

    Raises:
        ValueError: If the admin_group_ip is not in a valid CIDR format.
        subprocess.CalledProcessError: If any UFW command fails during execution.
        Exception: For any other unexpected errors during rule application.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    admin_group_ip = app_settings.admin_group_ip

    log_map_server(
        f"{symbols.get('step', '➡️')} Applying UFW rules...",
        "info",
        logger_to_use,
        app_settings,
    )

    if not validate_cidr(
        admin_group_ip,
        app_settings,
        current_logger=logger_to_use,
    ):
        msg = (
            f"UFW rule application aborted: Invalid ADMIN_GROUP_IP CIDR format "
            f"'{admin_group_ip}'."
        )
        log_map_server(
            f"{symbols.get('error', '❌')} {msg}",
            "error",
            logger_to_use,
            app_settings,
        )
        raise ValueError(msg)

    try:
        run_elevated_command(
            ["ufw", "default", "deny", "incoming"],
            app_settings,  # Pass app_settings
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["ufw", "default", "allow", "outgoing"],
            app_settings,  # Pass app_settings
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["ufw", "allow", "in", "on", "lo"],
            app_settings,
            current_logger=logger_to_use,  # Pass app_settings
        )
        run_elevated_command(
            ["ufw", "allow", "out", "on", "lo"],
            app_settings,
            current_logger=logger_to_use,  # Pass app_settings
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
                    str(app_settings.pg.port),
                    "proto",
                    "tcp",
                    "comment",
                    "PostgreSQL from Admin",
                ],
                f"PostgreSQL from Admin on port {app_settings.pg.port}",
            ),
        ]
        for cmd_list, desc in admin_rules:
            log_map_server(
                f"{symbols.get('info', 'ℹ️')} Allowing {desc} via UFW...",  # Corrected: Added emoji
                "info",
                logger_to_use,
                app_settings,  # Pass app_settings
            )
            run_elevated_command(
                cmd_list, app_settings, current_logger=logger_to_use
            )  # Pass app_settings

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
                f"{symbols.get('info', 'ℹ️')} Allowing {desc} via UFW...",  # Corrected: Added emoji
                "info",
                logger_to_use,
                app_settings,  # Pass app_settings
            )
            run_elevated_command(
                cmd_list, app_settings, current_logger=logger_to_use
            )  # Pass app_settings

        log_map_server(
            f"{symbols.get('success', '✅')} UFW rules applied successfully.",  # Corrected: Added emoji
            "success",
            logger_to_use,
            app_settings,  # Pass app_settings
        )

    except subprocess.CalledProcessError as e:
        log_map_server(
            f"{symbols.get('error', '❌')} A UFW command failed during rule application. Command: '{e.cmd}', Error: {e.stderr or e.stdout}",
            # Corrected: Added emoji
            "error",
            logger_to_use,
            app_settings,  # Pass app_settings
        )
        raise
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} An unexpected error occurred during UFW rule application: {e}",
            # Corrected: Added emoji
            "error",
            logger_to_use,
            app_settings,  # Pass app_settings
        )
        raise


def activate_ufw_service(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Activates the UFW (Uncomplicated Firewall) service if it is not already active.

    This function checks the current status of the UFW service and enables it if
    it is inactive. It also displays the final status of the firewall with verbose
    output. The function logs each step of the process and handles potential errors.

    Parameters:
        app_settings (AppSettings): Application settings containing configuration
            details and logging symbols.
        current_logger (Optional[logging.Logger]): Logger instance to use for logging.
            If not provided, a module-level logger is used.

    Raises:
        subprocess.CalledProcessError: If any UFW command fails during execution.
        Exception: For any other unexpected errors during service activation.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols

    log_map_server(
        f"{symbols.get('step', '➡️')} Activating UFW service (enabling if inactive)...",
        "info",
        logger_to_use,
        app_settings,
    )

    try:
        status_result = run_elevated_command(
            ["ufw", "status"],
            app_settings,  # Pass app_settings
            capture_output=True,
            check=False,
            current_logger=logger_to_use,
        )

        if (
            status_result.stdout
            and "inactive" in status_result.stdout.lower()
        ):
            log_map_server(
                f"{symbols.get('warning', '!')} UFW is inactive. Enabling now. "  # Corrected: Added emoji
                "Ensure your SSH access and other essential ports are allowed by rules.",
                "warning",
                logger_to_use,
                app_settings,  # Pass app_settings
            )
            systemd_reload(
                app_settings=app_settings, current_logger=logger_to_use
            )  # Already correct

            run_elevated_command(
                ["ufw", "enable"],
                app_settings,  # Pass app_settings
                cmd_input="y\n",
                check=True,
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{symbols.get('success', '✅')} UFW enabled.",  # Corrected: Added emoji
                "success",
                logger_to_use,
                app_settings,  # Pass app_settings
            )
        elif (
            "inactive" not in status_result.stdout.lower()
            and status_result.returncode == 0
        ):
            log_map_server(
                f"{symbols.get('info', 'ℹ️')} UFW is already active.",  # Corrected: Added emoji
                "info",
                logger_to_use,
                app_settings,  # Pass app_settings
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
                f"{symbols.get('info', 'ℹ️')} UFW status not 'inactive'. Current status command output: STDOUT='{status_output}', STDERR='{stderr_output}', RC={status_result.returncode}. Assuming active or managed.",
                # Corrected: Added emoji
                "info",
                logger_to_use,
                app_settings,  # Pass app_settings
            )

        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Final UFW status:",  # Corrected: Added emoji
            "info",
            logger_to_use,
            app_settings,  # Pass app_settings
        )
        run_elevated_command(
            ["ufw", "status", "verbose"],
            app_settings,
            current_logger=logger_to_use,  # Pass app_settings
        )

    except subprocess.CalledProcessError as e:
        log_map_server(
            f"{symbols.get('error', '❌')} A UFW command failed during service activation. Command: '{e.cmd}', Error: {e.stderr or e.stdout}",
            # Corrected: Added emoji
            "error",
            logger_to_use,
            app_settings,  # Pass app_settings
        )
        raise
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} An unexpected error occurred during UFW service activation: {e}",
            # Corrected: Added emoji
            "error",
            logger_to_use,
            app_settings,  # Pass app_settings
        )
        raise
