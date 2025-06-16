import logging
from unittest.mock import MagicMock

import pytest

from installer.nginx_installer import ensure_nginx_package_installed
from setup.config_models import AppSettings


@pytest.fixture
def mock_logger():
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def mock_app_settings():
    return MagicMock(spec=AppSettings)


@pytest.fixture
def mock_symbols():
    return {
        "info": "ℹ️",
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
    }


@pytest.fixture
def mock_nginx_package_name():
    return "nginx"


def test_ensure_nginx_package_installed_success(
    mocker,
    mock_logger,
    mock_app_settings,
    mock_symbols,
    mock_nginx_package_name,
):
    mock_app_settings.symbols = mock_symbols
    mocker.patch(
        "installer.nginx_installer.NGINX_PACKAGE_NAME",
        mock_nginx_package_name,
    )
    mocker.patch(
        "common.command_utils.elevated_command_exists", return_value=True
    )
    mocker.patch(
        "common.command_utils.check_package_installed", return_value=True
    )
    mock_log_map_server = mocker.patch("common.command_utils.log_map_server")

    ensure_nginx_package_installed(
        mock_app_settings, current_logger=mock_logger
    )

    mock_log_map_server.assert_any_call(
        f"ℹ️ Checking Nginx package ('{mock_nginx_package_name}') installation status...",
        "info",
        mock_logger,
        mock_app_settings,
    )
    mock_log_map_server.assert_any_call(
        f"✅ Nginx package '{mock_nginx_package_name}' is installed and command exists.",
        "success",
        mock_logger,
        mock_app_settings,
    )


def test_ensure_nginx_package_installed_failure(
    mocker,
    mock_logger,
    mock_app_settings,
    mock_symbols,
    mock_nginx_package_name,
):
    mock_app_settings.symbols = mock_symbols
    mocker.patch(
        "installer.nginx_installer.NGINX_PACKAGE_NAME",
        mock_nginx_package_name,
    )
    mocker.patch(
        "common.command_utils.elevated_command_exists", return_value=False
    )
    mocker.patch(
        "common.command_utils.check_package_installed", return_value=False
    )
    mock_log_map_server = mocker.patch("common.command_utils.log_map_server")

    with pytest.raises(EnvironmentError):
        ensure_nginx_package_installed(
            mock_app_settings, current_logger=mock_logger
        )

    mock_log_map_server.assert_any_call(
        f"❌ Nginx package '{mock_nginx_package_name}' or command is NOT found/installed. "
        "This should have been handled by a core prerequisite installation step.",
        "error",
        mock_logger,
        mock_app_settings,
    )


def test_ensure_nginx_package_installed_default_logger(
    mocker, mock_app_settings, mock_symbols, mock_nginx_package_name
):
    mock_app_settings.symbols = mock_symbols
    mocker.patch(
        "installer.nginx_installer.NGINX_PACKAGE_NAME",
        mock_nginx_package_name,
    )
    mocker.patch(
        "common.command_utils.elevated_command_exists", return_value=True
    )
    mocker.patch(
        "common.command_utils.check_package_installed", return_value=True
    )
    mock_log_map_server = mocker.patch("common.command_utils.log_map_server")
    mock_module_logger = mocker.patch(
        "installer.nginx_installer.module_logger"
    )

    ensure_nginx_package_installed(mock_app_settings)

    mock_log_map_server.assert_any_call(
        f"ℹ️ Checking Nginx package ('{mock_nginx_package_name}') installation status...",
        "info",
        mock_module_logger,
        mock_app_settings,
    )
    mock_log_map_server.assert_any_call(
        f"✅ Nginx package '{mock_nginx_package_name}' is installed and command exists.",
        "success",
        mock_module_logger,
        mock_app_settings,
    )
