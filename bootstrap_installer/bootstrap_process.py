# bootstrap_installer/bootstrap_process.py
# -*- coding: utf-8 -*-
"""
Defines the bootstrap prerequisite orchestration process using the centralized orchestrator.
"""

from bootstrap_installer.bs_apt import ensure_python_apt_prerequisite
from bootstrap_installer.bs_build_tools import ensure_build_tools
from bootstrap_installer.bs_lsb import ensure_lsb_release
from bootstrap_installer.bs_pydantic import ensure_pydantic_prerequisites
from bootstrap_installer.bs_util_linux import ensure_util_linux
from bootstrap_installer.bs_utils import BS_SYMBOLS, get_bs_logger
from common.orchestrator import Orchestrator


def run_bootstrap_orchestration(app_settings, logger=None):
    """
    Configures and runs the bootstrap prerequisite orchestration.

    Args:
        app_settings: The application settings object.
        logger: An optional logger instance.

    Returns:
        A tuple containing:
        - success: True if the orchestration completed successfully, False otherwise.
        - context: The orchestration context containing state information.
    """
    effective_logger = logger or get_bs_logger("Orchestrator")

    effective_logger.info(
        f"{BS_SYMBOLS['info']} Starting bootstrap prerequisite orchestration..."
    )

    orchestrator = Orchestrator(app_settings, effective_logger)

    orchestrator.context["apt_updated_this_run"] = False
    orchestrator.context["any_install_attempted"] = False

    orchestrator.add_task(
        "Python3-apt Prerequisite", ensure_python_apt_prerequisite
    )
    orchestrator.add_task(
        "Pydantic Prerequisites", ensure_pydantic_prerequisites
    )
    orchestrator.add_task("LSB Release Prerequisite", ensure_lsb_release)
    orchestrator.add_task("util-linux Prerequisite", ensure_util_linux)
    orchestrator.add_task("Build Tools Prerequisites", ensure_build_tools)

    success = orchestrator.run()

    any_install_attempted_overall = orchestrator.context.get(
        "any_install_attempted", False
    )

    if any_install_attempted_overall:
        effective_logger.info(
            f"{BS_SYMBOLS['success']} Bootstrap prerequisite processing finished. System package installations were attempted."
        )
    else:
        effective_logger.info(
            f"{BS_SYMBOLS['success']} All checked bootstrap prerequisites were already met. No new installations were attempted in this run."
        )

    return success, orchestrator.context
