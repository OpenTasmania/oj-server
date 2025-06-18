"""
Base component class for all component modules.

This module provides the base class that all component modules must inherit from.
It defines the common interface that all components must implement.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Set

from installer.config_models import AppSettings


class BaseComponent(ABC):
    """
    Base class for all component modules.

    This class defines the common interface that all component modules must implement.
    It provides methods for installing, configuring, uninstalling, unconfiguring,
    and checking the status of a component.
    """

    # Class-level metadata that can be overridden by subclasses or set by the registry decorator
    metadata: Dict[str, Any] = {
        "dependencies": [],  # List of component names that this component depends on
        "estimated_time": 0,  # Estimated installation time in seconds
        "required_resources": {  # Required system resources
            "memory": 0,  # Required memory in MB
            "disk": 0,  # Required disk space in MB
            "cpu": 0,  # Required CPU cores
        },
        "description": "",  # Description of the component
    }

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the component.

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
    def configure(self) -> bool:
        """
        Configure the component.

        Returns:
            True if the configuration was successful, False otherwise.
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
    def unconfigure(self) -> bool:
        """
        Unconfigure the component.

        Returns:
            True if the unconfiguration was successful, False otherwise.
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

    @abstractmethod
    def is_configured(self) -> bool:
        """
        Check if the component is configured.

        Returns:
            True if the component is configured, False otherwise.
        """
        pass

    def rollback_installation(self) -> bool:
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

    def rollback_configuration(self) -> bool:
        """
        Rollback the configuration of the component.

        This method is called when a configuration fails and previous successful
        configurations need to be rolled back. By default, it calls the unconfigure
        method, but subclasses can override this to provide more specific rollback
        behavior.

        Returns:
            True if the rollback was successful, False otherwise.
        """
        self.logger.info(
            f"Rolling back configuration of {self.__class__.__name__}"
        )
        return self.unconfigure()

    def get_dependencies(self) -> Set[str]:
        """
        Get the dependencies of this component.

        Returns:
            A set of component names that this component depends on.
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
        Get the description of the component.

        Returns:
            The description of the component.
        """
        return str(self.metadata.get("description", ""))
