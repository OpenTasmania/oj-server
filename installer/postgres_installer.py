# setup/postgres_installer.py
# -*- coding: utf-8 -*-
"""
Handles initial setup checks for PostgreSQL.
Actual package installation is expected to be done by a core prerequisite step.
"""

import logging
from typing import Optional

from common.command_utils import check_package_installed, log_map_server
from setup import (
    config,
)
from setup.config_models import AppSettings

module_logger = logging.getLogger(__name__)


def ensure_postgres_packages_are_installed(
    app_settings: AppSettings,
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Ensures that all required PostgreSQL packages listed in the configuration are installed.
    This function checks the installation status of required PostgreSQL packages specified
    in the configuration file. It uses a logger to report the status of each package, either
    as installed or missing. If any package is missing, an error is raised. If no packages
    are listed in the configuration, a warning is logged and the function exits without
    performing further actions.

    Args:
        app_settings: The application settings object containing the necessary configuration
            for package installation checks.
        current_logger: An optional logger instance to be used for logging messages. If not
            provided, the module-level logger is used instead.

    Raises:
        EnvironmentError: Raised if one or more required PostgreSQL packages are not installed.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['info']} Checking PostgreSQL package installation status...",
        "info",
        logger_to_use,
    )

    all_found = True
    if not config.POSTGRES_PACKAGES:
        log_map_server(
            f"{config.SYMBOLS['warning']} No PostgreSQL packages listed in config.POSTGRES_PACKAGES. Skipping check.",
            "warning",
            logger_to_use,
        )
        # TODO: Decide if to error or pass
        # Depending on desired behavior, this could be an error or just a pass.
        # For now, we assume if it's empty, it's intentional.
        return

    for pkg in config.POSTGRES_PACKAGES:
        if check_package_installed(
            pkg, app_settings=app_settings, current_logger=logger_to_use
        ):  # Pass app_settings
            log_map_server(
                f"{config.SYMBOLS['success']} Package '{pkg}' is installed.",
                "debug",
                logger_to_use,
            )
        else:
            log_map_server(
                f"{config.SYMBOLS['error']} PostgreSQL package '{pkg}' is NOT installed. "
                "This should have been handled by a core prerequisite installation step.",
                "error",
                logger_to_use,
            )
            all_found = False

    if not all_found:
        raise EnvironmentError(
            "One or more essential PostgreSQL packages are missing. "
            "Please ensure core prerequisites installation ran successfully."
        )
    else:
        log_map_server(
            f"{config.SYMBOLS['success']} All required PostgreSQL packages confirmed as installed.",
            "success",
            logger_to_use,
        )
