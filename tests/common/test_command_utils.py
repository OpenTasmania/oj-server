import logging
import subprocess
from unittest.mock import MagicMock, Mock

import pytest
from pytest_mock import MockerFixture

from common.command_utils import (
    check_package_installed,
    command_exists,
    elevated_command_exists,
    log_map_server,
    run_command,
    run_elevated_command,
)
from setup.config_models import AppSettings


@pytest.fixture
def app_settings():
    """Fixture to provide a basic AppSettings object."""
    return AppSettings(
        admin_group_ip="127.0.0.1",
        gtfs_feed_url="http://localhost/feed",
        vm_ip_or_domain="localhost",
        pg_tileserv_binary_location="/usr/bin/pg_tileserv",
        log_prefix="test_prefix",
        container_runtime_command="docker",
        osrm_image_tag="osrm/tag",
        symbols={
            "warning": "!",
            "gear": "⚙️",
            "error": "❌",
        },
    )


@pytest.fixture
def mock_logger():
    """Fixture to create a mock logger for testing."""
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def mock_app_settings():
    """Fixture to create mock AppSettings for testing."""
    mock_settings = MagicMock(spec=AppSettings)
    mock_settings.symbols = {"error": "❌", "info": "ℹ️", "warning": "!"}
    return mock_settings


@pytest.fixture
def mock_run_elevated_command(mocker):
    return mocker.patch("common.command_utils.run_elevated_command")


@pytest.fixture
def mock_log_map_server(mocker):
    return mocker.patch("common.command_utils.log_map_server")


def test_check_package_installed_success(
    mocker, mock_logger, mock_app_settings
):
    """Test when the package is installed successfully."""
    run_command_mock = mocker.patch(
        "common.command_utils.run_command",
        return_value=MagicMock(returncode=0, stdout="install ok installed"),
    )

    result = check_package_installed(
        "example-package", mock_app_settings, mock_logger
    )

    run_command_mock.assert_called_once_with(
        ["dpkg-query", "-W", "-f='${Status}'", "example-package"],
        mock_app_settings,
        check=False,
        capture_output=True,
        text=True,
        current_logger=mock_logger,
    )
    assert result is True


def test_check_package_installed_not_installed(
    mocker, mock_logger, mock_app_settings
):
    """Test when the package is not installed."""
    run_command_mock = mocker.patch(
        "common.command_utils.run_command",
        return_value=MagicMock(returncode=0, stdout="not installed"),
    )

    result = check_package_installed(
        "example-package", mock_app_settings, mock_logger
    )

    run_command_mock.assert_called_once_with(
        ["dpkg-query", "-W", "-f='${Status}'", "example-package"],
        mock_app_settings,
        check=False,
        capture_output=True,
        text=True,
        current_logger=mock_logger,
    )
    assert result is False


def test_check_package_installed_dpkg_query_not_found(
    mocker, mock_logger, mock_app_settings
):
    """Test when dpkg-query command is not found."""
    mocker.patch(
        "common.command_utils.run_command", side_effect=FileNotFoundError
    )

    result = check_package_installed(
        "example-package", mock_app_settings, mock_logger
    )

    mock_logger.error.assert_called_with(
        "❌ dpkg-query command not found. Cannot check package 'example-package'.",
        exc_info=False,
    )
    assert result is False


def test_check_package_installed_unexpected_error(
    mocker, mock_logger, mock_app_settings
):
    """Test when an unexpected error occurs."""
    mocker.patch(
        "common.command_utils.run_command",
        side_effect=Exception("Unexpected error"),
    )

    result = check_package_installed(
        "example-package", mock_app_settings, mock_logger
    )

    mock_logger.error.assert_called_with(
        "❌ Error checking if package 'example-package' is installed: Unexpected error",
        exc_info=False,
    )
    assert result is False


def test_elevated_command_exists_success(
    mock_run_elevated_command, mock_logger, mock_app_settings
):
    """Test if elevated_command_exists returns True when the command is found."""
    mock_run_elevated_command.return_value = MagicMock()

    result = elevated_command_exists("ls", mock_app_settings, mock_logger)

    assert result is True
    mock_run_elevated_command.assert_called_once_with(
        ["which", "ls"],
        mock_app_settings,
        capture_output=True,
        check=True,
        current_logger=mock_logger,
    )


def test_elevated_command_exists_command_not_found(
    mock_run_elevated_command, mock_logger, mock_app_settings
):
    """Test if elevated_command_exists returns False when the command is not found."""
    mock_run_elevated_command.side_effect = subprocess.CalledProcessError(
        1, "cmd"
    )

    result = elevated_command_exists(
        "fakecommand", mock_app_settings, mock_logger
    )

    assert result is False
    mock_run_elevated_command.assert_called_once_with(
        ["which", "fakecommand"],
        mock_app_settings,
        capture_output=True,
        check=True,
        current_logger=mock_logger,
    )


def test_elevated_command_exists_file_not_found_error(
    mock_run_elevated_command,
    mock_log_map_server,
    mock_logger,
    mock_app_settings,
):
    """Test if elevated_command_exists handles FileNotFoundError correctly."""
    mock_run_elevated_command.side_effect = FileNotFoundError

    result = elevated_command_exists("ls", mock_app_settings, mock_logger)

    assert result is False
    mock_log_map_server.assert_called_once_with(
        "! Could not check for elevated command 'ls' as 'sudo' or 'which' may be missing.",
        "warning",
        mock_logger,
        mock_app_settings,
    )


def test_elevated_command_exists_unexpected_error(
    mock_run_elevated_command,
    mock_log_map_server,
    mock_logger,
    mock_app_settings,
):
    """Test if elevated_command_exists handles unexpected exceptions correctly."""
    mock_run_elevated_command.side_effect = Exception("Unexpected error")

    result = elevated_command_exists("ls", mock_app_settings, mock_logger)

    assert result is False
    mock_log_map_server.assert_called_once_with(
        "! Error checking elevated command 'ls': Unexpected error",
        "warning",
        mock_logger,
        mock_app_settings,
    )


def test_command_exists_when_command_is_available(mocker):
    """Test command_exists returns True when the command is available in PATH."""
    mock_shutil_which = mocker.patch(
        "shutil.which", return_value="/usr/bin/valid_command"
    )
    result = command_exists("valid_command")
    mock_shutil_which.assert_called_once_with("valid_command")
    assert result is True, "Expected True when command exists in PATH"


def test_command_exists_when_command_is_not_available(mocker):
    """Test command_exists returns False when the command is not available in PATH."""
    mock_shutil_which = mocker.patch("shutil.which", return_value=None)
    result = command_exists("invalid_command")
    mock_shutil_which.assert_called_once_with("invalid_command")
    assert result is False, (
        "Expected False when command does not exist in PATH"
    )


def test_command_exists_with_empty_command(mocker):
    """Test command_exists handles an empty string as the command."""
    mock_shutil_which = mocker.patch("shutil.which", return_value=None)
    result = command_exists("")
    mock_shutil_which.assert_called_once_with("")
    assert result is False, "Expected False when empty command is passed"


def test_run_elevated_command_success(mocker):
    """Test that the run_elevated_command function successfully executes a command."""
    mock_run_command = mocker.patch("common.command_utils.run_command")
    mock_run_command.return_value = subprocess.CompletedProcess(
        args=["echo", "test"], returncode=0, stdout="test\n", stderr=""
    )

    logger = logging.getLogger("test_logger")
    app_settings_mock = Mock(spec=AppSettings)
    result = run_elevated_command(
        command=["echo", "test"],
        app_settings=app_settings_mock,
        check=True,
        capture_output=True,
        current_logger=logger,
    )

    mock_run_command.assert_called_once_with(
        ["sudo", "echo", "test"],
        app_settings_mock,
        check=True,
        shell=False,
        capture_output=True,
        text=True,
        cmd_input=None,
        current_logger=logger,
        cwd=None,
        env=None,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "test"


def test_run_elevated_command_failure(mocker):
    """Test that the run_elevated_command function raises an exception on failure when check=True."""
    mock_run_command = mocker.patch(
        "common.command_utils.run_command",
        side_effect=subprocess.CalledProcessError(
            returncode=1, cmd="invalid_command", stderr="Command not found"
        ),
    )

    logger = logging.getLogger("test_logger")
    app_settings_mock = Mock(spec=AppSettings)
    with pytest.raises(subprocess.CalledProcessError):
        run_elevated_command(
            command=["invalid_command"],
            app_settings=app_settings_mock,
            check=True,
            capture_output=True,
            current_logger=logger,
        )

    mock_run_command.assert_called_once_with(
        ["sudo", "invalid_command"],
        app_settings_mock,
        check=True,
        shell=False,
        capture_output=True,
        text=True,
        cmd_input=None,
        current_logger=logger,
        cwd=None,
        env=None,
    )


def test_run_elevated_command_with_input(mocker: MockerFixture):
    """Test that the run_elevated_command function passes standard input to the command."""
    mock_run_command = mocker.patch("common.command_utils.run_command")
    mock_run_command.return_value = subprocess.CompletedProcess(
        args=["cat"], returncode=0, stdout="input\n", stderr=""
    )

    logger = logging.getLogger("test_logger")
    app_settings_mock = Mock(spec=AppSettings)
    result = run_elevated_command(
        command=["cat"],
        app_settings=app_settings_mock,
        cmd_input="input",
        check=True,
        capture_output=True,
        current_logger=logger,
    )

    mock_run_command.assert_called_once_with(
        ["sudo", "cat"],
        app_settings_mock,
        check=True,
        shell=False,
        capture_output=True,
        text=True,
        cmd_input="input",
        current_logger=logger,
        cwd=None,
        env=None,
    )
    assert result.stdout.strip() == "input"


def test_run_command_success(mocker: MockerFixture, app_settings):
    """Test successful execution of run_command."""
    mock_subprocess_run = mocker.patch("subprocess.run")
    mock_subprocess_run.return_value = subprocess.CompletedProcess(
        args=["echo", "test"],
        returncode=0,
        stdout="test",
        stderr="",
    )

    current_logger = logging.getLogger("test_logger")
    result = run_command(
        command=["echo", "test"],
        app_settings=app_settings,
        current_logger=current_logger,
    )

    assert result.returncode == 0
    assert result.stdout == "test"


def test_run_command_failure(mocker: MockerFixture, app_settings):
    """Test failure when run_command returns a non-zero exit code."""
    mocker.patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(
            returncode=1,
            cmd="fail_cmd",
            output="",
            stderr="error occurred",
        ),
    )

    current_logger = logging.getLogger("test_logger")
    with pytest.raises(subprocess.CalledProcessError):
        run_command(
            command="fail_cmd",
            app_settings=app_settings,
            current_logger=current_logger,
        )


def test_run_command_file_not_found(mocker: MockerFixture, app_settings):
    """Test file not found error in run_command."""
    mocker.patch(
        "subprocess.run", side_effect=FileNotFoundError("command not found")
    )

    current_logger = logging.getLogger("test_logger")
    with pytest.raises(FileNotFoundError):
        run_command(
            command="non_existent_cmd",
            app_settings=app_settings,
            current_logger=current_logger,
        )


def test_run_command_with_shell(mocker: MockerFixture, app_settings):
    """Test run_command using shell=True."""
    mock_subprocess_run = mocker.patch("subprocess.run")
    mock_subprocess_run.return_value = subprocess.CompletedProcess(
        args="echo test",
        returncode=0,
        stdout="test",
        stderr="",
    )

    current_logger = logging.getLogger("test_logger")
    result = run_command(
        command="echo test",
        app_settings=app_settings,
        shell=True,
        current_logger=current_logger,
    )

    assert result.returncode == 0
    assert result.stdout == "test"


def test_run_command_with_input(mocker: MockerFixture, app_settings):
    """Test run_command with command input."""
    mock_subprocess_run = mocker.patch("subprocess.run")
    mock_subprocess_run.return_value = subprocess.CompletedProcess(
        args=["cat"],
        returncode=0,
        stdout="input_data",
        stderr="",
    )

    current_logger = logging.getLogger("test_logger")
    result = run_command(
        command=["cat"],
        app_settings=app_settings,
        cmd_input="input_data",
        current_logger=current_logger,
    )

    assert result.returncode == 0
    assert result.stdout == "input_data"


def test_log_map_server_info_level(mocker):
    """Test logging a message at the 'info' level."""
    mock_logger = mocker.Mock(spec=logging.Logger)
    message = "This is an info message"
    log_map_server(message=message, level="info", current_logger=mock_logger)
    mock_logger.info.assert_called_once_with(message, exc_info=False)


def test_log_map_server_warning_level(mocker):
    """Test logging a message at the 'warning' level."""
    mock_logger = mocker.Mock(spec=logging.Logger)
    message = "This is a warning message"
    log_map_server(
        message=message, level="warning", current_logger=mock_logger
    )
    mock_logger.warning.assert_called_once_with(message, exc_info=False)


def test_log_map_server_error_level_with_exception(mocker):
    """Test logging a message at the 'error' level with exception information."""
    mock_logger = mocker.Mock(spec=logging.Logger)
    message = "This is an error message"
    log_map_server(
        message=message,
        level="error",
        current_logger=mock_logger,
        exc_info=True,
    )
    mock_logger.error.assert_called_once_with(message, exc_info=True)


def test_log_map_server_critical_level(mocker):
    """Test logging a message at the 'critical' level."""
    mock_logger = mocker.Mock(spec=logging.Logger)
    message = "This is a critical message"
    log_map_server(
        message=message, level="critical", current_logger=mock_logger
    )
    mock_logger.critical.assert_called_once_with(message, exc_info=False)


def test_log_map_server_debug_level(mocker):
    """Test logging a message at the 'debug' level."""
    mock_logger = mocker.Mock(spec=logging.Logger)
    message = "This is a debug message"
    log_map_server(message=message, level="debug", current_logger=mock_logger)
    mock_logger.debug.assert_called_once_with(message, exc_info=False)


def test_log_map_server_default_logger(mocker):
    """Test logging with the default logger when none is provided."""
    mock_default_logger_instance = MagicMock(spec=logging.Logger)
    mocker.patch(
        "common.command_utils.module_logger", new=mock_default_logger_instance
    )

    message = "Logging with default logger"
    log_map_server(message=message, level="info", current_logger=None)
    mock_default_logger_instance.info.assert_called_once_with(
        message, exc_info=False
    )


def test_log_map_server_with_app_settings(mocker):
    """Test logging with app settings included."""
    mock_logger = mocker.Mock(spec=logging.Logger)
    mock_app_settings = MagicMock(spec=AppSettings)
    message = "Logging with app settings"
    log_map_server(
        message=message,
        level="info",
        current_logger=mock_logger,
        app_settings=mock_app_settings,
    )
    mock_logger.info.assert_called_once_with(message, exc_info=False)
