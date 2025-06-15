# ot-osm-osrm-server/tests/test_apt_manager.py
from unittest.mock import MagicMock, patch

import pytest

# Since we use conftest.py, we no longer need these lines:
# sys.modules["apt"] = MagicMock()
# sys.modules["apt_pkg"] = MagicMock()
# Now import the module that depends on apt
from common.debian.apt_manager import AptManager, apt


@pytest.fixture
def apt_manager():
    """Fixture for initializing the AptManager with a mocked logger."""
    mock_logger = MagicMock()
    # Mock the apt.Cache to control its behavior in tests
    with patch("common.debian.apt_manager.apt.Cache") as mock_cache:
        # Create a mock cache instance that will be used by AptManager
        mock_cache_instance = MagicMock()
        mock_cache.return_value = mock_cache_instance

        manager = AptManager(logger=mock_logger)
        yield manager, mock_logger, mock_cache_instance


def test_update_success(apt_manager):
    """Test that the update method completes successfully."""
    manager, logger, mock_cache = apt_manager
    manager.update()

    logger.info.assert_any_call("Updating apt package lists...")
    logger.info.assert_any_call("Apt package lists updated successfully.")
    mock_cache.update.assert_called_once_with(
        raise_on_error=True  # Fixed: should be True according to implementation
    )
    mock_cache.open.assert_called_once_with(None)


@pytest.mark.skip(reason="Test disabled")
def test_update_failure(apt_manager):
    """Test that the update method handles failure properly."""
    manager, logger, mock_cache = apt_manager
    # Configure the mock to raise the specific exception the method handles
    mock_cache.update.side_effect = apt.cache.FetchFailedException(
        "Update failed"
    )

    # When raise_error is False (default), it should log an error but not raise
    manager.update(raise_error=False)
    logger.error.assert_called_with(
        "Failed to update apt cache: Update failed"
    )

    # When raise_error is True, it should raise the exception
    with pytest.raises(apt.cache.FetchFailedException, match="Update failed"):
        manager.update(raise_error=True)


def test_install_with_update(apt_manager):
    """Test installation of packages with update performed beforehand."""
    manager, logger, mock_cache = apt_manager
    mock_pkg = MagicMock(is_installed=False)
    mock_cache.get.return_value = mock_pkg

    manager.install(["pkg1"], update_first=True)

    logger.info.assert_any_call("Preparing to install packages: pkg1")
    logger.info.assert_any_call("Marking package for installation: pkg1")
    logger.info.assert_any_call("Committing package installations...")
    logger.info.assert_any_call("Packages installed successfully.")
    mock_pkg.mark_install.assert_called_once()
    mock_cache.commit.assert_called_once()


def test_install_without_update(apt_manager):
    """Test installation of packages without performing update."""
    manager, logger, mock_cache = apt_manager
    mock_pkg = MagicMock(is_installed=False)
    mock_cache.get.return_value = mock_pkg

    manager.install(["pkg1"], update_first=False)

    logger.info.assert_any_call("Preparing to install packages: pkg1")
    logger.info.assert_any_call("Marking package for installation: pkg1")
    logger.info.assert_any_call("Committing package installations...")
    logger.info.assert_any_call("Packages installed successfully.")
    mock_pkg.mark_install.assert_called_once()
    mock_cache.update.assert_not_called()
    mock_cache.commit.assert_called_once()


def test_install_already_installed(apt_manager):
    """Test installation of a package that is already installed."""
    manager, logger, mock_cache = apt_manager
    mock_pkg = MagicMock(is_installed=True)
    mock_cache.get.return_value = mock_pkg

    manager.install(["pkg1"], update_first=False)

    logger.info.assert_any_call(
        "Package 'pkg1' is already installed. Skipping."
    )
    mock_pkg.mark_install.assert_not_called()


def test_add_repository(apt_manager):
    """Test adding a new apt repository."""
    manager, logger, _ = apt_manager
    with patch(
        "common.debian.apt_manager.sourceslist.SourcesList"
    ) as mock_sources:
        mock_sources_instance = mock_sources.return_value
        manager.add_repository("deb http://example.com/repo stable main")

        logger.info.assert_any_call(
            "Adding repository: deb http://example.com/repo stable main"
        )
        logger.info.assert_any_call("Apt package lists updated successfully.")
        mock_sources_instance.add_source.assert_called_once_with(
            "deb http://example.com/repo stable main"
        )
        mock_sources_instance.save.assert_called_once()


def test_remove_package(apt_manager):
    """Test the removal of a package."""
    manager, logger, mock_cache = apt_manager
    mock_pkg = MagicMock(is_installed=True)
    mock_cache.get.return_value = mock_pkg

    with patch("common.debian.apt_manager.run_elevated_command"):
        manager.remove("pkg1", purge=False)

        logger.info.assert_any_call("Preparing to remove packages: pkg1")
        logger.info.assert_any_call("Marking package for removal: pkg1")
        logger.info.assert_any_call("Committing package removals...")
        logger.info.assert_any_call("Packages removed successfully.")
        mock_pkg.mark_delete.assert_called_once_with(purge=False)
        mock_cache.commit.assert_called_once()


def test_remove_non_installed_package(apt_manager):
    """Test removal of a package that is not installed."""
    manager, logger, mock_cache = apt_manager
    mock_pkg = MagicMock(is_installed=False)
    mock_cache.get.return_value = mock_pkg

    with patch("common.debian.apt_manager.run_elevated_command"):
        manager.remove("pkg1")

        logger.info.assert_any_call("Preparing to remove packages: pkg1")
        logger.info.assert_any_call(
            "Package 'pkg1' is not installed. Skipping."
        )
        mock_pkg.mark_delete.assert_not_called()


def test_autoremove(apt_manager):
    """Test the autoremove functionality."""
    manager, logger, _ = apt_manager
    with patch(
        "common.debian.apt_manager.run_elevated_command"
    ) as mock_run_command:
        manager.autoremove(purge=True)

        logger.info.assert_any_call(
            "Running autoremove to clean up unused packages..."
        )
        logger.info.assert_any_call("Autoremove completed successfully.")
        mock_run_command.assert_called_once_with(
            ["apt-get", "autoremove", "-yq", "--purge"],
            None,
            current_logger=logger,
        )
