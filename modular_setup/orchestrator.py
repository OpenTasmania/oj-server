"""
Core orchestrator for the modular setup framework.

This module provides the SetupOrchestrator class, which is responsible for
loading the configuration file, iterating through the requested configuration
tasks, looking up the appropriate configurator module in the registry, and
executing it.
"""

import importlib
import logging
import os
import sys
from typing import Dict, List, Optional

import yaml

from common.orchestrator import Orchestrator
from modular.orchestrator import ComponentOrchestrator
from modular_setup.registry import ConfiguratorRegistry
from setup.config_models import AppSettings


# For backward compatibility during migration
class SetupOrchestrator:
    """
    Legacy orchestrator for the modular setup framework.

    This class is maintained for backward compatibility during migration.
    It forwards most of its method calls to the ComponentOrchestrator.
    """

    def __init__(
        self,
        config_file: str = "config.yaml",
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the setup orchestrator.

        Args:
            config_file: Path to the configuration file.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        self.config_file = config_file
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.app_settings: Optional[AppSettings] = None
        self.orchestrator: Optional[Orchestrator] = None
        self._component_orchestrator: Optional[ComponentOrchestrator] = None

    def load_config(self) -> AppSettings:
        """
        Load the configuration file.

        Returns:
            The application settings.

        Raises:
            FileNotFoundError: If the configuration file does not exist.
            yaml.YAMLError: If the configuration file is not valid YAML.
        """
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_file}"
            )

        try:
            with open(self.config_file, "r") as f:
                config_data = yaml.safe_load(f)

            # Convert the YAML data to an AppSettings object
            app_settings = AppSettings(**config_data)
            self.app_settings = app_settings
            return app_settings
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing configuration file: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            raise

    def _import_configurators(self) -> None:
        """
        Import all configurator modules to ensure they are registered.

        This method dynamically imports all Python modules in the configurators
        directory to ensure that their decorators are executed and they are
        registered with the ConfiguratorRegistry.
        """
        configurators_dir = os.path.join(
            os.path.dirname(__file__), "configurators"
        )

        # Add the configurators directory to the Python path if it's not already there
        if configurators_dir not in sys.path:
            sys.path.append(configurators_dir)

        # Import all Python modules in the configurators directory
        for filename in os.listdir(configurators_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = filename[:-3]  # Remove the .py extension
                try:
                    importlib.import_module(
                        f"modular_setup.configurators.{module_name}"
                    )
                    self.logger.debug(
                        f"Imported configurator module: {module_name}"
                    )
                except ImportError as e:
                    self.logger.error(
                        f"Error importing configurator module {module_name}: {str(e)}"
                    )

    def _get_component_orchestrator(self) -> ComponentOrchestrator:
        """
        Get or create a ComponentOrchestrator instance.

        Returns:
            A ComponentOrchestrator instance.
        """
        if self.app_settings is None:
            self.app_settings = self.load_config()

        if self._component_orchestrator is None:
            self._component_orchestrator = ComponentOrchestrator(
                self.app_settings, self.logger
            )

        return self._component_orchestrator

    def configure(
        self, configurators: Optional[List[str]] = None, force: bool = False
    ) -> bool:
        """
        Configure the system using the specified configurators.

        Args:
            configurators: List of configurator names to use. If None, all configurators
                           specified in the configuration file will be used.
            force: If True, force reconfiguration even if already configured.

        Returns:
            True if the configuration was successful, False otherwise.
        """
        if self.app_settings is None:
            self.app_settings = self.load_config()

        # Import all configurator modules to ensure they are registered
        self._import_configurators()

        # If no configurators are specified, use all configurators from the config
        if configurators is None:
            # This is a placeholder. In a real implementation, you would extract
            # the list of configurators from the configuration file.
            configurators = list(
                ConfiguratorRegistry.get_all_configurators().keys()
            )

        # Forward to ComponentOrchestrator
        component_orchestrator = self._get_component_orchestrator()
        return component_orchestrator.configure(configurators, force)

    def unconfigure(self, configurators: Optional[List[str]] = None) -> bool:
        """
        Unconfigure the system using the specified configurators.

        Args:
            configurators: List of configurator names to use. If None, all configurators
                           specified in the configuration file will be used.

        Returns:
            True if the unconfiguration was successful, False otherwise.
        """
        if self.app_settings is None:
            self.app_settings = self.load_config()

        # Import all configurator modules to ensure they are registered
        self._import_configurators()

        # If no configurators are specified, use all configurators from the config
        if configurators is None:
            # This is a placeholder. In a real implementation, you would extract
            # the list of configurators from the configuration file.
            configurators = list(
                ConfiguratorRegistry.get_all_configurators().keys()
            )

        # Forward to ComponentOrchestrator
        component_orchestrator = self._get_component_orchestrator()
        return component_orchestrator.unconfigure(configurators)

    def check_status(
        self, configurators: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """
        Check the configuration status of the system.

        Args:
            configurators: List of configurator names to check. If None, all configurators
                           specified in the configuration file will be checked.

        Returns:
            A dictionary mapping configurator names to their configuration status.
        """
        if self.app_settings is None:
            self.app_settings = self.load_config()

        # Import all configurator modules to ensure they are registered
        self._import_configurators()

        # If no configurators are specified, use all configurators from the config
        if configurators is None:
            # This is a placeholder. In a real implementation, you would extract
            # the list of configurators from the configuration file.
            configurators = list(
                ConfiguratorRegistry.get_all_configurators().keys()
            )

        # Forward to ComponentOrchestrator
        component_orchestrator = self._get_component_orchestrator()
        status_dict = component_orchestrator.check_status(configurators)

        # Convert the status dict to the expected format
        return {
            name: info["configured"] for name, info in status_dict.items()
        }
