"""
Base configurator class for all configurator modules.

This module provides the base class that all configurator modules must inherit from.
It defines the common interface that all configurators must implement.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Set

from setup.config_models import AppSettings


class BaseConfigurator(ABC):
    """
    Base class for all configurator modules.

    This class defines the common interface that all configurator modules must implement.
    It provides methods for configuring, unconfiguring, and checking the status of
    a component.
    """

    # Class-level metadata that can be overridden by subclasses or set by the registry decorator
    metadata: Dict[str, Any] = {
        "dependencies": [],  # List of configurator names that this configurator depends on
        "description": "",  # Description of the configurator
    }

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the configurator.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        self.app_settings = app_settings
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def configure(self) -> bool:
        """
        Configure the component.

        Returns:
            True if the configuration was successful, False otherwise.
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
    def is_configured(self) -> bool:
        """
        Check if the component is configured.

        Returns:
            True if the component is configured, False otherwise.
        """
        pass

    def rollback(self) -> bool:
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
        Get the dependencies of this configurator.

        Returns:
            A set of configurator names that this configurator depends on.
        """
        return set(self.metadata.get("dependencies", []))

    def get_description(self) -> str:
        """
        Get the description of the configurator.

        Returns:
            The description of the configurator.
        """
        return str(self.metadata.get("description", ""))
