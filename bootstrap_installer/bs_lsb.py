# bootstrap_installer/bs_lsb.py
# -*- coding: utf-8 -*-
"""
Ensures the 'lsb_release' command is available on the system.

The 'lsb_release' utility is used to reliably determine Linux Standard Base
(LSB) information about the current distribution, such as the codename (e.g.,
'bookworm'). This module's 'ensure_lsb_release' function checks for the
command's existence and installs the 'lsb-release' package if it is missing,
a common step in the bootstrap process.
"""

import sys

from bootstrap_installer.bs_utils import (
    BS_SYMBOLS,
    apt_install_packages,
    bootstrap_cmd_exists,
    get_bs_logger,
)

logger = get_bs_logger("LsbRelease")


def ensure_lsb_release(context: dict, **kwargs) -> None:
    """
    Checks for the lsb_release command and installs the 'lsb-release'
    package if it is missing.

    This function interacts with the orchestrator context to manage state:
    - Reads 'apt_updated_this_run' to see if 'apt update' is needed.
    - Sets 'any_install_attempted' to True if an installation is performed.
    - Updates 'apt_updated_this_run' with the status after any installation.

    Args:
        context (dict): The orchestrator's shared context dictionary.
        **kwargs: Catches any other arguments the orchestrator might pass.
    """
    logger.info(f"{BS_SYMBOLS['info']} Checking for 'lsb_release' command...")
    if bootstrap_cmd_exists("lsb_release"):
        logger.info(
            f"{BS_SYMBOLS['success']} 'lsb_release' command already available."
        )
        return

    logger.warning(
        "'lsb_release' not found. Installing 'lsb-release' package..."
    )
    context["any_install_attempted"] = True
    apt_updated_already = context.get("apt_updated_this_run", False)

    apt_update_status = apt_install_packages(
        ["lsb-release"], logger, apt_updated_already
    )
    context["apt_updated_this_run"] = apt_update_status

    if not bootstrap_cmd_exists("lsb_release"):
        logger.critical(
            f"{BS_SYMBOLS['error']} Failed to make 'lsb_release' available. The installer cannot continue."
        )
        sys.exit(1)
    else:
        logger.info(
            f"{BS_SYMBOLS['success']} 'lsb_release' is now available."
        )
