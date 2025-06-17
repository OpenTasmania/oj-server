# modular_bootstrap/mb_apt.py
# -*- coding: utf-8 -*-
"""
Ensures the presence of the 'python3-apt' package, a critical prerequisite
for the application's package management capabilities.

This module contains the function 'ensure_python_apt_prerequisite', which is
designed to be executed as a task within the modular bootstrap orchestration process.
It checks if the necessary 'apt' Python module is available and, if not,
attempts to install the 'python3-apt' system package to satisfy the
dependency.
"""

import sys

from modular_bootstrap.mb_utils import (
    MB_SYMBOLS,
    apt_install_packages,
    check_python_module,
    get_mb_logger,
)

logger = get_mb_logger("Apt")


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
        f"{MB_SYMBOLS['info']} Checking for python3-apt module (required for AptManager)..."
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
                f"{MB_SYMBOLS['error']} CRITICAL: Module '{module_name}' still not available after apt install attempt. Exiting."
            )
            sys.exit(1)
        logger.info(f"{MB_SYMBOLS['success']} python3-apt module ensured.")
    else:
        logger.info(
            f"{MB_SYMBOLS['success']} Python module '{module_name}' already available."
        )
