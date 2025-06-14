import os
from unittest.mock import patch

import pytest

from common.pgpass_utils import setup_pgpass
from setup.config_models import (
    PGPASSWORD_DEFAULT,
    AppSettings,
    PostgresSettings,
)


@pytest.fixture
def mock_app_settings():
    pg_settings = PostgresSettings(
        host="localhost",
        port=5432,
        database="testdb",
        user="testuser",
        password="testpassword",
    )
    return AppSettings(
        pg=pg_settings,
        dev_override_unsafe_password=False,
        symbols={
            "info": "ℹ️",
            "warning": "!",
            "error": "❌",
            "success": "✅",
        },
    )


def test_pgpass_created_successfully(mock_app_settings, mocker):
    mock_logger = mocker.MagicMock()
    mock_user = "testuser"
    mock_home_dir = "/home/testuser"

    with (
        patch("getpass.getuser", return_value=mock_user),
        patch("os.path.expanduser", return_value=mock_home_dir),
        patch("os.path.isdir", return_value=True),
        patch("os.path.isfile", return_value=False),
        patch("builtins.open", mocker.mock_open()) as mock_file,
        patch("os.chmod") as mock_chmod,
    ):
        setup_pgpass(mock_app_settings, current_logger=mock_logger)

        pgpass_path = os.path.join(mock_home_dir, ".pgpass")
        expected_content = "localhost:5432:testdb:testuser:testpassword\n"

        mock_logger.info.assert_called()
        mock_chmod.assert_called_once_with(pgpass_path, 0o600)

        # Assert that the file was opened for writing with the correct content and encoding.
        mock_file.assert_called_once_with(pgpass_path, "w", encoding="utf-8")
        mock_file().write.assert_called_once_with(expected_content)


def test_pgpass_skipped_no_password(mock_app_settings, mocker):
    mock_app_settings.pg.password = None
    mock_logger = mocker.MagicMock()

    setup_pgpass(mock_app_settings, current_logger=mock_logger)

    mock_logger.info.assert_called_with(
        "ℹ️ PGPASSWORD is not set, is default (and dev override is not active), or other issue. .pgpass file not created/updated.",
        exc_info=False,
    )


def test_pgpass_default_password_dev_override(mock_app_settings, mocker):
    mock_app_settings.pg.password = PGPASSWORD_DEFAULT
    mock_app_settings.dev_override_unsafe_password = True
    mock_logger = mocker.MagicMock()
    mock_user = "testuser"
    mock_home_dir = "/home/testuser"

    with (
        patch("getpass.getuser", return_value=mock_user),
        patch("os.path.expanduser", return_value=mock_home_dir),
        patch("os.path.isdir", return_value=True),
        patch("os.path.isfile", return_value=False),
        patch("builtins.open", mocker.mock_open()),
        patch("os.chmod"),
        patch("common.pgpass_utils.log_map_server") as mock_log_map_server,
    ):
        setup_pgpass(mock_app_settings, current_logger=mock_logger)

        mock_log_map_server.assert_any_call(
            "! DEV OVERRIDE: Proceeding with .pgpass creation using the default (unsafe) password.",
            "warning",
            mock_logger,
            mock_app_settings,
        )


def test_pgpass_handles_existing_file(mock_app_settings, mocker):
    mock_logger = mocker.MagicMock()
    mock_user = "testuser"
    mock_home_dir = "/home/testuser"

    existing_pgpass_content = [
        "localhost:5432:testdb:testuser:oldpassword",
        "otherhost:5432:otherdb:otheruser:otherpassword",
    ]
    updated_pgpass_content = [
        "otherhost:5432:otherdb:otheruser:otherpassword",
        "localhost:5432:testdb:testuser:testpassword\n",
    ]

    with (
        patch("getpass.getuser", return_value=mock_user),
        patch("os.path.expanduser", return_value=mock_home_dir),
        patch("os.path.isdir", return_value=True),
        patch("os.path.isfile", return_value=True),
        patch(
            "builtins.open",
            mocker.mock_open(read_data="\n".join(existing_pgpass_content)),
        ) as mock_file,
        patch("os.chmod") as mock_chmod,
    ):
        setup_pgpass(mock_app_settings, current_logger=mock_logger)

        mock_file().write.assert_any_call(
            "localhost:5432:testdb:testuser:testpassword\n"
        )
        assert mock_file().write.call_count == len(updated_pgpass_content)
        mock_chmod.assert_called_once_with(
            os.path.join(mock_home_dir, ".pgpass"), 0o600
        )


def test_pgpass_error_creating_file(mock_app_settings, mocker):
    mock_logger = mocker.MagicMock()
    mock_user = "testuser"
    mock_home_dir = "/home/testuser"

    with (
        patch("getpass.getuser", return_value=mock_user),
        patch("os.path.expanduser", return_value=mock_home_dir),
        patch("os.path.isdir", return_value=True),
        patch("os.path.isfile", return_value=False),
        patch("builtins.open", side_effect=IOError("Permission denied")),
        patch("os.chmod"),
    ):
        setup_pgpass(mock_app_settings, current_logger=mock_logger)

        mock_logger.error.assert_called_with(
            "   Ensure user testuser has write permissions to their home directory.",
            exc_info=False,
        )
