# ot-osm-osrm-server/bs_installer/bs_pydantic.py
# -*- coding: utf-8 -*-
import sys

from bs_installer.bs_utils import (
    BS_SYMBOLS,
    apt_install_packages,
    check_python_module,
    get_bs_logger,
)

logger = get_bs_logger("Pydantic")


def ensure_pydantic_prerequisites(
    apt_updated_already: bool,
) -> tuple[bool, bool]:
    """
    Checks for pydantic and pydantic_settings Python modules.
    Attempts to install them via apt if missing.

    Returns:
        Tuple (install_attempted_for_this_group: bool,
               apt_updated_in_this_call_or_before: bool)
    Exits on critical failure to make modules available.
    """
    logger.info(
        f"{BS_SYMBOLS['info']} Checking for Pydantic and Pydantic-Settings modules..."
    )

    modules_to_ensure = {
        "pydantic": "python3-pydantic",
        "pydantic_settings": "python3-pydantic-settings",
    }
    missing_apt_packages_for_modules = []
    install_attempted_this_group = False

    for module_name, apt_pkg_name in modules_to_ensure.items():
        if not check_python_module(module_name, logger):
            logger.info(
                f"Python module '{module_name}' (apt: {apt_pkg_name}) marked for installation."
            )
            missing_apt_packages_for_modules.append(apt_pkg_name)
            install_attempted_this_group = True
        else:
            logger.info(
                f"{BS_SYMBOLS['success']} Python module '{module_name}' already available."
            )

    apt_update_status_after_call = apt_updated_already
    if missing_apt_packages_for_modules:
        apt_update_status_after_call = apt_install_packages(
            missing_apt_packages_for_modules, logger, apt_updated_already
        )
        # Re-verify crucial modules after install attempt
        for module_name in modules_to_ensure.keys():
            if not check_python_module(module_name, logger):  # Check again
                logger.error(
                    f"{BS_SYMBOLS['error']} CRITICAL: Module '{module_name}' still not available after apt install attempt. Exiting."
                )
                sys.exit(1)
        logger.info(
            f"{BS_SYMBOLS['success']} Pydantic-related modules ensured."
        )

    return install_attempted_this_group, apt_update_status_after_call
