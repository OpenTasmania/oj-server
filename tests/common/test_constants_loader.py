import logging
from pathlib import Path

import pytest
import yaml

from common.constants_loader import (
    get_constant,
    get_constants,
    get_step,
    get_task,
    get_task_steps,
    is_feature_enabled,
    is_task_enabled,
    validate_tasks,
)


def test_get_task_steps_with_valid_task(mock_constants_file):
    """Test get_task_steps with a valid task name."""
    task_name = "build_app"
    steps = get_task_steps(task_name)
    assert isinstance(steps, list), "Expected a list of steps"
    assert "compile_code" in steps, (
        "Expected task steps to include 'compile_code'"
    )


def test_validate_tasks_with_no_circular_references(
    mock_constants_file, mock_logger
):
    """Test validate_tasks when there are circular references in the mock file."""
    # The mock_constants_file fixture includes a circular_task that references itself,
    # so validate_tasks() should return False
    result = validate_tasks()
    assert result is False, (
        "Expected validate_tasks to return False when circular references exist"
    )


def test_validate_tasks_with_circular_references(
    mock_constants_file, mock_logger, monkeypatch
):
    """Test validate_tasks when there are circular references."""

    # Mock get_task_steps to simulate circular references
    def mock_get_task_steps(task_name, visited=None):
        if task_name == "circular_task":
            raise ValueError("Circular reference detected")
        return []

    monkeypatch.setattr(
        "common.constants_loader.get_task_steps", mock_get_task_steps
    )

    result = validate_tasks()
    assert result is False, (
        "Expected validate_tasks to return False when circular references exist"
    )


def test_get_task_steps_with_circular_reference(mock_constants_file):
    """Test get_task_steps for handling circular references."""
    task_name = "circular_task"
    with pytest.raises(ValueError, match="Circular reference detected"):
        get_task_steps(task_name)


def test_get_task_steps_with_invalid_task_name(mock_constants_file):
    """Test get_task_steps with an invalid task name."""
    task_name = "nonexistent_task"
    steps = get_task_steps(task_name)
    assert steps == [], "Expected an empty list for nonexistent task"


def test_get_step_valid(mock_constants_file, mock_logger):
    """Test get_step with a valid step name."""
    value = get_step("step_one")
    assert value is not None, "Expected step_one to exist, but it's None"
    assert isinstance(value, dict), "Expected step_one to return a dictionary"
    assert value.get("description") == "First step", (
        f"Expected step_one description to be 'First step', got '{value.get('description')}'"
    )


def test_get_step_invalid(mock_constants_file, mock_logger):
    """Test get_step with an invalid step name."""
    value = get_step("nonexistent_step")
    assert value is None, (
        "Expected nonexistent_step to return None, but got a value"
    )


def test_get_constant_invalid_path(mock_constants_file, mock_logger):
    """Test get_constant with an invalid path."""
    value = get_constant("nonexistent.path", default="default_value")
    assert value == "default_value", (
        f"Expected default value 'default_value', got '{value}'"
    )


def test_get_constant_partial_path(mock_constants_file, mock_logger):
    """Test get_constant with a partial path."""
    value = get_constant("features", default=None)
    assert isinstance(value, dict), "Expected 'features' to be a dictionary"
    assert "feature_one" in value, (
        "Expected 'features' to contain 'feature_one'"
    )


def test_get_constant_empty_path(mock_constants_file, mock_logger):
    """Test get_constant with an empty path."""
    value = get_constant("", default="default_value")
    assert value == "default_value", (
        f"Expected default value 'default_value', got '{value}'"
    )


def test_is_feature_enabled_true(mock_constants_file, mock_logger):
    """Test is_feature_enabled with a feature that is enabled."""
    result = is_feature_enabled("feature_one")
    assert result is True, "Expected feature_one to be enabled"


def test_is_feature_enabled_false(mock_constants_file, mock_logger):
    """Test is_feature_enabled with a feature that is disabled."""
    result = is_feature_enabled("feature_two")
    assert result is False, "Expected feature_two to be disabled"


def test_is_feature_enabled_nonexistent(mock_constants_file, mock_logger):
    """Test is_feature_enabled with a nonexistent feature."""
    result = is_feature_enabled("nonexistent_feature", default=True)
    assert result is True, (
        "Expected nonexistent_feature to use the default value (True)"
    )


def test_is_task_enabled_true(mock_constants_file, mock_logger):
    """Test is_task_enabled with a task that is enabled."""
    result = is_task_enabled("build_app")
    assert result is True, "Expected build_app task to be enabled"


def test_is_task_enabled_false(mock_constants_file, mock_logger):
    """Test is_task_enabled with a task that is disabled."""
    result = is_task_enabled("circular_task")
    assert result is False, "Expected circular_task to be disabled"


def test_is_task_enabled_nonexistent(mock_constants_file, mock_logger):
    """Test is_task_enabled with a nonexistent task."""
    result = is_task_enabled("nonexistent_task")
    assert result is False, "Expected nonexistent_task to be disabled"


def test_get_task_valid(mock_constants_file, mock_logger):
    """Test get_task with a valid task name."""
    task = get_task("build_app")
    assert task is not None, "Expected build_app task to exist"
    assert isinstance(task, dict), "Expected task to be a dictionary"
    assert task.get("name") == "Build Application", (
        f"Expected task name to be 'Build Application', got '{task.get('name')}'"
    )
    assert task.get("enabled") is True, "Expected task to be enabled"
    assert "steps" in task, "Expected task to have steps"
    assert isinstance(task["steps"], list), "Expected steps to be a list"
    assert "compile_code" in task["steps"], (
        "Expected steps to include 'compile_code'"
    )


def test_get_task_invalid(mock_constants_file, mock_logger):
    """Test get_task with an invalid task name."""
    task = get_task("nonexistent_task")
    assert task is None, "Expected nonexistent_task to return None"


def test_get_constant_invalid_yaml_file_path(monkeypatch, tmp_path):
    """Test get_constant when the YAML file path is invalid."""
    invalid_yaml_file = tmp_path / "does_not_exist.yaml"
    monkeypatch.setattr(
        "common.constants_loader.CONSTANTS_FILE", invalid_yaml_file
    )
    monkeypatch.setattr("common.constants_loader._constants_cache", None)

    value = get_constant("some.path", default="default_value")
    assert value == "default_value", (
        f"Expected default value 'default_value', got '{value}'"
    )


@pytest.fixture
def mock_logger(monkeypatch):
    """Fixture to mock the logger."""
    mock_log = logging.getLogger("test_logger")
    monkeypatch.setattr("common.constants_loader.module_logger", mock_log)
    return mock_log


@pytest.fixture
def mock_constants_file(monkeypatch, tmp_path):
    """Fixture to create a mock constants file."""
    constants_file = tmp_path / "constants.yaml"
    constants_file.write_text("""
    # Mock constants file for testing
    app_name: TestApp
    version: 1.0.0

    # Feature flags
    features:
      feature_one: true
      feature_two: false

    # Tasks and Steps definitions
    tasks:
      build_app:
        name: "Build Application"
        description: "Build the application from source"
        enabled: true
        steps:
          - compile_code
          - package_app

      circular_task:
        name: "Circular Task"
        description: "A task with circular reference"
        enabled: false
        steps:
          - circular_task

    # Steps definitions
    steps:
      step_one:
        name: "Step One"
        description: "First step"
        command: "echo 'Step One'"

      compile_code:
        name: "Compile Code"
        description: "Compile the source code"
        command: "make compile"

      package_app:
        name: "Package Application"
        description: "Package the compiled application"
        command: "make package"
    """)

    # Mock the CONSTANTS_FILE and _constants_cache
    monkeypatch.setattr(
        "common.constants_loader.CONSTANTS_FILE", constants_file
    )
    monkeypatch.setattr("common.constants_loader._constants_cache", None)
    return constants_file


def test_get_constants(mock_constants_file, mock_logger):
    """Test loading constants from a valid YAML file."""
    constants = get_constants()
    assert constants["app_name"] == "TestApp", (
        f"Expected 'app_name' to be 'TestApp', got '{constants['app_name']}'"
    )
    assert constants["version"] == "1.0.0", (
        f"Expected 'version' to be '1.0.0', got '{constants['version']}'"
    )
    assert "features" in constants, (
        "Expected 'features' to be present in constants"
    )
    assert isinstance(constants["features"], dict), (
        "Expected 'features' to be a dictionary"
    )
    assert len(constants["features"]) == 2, (
        f"Expected 'features' to have 2 items, got '{len(constants['features'])}'"
    )
    assert "feature_one" in constants["features"], (
        "Expected 'feature_one' to be present in features"
    )
    assert constants["features"]["feature_one"] is True, (
        f"Expected 'feature_one' to be True, got '{constants['features']['feature_one']}'"
    )


def test_missing_constants_file(monkeypatch):
    """Test behavior when the constants file is missing."""
    monkeypatch.setattr(
        "common.constants_loader.CONSTANTS_FILE",
        Path("/invalid/path/constants.yaml"),
    )
    monkeypatch.setattr("common.constants_loader._constants_cache", None)

    with pytest.raises(FileNotFoundError, match="Constants file not found"):
        get_constants()


def test_invalid_yaml_syntax(monkeypatch, tmp_path):
    """Test behavior when the YAML file has invalid syntax."""
    invalid_yaml_file = tmp_path / "invalid_constants.yaml"
    invalid_yaml_file.write_text("invalid_yaml: [missing_end_bracket")

    monkeypatch.setattr(
        "common.constants_loader.CONSTANTS_FILE", invalid_yaml_file
    )
    monkeypatch.setattr("common.constants_loader._constants_cache", None)

    # The get_constants function will raise a yaml.parser.ParserError
    # which is caught and re-raised as a yaml.YAMLError
    with pytest.raises(yaml.YAMLError):
        get_constants()


def test_empty_constants_file(monkeypatch, tmp_path, mock_logger):
    """Test behavior when the constants file is empty."""
    empty_file = tmp_path / "empty_constants.yaml"
    empty_file.write_text("")

    monkeypatch.setattr("common.constants_loader.CONSTANTS_FILE", empty_file)
    monkeypatch.setattr("common.constants_loader._constants_cache", None)

    constants = get_constants()
    assert constants == {}, "Expected constants to be an empty dictionary"
