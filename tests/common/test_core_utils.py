import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from common.core_utils import SymbolFormatter, setup_logging


@pytest.fixture
def mock_root_logger(mocker):
    """Fixture to mock the root logger."""
    mock_logger = MagicMock()
    mocker.patch("logging.getLogger", return_value=mock_logger)
    mock_logger.handlers = []
    return mock_logger


def test_setup_logging_with_file_and_console(mocker):
    """Test setup_logging when both log_file and log_to_console are provided."""
    # Mock the handlers and formatter
    mock_file_handler = mocker.patch("logging.FileHandler")
    mock_stream_handler = mocker.patch("logging.StreamHandler")
    mock_formatter = mocker.patch("common.core_utils.SymbolFormatter")

    # Mock the root logger
    mock_root_logger = MagicMock()
    mocker.patch("logging.getLogger", return_value=mock_root_logger)
    mock_root_logger.handlers = []

    log_file_path = str(Path("logs/test.log"))

    setup_logging(log_file=log_file_path, log_to_console=True)

    # Check that the handlers were created correctly
    mock_file_handler.assert_called_once_with(Path(log_file_path), mode="a")
    mock_stream_handler.assert_called_once_with(sys.stdout)

    # Check that the formatter was created
    assert mock_formatter.call_count == 1

    # Check that the handlers were added to the root logger
    assert mock_root_logger.addHandler.call_count == 2


def test_setup_logging_without_handlers(mocker):
    """Test setup_logging when no handlers are provided."""
    # Mock the handlers and formatter
    mock_stream_handler = mocker.patch("logging.StreamHandler")
    mock_formatter = mocker.patch("common.core_utils.SymbolFormatter")

    # Mock the root logger
    mock_root_logger = MagicMock()
    mocker.patch("logging.getLogger", return_value=mock_root_logger)
    mock_root_logger.handlers = []

    setup_logging(log_to_console=False, log_file=None)

    # Check that a default handler was created
    mock_stream_handler.assert_called_once_with(sys.stdout)

    # Check that the formatter was created
    assert mock_formatter.call_count == 1

    # Check that the handler was added to the root logger
    assert mock_root_logger.addHandler.call_count == 1


def test_setup_logging_with_custom_format(mocker):
    """Test setup_logging with a custom log format."""

    mock_formatter = mocker.patch("common.core_utils.SymbolFormatter")

    # Mock the root logger
    mock_root_logger = MagicMock()
    mocker.patch("logging.getLogger", return_value=mock_root_logger)
    mock_root_logger.handlers = []

    custom_format = "{log_prefix}%(asctime)s - %(levelname)s - %(message)s"
    custom_prefix = "[TestPrefix]"

    setup_logging(log_format_str=custom_format, log_prefix=custom_prefix)

    expected_format = custom_format.format(log_prefix=custom_prefix + " ")

    # Check that the formatter was created with the expected format
    mock_formatter.assert_called_once_with(
        fmt=expected_format,
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def test_setup_logging_with_default_level(mocker):
    """Test setup_logging with default logging level."""

    mock_root_logger = MagicMock()
    mocker.patch("logging.getLogger", return_value=mock_root_logger)
    mock_root_logger.handlers = []

    setup_logging()

    mock_root_logger.setLevel.assert_called_once_with(logging.INFO)


def test_setup_logging_warning_on_file_handler_failure(capsys, mocker):
    """Test setup_logging gracefully handles file handler creation failure."""
    mocker.patch(
        "logging.FileHandler", side_effect=Exception("An error occurred")
    )

    # Mock the root logger
    mock_root_logger = MagicMock()
    mocker.patch("logging.getLogger", return_value=mock_root_logger)
    mock_root_logger.handlers = []

    setup_logging(log_file="invalid/path.log")
    captured = capsys.readouterr()

    assert (
        "Warning: Could not create file handler for log file" in captured.err
    )


def test_symbol_formatter():
    """Test that the SymbolFormatter adds the correct symbols."""
    formatter = SymbolFormatter(fmt="%(symbol)s %(message)s")

    debug_record = logging.LogRecord(
        name="test",
        level=logging.DEBUG,
        pathname="",
        lineno=0,
        msg="Debug message",
        args=(),
        exc_info=None,
    )
    info_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Info message",
        args=(),
        exc_info=None,
    )
    warning_record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname="",
        lineno=0,
        msg="Warning message",
        args=(),
        exc_info=None,
    )
    error_record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="",
        lineno=0,
        msg="Error message",
        args=(),
        exc_info=None,
    )
    critical_record = logging.LogRecord(
        name="test",
        level=logging.CRITICAL,
        pathname="",
        lineno=0,
        msg="Critical message",
        args=(),
        exc_info=None,
    )

    # Format the records and check that the correct symbols were added
    assert "🐛" in formatter.format(debug_record)
    assert "ℹ️" in formatter.format(info_record)
    assert "⚠️" in formatter.format(warning_record)
    assert "❌" in formatter.format(error_record)
    assert "🔥" in formatter.format(critical_record)
