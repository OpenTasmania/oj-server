# opentasmania-gitlab-osm-osrm-server/tests/test_install_boot_verbosity.py
# -*- coding: utf-8 -*-

import sys
from pathlib import Path
from unittest import mock

import pytest

# Add project root to sys.path to allow for direct import of project modules
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Imports from your project
from installer.main_installer import (
    PREREQ_BOOT_VERBOSITY_TAG,
    main_map_server_entry,
)
from setup.config_models import AppSettings

# The actual function being tested is indirectly called, but we'll verify its effects
# from setup.core_prerequisites import boot_verbosity as actual_boot_verbosity_func


@pytest.fixture
def mock_default_app_settings():
    """Provides a default AppSettings instance for tests."""
    # Create a basic AppSettings instance. If specific fields are accessed by
    # the parts of main_installer.py that run before the step execution,
    # ensure they have sensible defaults or are mocked appropriately.
    # Set dev_override_unsafe_password to True to bypass the vm_ip_or_domain check
    return AppSettings(dev_override_unsafe_password=True)


def test_boot_verbosity_switch_runs_correct_commands(
    mock_default_app_settings, monkeypatch, caplog
):
    """
    Tests that running the installer with '--boot-verbosity' executes
    the expected system commands related to boot verbosity setup and
    marks the step as complete.
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

    # 3. Mock functions and utilities called BY the boot_verbosity task itself
    #    These are located in setup.core_prerequisites
    mock_run_elevated_cmd_in_core = mock.Mock(
        return_value=mock.Mock(returncode=0, stdout="", stderr="")
    )
    monkeypatch.setattr(
        "setup.core_prerequisites.run_elevated_command",
        mock_run_elevated_cmd_in_core,
    )

    mock_backup_file_in_core = mock.Mock(
        return_value=True
    )  # Assume backup is successful
    monkeypatch.setattr(
        "setup.core_prerequisites.backup_file", mock_backup_file_in_core
    )

    mock_getpass_getuser_in_core = mock.Mock(return_value="testuser")
    monkeypatch.setattr(
        "setup.core_prerequisites.getpass.getuser",
        mock_getpass_getuser_in_core,
    )

    # 4. Execute the installer with the --boot-verbosity flag
    cli_args = ["--boot-verbosity"]
    exit_code = main_map_server_entry(cli_args)

    # 5. Assertions
    assert exit_code == 0, (
        f"Installer exited with {exit_code} instead of 0 for --boot-verbosity"
    )

    # Verify that main_installer's initial setup functions were called
    mock_load_app_settings.assert_called_once()
    mock_initialize_state.assert_called_once_with(
        mock_default_app_settings, mock.ANY
    )  # Logger is passed
    mock_setup_pgpass.assert_called_once_with(
        mock_default_app_settings, mock.ANY
    )  # Logger is passed

    # Verify that backup_file was called by boot_verbosity logic
    mock_backup_file_in_core.assert_called_once_with(
        "/etc/default/grub",
        mock_default_app_settings,
        current_logger=mock.ANY,
    )

    # Verify the sequence of commands that boot_verbosity should have called
    # via the mocked run_elevated_command in setup.core_prerequisites

    # Check for the sed command
    sed_call_found = False
    for call_args_tuple in mock_run_elevated_cmd_in_core.call_args_list:
        args, kwargs = (
            call_args_tuple  # Use .args and .kwargs as per mock documentation
        )
        cmd_list = args[0]
        if cmd_list[0] == "sed" and cmd_list[-1] == "/etc/default/grub":
            sed_call_found = True
            assert cmd_list[1] == "-i"
            # Check if at least one of the expected sed expressions is present
            assert any(
                r"/^GRUB_CMDLINE_LINUX_DEFAULT=/s/\bquiet\b//g" in item
                for item in cmd_list
            )
            assert any(
                r"/^GRUB_CMDLINE_LINUX_DEFAULT=/s/\bsplash\b//g" in item
                for item in cmd_list
            )
            break
    assert sed_call_found, (
        "Expected 'sed' command to modify /etc/default/grub was not called."
    )

    # Check for other commands
    mock_run_elevated_cmd_in_core.assert_any_call(
        ["update-grub"], mock_default_app_settings, current_logger=mock.ANY
    )
    mock_run_elevated_cmd_in_core.assert_any_call(
        ["update-initramfs", "-u"],
        mock_default_app_settings,
        current_logger=mock.ANY,
    )
    mock_run_elevated_cmd_in_core.assert_any_call(
        ["usermod", "-aG", "systemd-journal", "testuser"],
        mock_default_app_settings,
        current_logger=mock.ANY,
    )

    # Verify that getpass.getuser was called
    mock_getpass_getuser_in_core.assert_called_once()

    # Verify that the step was marked as completed
    mock_mark_step_completed.assert_called_once_with(
        PREREQ_BOOT_VERBOSITY_TAG,  # Use the imported constant
        app_settings=mock_default_app_settings,
        current_logger=mock.ANY,
    )
