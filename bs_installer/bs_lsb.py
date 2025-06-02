# ot-osm-osrm-server/bs_installer/bs_lsb.py
# -*- coding: utf-8 -*-
from bs_installer.bs_utils import (
    BS_SYMBOLS,
    apt_install_packages,
    bootstrap_cmd_exists,
    get_bs_logger,
)

logger = get_bs_logger("LSB")


def ensure_lsb_release(apt_updated_already: bool) -> tuple[bool, bool]:
    """
    Checks for the lsb_release command and installs the 'lsb-release' package if missing.
    Returns:
        Tuple (install_attempted_for_this_package: bool,
               apt_updated_in_this_call_or_before: bool)
    """
    logger.info(f"{BS_SYMBOLS['info']} Checking for 'lsb-release' command...")
    apt_package_name = "lsb-release"
    command_name = "lsb_release"  # The command provided by the package
    install_attempted_this_pkg = False

    apt_update_status_after_call = apt_updated_already
    if not bootstrap_cmd_exists(command_name):
        logger.info(
            f"Command '{command_name}' (from package '{apt_package_name}') not found, marked for installation."
        )
        apt_update_status_after_call = apt_install_packages(
            [apt_package_name], logger, apt_updated_already
        )
        install_attempted_this_pkg = True
        if not bootstrap_cmd_exists(command_name):  # Re-check
            logger.warning(
                f"{BS_SYMBOLS['warning']} Command '{command_name}' still not available after attempting to install '{apt_package_name}'. Main installer might use fallbacks."
            )
            # Not exiting, as the main installer (install.py) has fallbacks for uv installation.
        else:
            logger.info(
                f"{BS_SYMBOLS['success']} Command '{command_name}' (package '{apt_package_name}') now available."
            )
    else:
        logger.info(
            f"{BS_SYMBOLS['success']} Command '{command_name}' (package '{apt_package_name}') already available."
        )

    return install_attempted_this_pkg, apt_update_status_after_call
