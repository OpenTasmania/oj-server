"""
Orchestrator for the modular component framework.

This module provides the ComponentOrchestrator class, which is responsible for
loading the configuration, resolving dependencies, and executing the components
in the correct order.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Type

from modular.base_component import BaseComponent
from modular.registry import ComponentRegistry
from setup.config_models import AppSettings


class ComponentOrchestrator:
    """
    Orchestrator for the modular component framework.

    This class is responsible for loading the configuration, resolving dependencies,
    and executing the components in the correct order.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        self.app_settings = app_settings
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        # Import all component modules to ensure they are registered
        self._import_component_modules()

    def _import_component_modules(self):
        """
        Import all component modules to ensure they are registered.

        This method dynamically imports all Python modules in the components directory
        to ensure that all component classes are registered with the ComponentRegistry.
        """
        import importlib
        import pkgutil

        # Import installer modules
        try:
            import modular.installers

            # Get the path to the installers package
            installers_path = os.path.dirname(modular.installers.__file__)

            # Import all modules in the installers package
            for _, module_name, _ in pkgutil.iter_modules([installers_path]):
                # Skip __init__.py
                if module_name == "__init__":
                    continue

                # Import the module
                importlib.import_module(f"modular.installers.{module_name}")

                self.logger.debug(f"Imported installer module: {module_name}")
        except (ImportError, AttributeError) as e:
            self.logger.warning(
                f"Error importing installer modules: {str(e)}"
            )

        # Import configurator modules (Legacy - Commented out to prevent duplicates)
        # try:
        #     configurators_dir = os.path.join(
        #         os.path.dirname(os.path.dirname(__file__)),
        #         "modular_setup",
        #         "configurators",
        #     )
        #
        #     # Import all Python modules in the configurators directory
        #     for filename in os.listdir(configurators_dir):
        #         if filename.endswith(".py") and not filename.startswith("__"):
        #             module_name = filename[:-3]  # Remove the .py extension
        #             try:
        #                 importlib.import_module(
        #                     f"modular_setup.configurators.{module_name}"
        #                 )
        #                 self.logger.debug(
        #                     f"Imported configurator module: {module_name}"
        #                 )
        #             except ImportError as e:
        #                 self.logger.warning(
        #                     f"Error importing configurator module {module_name}: {str(e)}"
        #                 )
        # except (ImportError, FileNotFoundError) as e:
        #     self.logger.warning(
        #         f"Error importing configurator modules: {str(e)}"
        #     )

    def get_available_components(self) -> Dict[str, Type[BaseComponent]]:
        """
        Get all available components.

        Returns:
            A dictionary mapping component names to component classes.
        """
        # Cast the return value to the expected type
        components = ComponentRegistry.get_all_components()
        return {name: component for name, component in components.items()}

    def resolve_dependencies(self, component_names: List[str]) -> List[str]:
        """
        Resolve dependencies for a list of components.

        Args:
            component_names: A list of component names.

        Returns:
            A list of component names in the order they should be processed.
        """
        return ComponentRegistry.resolve_dependencies(component_names)

    def install(self, component_names: List[str]) -> bool:
        """
        Install the specified components.

        Args:
            component_names: A list of component names.

        Returns:
            True if all installations were successful, False otherwise.
        """
        try:
            # Resolve dependencies
            resolved_names = self.resolve_dependencies(component_names)

            self.logger.info(
                f"Installing components in order: {', '.join(resolved_names)}"
            )

            # Create component instances
            components = {
                name: ComponentRegistry.get_component(name)(
                    self.app_settings, self.logger
                )
                for name in resolved_names
            }

            # Keep track of successfully installed components for rollback
            installed_components: List[str] = []

            # Install each component
            for name in resolved_names:
                self.logger.info(f"Installing component: {name}")

                if not components[name].install():
                    self.logger.error(f"Failed to install component: {name}")

                    # Rollback previously installed components in reverse order
                    self._rollback_installations(
                        components, installed_components
                    )

                    return False

                # Add to the list of successfully installed components
                installed_components.append(name)
                self.logger.info(f"Successfully installed component: {name}")

            self.logger.info("All components installed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error during installation: {str(e)}")

            # If we have a list of installed components, try to roll them back
            if "installed_components" in locals() and installed_components:
                self._rollback_installations(components, installed_components)

            return False

    def configure(
        self, component_names: List[str], force: bool = False
    ) -> bool:
        """
        Configure the specified components.

        Args:
            component_names: A list of component names.
            force: If True, force reconfiguration even if already configured.

        Returns:
            True if all configurations were successful, False otherwise.
        """
        try:
            # Resolve dependencies
            resolved_names = self.resolve_dependencies(component_names)

            self.logger.info(
                f"Configuring components in order: {', '.join(resolved_names)}"
            )

            # Create component instances
            components = {
                name: ComponentRegistry.get_component(name)(
                    self.app_settings, self.logger
                )
                for name in resolved_names
            }

            # Keep track of successfully configured components for rollback
            configured_components: List[str] = []

            # Configure each component
            for name in resolved_names:
                self.logger.info(f"Configuring component: {name}")

                # Check if the component is already configured and skip it if not forced
                if not force and components[name].is_configured():
                    self.logger.info(
                        f"Component {name} is already configured, skipping"
                    )
                    continue

                if not components[name].configure():
                    self.logger.error(
                        f"Failed to configure component: {name}"
                    )

                    # Rollback previously configured components in reverse order
                    self._rollback_configurations(
                        components, configured_components
                    )

                    return False

                # Add to the list of successfully configured components
                configured_components.append(name)
                self.logger.info(f"Successfully configured component: {name}")

            self.logger.info("All components configured successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error during configuration: {str(e)}")

            # If we have a list of configured components, try to roll them back
            if "configured_components" in locals() and configured_components:
                self._rollback_configurations(
                    components, configured_components
                )

            return False

    def uninstall(self, component_names: List[str]) -> bool:
        """
        Uninstall the specified components.

        Args:
            component_names: A list of component names.

        Returns:
            True if all uninstallations were successful, False otherwise.
        """
        try:
            # Resolve dependencies in reverse order for uninstallation
            resolved_names = self.resolve_dependencies(component_names)
            resolved_names.reverse()

            self.logger.info(
                f"Uninstalling components in order: {', '.join(resolved_names)}"
            )

            # Create component instances
            components = {
                name: ComponentRegistry.get_component(name)(
                    self.app_settings, self.logger
                )
                for name in resolved_names
            }

            # Uninstall each component
            for name in resolved_names:
                self.logger.info(f"Uninstalling component: {name}")

                if not components[name].uninstall():
                    self.logger.error(
                        f"Failed to uninstall component: {name}"
                    )
                    return False

                self.logger.info(
                    f"Successfully uninstalled component: {name}"
                )

            self.logger.info("All components uninstalled successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error during uninstallation: {str(e)}")
            return False

    def unconfigure(self, component_names: List[str]) -> bool:
        """
        Unconfigure the specified components.

        Args:
            component_names: A list of component names.

        Returns:
            True if all unconfigurations were successful, False otherwise.
        """
        try:
            # Resolve dependencies in reverse order for unconfiguration
            resolved_names = self.resolve_dependencies(component_names)
            resolved_names.reverse()

            self.logger.info(
                f"Unconfiguring components in order: {', '.join(resolved_names)}"
            )

            # Create component instances
            components = {
                name: ComponentRegistry.get_component(name)(
                    self.app_settings, self.logger
                )
                for name in resolved_names
            }

            # Unconfigure each component
            for name in resolved_names:
                self.logger.info(f"Unconfiguring component: {name}")

                if not components[name].unconfigure():
                    self.logger.error(
                        f"Failed to unconfigure component: {name}"
                    )
                    return False

                self.logger.info(
                    f"Successfully unconfigured component: {name}"
                )

            self.logger.info("All components unconfigured successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error during unconfiguration: {str(e)}")
            return False

    def _rollback_installations(
        self,
        components: Dict[str, Any],  # Use Any to avoid type conflicts
        installed_components: List[str],
    ) -> None:
        """
        Roll back installations in reverse order.

        Args:
            components: A dictionary mapping component names to component instances.
            installed_components: A list of component names that were successfully installed.
        """
        # Reverse the list to roll back in reverse order of installation
        for name in reversed(installed_components):
            self.logger.info(
                f"Rolling back installation of component: {name}"
            )

            try:
                if not components[name].rollback_installation():
                    self.logger.error(
                        f"Failed to roll back installation of component: {name}"
                    )
                else:
                    self.logger.info(
                        f"Successfully rolled back installation of component: {name}"
                    )
            except Exception as e:
                self.logger.error(
                    f"Error during rollback of component {name}: {str(e)}"
                )

    def _rollback_configurations(
        self,
        components: Dict[str, Any],  # Use Any to avoid type conflicts
        configured_components: List[str],
    ) -> None:
        """
        Roll back configurations in reverse order.

        Args:
            components: A dictionary mapping component names to component instances.
            configured_components: A list of component names that were successfully configured.
        """
        # Reverse the list to roll back in reverse order of configuration
        for name in reversed(configured_components):
            self.logger.info(
                f"Rolling back configuration of component: {name}"
            )

            try:
                if not components[name].rollback_configuration():
                    self.logger.error(
                        f"Failed to roll back configuration of component: {name}"
                    )
                else:
                    self.logger.info(
                        f"Successfully rolled back configuration of component: {name}"
                    )
            except Exception as e:
                self.logger.error(
                    f"Error during rollback of component {name}: {str(e)}"
                )

    def check_status(
        self, component_names: List[str]
    ) -> Dict[str, Dict[str, bool]]:
        """
        Check the status of the specified components.

        Args:
            component_names: A list of component names.

        Returns:
            A dictionary mapping component names to their status (installed and configured).
        """
        try:
            # Create component instances
            components = {
                name: ComponentRegistry.get_component(name)(
                    self.app_settings, self.logger
                )
                for name in component_names
            }

            # Check status of each component
            status = {}
            for name in component_names:
                self.logger.info(f"Checking status of component: {name}")

                installed = components[name].is_installed()
                configured = components[name].is_configured()

                status[name] = {
                    "installed": installed,
                    "configured": configured,
                }

                if installed:
                    self.logger.info(f"Component {name} is installed")
                else:
                    self.logger.info(f"Component {name} is not installed")

                if configured:
                    self.logger.info(f"Component {name} is configured")
                else:
                    self.logger.info(f"Component {name} is not configured")

            return status

        except Exception as e:
            self.logger.error(f"Error checking status: {str(e)}")
            return {
                name: {"installed": False, "configured": False}
                for name in component_names
            }


# For backward compatibility during migration
class InstallerOrchestrator(ComponentOrchestrator):
    """
    Legacy orchestrator for the modular installer framework.

    This class is maintained for backward compatibility during migration.
    It inherits from ComponentOrchestrator and provides aliases for the methods.
    """

    def _import_installer_modules(self):
        """Alias for _import_component_modules"""
        return self._import_component_modules()

    def get_available_installers(self) -> Dict[str, Type[BaseComponent]]:
        """Alias for get_available_components"""
        return self.get_available_components()

    def check_installation_status(
        self, installer_names: List[str]
    ) -> Dict[str, bool]:
        """
        Check the installation status of the specified components.

        Args:
            installer_names: A list of installer names.

        Returns:
            A dictionary mapping installer names to their installation status.
        """
        status = self.check_status(installer_names)
        return {name: info["installed"] for name, info in status.items()}
