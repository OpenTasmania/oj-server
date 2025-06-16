# ot-osm-osrm-server/bs_installer/bs_build_tools.py
# -*- coding: utf-8 -*-

from .bs_utils import (  # Import new util
    BS_SYMBOLS,
    apt_install_packages,
    get_bs_logger,
    is_apt_package_installed_dpkg,
)

logger = get_bs_logger("BuildTools")


def ensure_build_tools(
    apt_updated_already: bool, context=None, app_settings=None, **kwargs
) -> tuple[bool, bool]:
    """
    Ensures 'build-essential' and 'python3-dev' are installed via apt,
    only if they are not already detected.

    Args:
        apt_updated_already: Whether apt has been updated already in this run.
        context: The shared orchestrator context.
        app_settings: The application settings.
        **kwargs: Additional keyword arguments.

    Returns:
        Tuple (install_attempted_for_these_packages: bool,
               apt_updated_in_this_call_or_before: bool)
    """
    logger.info(
        f"{BS_SYMBOLS['info']} Checking for essential build tools (build-essential, python3-dev)..."
    )

    apt_packages_to_target = []
    # Default to False, only set to True if apt_install_packages is actually called
    install_attempted_this_group = False

    # Check for build-essential
    if not is_apt_package_installed_dpkg("build-essential", logger):
        logger.info(
            "'build-essential' (provides gcc, make, etc.) not found or not fully installed, marked for installation."
        )
        apt_packages_to_target.append("build-essential")
    else:
        logger.info(
            f"{BS_SYMBOLS['success']} 'build-essential' is already installed."
        )

    # Check for python3-dev
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
    if (
        apt_packages_to_target
    ):  # Only if there's something to actually install
        install_attempted_this_group = (
            True  # An actual install attempt will be made
        )
        apt_update_status_after_call = apt_install_packages(
            apt_packages_to_target, logger, apt_updated_already
        )

        # Optional: Re-verify after install attempt if critical, though apt_install_packages would exit on failure
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
        # install_attempted_this_group remains False

    # Update context if provided
    if context is not None:
        context["apt_updated_this_run"] = apt_update_status_after_call
        if install_attempted_this_group:
            context["any_install_attempted"] = True

    return install_attempted_this_group, apt_update_status_after_call
