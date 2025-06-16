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


def ensure_python_apt_prerequisite(context: dict, **kwargs) -> None:
    """
    Checks for the python3-apt module which is required for AptManager,
    and installs it via apt if it's missing.

    This function interacts with the orchestrator context to manage state:
    - Reads 'apt_updated_this_run' to see if 'apt update' is needed.
    - Sets 'any_install_attempted' to True if an installation is performed.
    - Updates 'apt_updated_this_run' with the status after any installation.

    Args:
        context (dict): The orchestrator's shared context dictionary.
        **kwargs: Catches any other arguments the orchestrator might pass.

    Exits on critical failure to make the python3-apt module available.
    """
    logger.info(
        f"{BS_SYMBOLS['info']} Checking for python3-apt module (required for AptManager)..."
    )

    module_name = "apt"
    apt_pkg_name = "python3-apt"

    apt_updated_already = context.get("apt_updated_this_run", False)

    if not check_python_module(module_name, logger):
        logger.info(
            f"Python module '{module_name}' (apt: {apt_pkg_name}) marked for installation."
        )
        context["any_install_attempted"] = True

        apt_update_status_after_call = apt_install_packages(
            [apt_pkg_name], logger, apt_updated_already
        )

        context["apt_updated_this_run"] = apt_update_status_after_call

        if not check_python_module(module_name, logger):
            logger.error(
                f"{BS_SYMBOLS['error']} CRITICAL: Module '{module_name}' still not available after apt install attempt. Exiting."
            )
            sys.exit(1)
        logger.info(f"{BS_SYMBOLS['success']} python3-apt module ensured.")
    else:
        logger.info(
            f"{BS_SYMBOLS['success']} Python module '{module_name}' already available."
        )
