# modular_bootstrap/mb_util_linux.py
# -*- coding: utf-8 -*-
"""
Ensures the 'util-linux' package is installed on the system.

The 'util-linux' package provides essential utilities like 'dmesg' that are
used by the application. This module's 'ensure_util_linux' function checks for
the presence of 'dmesg' and installs the 'util-linux' package if it is missing.
"""

from modular_bootstrap.mb_utils import (
    MB_SYMBOLS,
    apt_install_packages,
    get_mb_logger,
    modular_bootstrap_cmd_exists,
)

logger = get_mb_logger("UtilLinux")


def ensure_util_linux(context: dict, **kwargs) -> None:
    """
    Ensures 'util-linux' is installed, which provides 'dmesg'.

    This function interacts with the orchestrator context to manage state:
    - Reads 'apt_updated_this_run' to see if 'apt update' is needed.
    - Sets 'any_install_attempted' to True if an installation is performed.
    - Updates 'apt_updated_this_run' with the status after any installation.

    Args:
        context (dict): The orchestrator's shared context dictionary.
        **kwargs: Catches any other arguments the orchestrator might pass.
    """
    logger.info(
        f"{MB_SYMBOLS['info']} Checking for 'dmesg' (from 'util-linux')..."
    )
    if modular_bootstrap_cmd_exists("dmesg"):
        logger.info(
            f"{MB_SYMBOLS['success']} 'dmesg' command already available."
        )
        return

    logger.warning("'dmesg' not found. Ensuring 'util-linux' is installed...")
    context["any_install_attempted"] = True
    apt_updated_already = context.get("apt_updated_this_run", False)

    apt_update_status = apt_install_packages(
        ["util-linux"], logger, apt_updated_already
    )
    context["apt_updated_this_run"] = apt_update_status

    if not modular_bootstrap_cmd_exists("dmesg"):
        logger.warning(
            f"{MB_SYMBOLS['warning']} Could not confirm 'dmesg' after install. This may be okay on some minimal systems."
        )
    else:
        logger.info(f"{MB_SYMBOLS['success']} 'dmesg' is now available.")
