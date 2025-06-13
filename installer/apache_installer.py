# installer/apache_installer.py
# -*- coding: utf-8 -*-
"""
Handles initial setup checks for Apache and mod_tile.
Actual package installation is expected to be done by a core prerequisite step.
"""

import logging
from typing import Optional

from common.command_utils import check_package_installed, log_map_server
from setup.config_models import AppSettings

module_logger = logging.getLogger(__name__)


def ensure_apache_packages_installed(
    app_settings: AppSettings, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Ensures that required Apache and mod_tile related packages are installed. This function checks for the presence of
    certain Apache-related packages, logs their installation status, and raises an error if any essential package is missing.

    Parameters
    ----------
    app_settings : AppSettings
        The application settings object containing configuration and environment details used for the package verification.

    current_logger : Optional[logging.Logger], default=None
        A logger instance to log messages during the execution. If not provided,
        a module-level logger is used.

    Raises
    ------
    EnvironmentError
        Raised when one or more required Apache/mod_tile packages are missing, indicating an incomplete prerequisite installation.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols

    log_map_server(
        f"{symbols.get('info', 'ℹ️')} Checking Apache package installation status...",
        "info",
        logger_to_use,
        app_settings,
    )

    apache_packages_to_check = ["apache2", "libapache2-mod-tile"]
    all_found = True

    # TODO: Do better
    # Check if these specific packages are listed in the broader MAPPING_PACKAGES from static_config
    # This is more of a consistency check on how packages are defined.
    # For now, directly use the list above.
    # If you want to ensure they are part of a central list:
    # for pkg_name in apache_packages_to_check:
    # if pkg_name not in static_config.MAPPING_PACKAGES:
    # logger_to_use.warning(f"Package {pkg_name} for Apache check is not in static_config.MAPPING_PACKAGES list.")

    for pkg in apache_packages_to_check:
        if check_package_installed(
            pkg, app_settings=app_settings, current_logger=logger_to_use
        ):
            log_map_server(
                f"{symbols.get('success', '✅')} Package '{pkg}' is installed.",
                "debug",
                logger_to_use,
                app_settings,
            )
        else:
            log_map_server(
                f"{symbols.get('error', '❌')} Apache related package '{pkg}' is NOT installed. "
                "This should have been handled by a core prerequisite installation step.",
                "error",
                logger_to_use,
                app_settings,
            )
            all_found = False

    if not all_found:
        raise EnvironmentError(
            "One or more essential Apache/mod_tile packages are missing. "
            "Please ensure core prerequisites installation (which installs from static_config.MAPPING_PACKAGES) ran successfully."
        )
    else:
        log_map_server(
            f"{symbols.get('success', '✅')} All required Apache/mod_tile packages confirmed as installed.",
            "success",
            logger_to_use,
            app_settings,
        )
