# opentasmania-gitlab-osm-osrm-server/tests/install/test_install_render_data_setup.py
# -*- coding: utf-8 -*-

import sys
from pathlib import Path
from unittest import mock

import pytest

# Add project root to sys.path to allow for direct import of project modules
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# Imports from your project
from installer.main_installer import (
    DATAPROC_OSM2PGSQL_IMPORT_TAG,
    OSM_PBF_DOWNLOAD_TAG,
    main_map_server_entry,
    pbf_path_holder,
)
from setup.config_models import AppSettings


@pytest.fixture
def mock_default_app_settings():
    """Provides a default AppSettings instance for tests."""
    # Create a basic AppSettings instance with sensible defaults
    # Set dev_override_unsafe_password to True to bypass the vm_ip_or_domain check
    return AppSettings(dev_override_unsafe_password=True)


def test_rendering_data_setup_sequence_runs_correct_steps(
    mock_default_app_settings, monkeypatch, caplog
):
    """
    Tests that running the installer with '--render-prep' executes
    the expected steps related to rendering data setup and
    marks the steps as complete.
    """
    # 1. Mock configuration loading and initial setup steps in main_installer
    mock_load_app_settings = mock.Mock(return_value=mock_default_app_settings)
    monkeypatch.setattr(
        "installer.main_installer.load_app_settings", mock_load_app_settings
    )

    mock_initialize_state = mock.Mock()
    monkeypatch.setattr(
        "installer.main_installer.initialize_state_system",
        mock_initialize_state,
    )

    mock_setup_pgpass = mock.Mock()
    monkeypatch.setattr(
        "installer.main_installer.setup_pgpass", mock_setup_pgpass
    )

    mock_get_script_hash_main = mock.Mock(return_value="dummy_main_hash")
    monkeypatch.setattr(
        "installer.main_installer.get_current_script_hash",
        mock_get_script_hash_main,
    )

    mock_get_script_hash_state_mgr = mock.Mock(
        return_value="dummy_state_hash"
    )
    monkeypatch.setattr(
        "setup.state_manager.common_get_current_script_hash",
        mock_get_script_hash_state_mgr,
    )

    # Mock os.geteuid for non-root simulation in main_installer log messages
    monkeypatch.setattr("os.geteuid", mock.Mock(return_value=1000))

    # 2. Mock step execution helpers (used by execute_step)
    monkeypatch.setattr(
        "setup.step_executor.is_step_completed", mock.Mock(return_value=False)
    )  # Assume step not done
    mock_mark_step_completed = mock.Mock()
    monkeypatch.setattr(
        "setup.step_executor.mark_step_completed", mock_mark_step_completed
    )
    # Ensure cli_prompt_for_rerun is mocked if is_step_completed returns True
    monkeypatch.setattr(
        "installer.main_installer.cli_prompt_for_rerun",
        mock.Mock(return_value=False),
    )

    # 3. Mock functions called by the rendering_data_setup_sequence
    mock_download_base_pbf = mock.Mock(return_value="/path/to/downloaded.pbf")
    monkeypatch.setattr(
        "installer.main_installer.download_base_pbf",
        mock_download_base_pbf,
    )

    mock_import_pbf_to_postgis = mock.Mock(return_value=True)
    monkeypatch.setattr(
        "installer.main_installer.import_pbf_to_postgis_with_osm2pgsql",
        mock_import_pbf_to_postgis,
    )

    # Reset the pbf_path_holder to ensure it's empty before the test
    pbf_path_holder["path"] = None

    # 4. Execute the installer with the --render-prep flag
    cli_args = ["--render-prep"]
    exit_code = main_map_server_entry(cli_args)

    # 5. Assertions
    assert exit_code == 0, (
        f"Installer exited with {exit_code} instead of 0 for --render-prep"
    )

    # Verify that main_installer's initial setup functions were called
    mock_load_app_settings.assert_called_once()
    mock_initialize_state.assert_called_once_with(
        mock_default_app_settings, mock.ANY
    )  # Logger is passed
    mock_setup_pgpass.assert_called_once_with(
        mock_default_app_settings, mock.ANY
    )  # Logger is passed

    # Verify that download_base_pbf was called
    mock_download_base_pbf.assert_called_once_with(
        mock_default_app_settings, mock.ANY
    )

    # Verify that import_pbf_to_postgis_with_osm2pgsql was called with the correct path
    mock_import_pbf_to_postgis.assert_called_once_with(
        "/path/to/downloaded.pbf", mock_default_app_settings, mock.ANY
    )

    # Verify that the steps were marked as completed
    mock_mark_step_completed.assert_any_call(
        OSM_PBF_DOWNLOAD_TAG,
        app_settings=mock_default_app_settings,
        current_logger=mock.ANY,
    )
    mock_mark_step_completed.assert_any_call(
        DATAPROC_OSM2PGSQL_IMPORT_TAG,
        app_settings=mock_default_app_settings,
        current_logger=mock.ANY,
    )

    # Verify that the pbf_path_holder was updated
    assert pbf_path_holder["path"] == "/path/to/downloaded.pbf"


def test_rendering_data_setup_sequence_reuses_existing_pbf(
    mock_default_app_settings, monkeypatch, caplog
):
    """
    Tests that the rendering_data_setup_sequence reuses an existing PBF file
    if one is already available in the pbf_path_holder.
    """
    # 1. Mock configuration loading and initial setup steps in main_installer
    mock_load_app_settings = mock.Mock(return_value=mock_default_app_settings)
    monkeypatch.setattr(
        "installer.main_installer.load_app_settings", mock_load_app_settings
    )

    mock_initialize_state = mock.Mock()
    monkeypatch.setattr(
        "installer.main_installer.initialize_state_system",
        mock_initialize_state,
    )

    mock_setup_pgpass = mock.Mock()
    monkeypatch.setattr(
        "installer.main_installer.setup_pgpass", mock_setup_pgpass
    )

    mock_get_script_hash_main = mock.Mock(return_value="dummy_main_hash")
    monkeypatch.setattr(
        "installer.main_installer.get_current_script_hash",
        mock_get_script_hash_main,
    )

    mock_get_script_hash_state_mgr = mock.Mock(
        return_value="dummy_state_hash"
    )
    monkeypatch.setattr(
        "setup.state_manager.common_get_current_script_hash",
        mock_get_script_hash_state_mgr,
    )

    # Mock os.geteuid for non-root simulation in main_installer log messages
    monkeypatch.setattr("os.geteuid", mock.Mock(return_value=1000))

    # 2. Mock step execution helpers (used by execute_step)
    monkeypatch.setattr(
        "setup.step_executor.is_step_completed", mock.Mock(return_value=False)
    )  # Assume step not done
    mock_mark_step_completed = mock.Mock()
    monkeypatch.setattr(
        "setup.step_executor.mark_step_completed", mock_mark_step_completed
    )
    # Ensure cli_prompt_for_rerun is mocked if is_step_completed returns True
    monkeypatch.setattr(
        "installer.main_installer.cli_prompt_for_rerun",
        mock.Mock(return_value=False),
    )

    # 3. Mock functions called by the rendering_data_setup_sequence
    mock_download_base_pbf = mock.Mock(return_value="/path/to/new.pbf")
    monkeypatch.setattr(
        "installer.main_installer.download_base_pbf",
        mock_download_base_pbf,
    )

    mock_import_pbf_to_postgis = mock.Mock(return_value=True)
    monkeypatch.setattr(
        "installer.main_installer.import_pbf_to_postgis_with_osm2pgsql",
        mock_import_pbf_to_postgis,
    )

    # Set the pbf_path_holder to simulate an existing PBF file
    pbf_path_holder["path"] = "/path/to/existing.pbf"

    # 4. Execute the installer with the --render-prep flag
    cli_args = ["--render-prep"]
    exit_code = main_map_server_entry(cli_args)

    # 5. Assertions
    assert exit_code == 0, (
        f"Installer exited with {exit_code} instead of 0 for --render-prep"
    )

    # Verify that download_base_pbf was NOT called
    mock_download_base_pbf.assert_not_called()

    # Verify that import_pbf_to_postgis_with_osm2pgsql was called with the existing path
    mock_import_pbf_to_postgis.assert_called_once_with(
        "/path/to/existing.pbf", mock_default_app_settings, mock.ANY
    )

    # Verify that the steps were marked as completed
    mock_mark_step_completed.assert_any_call(
        OSM_PBF_DOWNLOAD_TAG,
        app_settings=mock_default_app_settings,
        current_logger=mock.ANY,
    )
    mock_mark_step_completed.assert_any_call(
        DATAPROC_OSM2PGSQL_IMPORT_TAG,
        app_settings=mock_default_app_settings,
        current_logger=mock.ANY,
    )

    # Verify that the pbf_path_holder was not changed
    assert pbf_path_holder["path"] == "/path/to/existing.pbf"


def test_rendering_data_setup_sequence_handles_import_failure(
    mock_default_app_settings, monkeypatch, caplog
):
    """
    Tests that the rendering_data_setup_sequence handles failures in the
    import_pbf_to_postgis_with_osm2pgsql function.
    """
    # 1. Mock configuration loading and initial setup steps in main_installer
    mock_load_app_settings = mock.Mock(return_value=mock_default_app_settings)
    monkeypatch.setattr(
        "installer.main_installer.load_app_settings", mock_load_app_settings
    )

    mock_initialize_state = mock.Mock()
    monkeypatch.setattr(
        "installer.main_installer.initialize_state_system",
        mock_initialize_state,
    )

    mock_setup_pgpass = mock.Mock()
    monkeypatch.setattr(
        "installer.main_installer.setup_pgpass", mock_setup_pgpass
    )

    mock_get_script_hash_main = mock.Mock(return_value="dummy_main_hash")
    monkeypatch.setattr(
        "installer.main_installer.get_current_script_hash",
        mock_get_script_hash_main,
    )

    mock_get_script_hash_state_mgr = mock.Mock(
        return_value="dummy_state_hash"
    )
    monkeypatch.setattr(
        "setup.state_manager.common_get_current_script_hash",
        mock_get_script_hash_state_mgr,
    )

    # Mock os.geteuid for non-root simulation in main_installer log messages
    monkeypatch.setattr("os.geteuid", mock.Mock(return_value=1000))

    # 2. Mock step execution helpers (used by execute_step)
    monkeypatch.setattr(
        "setup.step_executor.is_step_completed", mock.Mock(return_value=False)
    )  # Assume step not done
    mock_mark_step_completed = mock.Mock()
    monkeypatch.setattr(
        "setup.step_executor.mark_step_completed", mock_mark_step_completed
    )
    # Ensure cli_prompt_for_rerun is mocked if is_step_completed returns True
    monkeypatch.setattr(
        "installer.main_installer.cli_prompt_for_rerun",
        mock.Mock(return_value=False),
    )

    # 3. Mock functions called by the rendering_data_setup_sequence
    mock_download_base_pbf = mock.Mock(return_value="/path/to/downloaded.pbf")
    monkeypatch.setattr(
        "installer.main_installer.download_base_pbf",
        mock_download_base_pbf,
    )

    # Simulate a failure in import_pbf_to_postgis_with_osm2pgsql
    mock_import_pbf_to_postgis = mock.Mock(return_value=False)
    monkeypatch.setattr(
        "installer.main_installer.import_pbf_to_postgis_with_osm2pgsql",
        mock_import_pbf_to_postgis,
    )

    # Reset the pbf_path_holder to ensure it's empty before the test
    pbf_path_holder["path"] = None

    # 4. Execute the installer with the --render-prep flag
    cli_args = ["--render-prep"]
    exit_code = main_map_server_entry(cli_args)

    # 5. Assertions
    assert exit_code == 1, (
        f"Installer exited with {exit_code} instead of 1 for --render-prep with import failure"
    )

    # Verify that download_base_pbf was called
    mock_download_base_pbf.assert_called_once_with(
        mock_default_app_settings, mock.ANY
    )

    # Verify that import_pbf_to_postgis_with_osm2pgsql was called
    mock_import_pbf_to_postgis.assert_called_once_with(
        "/path/to/downloaded.pbf", mock_default_app_settings, mock.ANY
    )

    # Verify that only the download step was marked as completed
    mock_mark_step_completed.assert_called_once_with(
        OSM_PBF_DOWNLOAD_TAG,
        app_settings=mock_default_app_settings,
        current_logger=mock.ANY,
    )
    # The import step should not be marked as completed
    assert not any(
        call[0][0] == DATAPROC_OSM2PGSQL_IMPORT_TAG
        for call in mock_mark_step_completed.call_args_list
    )

    # Verify that the pbf_path_holder was updated
    assert pbf_path_holder["path"] == "/path/to/downloaded.pbf"
