# setup/apache_installer.py
# -*- coding: utf-8 -*-
"""
Handles initial setup checks for Apache and mod_tile.
Actual package installation is expected to be done by a core prerequisite step.
"""
import logging
from typing import Optional

from common.command_utils import log_map_server, check_package_installed
from setup import config  # For SYMBOLS and package list reference

module_logger = logging.getLogger(__name__)


def ensure_apache_packages_installed(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Confirms that Apache and libapache2-mod-tile packages (expected to be
    installed by a core prerequisite step) are present.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['info']} Checking Apache package installation status...",
        "info",
        logger_to_use
    )

    # Packages expected to be in config.MAPPING_PACKAGES
    apache_packages = ["apache2", "libapache2-mod-tile"]
    all_found = True

    for pkg in apache_packages:
        if check_package_installed(pkg, current_logger=logger_to_use):
            log_map_server(
                f"{config.SYMBOLS['success']} Package '{pkg}' is installed.",
                "debug",
                logger_to_use
            )
        else:
            log_map_server(
                f"{config.SYMBOLS['error']} Apache related package '{pkg}' is NOT installed. "
                "This should have been handled by a core prerequisite installation step.",
                "error",
                logger_to_use
            )
            all_found = False

    if not all_found:
        raise EnvironmentError(
            "One or more essential Apache/mod_tile packages are missing. "
            "Please ensure core prerequisites installation ran successfully."
        )
    else:
        log_map_server(
            f"{config.SYMBOLS['success']} All required Apache/mod_tile packages confirmed as installed.",
            "success",
            logger_to_use
        )

# No other specific "installation" steps for Apache usually,
# as package manager handles service file creation etc.
# Directory creation for logs/sites is also typically handled by the package.