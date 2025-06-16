import logging
from unittest.mock import MagicMock

import pytest

from setup.config_models import ApacheSettings, AppSettings
from setup.configure.apache_configurator import (
    configure_apache_ports,
    create_apache_tile_site_config,
)


def test_configure_apache_ports_success(mocker):
    """Test successful configuration of Apache ports."""
    # Mock dependencies
    mock_logger = MagicMock(spec=logging.Logger)
    mock_app_settings = AppSettings(
        apache=ApacheSettings(listen_port=8080),
        vm_ip_or_domain="dummy.domain.com",
        symbols={"success": "✅", "step": "➡️"},
    )

    mock_backup_file = mocker.patch(
        "setup.configure.apache_configurator.backup_file",
        return_value=True,
    )
    mock_run_command = mocker.patch(
        "setup.configure.apache_configurator.run_elevated_command"
    )
    mocker.patch(
        "setup.configure.apache_configurator.os.path.exists",
        return_value=True,
    )

    configure_apache_ports(mock_app_settings, current_logger=mock_logger)

    # Validate interactions
    mock_backup_file.assert_called_once_with(
        mocker.ANY, mock_app_settings, current_logger=mock_logger
    )
    mock_run_command.assert_any_call(
        ["sed", "-i.bak_ports_sed", "s/^Listen 80$/Listen 8080/", mocker.ANY],
        mock_app_settings,
        current_logger=mock_logger,
    )
    assert mock_run_command.call_count == 2
    mock_logger.info.assert_any_call(
        "✅ Apache configured to listen on port 8080 (original backed up).",
        exc_info=False,
    )


def test_create_apache_tile_site_config_success(mocker):
    """Test successful creation of Apache tile site configuration."""
    mock_logger = MagicMock(spec=logging.Logger)
    mock_app_settings = AppSettings(
        apache=ApacheSettings(
            listen_port=8080,
            server_name_apache="example.com",
            tile_site_template="ServerName {server_name_apache}\nListen {apache_listen_port}\n",
        ),
        vm_ip_or_domain="example.com",
        symbols={"success": "✅", "step": "➡️"},
    )

    mock_run_command = mocker.patch(
        "setup.configure.apache_configurator.run_elevated_command"
    )

    create_apache_tile_site_config(
        mock_app_settings, current_logger=mock_logger
    )

    mock_run_command.assert_called_once_with(
        ["tee", mocker.ANY],
        mock_app_settings,
        cmd_input="ServerName example.com\nListen 8080\n",
        current_logger=mock_logger,
    )
    mock_logger.info.assert_any_call(
        "✅ Created/Updated Apache tile site configuration file.",
        exc_info=False,
    )


def test_configure_apache_ports_missing_file(mocker):
    """Test configuration failure due to missing Apache ports.conf file."""
    mock_logger = MagicMock(spec=logging.Logger)
    mock_app_settings = AppSettings(
        apache=ApacheSettings(listen_port=8080),
        vm_ip_or_domain="dummy.domain.com",
        symbols={"critical": "🔥", "step": "➡️"},
    )

    mock_backup_file = mocker.patch(
        "setup.configure.apache_configurator.backup_file",
        side_effect=FileNotFoundError,
    )
    mock_run_command = mocker.patch(
        "setup.configure.apache_configurator.run_elevated_command"
    )
    mocker.patch(
        "setup.configure.apache_configurator.os.path.exists",
        return_value=False,
    )

    with pytest.raises(FileNotFoundError):
        configure_apache_ports(mock_app_settings, current_logger=mock_logger)

    # Validate interactions
    mock_backup_file.assert_not_called()
    mock_run_command.assert_called_once()
    mock_logger.critical.assert_called_once_with(
        "🔥 Apache ports configuration file /etc/apache2/ports.conf not found.",
    )


def test_configure_apache_ports_backup_failure(mocker):
    """Test configuration failure due to backup process failure."""
    mock_logger = MagicMock(spec=logging.Logger)
    mock_app_settings = AppSettings(
        apache=ApacheSettings(listen_port=8080),
        vm_ip_or_domain="dummy.domain.com",
        symbols={"error": "❌", "step": "➡️"},
    )

    mock_backup_file = mocker.patch(
        "setup.configure.apache_configurator.backup_file",
        return_value=False,
    )
    mock_run_command = mocker.patch(
        "setup.configure.apache_configurator.run_elevated_command"
    )
    mocker.patch(
        "setup.configure.apache_configurator.os.path.exists",
        return_value=True,
    )

    configure_apache_ports(mock_app_settings, current_logger=mock_logger)

    # Validate interactions
    mock_backup_file.assert_called_once_with(
        mocker.ANY, mock_app_settings, current_logger=mock_logger
    )
    mock_run_command.assert_not_called()
    mock_logger.error.assert_called_once_with(
        "❌ Failed to backup /etc/apache2/ports.conf. Stopping configuration.",
        exc_info=False,
    )
