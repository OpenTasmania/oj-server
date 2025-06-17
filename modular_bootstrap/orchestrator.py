# modular_bootstrap/orchestrator.py
# -*- coding: utf-8 -*-
"""
This module defines the orchestration process for ensuring that all modular bootstrap
prerequisites are met. It leverages a centralized orchestrator to execute a
sequence of tasks, each responsible for a specific setup requirement.

The primary function, `run_modular_bootstrap`, configures and executes
this orchestration. It ensures that essential tools and libraries, such as
build tools, Python modules, and system utilities, are installed and properly
configured before the main application setup begins.

This modular approach allows for a clean separation of concerns, where each
prerequisite is handled by a dedicated function. The orchestrator manages the
execution flow and maintains the overall state, providing a clear and robust
process for initializing the application's environment.
"""

from common.orchestrator import Orchestrator
from modular_bootstrap.mb_apt import ensure_python_apt_prerequisite
from modular_bootstrap.mb_build_tools import ensure_build_tools
from modular_bootstrap.mb_lsb import ensure_lsb_release
from modular_bootstrap.mb_pydantic import ensure_pydantic_prerequisites
from modular_bootstrap.mb_util_linux import ensure_util_linux
from modular_bootstrap.mb_utils import MB_SYMBOLS, get_mb_logger


def run_modular_bootstrap(app_settings, logger=None):
    """
    Configures and executes the modular bootstrap prerequisite orchestration to ensure
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
    effective_logger = logger or get_mb_logger("Orchestrator")

    effective_logger.info(
        f"{MB_SYMBOLS['info']} Starting modular bootstrap prerequisite orchestration..."
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
            f"{MB_SYMBOLS['success']} Modular bootstrap prerequisite processing finished. "
            "System package installations were attempted."
        )
    else:
        effective_logger.info(
            f"{MB_SYMBOLS['success']} All checked modular bootstrap prerequisites were "
            "already met. No new installations were attempted in this run."
        )

    return success, orchestrator.context
