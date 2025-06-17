# tests/test_apt_manager.py
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from common.debian.apt_manager import AptManager


@pytest.fixture
def apt_manager():
    """Fixture to initialize AptManager with mocked dependencies."""
    mock_logger = MagicMock()
    mock_app_settings = MagicMock()
    with (
        patch(
            "common.debian.apt_manager.run_elevated_command"
        ) as mock_run_elevated,
        patch("common.debian.apt_manager.run_command") as mock_run_cmd,
        patch("common.debian.apt_manager.command_exists", return_value=True),
        patch("common.debian.apt_manager.os.path.exists") as mock_path_exists,
    ):
        manager = AptManager(logger=mock_logger)
        yield (
            manager,
            mock_logger,
            mock_run_elevated,
            mock_run_cmd,
            mock_path_exists,
            mock_app_settings,
        )


def test_install_new_package(apt_manager):
    """Test installation of a new package."""
    manager, logger, mock_run_elevated, mock_run_cmd, _, mock_app_settings = (
        apt_manager
    )
    mock_run_cmd.side_effect = subprocess.CalledProcessError(1, "cmd")

    manager.install(["pkg1"], mock_app_settings, update_first=False)

    logger.info.assert_any_call("Marking package for installation: pkg1")
    logger.info.assert_any_call("Committing installation for: pkg1")
    mock_run_elevated.assert_called_once_with(
        ["apt-get", "install", "-yq", "pkg1"],
        mock_app_settings,
        current_logger=logger,
    )


def test_install_already_installed(apt_manager):
    """Test installation of an already installed package."""
    manager, logger, mock_run_elevated, mock_run_cmd, _, mock_app_settings = (
        apt_manager
    )
    mock_run_cmd.return_value = MagicMock(stdout="install ok installed")

    manager.install(["pkg1"], mock_app_settings, update_first=False)

    logger.info.assert_any_call(
        "Package 'pkg1' is already installed. Skipping."
    )
    mock_run_elevated.assert_not_called()


def test_add_repository(apt_manager):
    """Test adding a new apt repository."""
    manager, logger, mock_run_elevated, _, _, mock_app_settings = apt_manager
    repo_string = "deb http://example.com/repo stable main"
    manager.add_repository(repo_string, mock_app_settings, update_after=True)

    logger.info.assert_any_call(f"Adding repository: {repo_string}")
    mock_run_elevated.assert_any_call(
        ["add-apt-repository", "-y", repo_string],
        mock_app_settings,
        current_logger=logger,
    )
    mock_run_elevated.assert_any_call(
        ["apt-get", "update", "-yq"], mock_app_settings, current_logger=logger
    )


def test_remove_package(apt_manager):
    """Test the removal of an installed package."""
    manager, logger, mock_run_elevated, mock_run_cmd, _, mock_app_settings = (
        apt_manager
    )
    mock_run_cmd.return_value = MagicMock(stdout="install ok installed")

    manager.remove("pkg1", purge=False, app_settings=mock_app_settings)

    logger.info.assert_any_call("Marking package for removal: pkg1")
    logger.info.assert_any_call("Committing remove for: pkg1")
    mock_run_elevated.assert_called_once_with(
        ["apt-get", "remove", "-yq", "pkg1"],
        mock_app_settings,
        current_logger=logger,
    )


def test_remove_non_installed_package(apt_manager):
    """Test removal of a package that is not installed."""
    manager, logger, mock_run_elevated, mock_run_cmd, _, mock_app_settings = (
        apt_manager
    )
    mock_run_cmd.side_effect = subprocess.CalledProcessError(1, "cmd")

    manager.remove("pkg1", app_settings=mock_app_settings)

    logger.info.assert_any_call("Package 'pkg1' is not installed. Skipping.")
    mock_run_elevated.assert_not_called()


def test_autoremove(apt_manager):
    """Test the autoremove functionality."""
    manager, logger, mock_run_elevated, _, _, mock_app_settings = apt_manager
    manager.autoremove(purge=True, app_settings=mock_app_settings)

    logger.info.assert_any_call(
        "Running autoremove to clean up unused packages..."
    )
    mock_run_elevated.assert_called_once_with(
        ["apt-get", "autoremove", "-yq", "--purge"],
        mock_app_settings,
        current_logger=logger,
    )


def test_clean(apt_manager):
    """Test the clean functionality."""
    manager, logger, mock_run_elevated, _, _, mock_app_settings = apt_manager
    manager.clean(app_settings=mock_app_settings)

    logger.info.assert_any_call("Cleaning apt package cache...")
    mock_run_elevated.assert_called_once_with(
        ["apt-get", "clean"], mock_app_settings, current_logger=logger
    )


def test_remove_repository(apt_manager):
    """Test removing a repository."""
    manager, logger, mock_run_elevated, _, _, mock_app_settings = apt_manager
    repo_string = "deb http://example.com/repo stable main"
    manager.remove_repository(
        repo_string, update_after=True, app_settings=mock_app_settings
    )

    logger.info.assert_any_call(f"Removing repository: {repo_string}")
    mock_run_elevated.assert_any_call(
        ["add-apt-repository", "--remove", "-y", repo_string],
        mock_app_settings,
        current_logger=logger,
    )
    # Check that update was called
    mock_run_elevated.assert_any_call(
        ["apt-get", "update", "-yq"], mock_app_settings, current_logger=logger
    )


def test_remove_gpg_key_by_file(apt_manager):
    """Test removing a GPG key by file path."""
    (
        manager,
        logger,
        mock_run_elevated,
        _,
        mock_path_exists,
        mock_app_settings,
    ) = apt_manager
    key_path = "/etc/apt/trusted.gpg.d/example.gpg"
    mock_path_exists.return_value = True

    manager.remove_gpg_key(key_path, app_settings=mock_app_settings)

    logger.info.assert_any_call(f"Removing GPG keyring file: {key_path}")
    mock_path_exists.assert_called_with(key_path)
    mock_run_elevated.assert_called_with(
        ["rm", "-f", key_path], mock_app_settings, current_logger=logger
    )


def test_remove_gpg_key_by_identifier(apt_manager):
    """Test removing a GPG key by identifier."""
    manager, logger, mock_run_elevated, _, _, mock_app_settings = apt_manager
    key_id = "A1BD8E9D78F7FE5C3E65D8AF8B48AD6246925553"

    manager.remove_gpg_key(key_id, app_settings=mock_app_settings)

    logger.info.assert_any_call(f"Removing GPG key with identifier: {key_id}")
    mock_run_elevated.assert_called_with(
        ["gpg", "--batch", "--yes", "--delete-keys", key_id],
        mock_app_settings,
        current_logger=logger,
    )
