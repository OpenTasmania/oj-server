# ot-osm-osrm-server/bootstrap_installer/bs_util_linux.py
# -*- coding: utf-8 -*-
from bootstrap_installer.bs_utils import (
    BS_SYMBOLS,
    apt_install_packages,
    bootstrap_cmd_exists,
    get_bs_logger,
)

logger = get_bs_logger("UtilLinux")


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
        f"{BS_SYMBOLS['info']} Checking for 'dmesg' (from 'util-linux')..."
    )
    if bootstrap_cmd_exists("dmesg"):
        logger.info(
            f"{BS_SYMBOLS['success']} 'dmesg' command already available."
        )
        return

    logger.warning("'dmesg' not found. Ensuring 'util-linux' is installed...")
    context["any_install_attempted"] = True
    apt_updated_already = context.get("apt_updated_this_run", False)

    apt_update_status = apt_install_packages(
        ["util-linux"], logger, apt_updated_already
    )
    context["apt_updated_this_run"] = apt_update_status

    if not bootstrap_cmd_exists("dmesg"):
        logger.warning(
            f"{BS_SYMBOLS['warning']} Could not confirm 'dmesg' after install. This may be okay on some minimal systems."
        )
    else:
        logger.info(f"{BS_SYMBOLS['success']} 'dmesg' is now available.")
