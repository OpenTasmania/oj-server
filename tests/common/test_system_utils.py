import logging
import subprocess
from unittest.mock import Mock

from common.system_utils import (
    get_current_script_hash,
    get_debian_codename,
    get_primary_ip_address,
)
from setup.config_models import AppSettings


def test_get_current_script_hash_error_handling(mocker):
    """Test that get_current_script_hash returns None when there is an error."""
    mock_calculate_project_hash = mocker.patch(
        "common.system_utils.calculate_project_hash"
    )
    mock_calculate_project_hash.side_effect = Exception("Mocked exception")

    project_root_dir = mocker.Mock()
    app_settings = AppSettings()
    logger = logging.getLogger("test_logger")

    result = get_current_script_hash(
        project_root_dir=project_root_dir,
        app_settings=app_settings,
        logger_instance=logger,
    )

    assert result is None, "Expected None when an error occurs"
    mock_calculate_project_hash.assert_called_once_with(
        project_root_dir, app_settings, current_logger=logger
    )


def test_get_debian_codename_success(mocker):
    """Test that get_debian_codename returns the correct codename."""
    mock_run_command = mocker.patch("common.system_utils.run_command")
    mock_run_command.return_value = Mock(stdout="bookworm\n")

    app_settings = Mock()
    logger = logging.getLogger("test_logger")
    result = get_debian_codename(
        app_settings=app_settings, current_logger=logger
    )

    assert result == "bookworm", f"Expected 'bookworm', got '{result}'"
    mock_run_command.assert_called_once_with(
        ["lsb_release", "-cs"],
        app_settings,
        capture_output=True,
        check=True,
        current_logger=logger,
    )


def test_get_debian_codename_command_not_found(mocker):
    """Test that get_debian_codename handles FileNotFoundError."""
    mock_run_command = mocker.patch("common.system_utils.run_command")
    mock_run_command.side_effect = FileNotFoundError("lsb_release not found")

    app_settings = Mock()
    app_settings.symbols.get.return_value = "!"
    mock_logger = Mock()
    result = get_debian_codename(
        app_settings=app_settings, current_logger=mock_logger
    )

    assert result is None, "Expected None when lsb_release is not found"
    mock_logger.warning.assert_called_once_with(
        "! lsb_release command not found. Cannot determine Debian codename.",
        exc_info=False,
    )


def test_get_debian_codename_command_error(mocker):
    """Test that get_debian_codename handles subprocess.CalledProcessError."""
    mock_run_command = mocker.patch("common.system_utils.run_command")
    mock_run_command.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=["lsb_release", "-cs"]
    )

    app_settings = Mock()
    result = get_debian_codename(app_settings=app_settings)

    assert result is None, "Expected None when the command fails"


def test_get_debian_codename_unexpected_exception(mocker):
    """Test that get_debian_codename handles unexpected exceptions."""
    mock_run_command = mocker.patch("common.system_utils.run_command")
    mock_run_command.side_effect = Exception("Unexpected error")

    app_settings = Mock()
    app_settings.symbols.get.return_value = "!"
    mock_logger = Mock()
    result = get_debian_codename(
        app_settings=app_settings, current_logger=mock_logger
    )

    assert result is None, "Expected None when an unexpected exception occurs"
    mock_logger.warning.assert_called_once_with(
        "! Unexpected error getting Debian codename: Unexpected error",
        exc_info=False,
    )


def test_get_primary_ip_address_successful(mocker):
    """Test that get_primary_ip_address returns a valid IP address."""
    mock_socket = mocker.patch("common.system_utils.socket.socket")
    mock_socket_instance = mock_socket.return_value
    mock_socket_instance.getsockname.return_value = ("192.168.1.1", 0)

    result = get_primary_ip_address()

    assert result == "192.168.1.1", f"Expected '192.168.1.1', got '{result}'"
    mock_socket_instance.connect.assert_called_once_with(("8.8.8.8", 80))
    mock_socket_instance.close.assert_called_once()


def test_get_primary_ip_address_exception(mocker):
    """Test that get_primary_ip_address handles exceptions and returns None."""
    mock_socket = mocker.patch("common.system_utils.socket.socket")
    mock_socket.side_effect = Exception("Mocked exception")

    mock_logger = Mock()
    result = get_primary_ip_address(current_logger=mock_logger)

    assert result is None, "Expected None when exception occurs"
    mock_logger.warning.assert_called_once_with(
        "⚠️ Could not determine primary IP address: Mocked exception",
        exc_info=False,
    )


def test_get_primary_ip_address_custom_logger_and_symbols(mocker):
    """Test that get_primary_ip_address uses custom logger and symbols."""
    mock_socket = mocker.patch("common.system_utils.socket.socket")
    mock_socket.side_effect = Exception("Mocked exception with symbols")

    mock_logger = Mock()
    mock_symbols = {"warning": "!"}
    app_settings = AppSettings(symbols=mock_symbols)

    result = get_primary_ip_address(
        app_settings=app_settings, current_logger=mock_logger
    )

    assert result is None, "Expected None when exception occurs"
    mock_logger.warning.assert_called_once_with(
        "! Could not determine primary IP address: Mocked exception with symbols",
        exc_info=False,
    )


def test_get_primary_ip_address_no_custom_logger_or_symbols(mocker):
    """Test that get_primary_ip_address uses default logger and symbols."""
    mock_socket = mocker.patch("common.system_utils.socket.socket")
    mock_socket.side_effect = Exception("Another mocked exception")

    result = get_primary_ip_address()

    assert result is None, "Expected None when exception occurs"
