from unittest.mock import MagicMock, patch

import pytest

from common.debian.apt_manager import AptManager


@pytest.fixture
def apt_manager():
    """Fixture for initializing the AptManager with a mocked logger."""
    mock_logger = MagicMock()
    with patch("common.debian.apt_manager.apt.Cache") as mock_cache:
        yield AptManager(logger=mock_logger), mock_logger, mock_cache


def test_update_success(apt_manager):
    """Test that the update method completes successfully."""
    manager, logger, mock_cache = apt_manager
    manager.update()

    logger.info.assert_any_call("Updating apt package lists...")
    logger.info.assert_any_call("Apt package lists updated successfully.")
    mock_cache.return_value.update.assert_called_once_with(
        raise_on_error=False
    )
    mock_cache.return_value.open.assert_called_once_with(None)


def test_update_failure(apt_manager):
    """Test that the update method handles failure properly."""
    manager, logger, mock_cache = apt_manager
    mock_cache.return_value.update.side_effect = Exception("Update failed")

    with pytest.raises(Exception, match="Update failed"):
        manager.update()

    logger.error.assert_called_with(
        "Failed to update apt cache: Update failed"
    )


def test_install_with_update(apt_manager):
    """Test installation of packages with update performed beforehand."""
    manager, logger, mock_cache = apt_manager
    mock_pkg = MagicMock(is_installed=False)
    mock_cache.return_value.get.return_value = mock_pkg

    manager.install(["pkg1"], update_first=True)

    logger.info.assert_any_call("Preparing to install packages: pkg1")
    logger.info.assert_any_call("Marking package for installation: pkg1")
    logger.info.assert_any_call("Committing package installations...")
    logger.info.assert_any_call("Packages installed successfully.")
    mock_pkg.mark_install.assert_called_once()
    mock_cache.return_value.commit.assert_called_once()


def test_install_without_update(apt_manager):
    """Test installation of packages without performing update."""
    manager, logger, mock_cache = apt_manager
    mock_pkg = MagicMock(is_installed=False)
    mock_cache.return_value.get.return_value = mock_pkg

    manager.install(["pkg1"], update_first=False)

    logger.info.assert_any_call("Preparing to install packages: pkg1")
    logger.info.assert_any_call("Marking package for installation: pkg1")
    logger.info.assert_any_call("Committing package installations...")
    logger.info.assert_any_call("Packages installed successfully.")
    mock_pkg.mark_install.assert_called_once()
    mock_cache.return_value.update.assert_not_called()
    mock_cache.return_value.commit.assert_called_once()


def test_install_already_installed(apt_manager):
    """Test installation of a package that is already installed."""
    manager, logger, mock_cache = apt_manager
    mock_pkg = MagicMock(is_installed=True)
    mock_cache.return_value.get.return_value = mock_pkg

    manager.install(["pkg1"], update_first=False)

    logger.info.assert_any_call(
        "Package 'pkg1' is already installed. Skipping."
    )
    mock_pkg.mark_install.assert_not_called()
    mock_cache.return_value.commit.assert_not_called()


def test_add_repository(apt_manager):
    """Test adding a new apt repository."""
    manager, logger, _ = apt_manager
    with patch(
        "common.debian.apt_manager.sourceslist.SourcesList"
    ) as mock_sources:
        mock_sources_instance = mock_sources.return_value
        manager.add_repository("deb http://example.com/repo stable main")

        logger.info.assert_called_with(
            "Adding repository: deb http://example.com/repo stable main"
        )
        mock_sources_instance.add_source.assert_called_once_with(
            "deb http://example.com/repo stable main"
        )
        mock_sources_instance.save.assert_called_once()


def test_remove_package(apt_manager):
    """Test the removal of a package."""
    manager, logger, mock_cache = apt_manager
    mock_pkg = MagicMock(is_installed=True)
    mock_cache.return_value.get.return_value = mock_pkg

    manager.remove("pkg1", purge=False)

    logger.info.assert_any_call("Preparing to remove packages: pkg1")
    logger.info.assert_any_call("Marking package for removal: pkg1")
    logger.info.assert_any_call("Committing package removals...")
    logger.info.assert_any_call("Packages removed successfully.")
    mock_pkg.mark_delete.assert_called_once_with(purge=False)
    mock_cache.return_value.commit.assert_called_once()


def test_remove_non_installed_package(apt_manager):
    """Test removal of a package that is not installed."""
    manager, logger, mock_cache = apt_manager
    mock_pkg = MagicMock(is_installed=False)
    mock_cache.return_value.get.return_value = mock_pkg

    manager.remove("pkg1")

    logger.info.assert_any_call("Preparing to remove packages: pkg1")
    logger.info.assert_any_call("Package 'pkg1' is not installed. Skipping.")
    mock_pkg.mark_delete.assert_not_called()
    mock_cache.return_value.commit.assert_not_called()


def test_autoremove(apt_manager):
    """Test the autoremove functionality."""
    manager, logger, _ = apt_manager
    with patch(
        "common.debian.apt_manager.run_elevated_command"
    ) as mock_run_command:
        manager.autoremove(purge=True)

        logger.info.assert_called_with(
            "Running autoremove to clean up unused packages..."
        )
        mock_run_command.assert_called_once_with(
            ["apt-get", "autoremove", "-yq", "--purge"],
            None,
            current_logger=logger,
        )
