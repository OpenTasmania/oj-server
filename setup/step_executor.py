# setup/step_executor.py
# -*- coding: utf-8 -*-
"""
Provides functionality to execute individual setup steps.

This module defines a function to run a given setup step, which includes
checking its completion status, prompting the user for re-run if already
completed, executing the step function, and marking it as completed upon
successful execution.
"""

import logging
from typing import Any, Callable, Optional

# log_map_server and state_manager functions now expect AppSettings
from common.command_utils import log_map_server

# Import AppSettings for type hinting
from setup.config_models import AppSettings
from setup.state_manager import is_step_completed, mark_step_completed

module_logger = logging.getLogger(__name__)


def execute_step(
    step_tag: str,
    step_description: str,
    step_function: Callable[[AppSettings, Optional[logging.Logger]], Any],
    app_settings: AppSettings,  # Added app_settings parameter
    current_logger_instance: Optional[logging.Logger],
    prompt_user_for_rerun: Callable[
        [str, AppSettings, Optional[logging.Logger]], bool
    ],
    cli_flag: Optional[str] = None,
    group_cli_flag: Optional[str] = None,
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
                       Expected signature: (app_settings: AppSettings, current_logger: Optional[logging.Logger]) -> Any
                       Should return False to indicate failure. Any other return value (including None) or the absence
                       of a return value is considered success. An exception will always be treated as a failure.
        app_settings: The application settings object.
        current_logger_instance: The logger instance to use.
        prompt_user_for_rerun: Callback for user prompts.
                               Expected signature: (prompt: str, app_settings: AppSettings, logger: Optional[logging.Logger]) -> bool
        cli_flag: The individual command line flag that triggered this step.
        group_cli_flag: The group command line flag that triggered this step.

    Returns:
        True if the step was successfully executed or if it was skipped.
        False if the step execution failed.
    """
    logger_to_use = (
        current_logger_instance if current_logger_instance else module_logger
    )
    symbols = app_settings.symbols
    run_this_step = True

    if is_step_completed(
        step_tag, app_settings=app_settings, current_logger=logger_to_use
    ):
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Step '{step_description}' ({step_tag}) is already marked as completed.",
            "info",
            logger_to_use,
            app_settings,
        )

        prompt = f"Step '{step_description}' ({step_tag}) is completed. Re-run anyway?"
        if prompt_user_for_rerun(prompt, app_settings, logger_to_use):
            log_map_server(
                f"{symbols.get('info', 'ℹ️')} User chose to re-run step: {step_tag}",
                "info",
                logger_to_use,
                app_settings,
            )
        else:
            log_map_server(
                f"{symbols.get('info', 'ℹ️')} Skipping re-run of step: {step_tag}",
                "info",
                logger_to_use,
                app_settings,
            )
            run_this_step = False

    if run_this_step:
        log_map_server(
            f"--- {symbols.get('step', '➡️')} Executing: {step_description} ({step_tag}) ---",
            "info",
            logger_to_use,
            app_settings,
        )
        if cli_flag or group_cli_flag:
            cli_flag_info = f"CLI flag: {cli_flag}" if cli_flag else ""
            group_flag_info = (
                f"Group CLI flag: {group_cli_flag}" if group_cli_flag else ""
            )
            separator = " | " if cli_flag and group_cli_flag else ""
            log_map_server(
                f"   {symbols.get('info', 'ℹ️')} Triggered by: {cli_flag_info}{separator}{group_flag_info}",
                "info",
                logger_to_use,
                app_settings,
            )
        try:
            step_result = step_function(app_settings, logger_to_use)

            if step_result is False:
                log_map_server(
                    f"{symbols.get('error', '❌')} Step function returned False: {step_description} ({step_tag})",
                    "error",
                    logger_to_use,
                    app_settings,
                )
                return False

            mark_step_completed(
                step_tag,
                app_settings=app_settings,
                current_logger=logger_to_use,
            )
            log_map_server(
                f"--- {symbols.get('success', '✅')} Successfully completed: {step_description} ({step_tag}) ---",
                "success",
                logger_to_use,
                app_settings,
            )
            return True
        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '❌')} FAILED: {step_description} ({step_tag})",
                "error",
                logger_to_use,
                app_settings,
            )
            log_map_server(
                f"   Error details: {str(e)}",
                "error",
                logger_to_use,
                app_settings,
                exc_info=True,
            )
            return False

    return True
