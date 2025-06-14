import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from common.core_utils import setup_logging


@pytest.fixture
def mock_basic_config(mocker):
    """Fixture to mock logging.basicConfig."""
    return mocker.patch("logging.basicConfig")


@pytest.fixture
def mock_logger(mocker):
    """Fixture to mock the logger."""
    return mocker.patch("logging.getLogger")


def test_setup_logging_with_file_and_console(mock_basic_config, mocker):
    """Test setup_logging when both log_file and log_to_console are provided."""
    mock_file_handler = mocker.patch("logging.FileHandler")
    log_file_path = str(Path("logs/test.log"))

    setup_logging(log_file=log_file_path, log_to_console=True)

    mock_file_handler.assert_called_once_with(Path(log_file_path), mode="a")
    assert mock_basic_config.call_count == 1


def test_setup_logging_without_handlers(mock_basic_config, mocker):
    """Test setup_logging when no handlers are provided."""
    mock_stream_handler = mocker.patch("logging.StreamHandler")
    mock_stream_handler_instance = MagicMock()
    mock_stream_handler.return_value = mock_stream_handler_instance

    setup_logging(log_to_console=False, log_file=None)

    mock_stream_handler.assert_called_once_with(sys.stdout)
    assert mock_basic_config.call_count == 1


def test_setup_logging_with_custom_format(mock_basic_config, mocker):
    """Test setup_logging with a custom log format."""
    custom_format = "{log_prefix}%(asctime)s - %(levelname)s - %(message)s"
    custom_prefix = "[TestPrefix]"

    setup_logging(log_format_str=custom_format, log_prefix=custom_prefix)

    expected_format = custom_format.format(log_prefix=custom_prefix + " ")
    mock_basic_config.assert_called_once_with(
        level=logging.INFO,
        format=expected_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=mocker.ANY,
        force=True,
    )


def test_setup_logging_with_default_level(mock_basic_config, mocker):
    """Test setup_logging with default logging level."""
    setup_logging()

    mock_basic_config.assert_called_once_with(
        level=logging.INFO,
        format=mocker.ANY,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=mocker.ANY,
        force=True,
    )


def test_setup_logging_warning_on_file_handler_failure(
    mock_basic_config, capsys, mocker
):
    """Test setup_logging gracefully handles file handler creation failure."""
    mocker.patch(
        "logging.FileHandler", side_effect=Exception("An error occurred")
    )

    setup_logging(log_file="invalid/path.log")
    captured = capsys.readouterr()

    assert (
        "Warning: Could not create file handler for log file" in captured.err
    )
