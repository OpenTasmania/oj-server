# modular_bootstrap/mb_build_tools.py
# -*- coding: utf-8 -*-
"""
Ensures that essential build tools are installed on the system.

This module provides the 'ensure_build_tools' function, which verifies the
presence of 'build-essential' (providing gcc, make, etc.) and 'python3-dev'
(providing Python header files). These packages are fundamental for compiling
Python C-extensions and other native code required by the application's
dependencies. This check is intended to be run as part of the modular bootstrap
orchestration sequence.
"""

import sys

from bootstrap.mb_utils import (
    MB_SYMBOLS,
    apt_install_packages,
    get_mb_logger,
    modular_bootstrap_cmd_exists,
)

logger = get_mb_logger("BuildTools")


def ensure_build_tools(context: dict, **kwargs) -> None:
    """
    Ensures 'build-essential' and 'python3-dev' are installed for compiling
    Python extensions and other software.

    This function interacts with the orchestrator context to manage state:
    - Reads 'apt_updated_this_run' to see if 'apt update' is needed.
    - Sets 'any_install_attempted' to True if an installation is performed.
    - Updates 'apt_updated_this_run' with the status after any installation.

    Args:
        context (dict): The orchestrator's shared context dictionary.
        **kwargs: Catches any other arguments the orchestrator might pass.
    """
    logger.info(
        f"{MB_SYMBOLS['info']} Checking for build tools ('build-essential', 'python3-dev')..."
    )

    build_essential_present = modular_bootstrap_cmd_exists(
        "gcc"
    ) and modular_bootstrap_cmd_exists("make")

    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    python_dev_present = modular_bootstrap_cmd_exists(
        f"python{py_ver}-config"
    )

    packages_to_install = []
    if not build_essential_present:
        packages_to_install.append("build-essential")
    if not python_dev_present:
        packages_to_install.append("python3-dev")

    if not packages_to_install:
        logger.info(
            f"{MB_SYMBOLS['success']} Build tools appear to be installed."
        )
        return

    if "build-essential" in packages_to_install:
        logger.warning(
            "'gcc' or 'make' not found. Will install 'build-essential'."
        )
    if "python3-dev" in packages_to_install:
        logger.warning(
            f"Python dev headers (e.g., 'python{py_ver}-config') not found. Will install 'python3-dev'."
        )

    logger.info(f"Installing build tools: {', '.join(packages_to_install)}")
    context["any_install_attempted"] = True
    apt_updated_already = context.get("apt_updated_this_run", False)

    apt_update_status = apt_install_packages(
        packages_to_install, logger, apt_updated_already
    )
    context["apt_updated_this_run"] = apt_update_status

    final_gcc_ok = modular_bootstrap_cmd_exists("gcc")
    final_py_dev_ok = modular_bootstrap_cmd_exists(f"python{py_ver}-config")

    if not final_gcc_ok or not final_py_dev_ok:
        logger.critical(
            f"{MB_SYMBOLS['error']} CRITICAL: Failed to verify build tools after installation. Check apt logs. The installer cannot continue."
        )
        sys.exit(1)
    else:
        logger.info(f"{MB_SYMBOLS['success']} Build tools are now available.")
