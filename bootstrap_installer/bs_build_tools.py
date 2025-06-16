# ot-osm-osrm-server/bs_installer/bs_build_tools.py
# -*- coding: utf-8 -*-

from .bs_utils import (  # Import new util
    BS_SYMBOLS,
    apt_install_packages,
    get_bs_logger,
    is_apt_package_installed_dpkg,
)

logger = get_bs_logger("BuildTools")


def ensure_build_tools(apt_updated_already: bool) -> tuple[bool, bool]:
    """
    Ensures 'build-essential' and 'python3-dev' are installed via apt,
    only if they are not already detected.
    Returns:
        Tuple (install_attempted_for_these_packages: bool,
               apt_updated_in_this_call_or_before: bool)
    """
    logger.info(
        f"{BS_SYMBOLS['info']} Checking for essential build tools (build-essential, python3-dev)..."
    )

    apt_packages_to_target = []
    install_attempted_this_group = False

    if not is_apt_package_installed_dpkg("build-essential", logger):
        logger.info(
            "'build-essential' (provides gcc, make, etc.) not found or not fully installed, marked for installation."
        )
        apt_packages_to_target.append("build-essential")
    else:
        logger.info(
            f"{BS_SYMBOLS['success']} 'build-essential' is already installed."
        )

    if not is_apt_package_installed_dpkg("python3-dev", logger):
        logger.info(
            "'python3-dev' not found or not fully installed, marked for installation."
        )
        apt_packages_to_target.append("python3-dev")
    else:
        logger.info(
            f"{BS_SYMBOLS['success']} 'python3-dev' is already installed."
        )

    apt_update_status_after_call = apt_updated_already
    if apt_packages_to_target:
        install_attempted_this_group = True
        apt_update_status_after_call = apt_install_packages(
            apt_packages_to_target, logger, apt_updated_already
        )

        if (
            "build-essential" in apt_packages_to_target
            and not is_apt_package_installed_dpkg("build-essential", logger)
        ):
            logger.warning(
                f"{BS_SYMBOLS['warning']} 'build-essential' might not have installed correctly or is still not detected by dpkg-query."
            )
        if (
            "python3-dev" in apt_packages_to_target
            and not is_apt_package_installed_dpkg("python3-dev", logger)
        ):
            logger.warning(
                f"{BS_SYMBOLS['warning']} 'python3-dev' might not have installed correctly or is still not detected by dpkg-query."
            )

        logger.info(
            f"{BS_SYMBOLS['success']} Build tools packages ('{', '.join(apt_packages_to_target)}') processed via apt."
        )
    else:
        logger.info(
            f"{BS_SYMBOLS['info']} No new build tool installations were required by apt."
        )

    return install_attempted_this_group, apt_update_status_after_call
