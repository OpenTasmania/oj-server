# common/constants_loader.py
# -*- coding: utf-8 -*-
"""
Constants loader for the application.

Provides utilities for loading and accessing constants from the constants.yaml file.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

# Constants file path
CONSTANTS_FILE = Path(__file__).parent / "constants.yaml"

# Cache for loaded constants
_constants_cache: Optional[Dict[str, Any]] = None

# Set up logger
module_logger = logging.getLogger(__name__)


def get_constants() -> Dict[str, Any]:
    """
    Load constants from the YAML file.
    Returns a dictionary of constants.

    Returns:
        Dict[str, Any]: A dictionary containing all constants from the YAML file.

    Raises:
        FileNotFoundError: If the constants file doesn't exist.
        yaml.YAMLError: If there's an error parsing the YAML file.
    """
    global _constants_cache

    if _constants_cache is not None:
        return _constants_cache

    if not CONSTANTS_FILE.exists():
        raise FileNotFoundError(
            f"Constants file not found at {CONSTANTS_FILE}"
        )

    try:
        with open(CONSTANTS_FILE, "r", encoding="utf-8") as f:
            _constants_cache = yaml.safe_load(f)

        if _constants_cache is None:
            # If the file is empty or contains only comments
            _constants_cache = {}

        module_logger.info(f"Loaded constants from {CONSTANTS_FILE}")
        return _constants_cache
    except yaml.YAMLError as e:
        module_logger.error(
            f"Error parsing constants file {CONSTANTS_FILE}: {e}"
        )
        raise
    except Exception as e:
        module_logger.error(
            f"Error loading constants file {CONSTANTS_FILE}: {e}"
        )
        raise


def get_constant(path: str, default: Any = None) -> Any:
    """
    Get a constant value by its path.

    Args:
        path: Dot-separated path to the constant (e.g., "features.pgadmin_enabled")
        default: Default value to return if the constant is not found

    Returns:
        The constant value or the default if not found
    """
    try:
        constants = get_constants()

        parts = path.split(".")
        current = constants

        for part in parts:
            if not isinstance(current, dict) or part not in current:
                module_logger.debug(
                    f"Constant '{path}' not found, using default: {default}"
                )
                return default
            current = current[part]

        return current
    except Exception as e:
        module_logger.warning(
            f"Error retrieving constant '{path}': {e}. Using default: {default}"
        )
        return default


def is_feature_enabled(feature_name: str, default: bool = False) -> bool:
    """
    Check if a feature is enabled in the constants.

    Args:
        feature_name: The name of the feature to check
        default: Default value to return if the feature flag is not found

    Returns:
        True if the feature is enabled, False otherwise
    """
    result = get_constant(f"features.{feature_name}", default)
    return bool(result)


def get_task(task_name: str) -> Optional[Dict[str, Any]]:
    """
    Get a task by name.

    Args:
        task_name: The name of the task to get

    Returns:
        The task dictionary or None if not found
    """
    tasks = get_constant("tasks", {})
    if not isinstance(tasks, dict):
        return None
    return tasks.get(task_name)


def get_step(step_name: str) -> Optional[Dict[str, Any]]:
    """
    Get a step by name.

    Args:
        step_name: The name of the step to get

    Returns:
        The step dictionary or None if not found
    """
    steps = get_constant("steps", {})
    if not isinstance(steps, dict):
        return None
    return steps.get(step_name)


def is_task_enabled(task_name: str) -> bool:
    """
    Check if a task is enabled.

    Args:
        task_name: The name of the task to check

    Returns:
        True if the task is enabled, False otherwise
    """
    task = get_task(task_name)
    if task is None:
        module_logger.warning(f"Task '{task_name}' not found")
        return False

    enabled_value = task.get("enabled", False)
    return bool(enabled_value)


def get_task_steps(
    task_name: str, visited: Optional[Set[str]] = None
) -> List[str]:
    """
    Get all steps for a task, including steps from sub-tasks.

    Args:
        task_name: The name of the task to get steps for
        visited: Set of already visited tasks (used to detect circular references)

    Returns:
        List of step names

    Raises:
        ValueError: If a circular reference is detected
    """
    if visited is None:
        visited = set()

    # Check for circular references
    if task_name in visited:
        raise ValueError(f"Circular reference detected in task '{task_name}'")

    visited.add(task_name)

    task = get_task(task_name)
    if task is None:
        module_logger.warning(f"Task '{task_name}' not found")
        return []

    steps = []
    task_steps = task.get("steps", [])

    for step in task_steps:
        # If the step is a task, get its steps recursively
        if get_task(step) is not None:
            steps.extend(get_task_steps(step, visited.copy()))
        else:
            steps.append(step)

    return steps


def validate_tasks() -> bool:
    """
    Validate that there are no circular references in tasks.

    Returns:
        True if validation passes, False otherwise
    """
    tasks = get_constant("tasks", {})

    for task_name in tasks:
        try:
            get_task_steps(task_name)
        except ValueError as e:
            module_logger.error(f"Task validation failed: {e}")
            return False

    return True
