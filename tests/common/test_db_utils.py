import os
from unittest.mock import MagicMock

from common.db_utils import get_db_connection


def test_get_db_connection_successful(mocker):
    """Test successful database connection."""
    mock_conn = MagicMock()
    mocker.patch("psycopg.connect", return_value=mock_conn)
    result = get_db_connection({"dbname": "test_db", "user": "test_user"})
    assert result == mock_conn


def test_get_db_connection_operational_error(mocker):
    """Test connection with operational error."""
    mocker.patch("psycopg.connect", side_effect=Exception("OperationalError"))
    mock_logger = mocker.patch("common.db_utils.module_logger.error")
    result = get_db_connection({"dbname": "test_db", "user": "test_user"})
    assert result is None
    assert mock_logger.call_count == 1


def test_get_db_connection_fallback_to_default_params(mocker):
    """Test connection using default parameters when no db_params are provided."""
    mock_conn = MagicMock()
    mocker.patch("psycopg.connect", return_value=mock_conn)
    mocker.patch(
        "common.db_utils.DEFAULT_DB_PARAMS",
        {
            "dbname": "default_db",
            "user": "default_user",
            "host": "localhost",
            "port": "5432",
        },
    )
    result = get_db_connection()
    assert result == mock_conn


def test_get_db_connection_invalid_password(mocker):
    """Test critical log for default placeholder password."""
    mock_logger = mocker.patch("common.db_utils.module_logger.critical")
    os.environ["PG_OSM_PASSWORD"] = "yourStrongPasswordHere"
    os.environ["PGPASSWORD"] = "yourStrongPasswordHere"
    result = get_db_connection({"password": "yourStrongPasswordHere"})
    assert result is None
    mock_logger.assert_called_once()


def test_get_db_connection_with_partial_parameters(mocker):
    """Test connection when partial db_params are provided."""
    mock_conn = MagicMock()
    mocker.patch("psycopg.connect", return_value=mock_conn)
    mocker.patch(
        "common.db_utils.DEFAULT_DB_PARAMS",
        {
            "dbname": "fallback_db",
            "user": "fallback_user",
            "host": "localhost",
            "port": "5432",
        },
    )
    result = get_db_connection({"dbname": "custom_db"})
    assert result == mock_conn
