# File: tests/test_nodejs_installer.py
from unittest.mock import Mock, patch

import pytest

from installer.nodejs_installer import install_nodejs_lts
from setup.config_models import AppSettings


@pytest.fixture
def mock_app_settings():
    """Fixture for creating a mock AppSettings object."""
    return Mock(
        spec=AppSettings,
        symbols={"step": "➡️", "gear": "⚙️", "error": "❌", "success": "✅"},
    )


@pytest.fixture
def mock_logger():
    """Fixture for creating a mock logger."""
    return Mock()


@patch("installer.nodejs_installer.log_map_server")
@patch("installer.nodejs_installer.run_command")
@patch("installer.nodejs_installer.run_elevated_command")
def test_install_nodejs_lts_success(
    mock_run_elevated_command,
    mock_run_command,
    mock_log_map_server,
    mock_app_settings,
    mock_logger,
):
    """Test that install_nodejs_lts runs successfully without exceptions."""
    mock_run_command.return_value.stdout = "Script executed successfully"
    mock_run_command.return_value.returncode = 0
    mock_run_elevated_command.return_value.returncode = 0

    install_nodejs_lts(mock_app_settings, current_logger=mock_logger)

    mock_log_map_server.assert_called()
    mock_run_command.assert_called()
    mock_run_elevated_command.assert_called()


@patch("installer.nodejs_installer.log_map_server")
@patch("installer.nodejs_installer.run_command")
@patch("installer.nodejs_installer.run_elevated_command")
def test_install_nodejs_lts_command_failure(
    mock_run_elevated_command,
    mock_run_command,
    mock_log_map_server,
    mock_app_settings,
    mock_logger,
):
    """Test that install_nodejs_lts logs error when a command fails."""
    mock_run_command.side_effect = Exception("Command failed")

    with pytest.raises(Exception, match="Command failed"):
        install_nodejs_lts(mock_app_settings, current_logger=mock_logger)

    mock_log_map_server.assert_called_with(
        "❌ Failed to install Node.js LTS: Command failed",
        "error",
        mock_logger,
        mock_app_settings,
        exc_info=True,
    )
    mock_run_command.assert_called()


@patch("installer.nodejs_installer.log_map_server")
@patch("installer.nodejs_installer.run_command")
@patch("installer.nodejs_installer.run_elevated_command")
def test_install_nodejs_lts_no_logger(
    mock_run_elevated_command,
    mock_run_command,
    mock_log_map_server,
    mock_app_settings,
):
    """Test that install_nodejs_lts uses default logger if none is provided."""
    mock_run_command.return_value.stdout = "Output"
    mock_run_elevated_command.return_value.returncode = 0

    install_nodejs_lts(mock_app_settings)

    mock_log_map_server.assert_called()
    mock_run_command.assert_called()
    mock_run_elevated_command.assert_called()
