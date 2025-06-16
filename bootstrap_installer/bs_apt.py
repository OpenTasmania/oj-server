# ot-osm-osrm-server/bs_installer/bs_apt.py
# -*- coding: utf-8 -*-
import sys

from bootstrap_installer.bs_utils import (
    BS_SYMBOLS,
    apt_install_packages,
    check_python_module,
    get_bs_logger,
)

logger = get_bs_logger("Apt")


def ensure_python_apt_prerequisite(
    apt_updated_already: bool, context=None, app_settings=None, **kwargs
) -> tuple[bool, bool]:
    """
    Checks for the python3-apt module which is required for AptManager.
    Attempts to install it via apt if missing.

    Args:
        apt_updated_already: Whether apt has been updated already in this run.
        context: The shared orchestrator context.
        app_settings: The application settings.
        **kwargs: Additional keyword arguments.

    Returns:
        Tuple (install_attempted_for_this_group: bool,
               apt_updated_in_this_call_or_before: bool)
    Exits on critical failure to make module available.
    """
    logger.info(
        f"{BS_SYMBOLS['info']} Checking for python3-apt module (required for AptManager)..."
    )

    module_name = "apt"
    apt_pkg_name = "python3-apt"
    install_attempted = False

    if not check_python_module(module_name, logger):
        logger.info(
            f"Python module '{module_name}' (apt: {apt_pkg_name}) marked for installation."
        )
        install_attempted = True

        # Install python3-apt using apt directly
        apt_update_status_after_call = apt_install_packages(
            [apt_pkg_name], logger, apt_updated_already
        )

        # Re-verify the module after install attempt
        if not check_python_module(module_name, logger):
            logger.error(
                f"{BS_SYMBOLS['error']} CRITICAL: Module '{module_name}' still not available after apt install attempt. Exiting."
            )
            sys.exit(1)
        logger.info(f"{BS_SYMBOLS['success']} python3-apt module ensured.")
        # Update context if provided
        if context is not None:
            context["apt_updated_this_run"] = apt_update_status_after_call
            if install_attempted:
                context["any_install_attempted"] = True
        return install_attempted, apt_update_status_after_call
    else:
        logger.info(
            f"{BS_SYMBOLS['success']} Python module '{module_name}' already available."
        )
        # Update context if provided
        if context is not None:
            context["apt_updated_this_run"] = apt_updated_already
        return install_attempted, apt_updated_already
