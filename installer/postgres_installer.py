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
    config,  # For SYMBOLS and package list reference (config.POSTGRES_PACKAGES)
)

module_logger = logging.getLogger(__name__)


def ensure_postgres_packages_are_installed(
        current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Confirms that PostgreSQL packages (expected to be installed by a core
    prerequisite step) are present.
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
        # Depending on desired behavior, this could be an error or just a pass.
        # For now, we assume if it's empty, it's intentional.
        return

    for pkg in config.POSTGRES_PACKAGES:
        if check_package_installed(pkg, current_logger=logger_to_use):
            log_map_server(
                f"{config.SYMBOLS['success']} Package '{pkg}' is installed.",
                "debug",  # More verbose, success is for the overall step
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

# If there were other setup-specific actions before configuration, they'd go here.
# For PostgreSQL, most actions are configuration after the package install.
