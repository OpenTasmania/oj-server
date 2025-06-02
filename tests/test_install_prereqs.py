# opentasmania-gitlab-osm-osrm-server/tests/test_install_prereqs.py
# -*- coding: utf-8 -*-
# tests/test_install_prereqs.py
import sys
from pathlib import Path
from unittest import mock

import pytest

# Add project root to sys.path to allow for direct import of project modules
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Imports from your project
from installer.main_installer import (
    ALL_CORE_PREREQUISITES_GROUP_TAG,
    main_map_server_entry,
)
from setup.config_models import AppSettings

# Import specific tags for sub-steps if you want to be very precise in assertions
from setup.core_prerequisites import (
    PREREQ_BOOT_VERBOSITY_TAG as CORE_PREREQ_BOOT_VERBOSITY_TAG,  # Alias to avoid conflict if main_installer also defines it
)
from setup.core_prerequisites import (
    PREREQ_CORE_CONFLICTS_TAG as CORE_PREREQ_CORE_CONFLICTS_TAG,
)
from setup.core_prerequisites import (
    PREREQ_DOCKER_ENGINE_TAG as CORE_PREREQ_DOCKER_ENGINE_TAG,
)
from setup.core_prerequisites import (
    PREREQ_ESSENTIAL_UTILS_TAG as CORE_PREREQ_ESSENTIAL_UTILS_TAG,
)
from setup.core_prerequisites import (
    PREREQ_MAPPING_FONT_PACKAGES_TAG as CORE_PREREQ_MAPPING_FONT_PACKAGES_TAG,
)
from setup.core_prerequisites import (
    PREREQ_NODEJS_LTS_TAG as CORE_PREREQ_NODEJS_LTS_TAG,
)
from setup.core_prerequisites import (
    PREREQ_POSTGRES_PACKAGES_TAG as CORE_PREREQ_POSTGRES_PACKAGES_TAG,
)
from setup.core_prerequisites import (
    PREREQ_PYTHON_PACKAGES_TAG as CORE_PREREQ_PYTHON_PACKAGES_TAG,
)
from setup.core_prerequisites import (
    PREREQ_UNATTENDED_UPGRADES_TAG as CORE_PREREQ_UNATTENDED_UPGRADES_TAG,
)


@pytest.fixture
def mock_default_app_settings():
    """Provides a default AppSettings instance for tests."""
    return AppSettings()


def test_prereqs_switch_orchestrates_core_prerequisites(
    mock_default_app_settings, monkeypatch, caplog
):
    """
    Tests that running 'main_installer.py --prereqs' correctly orchestrates
    the execution of all defined core prerequisite steps.
    """
    # 1. Mock configuration loading and initial setup steps in main_installer.py
    monkeypatch.setattr(
        "installer.main_installer.load_app_settings",
        mock.Mock(return_value=mock_default_app_settings),
    )
    monkeypatch.setattr(
        "installer.main_installer.initialize_state_system", mock.Mock()
    )
    monkeypatch.setattr("installer.main_installer.setup_pgpass", mock.Mock())
    monkeypatch.setattr(
        "installer.main_installer.get_current_script_hash",
        mock.Mock(return_value="dummy_hash"),
    )
    monkeypatch.setattr(
        "setup.state_manager.common_get_current_script_hash",
        mock.Mock(return_value="dummy_hash"),
    )
    monkeypatch.setattr(
        "os.geteuid", mock.Mock(return_value=1000)
    )  # Simulate non-root

    # 2. Mock interactions for setup.step_executor.execute_step
    #    This mock will apply to ALL calls to execute_step, including the one for the
    #    main --prereqs group and all sub-steps called by core_prerequisites_group.
    mock_is_step_completed = mock.Mock(
        return_value=False
    )  # Assume no steps are completed initially
    monkeypatch.setattr(
        "setup.step_executor.is_step_completed", mock_is_step_completed
    )

    mock_mark_step_completed_all_calls = (
        mock.Mock()
    )  # This will capture all calls
    monkeypatch.setattr(
        "setup.step_executor.mark_step_completed",
        mock_mark_step_completed_all_calls,
    )

    # Mock cli_prompt_for_rerun which is used by execute_step.
    # This needs to be patched where execute_step imports it from, or where main_installer passes it.
    # main_installer passes its own cli_prompt_for_rerun to the first execute_step.
    # core_prerequisites_group passes main_installer.cli_prompt_for_rerun to its internal execute_step calls.
    monkeypatch.setattr(
        "installer.main_installer.cli_prompt_for_rerun",
        mock.Mock(return_value=False),
    )
    # Also patch it in setup.core_prerequisites if it were to directly import and use cli_prompt_for_rerun
    # However, core_prerequisites.py receives the prompt function as an argument to execute_step.

    # 3. Mock the actual prerequisite functions that core_prerequisites_group is supposed to call.
    #    These are patched in their respective modules.
    mock_boot_verbosity = mock.Mock()
    monkeypatch.setattr(
        "setup.core_prerequisites.boot_verbosity", mock_boot_verbosity
    )

    mock_core_conflict_removal = mock.Mock()
    monkeypatch.setattr(
        "setup.core_prerequisites.core_conflict_removal",
        mock_core_conflict_removal,
    )

    mock_install_essential_utilities = mock.Mock()
    monkeypatch.setattr(
        "setup.core_prerequisites.install_essential_utilities",
        mock_install_essential_utilities,
    )

    mock_install_python_system_packages = mock.Mock()
    monkeypatch.setattr(
        "setup.core_prerequisites.install_python_system_packages",
        mock_install_python_system_packages,
    )

    mock_install_postgres_packages = mock.Mock()
    monkeypatch.setattr(
        "setup.core_prerequisites.install_postgres_packages",
        mock_install_postgres_packages,
    )

    mock_install_mapping_and_font_packages = mock.Mock()
    monkeypatch.setattr(
        "setup.core_prerequisites.install_mapping_and_font_packages",
        mock_install_mapping_and_font_packages,
    )

    mock_install_unattended_upgrades = mock.Mock()
    monkeypatch.setattr(
        "setup.core_prerequisites.install_unattended_upgrades",
        mock_install_unattended_upgrades,
    )

    # These are imported into setup.core_prerequisites from installer.*
    mock_install_docker_engine_in_core = mock.Mock()
    monkeypatch.setattr(
        "setup.core_prerequisites.install_docker_engine",
        mock_install_docker_engine_in_core,
    )

    mock_install_nodejs_lts_in_core = mock.Mock()
    monkeypatch.setattr(
        "setup.core_prerequisites.install_nodejs_lts",
        mock_install_nodejs_lts_in_core,
    )

    # 4. Execute main_installer.py with the --prereqs flag
    cli_args = ["--prereqs"]
    exit_code = main_map_server_entry(cli_args)

    # 5. Assertions
    assert exit_code == 0, (
        f"Installer with --prereqs exited with {exit_code} instead of 0"
    )

    # Verify that the mocked prerequisite functions were called
    mock_boot_verbosity.assert_called_once_with(
        mock_default_app_settings, mock.ANY
    )
    mock_core_conflict_removal.assert_called_once_with(
        mock_default_app_settings, mock.ANY
    )
    mock_install_essential_utilities.assert_called_once_with(
        mock_default_app_settings, mock.ANY
    )
    mock_install_python_system_packages.assert_called_once_with(
        mock_default_app_settings, mock.ANY
    )
    mock_install_postgres_packages.assert_called_once_with(
        mock_default_app_settings, mock.ANY
    )
    mock_install_mapping_and_font_packages.assert_called_once_with(
        mock_default_app_settings, mock.ANY
    )
    mock_install_unattended_upgrades.assert_called_once_with(
        mock_default_app_settings, mock.ANY
    )
    mock_install_docker_engine_in_core.assert_called_once_with(
        mock_default_app_settings, mock.ANY
    )
    mock_install_nodejs_lts_in_core.assert_called_once_with(
        mock_default_app_settings, mock.ANY
    )

    # Verify that mark_step_completed was called for each sub-step tag AND the main group tag
    # The tags for sub-steps are defined in core_prerequisites.py (and imported here for assertion)
    expected_sub_step_tags_in_order = [
        CORE_PREREQ_BOOT_VERBOSITY_TAG,
        CORE_PREREQ_CORE_CONFLICTS_TAG,
        CORE_PREREQ_ESSENTIAL_UTILS_TAG,
        CORE_PREREQ_PYTHON_PACKAGES_TAG,
        CORE_PREREQ_POSTGRES_PACKAGES_TAG,
        CORE_PREREQ_MAPPING_FONT_PACKAGES_TAG,
        CORE_PREREQ_UNATTENDED_UPGRADES_TAG,
        CORE_PREREQ_DOCKER_ENGINE_TAG,
        CORE_PREREQ_NODEJS_LTS_TAG,
    ]

    # Construct the expected calls for sub-steps
    expected_mark_complete_calls = [
        mock.call(
            tag,
            app_settings=mock_default_app_settings,
            current_logger=mock.ANY,
        )
        for tag in expected_sub_step_tags_in_order
    ]
    # Add the call for the main group itself, which should happen after all sub-steps
    expected_mark_complete_calls.append(
        mock.call(
            ALL_CORE_PREREQUISITES_GROUP_TAG,
            app_settings=mock_default_app_settings,
            current_logger=mock.ANY,
        )
    )

    # Check all calls to the globally patched mark_step_completed
    mock_mark_step_completed_all_calls.assert_has_calls(
        expected_mark_complete_calls, any_order=False
    )
    assert mock_mark_step_completed_all_calls.call_count == len(
        expected_mark_complete_calls
    )
