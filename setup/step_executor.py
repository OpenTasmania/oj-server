# osm/setup/step_executor.py
# -*- coding: utf-8 -*-
"""
Provides functionality to execute individual setup steps.

This module defines a function to run a given setup step, which includes
checking its completion status, prompting the user for re-run if already
completed, executing the step function, and marking it as completed upon
successful execution.
"""

import logging
from typing import Callable, Optional

from setup import config  # For SYMBOLS
from setup.command_utils import log_map_server
from setup.state_manager import is_step_completed, mark_step_completed

module_logger = logging.getLogger(__name__)


def execute_step(
    step_tag: str,
    step_description: str,
    step_function: Callable[[Optional[logging.Logger]], None],
    current_logger_instance: Optional[logging.Logger],
    prompt_user_for_rerun: Callable[[str], bool]
) -> bool:
    """
    Execute a single setup step.

    Checks if the step is already completed. If so, it prompts the user
    to re-run. If the step needs to be run (either not completed or user
    chose to re-run), it executes the provided step function and marks
    the step as completed on success.

    Args:
        step_tag: A unique string identifier for the step.
        step_description: A human-readable description of the step.
        step_function: The function to call to execute the step.
                       It's expected to take an optional logger instance.
        current_logger_instance: The logger instance to use for logging
                                 within this function and to pass to the
                                 step_function.
        prompt_user_for_rerun: A callback function that takes a prompt
                               string and returns True (yes) or False (no)
                               based on user input.

    Returns:
        True if the step was successfully executed or if it was skipped
        because it was already completed and the user chose not to re-run.
        False if the step execution failed.
    """
    logger_to_use = current_logger_instance if current_logger_instance \
        else module_logger
    run_this_step = True

    if is_step_completed(step_tag, current_logger=logger_to_use):
        log_map_server(
            f"{config.SYMBOLS['info']} Step '{step_description}' ({step_tag}) "
            "is already marked as completed.",
            "info",
            logger_to_use
        )
        # Use the callback for the prompt.
        prompt = (
            f"Step '{step_description}' ({step_tag}) is completed. "
            "Re-run anyway?"
        )
        if prompt_user_for_rerun(prompt):
            log_map_server(
                f"{config.SYMBOLS['info']} User chose to re-run step: "
                f"{step_tag}",
                "info", logger_to_use
            )
            # run_this_step remains True.
        else:
            log_map_server(
                f"{config.SYMBOLS['info']} Skipping re-run of step: "
                f"{step_tag}",
                "info", logger_to_use
            )
            run_this_step = False

    if run_this_step:
        log_map_server(
            f"--- {config.SYMBOLS['step']} Executing: {step_description} "
            f"({step_tag}) ---",
            "info",
            logger_to_use
        )
        try:
            # Pass the logger to the actual step function.
            step_function(logger_to_use)
            mark_step_completed(step_tag, current_logger=logger_to_use)
            log_map_server(
                f"--- {config.SYMBOLS['success']} Successfully completed: "
                f"{step_description} ({step_tag}) ---",
                "success",
                logger_to_use
            )
            return True
        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} FAILED: {step_description} "
                f"({step_tag})",
                "error",
                logger_to_use
            )
            log_map_server(f"   Error details: {str(e)}", "error", logger_to_use)
            # Include traceback for debugging if desired, e.g.,
            # logger_to_use.exception("Detailed error information:")
            return False

    # If step was skipped because it was completed and user chose not to re-run.
    return True