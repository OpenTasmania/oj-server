# configure/ufw_configurator.py
# -*- coding: utf-8 -*-
"""
Handles configuration of UFW (Uncomplicated Firewall) rules and service activation.
"""
import logging
import subprocess  # For CalledProcessError
from typing import Optional

from common.command_utils import log_map_server, run_elevated_command
from common.network_utils import validate_cidr
from common.system_utils import systemd_reload  # For activate_ufw_service
# Import AppSettings for type hinting
from setup.config_models import AppSettings

# Import static constants from the (to be) slimmed-down config module
# from setup import config as static_config # Not strictly needed here if symbols come from app_settings

module_logger = logging.getLogger(__name__)


def apply_ufw_rules(
        app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Applies the defined UFW rules (default policies and allows).
    Uses app_settings for admin_group_ip and logging symbols.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    admin_group_ip = app_settings.admin_group_ip

    log_map_server(
        f"{symbols.get('step', '')} Applying UFW rules...",
        "info",
        logger_to_use,
    )

    if not validate_cidr(
            admin_group_ip,
            current_logger=logger_to_use,
            app_settings=app_settings,
    ):  # Pass app_settings
        msg = (
            f"UFW rule application aborted: Invalid ADMIN_GROUP_IP CIDR format "
            f"'{admin_group_ip}'."
        )
        log_map_server(
            f"{symbols.get('error', '')} {msg}", "error", logger_to_use
        )
        raise ValueError(msg)

    try:
        # Set default policies
        run_elevated_command(
            ["ufw", "default", "deny", "incoming"],
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["ufw", "default", "allow", "outgoing"],
            current_logger=logger_to_use,
        )

        # Allow traffic on loopback interface
        run_elevated_command(
            ["ufw", "allow", "in", "on", "lo"], current_logger=logger_to_use
        )
        run_elevated_command(
            ["ufw", "allow", "out", "on", "lo"], current_logger=logger_to_use
        )

        # Allow SSH and PostgreSQL from admin IP
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
                    "comment",  # Use configured PG port
                    "PostgreSQL from Admin",
                ],
                f"PostgreSQL from Admin on port {app_settings.pg.port}",
            ),
        ]
        for cmd_list, desc in admin_rules:
            log_map_server(
                f"{symbols.get('info', '')} Allowing {desc} via UFW...",
                "info",
                logger_to_use,
            )
            run_elevated_command(cmd_list, current_logger=logger_to_use)

        # Allow public HTTP and HTTPS
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
                logger_to_use,
            )
            run_elevated_command(cmd_list, current_logger=logger_to_use)

        log_map_server(
            f"{symbols.get('success', '')} UFW rules applied successfully.",
            "success",
            logger_to_use,
        )

    except subprocess.CalledProcessError as e:
        log_map_server(
            f"{symbols.get('error', '')} A UFW command failed during rule application. Command: '{e.cmd}', Error: {e.stderr or e.stdout}",
            "error",
            logger_to_use,
        )
        raise
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '')} An unexpected error occurred during UFW rule application: {e}",
            "error",
            logger_to_use,
        )
        raise


def activate_ufw_service(
        app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Ensures UFW package is installed (via check) and enables the UFW service if currently inactive.
    This function replaces the old enable_ufw_service from actions/ufw_setup_actions.py.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols

    log_map_server(
        f"{symbols.get('step', '')} Activating UFW service (enabling if inactive)...",
        "info",
        logger_to_use,
    )

    # The package check is now expected to be a separate step in main_installer.py
    # using installer.ufw_installer.ensure_ufw_package_installed(APP_CONFIG, logger).
    # However, a quick check here can be a safeguard, though it makes this function
    # do more than just "activate". For strict separation, this check should not be here.
    # For now, we'll assume the installer step has run. If not, UFW commands would fail anyway.
    # from installer.ufw_installer import ensure_ufw_package_installed # Example if we wanted to call it
    # ensure_ufw_package_installed(app_settings, logger_to_use) # This would be a call to the installer module

    try:
        # Check UFW status
        status_result = run_elevated_command(
            ["ufw", "status"],
            capture_output=True,
            check=False,  # Don't raise error if ufw status itself returns non-zero (e.g., if inactive)
            current_logger=logger_to_use,
        )

        # ufw status can return non-zero if inactive, so check output primarily
        if (
                status_result.stdout
                and "inactive" in status_result.stdout.lower()
        ):
            log_map_server(
                f"{symbols.get('warning', '')} UFW is inactive. Enabling now. "
                "Ensure your SSH access and other essential ports are allowed by rules.",
                "warning",
                logger_to_use,
            )
            # Reload systemd just in case, though UFW doesn't always need it for simple enable
            systemd_reload(
                app_settings=app_settings, current_logger=logger_to_use
            )  # Pass app_settings

            run_elevated_command(
                ["ufw", "enable"],
                cmd_input="y\n",  # Auto-confirm the enabling prompt
                check=True,  # This should succeed if UFW is installable and rules are okay
                current_logger=logger_to_use,
            )
            log_map_server(
                f"{symbols.get('success', '')} UFW enabled.",
                "success",
                logger_to_use,
            )
        elif (
                "inactive" not in status_result.stdout.lower()
                and status_result.returncode == 0
        ):
            log_map_server(
                f"{symbols.get('info', '')} UFW is already active.",
                "info",
                logger_to_use,
            )
        else:  # Some other status or error fetching status
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
                logger_to_use,
            )

        # Log final UFW status
        log_map_server(
            f"{symbols.get('info', '')} Final UFW status:",
            "info",
            logger_to_use,
        )
        run_elevated_command(
            ["ufw", "status", "verbose"], current_logger=logger_to_use
        )

    except subprocess.CalledProcessError as e:
        log_map_server(
            f"{symbols.get('error', '')} A UFW command failed during service activation. Command: '{e.cmd}', Error: {e.stderr or e.stdout}",
            "error",
            logger_to_use,
        )
        raise
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '')} An unexpected error occurred during UFW service activation: {e}",
            "error",
            logger_to_use,
        )
        raise
