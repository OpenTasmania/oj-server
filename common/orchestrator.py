# common/orchestrator.py
# -*- coding: utf-8 -*-
"""
Centralized orchestrator for managing and executing sequences of tasks.
"""

import logging
import sys
from typing import Any, Callable, Dict, List, Optional


class Orchestrator:
    """A centralized orchestrator to run a series of defined tasks."""

    def __init__(
        self,
        app_settings: Any,
        orchestrator_logger: Optional[logging.Logger] = None,
    ):
        """
        Initializes the Orchestrator.

        Args:
            app_settings: The application settings object.
            orchestrator_logger: An optional logger instance.
        """
        self.app_settings = app_settings
        self.logger = orchestrator_logger or logging.getLogger(__name__)
        self.tasks: List[Dict[str, Any]] = []
        # Shared context for tasks to pass state between each other
        self.context: Dict[str, Any] = {}

    def add_task(
        self,
        name: str,
        func: Callable,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        fatal: bool = True,
    ):
        """
        Adds a task to the execution list.

        Args:
            name: A human-readable name for the task.
            func: The function to execute for this task.
            args: A list of positional arguments to pass to the function.
            kwargs: A dictionary of keyword arguments to pass to the function.
            fatal: If True, a failure in this task will halt the entire orchestration.
        """
        self.tasks.append({
            "name": name,
            "func": func,
            "args": args or [],
            "kwargs": kwargs or {},
            "fatal": fatal,
        })
        self.logger.debug(f"Task '{name}' added to the queue.")

    def run(self) -> bool:
        """
        Executes all added tasks in sequence.

        Returns:
            True if all tasks completed successfully, False otherwise.
        """
        self.logger.info("Orchestration started.")
        for i, task in enumerate(self.tasks):
            task_name = task["name"]
            self.logger.info(
                f"--- Stage {i + 1}: Running task '{task_name}' ---"
            )

            try:
                # Pass the shared context to every function
                task["kwargs"]["context"] = self.context
                task["kwargs"]["app_settings"] = self.app_settings

                result = task["func"](*task["args"], **task["kwargs"])

                # Update context with the result if needed (optional)
                self.context[f"{task_name}_result"] = result

                self.logger.info(
                    f"✅ Task '{task_name}' completed successfully."
                )

            except Exception as e:
                self.logger.critical(
                    f"🔥 Task '{task_name}' failed: {e}", exc_info=True
                )
                if task.get("fatal", True):
                    self.logger.error(
                        "A fatal error occurred. Halting orchestration and exiting application."
                    )
                    sys.exit(1)
                else:
                    self.logger.warning(
                        f"Task '{task_name}' was non-fatal. Continuing orchestration."
                    )

        self.logger.info("✨ Orchestration finished successfully.")
        return True
