import logging
from unittest.mock import Mock

import pytest

from installer import certbot_installer
from installer.certbot_installer import install_certbot_packages
from setup.config_models import AppSettings


def test_install_certbot_packages_success(mocker):
    """Test successful installation of Certbot packages."""
    mock_logger = Mock(spec=logging.Logger)
    mock_apt_manager = Mock()
    app_settings = AppSettings(symbols={"package": "📦", "success": "✅"})

    mocker.patch(
        "installer.certbot_installer.AptManager",
        return_value=mock_apt_manager,
    )
    mocker.patch("installer.certbot_installer.log_map_server")

    install_certbot_packages(app_settings, current_logger=mock_logger)

    mock_apt_manager.install.assert_called_once_with(
        ["certbot", "python3-certbot-nginx"], update_first=True
    )
    certbot_installer.log_map_server.assert_any_call(
        "📦 Installing Certbot and Nginx plugin...",
        "info",
        mock_logger,
        app_settings,
    )
    certbot_installer.log_map_server.assert_any_call(
        "✅ Certbot packages installed.", "success", mock_logger, app_settings
    )


def test_install_certbot_packages_failure(mocker):
    """Test failure during installation of Certbot packages."""
    mock_logger = Mock(spec=logging.Logger)
    mock_apt_manager = Mock()
    mock_apt_manager.install.side_effect = Exception("Installation failed")
    app_settings = AppSettings(symbols={"package": "📦", "error": "❌"})

    mocker.patch(
        "installer.certbot_installer.AptManager",
        return_value=mock_apt_manager,
    )
    mocker.patch("installer.certbot_installer.log_map_server")

    with pytest.raises(Exception, match="Installation failed"):
        install_certbot_packages(app_settings, current_logger=mock_logger)

    mock_apt_manager.install.assert_called_once_with(
        ["certbot", "python3-certbot-nginx"], update_first=True
    )
    certbot_installer.log_map_server.assert_any_call(
        "📦 Installing Certbot and Nginx plugin...",
        "info",
        mock_logger,
        app_settings,
    )
    certbot_installer.log_map_server.assert_any_call(
        "❌ Failed to install Certbot packages: Installation failed",
        "error",
        mock_logger,
        app_settings,
        exc_info=True,
    )
