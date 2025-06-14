import logging
from subprocess import CalledProcessError

from pytest_mock import MockerFixture

from common.file_utils import backup_file
from setup.config_models import AppSettings


def test_backup_file_success(mocker: MockerFixture):
    """Test successful backup of a file."""
    mock_run_elevated_command = mocker.patch(
        "common.file_utils.run_elevated_command"
    )
    mock_log_map_server = mocker.patch("common.file_utils.log_map_server")

    app_settings = AppSettings()
    file_path = "/path/to/file.txt"

    # Mock successful file existence and backup
    mock_run_elevated_command.side_effect = [
        None,  # File existence check
        None,  # Backup operation
    ]

    result = backup_file(file_path, app_settings)

    mock_run_elevated_command.assert_called()
    mock_log_map_server.assert_called_with(
        mocker.ANY, "success", mocker.ANY, app_settings
    )
    assert result is True


def test_backup_file_nonexistent(mocker: MockerFixture):
    """Test when file doesn't exist, no backup needed."""
    mock_run_elevated_command = mocker.patch(
        "common.file_utils.run_elevated_command"
    )
    mock_log_map_server = mocker.patch("common.file_utils.log_map_server")

    app_settings = AppSettings()
    file_path = "/path/to/nonexistent_file.txt"

    # Mock file not existing
    mock_run_elevated_command.side_effect = [
        CalledProcessError(1, ["test", "-f", file_path])
    ]

    result = backup_file(file_path, app_settings)

    mock_run_elevated_command.assert_called_once()
    mock_log_map_server.assert_called_with(
        mocker.ANY, "info", mocker.ANY, app_settings
    )
    assert result is True


def test_backup_file_failure(mocker: MockerFixture):
    """Test backup failure due to an error."""
    mock_run_elevated_command = mocker.patch(
        "common.file_utils.run_elevated_command"
    )
    mock_log_map_server = mocker.patch("common.file_utils.log_map_server")

    app_settings = AppSettings()
    current_logger = logging.getLogger("test_logger")
    file_path = "/path/to/file.txt"

    # Mock file existence check success, but backup fails
    mock_run_elevated_command.side_effect = [
        None,  # File existence check
        Exception("Backup failed"),  # Backup operation fails
    ]

    result = backup_file(file_path, app_settings, current_logger)

    assert mock_run_elevated_command.call_count == 2
    mock_log_map_server.assert_called_with(
        mocker.ANY, "error", current_logger, app_settings
    )
    assert result is False


def test_backup_file_no_app_settings(mocker: MockerFixture):
    """Test backup file with no app_settings provided."""
    mock_run_elevated_command = mocker.patch(
        "common.file_utils.run_elevated_command"
    )
    mock_log_map_server = mocker.patch("common.file_utils.log_map_server")

    file_path = "/path/to/file.txt"

    # Mock successful file existence and backup
    mock_run_elevated_command.side_effect = [
        None,  # File existence check
        None,  # Backup operation
    ]

    result = backup_file(file_path, None)

    mock_run_elevated_command.assert_called()
    mock_log_map_server.assert_called_with(
        mocker.ANY, "success", mocker.ANY, None
    )
    assert result is True
