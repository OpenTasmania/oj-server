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
from typing import Any, Dict, List, Optional, Type

import yaml

from common.orchestrator import Orchestrator
from modular_setup.base_configurator import BaseConfigurator
from modular_setup.registry import ConfiguratorRegistry
from setup.config_models import AppSettings


class SetupOrchestrator:
    """
    Core orchestrator for the modular setup framework.

    This class is responsible for loading the configuration file, iterating
    through the requested configuration tasks, looking up the appropriate
    configurator module in the registry, and executing it.
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

        # Resolve dependencies to determine the order of configuration
        try:
            ordered_configurators = ConfiguratorRegistry.resolve_dependencies(
                configurators
            )
        except (KeyError, ValueError) as e:
            self.logger.error(
                f"Error resolving configurator dependencies: {str(e)}"
            )
            return False

        # Create a new orchestrator
        orchestrator = Orchestrator(self.app_settings, self.logger)
        self.orchestrator = orchestrator

        # Add tasks for each configurator
        for configurator_name in ordered_configurators:
            try:
                # Get the configurator class from the registry
                configurator_class = ConfiguratorRegistry.get_configurator(
                    configurator_name
                )

                # Create a function that will instantiate and configure the configurator
                def configure_task(
                    configurator_class: Type[BaseConfigurator],
                    app_settings: AppSettings,
                    context: Dict[str, Any],
                ) -> bool:
                    configurator = configurator_class(app_settings)

                    # Check if the component is already configured and skip it if not forced
                    if not force and configurator.is_configured():
                        self.logger.info(
                            f"{configurator_class.__name__} is already configured, skipping"
                        )
                        return True

                    return configurator.configure()

                # Add the task to the orchestrator
                orchestrator.add_task(
                    name=f"Configure {configurator_name}",
                    func=configure_task,
                    args=[configurator_class],
                    kwargs={},
                    fatal=True,
                )
            except KeyError:
                self.logger.error(
                    f"Configurator not found: {configurator_name}"
                )
                return False

        # Run the orchestrator
        result = orchestrator.run()
        return bool(result)

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

        # Resolve dependencies to determine the order of unconfiguration (reverse of configuration)
        try:
            ordered_configurators = ConfiguratorRegistry.resolve_dependencies(
                configurators
            )
            ordered_configurators.reverse()  # Unconfigure in reverse order
        except (KeyError, ValueError) as e:
            self.logger.error(
                f"Error resolving configurator dependencies: {str(e)}"
            )
            return False

        # Create a new orchestrator
        orchestrator = Orchestrator(self.app_settings, self.logger)
        self.orchestrator = orchestrator

        # Add tasks for each configurator
        for configurator_name in ordered_configurators:
            try:
                # Get the configurator class from the registry
                configurator_class = ConfiguratorRegistry.get_configurator(
                    configurator_name
                )

                # Create a function that will instantiate and unconfigure the configurator
                def unconfigure_task(
                    configurator_class: Type[BaseConfigurator],
                    app_settings: AppSettings,
                    context: Dict[str, Any],
                ) -> bool:
                    configurator = configurator_class(app_settings)
                    return configurator.unconfigure()

                # Add the task to the orchestrator
                orchestrator.add_task(
                    name=f"Unconfigure {configurator_name}",
                    func=unconfigure_task,
                    args=[configurator_class],
                    kwargs={},
                    fatal=True,
                )
            except KeyError:
                self.logger.error(
                    f"Configurator not found: {configurator_name}"
                )
                return False

        # Run the orchestrator
        result = orchestrator.run()
        return bool(result)

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

        # Check the status of each configurator
        status = {}
        for configurator_name in configurators:
            try:
                # Get the configurator class from the registry
                configurator_class = ConfiguratorRegistry.get_configurator(
                    configurator_name
                )

                # Instantiate the configurator and check if it's configured
                # We know self.app_settings is not None at this point
                assert self.app_settings is not None
                configurator = configurator_class(self.app_settings)
                status[configurator_name] = configurator.is_configured()
            except KeyError:
                self.logger.error(
                    f"Configurator not found: {configurator_name}"
                )
                status[configurator_name] = False

        return status
