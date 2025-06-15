import logging
from unittest.mock import MagicMock

import pytest

from installer.apache_installer import ensure_apache_packages_installed
from setup.config_models import AppSettings


@pytest.fixture
def mock_app_settings():
    mock = MagicMock(spec=AppSettings)
    mock.symbols = {"info": "ℹ️", "success": "✅", "error": "❌"}
    return mock


@pytest.fixture
def mock_logger():
    return MagicMock(spec=logging.Logger)


def test_ensure_apache_packages_installed_all_packages_installed(
    mock_app_settings, mock_logger, mocker
):
    mocker.patch(
        "installer.apache_installer.check_package_installed",
        side_effect=lambda pkg, *args, **kwargs: True,
    )
    mock_log_map_server = mocker.patch(
        "installer.apache_installer.log_map_server"
    )

    ensure_apache_packages_installed(app_settings=mock_app_settings)

    mock_log_map_server.assert_any_call(
        "✅ All required Apache/mod_tile packages confirmed as installed.",
        "success",
        mocker.ANY,
        mock_app_settings,
    )


def test_ensure_apache_packages_installed_missing_packages(
    mock_app_settings, mock_logger, mocker
):
    mocker.patch(
        "installer.apache_installer.check_package_installed",
        side_effect=lambda pkg, *args, **kwargs: pkg != "libapache2-mod-tile",
    )
    mocker.patch("installer.apache_installer.log_map_server")

    with pytest.raises(
        EnvironmentError,
        match="One or more essential Apache/mod_tile packages are missing.",
    ):
        ensure_apache_packages_installed(app_settings=mock_app_settings)


def test_ensure_apache_packages_installed_no_logger(
    mock_app_settings, mocker
):
    mocker.patch(
        "installer.apache_installer.check_package_installed",
        side_effect=lambda pkg, *args, **kwargs: True,
    )
    mock_log_map_server = mocker.patch(
        "installer.apache_installer.log_map_server"
    )

    ensure_apache_packages_installed(app_settings=mock_app_settings)

    mock_log_map_server.assert_any_call(
        "✅ All required Apache/mod_tile packages confirmed as installed.",
        "success",
        mocker.ANY,
        mock_app_settings,
    )
