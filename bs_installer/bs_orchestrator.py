# ot-osm-osrm-server/bs_installer/bs_orchestrator.py
# -*- coding: utf-8 -*-
from bs_installer.bs_build_tools import ensure_build_tools
from bs_installer.bs_lsb import ensure_lsb_release
from bs_installer.bs_pydantic import ensure_pydantic_prerequisites
from bs_installer.bs_utils import BS_SYMBOLS, get_bs_logger

logger = get_bs_logger("Orchestrator")


def ensure_all_bootstrap_prerequisites() -> bool:
    """
    Orchestrates all initial system prerequisite checks and installations.
    Calls specialized functions for pydantic, lsb_release, and build tools.

    Returns:
        True if any system package installations were attempted during this run,
             signaling that the calling script (install.py) should re-execute.
        False if all checked prerequisites were already met and no installations occurred.
    Sub-modules will exit with error code if their critical installations fail.
    """
    logger.info(
        f"{BS_SYMBOLS['info']} Starting bootstrap prerequisite orchestration..."
    )

    any_install_attempted_overall = False
    # Track if apt update has been run by any sub-module in this orchestration run
    # to avoid running it multiple times.
    apt_updated_this_orchestration_run = False

    # Pydantic & Pydantic Settings
    logger.info("--- Stage 1: Pydantic Prerequisites ---")
    install_attempted_pydantic, apt_updated_this_orchestration_run = (
        ensure_pydantic_prerequisites(apt_updated_this_orchestration_run)
    )
    if install_attempted_pydantic:
        any_install_attempted_overall = True

    # LSB Release
    logger.info("--- Stage 2: LSB Release Prerequisite ---")
    install_attempted_lsb, apt_updated_this_orchestration_run = (
        ensure_lsb_release(apt_updated_this_orchestration_run)
    )
    if install_attempted_lsb:
        any_install_attempted_overall = True

    # Build Tools (build-essential, python3-dev)
    logger.info("--- Stage 3: Build Tools Prerequisites ---")
    install_attempted_build_tools, apt_updated_this_orchestration_run = (
        ensure_build_tools(apt_updated_this_orchestration_run)
    )
    if install_attempted_build_tools:
        any_install_attempted_overall = True

    if any_install_attempted_overall:
        logger.info(
            f"{BS_SYMBOLS['success']} Bootstrap prerequisite processing finished. System package installations were attempted."
        )
        return True
    else:
        logger.info(
            f"{BS_SYMBOLS['success']} All checked bootstrap prerequisites were already met. No new installations were attempted in this run."
        )
        return False
