# ot-osm-osrm-server/bootstrap_installer/bs_pydantic.py
# -*- coding: utf-8 -*-
import sys

from bootstrap_installer.bs_utils import (
    BS_SYMBOLS,
    apt_install_packages,
    check_python_module,
    get_bs_logger,
)

logger = get_bs_logger("Pydantic")


def ensure_pydantic_prerequisites(context: dict, **kwargs) -> None:
    """
    Checks for pydantic and pydantic-settings modules, and installs them
    via apt if they are missing.

    This function interacts with the orchestrator context to manage state:
    - Reads 'apt_updated_this_run' to see if 'apt update' is needed.
    - Sets 'any_install_attempted' to True if an installation is performed.
    - Updates 'apt_updated_this_run' with the status after any installation.

    Args:
        context (dict): The orchestrator's shared context dictionary.
        **kwargs: Catches any other arguments the orchestrator might pass.
    """
    logger.info(f"{BS_SYMBOLS['info']} Checking for Pydantic modules...")
    modules_to_check = {
        "pydantic": "python3-pydantic",
        "pydantic_settings": "python3-pydantic-settings",
    }
    missing_packages = []

    for module, apt_pkg in modules_to_check.items():
        if not check_python_module(module, logger):
            logger.warning(
                f"Python module '{module}' not found. Will install via apt package '{apt_pkg}'."
            )
            missing_packages.append(apt_pkg)

    if not missing_packages:
        logger.info(
            f"{BS_SYMBOLS['success']} All Pydantic modules already available."
        )
        return

    context["any_install_attempted"] = True
    apt_updated_already = context.get("apt_updated_this_run", False)

    apt_update_status = apt_install_packages(
        missing_packages, logger, apt_updated_already
    )
    context["apt_updated_this_run"] = apt_update_status

    all_ok = True
    for module, apt_pkg in modules_to_check.items():
        if apt_pkg in missing_packages and not check_python_module(
            module, logger
        ):
            logger.error(
                f"{BS_SYMBOLS['error']} CRITICAL: Module '{module}' still not available after install attempt."
            )
            all_ok = False

    if all_ok:
        logger.info(
            f"{BS_SYMBOLS['success']} All required Pydantic modules are now available."
        )
    else:
        logger.critical(
            "Failed to install one or more Pydantic modules. The installer cannot continue."
        )
        sys.exit(1)
