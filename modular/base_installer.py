"""
Base installer class for all installer modules.

This module provides the base class that all installer modules must inherit from.
It defines the common interface that all installers must implement.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Set

from setup.config_models import AppSettings


class BaseInstaller(ABC):
    """
    Base class for all installer modules.

    This class defines the common interface that all installer modules must implement.
    It provides methods for installing, uninstalling, and checking the status of
    a component.
    """

    # Class-level metadata that can be overridden by subclasses or set by the registry decorator
    metadata: Dict[str, Any] = {
        "dependencies": [],  # List of installer names that this installer depends on
        "estimated_time": 0,  # Estimated installation time in seconds
        "required_resources": {  # Required system resources
            "memory": 0,  # Required memory in MB
            "disk": 0,  # Required disk space in MB
            "cpu": 0,  # Required CPU cores
        },
        "description": "",  # Description of the installer
    }

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the installer.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        self.app_settings = app_settings
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def install(self) -> bool:
        """
        Install the component.

        Returns:
            True if the installation was successful, False otherwise.
        """
        pass

    @abstractmethod
    def uninstall(self) -> bool:
        """
        Uninstall the component.

        Returns:
            True if the uninstallation was successful, False otherwise.
        """
        pass

    @abstractmethod
    def is_installed(self) -> bool:
        """
        Check if the component is installed.

        Returns:
            True if the component is installed, False otherwise.
        """
        pass

    def rollback(self) -> bool:
        """
        Rollback the installation of the component.

        This method is called when an installation fails and previous successful
        installations need to be rolled back. By default, it calls the uninstall
        method, but subclasses can override this to provide more specific rollback
        behavior.

        Returns:
            True if the rollback was successful, False otherwise.
        """
        self.logger.info(
            f"Rolling back installation of {self.__class__.__name__}"
        )
        return self.uninstall()

    def get_dependencies(self) -> Set[str]:
        """
        Get the dependencies of this installer.

        Returns:
            A set of installer names that this installer depends on.
        """
        return set(self.metadata.get("dependencies", []))

    def get_estimated_time(self) -> int:
        """
        Get the estimated installation time.

        Returns:
            The estimated installation time in seconds.
        """
        return int(self.metadata.get("estimated_time", 0))

    def get_required_resources(self) -> Dict[str, int]:
        """
        Get the required system resources.

        Returns:
            A dictionary of required system resources.
        """
        resources = self.metadata.get("required_resources", {})
        # Ensure we return the correct type
        return {k: int(v) for k, v in resources.items()}

    def get_description(self) -> str:
        """
        Get the description of the installer.

        Returns:
            The description of the installer.
        """
        return str(self.metadata.get("description", ""))
