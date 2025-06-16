# ot-osm-osrm-server/bootstrap_installer/bs_orchestrator.py
# -*- coding: utf-8 -*-

from bootstrap_installer.bs_apt import ensure_python_apt_prerequisite
from bootstrap_installer.bs_build_tools import ensure_build_tools
from bootstrap_installer.bs_lsb import ensure_lsb_release
from bootstrap_installer.bs_pydantic import ensure_pydantic_prerequisites
from bootstrap_installer.bs_util_linux import ensure_util_linux
from bootstrap_installer.bs_utils import BS_SYMBOLS, get_bs_logger


def run_bootstrap_orchestration_manual(app_settings, logger=None):
    """
    Manually orchestrates the bootstrap prerequisite checks.

    This function provides a procedural alternative to the class-based
    Orchestrator for simple, linear bootstrap sequences. It is essential for first stage
    booting the main installer and orchestrator.

    Args:
        app_settings: The application settings object.
        logger: An optional logger instance.

    Returns:
        A tuple containing:
        - success: True if all steps completed.
        - context: The final state context.
    """
    effective_logger = logger or get_bs_logger("ManualOrchestrator")
    effective_logger.info(
        f"{BS_SYMBOLS['info']} Starting manual bootstrap prerequisite checks..."
    )

    context = {
        "apt_updated_this_run": False,
        "any_install_attempted": False,
        "app_settings": app_settings,
    }

    # A list of tasks to execute in sequence
    tasks_to_run = [
        ("Python3-apt Prerequisite", ensure_python_apt_prerequisite),
        ("Pydantic Prerequisites", ensure_pydantic_prerequisites),
        ("LSB Release Prerequisite", ensure_lsb_release),
        ("util-linux Prerequisite", ensure_util_linux),
        ("Build Tools Prerequisites", ensure_build_tools),
    ]

    try:
        # Execute each task, passing the shared context
        for name, func in tasks_to_run:
            effective_logger.info(f"--- Running task '{name}' ---")
            func(context=context)

    except SystemExit:
        effective_logger.critical(
            "A critical prerequisite check failed. Aborting manual orchestration."
        )
        raise

    any_install_attempted_overall = context.get(
        "any_install_attempted", False
    )
    if any_install_attempted_overall:
        effective_logger.info(
            f"{BS_SYMBOLS['success']} Manual bootstrap checks finished. System package installations were attempted."
        )
    else:
        effective_logger.info(
            f"{BS_SYMBOLS['success']} All checked bootstrap prerequisites were already met."
        )

    return True, context
