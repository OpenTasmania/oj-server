# tests/install/test_install_setup.py
# -*- coding: utf-8 -*-
"""
Tests for the 'setup' command in install.py.
"""

import sys
from pathlib import Path
from unittest import mock

# Add project root to sys.path to allow for direct import of project modules
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# Import the main function from install.py
from install import main


def test_setup_command_all_components():
    """
    Test that the 'setup' command with default 'all' components works correctly.
    """
    # Mock the SetupOrchestrator class
    with mock.patch(
        "modular_setup.orchestrator.SetupOrchestrator"
    ) as mock_orchestrator_class:
        # Configure the mock
        mock_orchestrator_instance = mock_orchestrator_class.return_value
        mock_orchestrator_instance.configure.return_value = True

        # Call the main function with the 'setup' command
        result = main(["setup"])

        # Verify the result
        assert result == 0, "Expected successful execution (return code 0)"

        # Verify that SetupOrchestrator was instantiated correctly
        mock_orchestrator_class.assert_called_once()

        # Verify that configure was called with None (for all components)
        mock_orchestrator_instance.configure.assert_called_once_with(None)


def test_setup_command_specific_component():
    """
    Test that the 'setup' command with a specific component works correctly.
    """
    # Mock the SetupOrchestrator class
    with mock.patch(
        "modular_setup.orchestrator.SetupOrchestrator"
    ) as mock_orchestrator_class:
        # Configure the mock
        mock_orchestrator_instance = mock_orchestrator_class.return_value
        mock_orchestrator_instance.configure.return_value = True

        # Call the main function with the 'setup' command and a specific component
        result = main(["setup", "postgres"])

        # Verify the result
        assert result == 0, "Expected successful execution (return code 0)"

        # Verify that SetupOrchestrator was instantiated correctly
        mock_orchestrator_class.assert_called_once()

        # Verify that configure was called with the specific component
        mock_orchestrator_instance.configure.assert_called_once_with([
            "postgres"
        ])


def test_setup_command_failure():
    """
    Test that the 'setup' command handles failures correctly.
    """
    # Mock the SetupOrchestrator class
    with mock.patch(
        "modular_setup.orchestrator.SetupOrchestrator"
    ) as mock_orchestrator_class:
        # Configure the mock to simulate a failure
        mock_orchestrator_instance = mock_orchestrator_class.return_value
        mock_orchestrator_instance.configure.return_value = False

        # Call the main function with the 'setup' command
        result = main(["setup"])

        # Verify the result
        assert result == 1, "Expected failure (return code 1)"

        # Verify that SetupOrchestrator was instantiated correctly
        mock_orchestrator_class.assert_called_once()

        # Verify that configure was called
        mock_orchestrator_instance.configure.assert_called_once_with(
            None, force=False
        )


def test_setup_command_with_status_flag():
    """
    Test that the 'setup' command with the '--status' flag works correctly.
    """
    # Mock the SetupOrchestrator class
    with mock.patch(
        "modular_setup.orchestrator.SetupOrchestrator"
    ) as mock_orchestrator_class:
        # Configure the mock
        mock_orchestrator_instance = mock_orchestrator_class.return_value
        mock_orchestrator_instance.check_status.return_value = {
            "postgres": True,
            "apache": False,
        }

        # Call the main function with the 'setup' command and the '--status' flag
        result = main(["setup", "--status"])

        # Verify the result
        assert result == 1, (
            "Expected failure (return code 1) because not all components are configured"
        )

        # Verify that SetupOrchestrator was instantiated correctly
        mock_orchestrator_class.assert_called_once()

        # Verify that check_status was called
        mock_orchestrator_instance.check_status.assert_called_once_with(None)


def test_setup_command_with_force_flag():
    """
    Test that the 'setup' command with the '--force' flag works correctly.
    """
    # Mock the SetupOrchestrator class
    with mock.patch(
        "modular_setup.orchestrator.SetupOrchestrator"
    ) as mock_orchestrator_class:
        # Configure the mock
        mock_orchestrator_instance = mock_orchestrator_class.return_value
        mock_orchestrator_instance.configure.return_value = True

        # Call the main function with the 'setup' command and the '--force' flag
        result = main(["setup", "--force"])

        # Verify the result
        assert result == 0, "Expected successful execution (return code 0)"

        # Verify that SetupOrchestrator was instantiated correctly
        mock_orchestrator_class.assert_called_once()

        # Verify that configure was called with force=True
        mock_orchestrator_instance.configure.assert_called_once_with(
            None, force=True
        )


def test_setup_command_with_dry_run_flag():
    """
    Test that the 'setup' command with the '--dry-run' flag works correctly.
    """
    # Mock the SetupOrchestrator class and ConfiguratorRegistry
    with (
        mock.patch(
            "modular_setup.orchestrator.SetupOrchestrator"
        ) as mock_orchestrator_class,
        mock.patch(
            "modular_setup.registry.ConfiguratorRegistry"
        ) as mock_registry_class,
    ):
        # Configure the mocks
        mock_orchestrator_instance = mock_orchestrator_class.return_value
        mock_registry_class.get_all_configurators.return_value = {
            "postgres": None,
            "apache": None,
        }
        mock_registry_class.resolve_dependencies.return_value = [
            "postgres",
            "apache",
        ]
        mock_registry_class.get_configurator.side_effect = lambda name: type(
            name,
            (),
            {"metadata": {"description": f"Mock {name} configurator"}},
        )

        # Call the main function with the 'setup' command and the '--dry-run' flag
        result = main(["setup", "--dry-run"])

        # Verify the result
        assert result == 0, "Expected successful execution (return code 0)"

        # Verify that SetupOrchestrator was instantiated correctly
        mock_orchestrator_class.assert_called_once()

        # Verify that _import_configurators was called
        mock_orchestrator_instance._import_configurators.assert_called_once()

        # Verify that get_all_configurators was called
        mock_registry_class.get_all_configurators.assert_called_once()

        # Verify that resolve_dependencies was called
        mock_registry_class.resolve_dependencies.assert_called_once_with(
            list(
                mock_registry_class.get_all_configurators.return_value.keys()
            )
        )
