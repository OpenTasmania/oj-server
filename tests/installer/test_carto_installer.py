from pathlib import Path
from unittest.mock import MagicMock

import pytest

from common.command_utils import (
    command_exists,
    log_map_server,
    run_elevated_command,
)
from installer.carto_installer import (
    fetch_carto_external_data,
    install_carto_cli,
)
from setup.config_models import AppSettings


@pytest.fixture
def mock_app_settings():
    """Fixture to create a mock of AppSettings."""
    app_settings = AppSettings()
    app_settings.symbols = {"step": "➡️", "error": "❌", "success": "✅"}
    return app_settings


def test_install_carto_cli_success(mocker, mock_app_settings):
    """Test install_carto_cli function when installation succeeds."""
    mock_logger = mocker.MagicMock()
    mocker.patch("common.command_utils.command_exists", return_value=True)
    mocker.patch("common.command_utils.run_elevated_command")
    mocker.patch(
        "common.command_utils.run_command",
        return_value=MagicMock(stdout="1.2.3", returncode=0),
    )
    mocker.patch("common.command_utils.log_map_server")

    install_carto_cli(mock_app_settings, mock_logger)

    command_exists.assert_called_once_with("npm")
    run_elevated_command.assert_called_once_with(
        ["npm", "install", "-g", "carto"],
        mock_app_settings,
        current_logger=mock_logger,
    )
    log_map_server.assert_called()

    def test_fetch_carto_external_data_custom_script(
        mocker, mock_app_settings
    ):
        """Test fetch_carto_external_data function when custom script is used."""

    mock_logger = mocker.MagicMock()
    mock_script_path = mocker.patch(
        "installer.carto_installer.static_config.OSM_PROJECT_ROOT",
        return_value=Path("/custom/path"),
    )
    mock_custom_script_valid = mocker.patch(
        "installer.carto_installer.Path.is_file", return_value=True
    )
    mock_run_command = mocker.patch("common.command_utils.run_command")
    mock_log = mocker.patch("common.command_utils.log_map_server")

    fetch_carto_external_data(mock_app_settings, mock_logger)

    mock_script_path.assert_called_once()
    mock_custom_script_valid.assert_called_once()
    mock_run_command.assert_called_once()
    mock_log.assert_called()

    def test_fetch_carto_external_data_no_scripts(mocker, mock_app_settings):
        """Test fetch_carto_external_data function when no scripts are found."""

    mock_logger = mocker.MagicMock()
    mocker.patch("installer.carto_installer.Path.is_file", return_value=False)
    mock_log = mocker.patch("common.command_utils.log_map_server")

    with pytest.raises(FileNotFoundError):
        fetch_carto_external_data(mock_app_settings, mock_logger)

    mock_log.assert_called_with(
        mocker.ANY, "critical", mock_logger, mock_app_settings
    )


def test_install_carto_cli_npm_not_found(mocker, mock_app_settings):
    """Test install_carto_cli function when npm is not found."""
    mock_logger = mocker.MagicMock()
    mocker.patch("common.command_utils.command_exists", return_value=False)
    mock_log = mocker.patch("common.command_utils.log_map_server")

    with pytest.raises(EnvironmentError):
        install_carto_cli(mock_app_settings, mock_logger)

    command_exists.assert_called_once_with("npm")
    mock_log.assert_called_with(
        "❌ NPM (Node Package Manager) not found. Node.js needs to be installed first. Skipping carto CLI install.",
        "error",
        mock_logger,
        mock_app_settings,
    )


def test_install_carto_cli_failure(mocker, mock_app_settings):
    """Test install_carto_cli function when installation fails."""
    mock_logger = mocker.MagicMock()
    mocker.patch("common.command_utils.command_exists", return_value=True)
    mocker.patch(
        "common.command_utils.run_elevated_command",
        side_effect=RuntimeError("Installation error"),
    )
    mock_log = mocker.patch("common.command_utils.log_map_server")

    with pytest.raises(RuntimeError):
        install_carto_cli(mock_app_settings, mock_logger)

    command_exists.assert_called_once_with("npm")
    run_elevated_command.assert_called_once()
    mock_log.assert_called_with(
        "❌ Failed to install 'carto' via npm: Installation error. Check npm/Node.js.",
        "error",
        mock_logger,
        mock_app_settings,
    )
