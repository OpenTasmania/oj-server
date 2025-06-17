# tests/common/test_orchestrator.py
# -*- coding: utf-8 -*-
"""
Tests for the centralized orchestrator module.
"""

from unittest.mock import MagicMock

import pytest

from common.orchestrator import Orchestrator


class TestOrchestrator:
    """Tests for the Orchestrator class."""

    def test_init(self):
        """Test initialization of the Orchestrator class."""
        app_settings = MagicMock()
        logger = MagicMock()

        orchestrator = Orchestrator(app_settings, logger)

        assert orchestrator.app_settings == app_settings
        assert orchestrator.logger == logger
        assert orchestrator.tasks == []
        assert orchestrator.context == {}

    def test_add_task(self):
        """Test adding a task to the orchestrator."""
        app_settings = MagicMock()
        logger = MagicMock()

        orchestrator = Orchestrator(app_settings, logger)

        task_func = MagicMock()
        orchestrator.add_task(
            "Test Task",
            task_func,
            ["arg1", "arg2"],
            {"kwarg1": "value1"},
            False,
        )

        assert len(orchestrator.tasks) == 1
        task = orchestrator.tasks[0]
        assert task["name"] == "Test Task"
        assert task["func"] == task_func
        assert task["args"] == ["arg1", "arg2"]
        assert task["kwargs"] == {"kwarg1": "value1"}
        assert task["fatal"] is False

    def test_run_success(self):
        """Test running the orchestrator with successful tasks."""
        app_settings = MagicMock()
        logger = MagicMock()

        orchestrator = Orchestrator(app_settings, logger)

        task1 = MagicMock(return_value="result1")
        task2 = MagicMock(return_value="result2")

        orchestrator.add_task("Task 1", task1)
        orchestrator.add_task("Task 2", task2)

        result = orchestrator.run()

        assert result is True
        task1.assert_called_once()
        task2.assert_called_once()
        assert orchestrator.context["Task 1_result"] == "result1"
        assert orchestrator.context["Task 2_result"] == "result2"

    def test_run_failure_fatal(self):
        """Test running the orchestrator with a fatal task failure."""
        app_settings = MagicMock()
        logger = MagicMock()
        orchestrator = Orchestrator(app_settings, logger)
        task1 = MagicMock(side_effect=Exception("Task 1 failed"))
        task2 = MagicMock()
        orchestrator.add_task("Task 1", task1)
        orchestrator.add_task("Task 2", task2)

        with pytest.raises(SystemExit) as excinfo:
            orchestrator.run()

        assert excinfo.value.code == 1

        task1.assert_called_once()

        task2.assert_not_called()

        logger.critical.assert_called_once_with(
            "🔥 Task 'Task 1' failed: Task 1 failed", exc_info=True
        )
        logger.error.assert_called_once_with(
            "A fatal error occurred. Halting orchestration and exiting application."
        )

    def test_run_failure_non_fatal(self):
        """Test running the orchestrator with a non-fatal task failure."""
        app_settings = MagicMock()
        logger = MagicMock()

        orchestrator = Orchestrator(app_settings, logger)

        task1 = MagicMock(side_effect=Exception("Task 1 failed"))
        task2 = MagicMock()

        orchestrator.add_task("Task 1", task1, fatal=False)
        orchestrator.add_task("Task 2", task2)

        result = orchestrator.run()

        assert result is True
        task1.assert_called_once()
        task2.assert_called_once()

    def test_context_passing(self):
        """Test that context is passed to tasks and can be updated by them."""
        app_settings = MagicMock()
        logger = MagicMock()

        orchestrator = Orchestrator(app_settings, logger)

        def task1(context, app_settings, **kwargs):
            context["task1_data"] = "data from task 1"
            return "result1"

        def task2(context, app_settings, **kwargs):
            assert context["task1_data"] == "data from task 1"
            context["task2_data"] = "data from task 2"
            return "result2"

        orchestrator.add_task("Task 1", task1)
        orchestrator.add_task("Task 2", task2)

        result = orchestrator.run()

        assert result is True
        assert orchestrator.context["task1_data"] == "data from task 1"
        assert orchestrator.context["task2_data"] == "data from task 2"
        assert orchestrator.context["Task 1_result"] == "result1"
        assert orchestrator.context["Task 2_result"] == "result2"
