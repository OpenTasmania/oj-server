# tests/test_docker_installer.py
from unittest.mock import MagicMock, create_autospec

import pytest

from common.command_utils import (
    log_map_server,
    run_elevated_command,
)
from common.debian.apt_manager import AptManager
from installer.docker_installer import install_docker_engine
from setup.config_models import AppSettings


def test_install_docker_engine_success(mocker):
    """Test install_docker_engine function successful execution."""
    mock_logger = mocker.MagicMock()
    mock_app_settings = create_autospec(AppSettings)

    mock_apt_manager_instance = create_autospec(AptManager)
    mocker.patch(
        "installer.docker_installer.AptManager",
        return_value=mock_apt_manager_instance,
    )

    mocker.patch(
        "installer.docker_installer.run_command",
        return_value=MagicMock(stdout="amd64"),
    )
    mocker.patch(
        "installer.docker_installer.get_debian_codename",
        return_value="bullseye",
    )
    mocker.patch("installer.docker_installer.run_elevated_command")

    install_docker_engine(
        app_settings=mock_app_settings, current_logger=mock_logger
    )

    mock_apt_manager_instance.add_gpg_key_from_url.assert_called_once()
    mock_apt_manager_instance.add_repository.assert_called_once()
    mock_apt_manager_instance.install.assert_called_once()
    run_elevated_command.assert_called_once()
    log_map_server.assert_any_call(
        "✅ Docker Engine packages installed.",
        "success",
        mock_logger,
        mock_app_settings,
    )


def test_install_docker_engine_gpg_key_failure(mocker):
    """Test install_docker_engine with failure in adding the GPG key."""
    mock_logger = mocker.MagicMock()
    mock_app_settings = create_autospec(AppSettings)

    mock_apt_manager_instance = create_autospec(AptManager)
    mocker.patch(
        "installer.docker_installer.AptManager",
        return_value=mock_apt_manager_instance,
    )

    mock_apt_manager_instance.add_gpg_key_from_url.side_effect = Exception(
        "GPG key error"
    )

    with pytest.raises(Exception, match="GPG key error"):
        install_docker_engine(
            app_settings=mock_app_settings, current_logger=mock_logger
        )

    mock_apt_manager_instance.add_gpg_key_from_url.assert_called_once()
    mock_apt_manager_instance.add_repository.assert_not_called()
    mock_apt_manager_instance.install.assert_not_called()


def test_install_docker_engine_codename_error(mocker):
    """Test install_docker_engine when codename retrieval fails."""
    mock_logger = mocker.MagicMock()
    mock_app_settings = create_autospec(AppSettings)

    mock_apt_manager_instance = create_autospec(AptManager)
    mocker.patch(
        "installer.docker_installer.AptManager",
        return_value=mock_apt_manager_instance,
    )

    mocker.patch(
        "installer.docker_installer.run_command",
        return_value=MagicMock(stdout="amd64"),
    )
    mocker.patch(
        "installer.docker_installer.get_debian_codename", return_value=None
    )

    with pytest.raises(
        Exception, match="Could not determine Debian codename for Docker."
    ):
        install_docker_engine(
            app_settings=mock_app_settings, current_logger=mock_logger
        )

    mock_apt_manager_instance.add_gpg_key_from_url.assert_called_once()
    mock_apt_manager_instance.add_repository.assert_not_called()
    mock_apt_manager_instance.install.assert_not_called()
