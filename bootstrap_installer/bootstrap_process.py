# bootstrap_installer/bootstrap_process.py
# -*- coding: utf-8 -*-
"""
This module defines the orchestration process for ensuring that all bootstrap
prerequisites are met. It leverages a centralized orchestrator to execute a
sequence of tasks, each responsible for a specific setup requirement.

The primary function, `run_bootstrap_orchestration`, configures and executes
this orchestration. It ensures that essential tools and libraries, such as
build tools, Python modules, and system utilities, are installed and properly
configured before the main application setup begins.

This modular approach allows for a clean separation of concerns, where each
prerequisite is handled by a dedicated function. The orchestrator manages the
execution flow and maintains the overall state, providing a clear and robust
process for initializing the application's environment.
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
    Configures and executes the bootstrap prerequisite orchestration to ensure
    that all necessary tools and libraries are installed and configured.

    This function initializes an orchestrator and adds a series of tasks to
    it, each responsible for a specific prerequisite. These tasks are executed
    in a predefined order to ensure dependencies are handled correctly. The
    orchestrator manages the overall process, tracks the state of each task,
    and provides detailed logging.

    Args:
        app_settings: An object containing the application's configuration
                      settings. This is passed to the orchestrator to provide
                      context for the tasks.
        logger: An optional logger instance. If not provided, a default
                logger will be created.

    Returns:
        A tuple containing:
        - success (bool): True if all orchestration tasks completed
                          successfully, False otherwise.
        - context (dict): The orchestration context, which contains state
                          information such as whether any packages were
                          installed during the run.
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
            f"{BS_SYMBOLS['success']} Bootstrap prerequisite processing finished. "
            "System package installations were attempted."
        )
    else:
        effective_logger.info(
            f"{BS_SYMBOLS['success']} All checked bootstrap prerequisites were "
            "already met. No new installations were attempted in this run."
        )

    return success, orchestrator.context
