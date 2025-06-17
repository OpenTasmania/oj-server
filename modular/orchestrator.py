"""
Orchestrator for the modular installer framework.

This module provides the InstallerOrchestrator class, which is responsible for
loading the configuration, resolving dependencies, and executing the installers
in the correct order.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Type

from modular.base_installer import BaseInstaller
from modular.registry import InstallerRegistry
from setup.config_models import AppSettings


class InstallerOrchestrator:
    """
    Orchestrator for the modular installer framework.

    This class is responsible for loading the configuration, resolving dependencies,
    and executing the installers in the correct order.
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

        # Import all installer modules to ensure they are registered
        self._import_installer_modules()

    def _import_installer_modules(self):
        """
        Import all installer modules to ensure they are registered.

        This method dynamically imports all Python modules in the installers directory
        to ensure that all installer classes are registered with the InstallerRegistry.
        """
        import importlib
        import pkgutil

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

    def get_available_installers(self) -> Dict[str, Type[BaseInstaller]]:
        """
        Get all available installers.

        Returns:
            A dictionary mapping installer names to installer classes.
        """
        # Cast the return value to the expected type
        installers = InstallerRegistry.get_all_installers()
        return {name: installer for name, installer in installers.items()}

    def resolve_dependencies(self, installer_names: List[str]) -> List[str]:
        """
        Resolve dependencies for a list of installers.

        Args:
            installer_names: A list of installer names.

        Returns:
            A list of installer names in the order they should be installed.
        """
        return InstallerRegistry.resolve_dependencies(installer_names)

    def install(self, installer_names: List[str]) -> bool:
        """
        Install the specified components.

        Args:
            installer_names: A list of installer names.

        Returns:
            True if all installations were successful, False otherwise.
        """
        try:
            # Resolve dependencies
            resolved_names = self.resolve_dependencies(installer_names)

            self.logger.info(
                f"Installing components in order: {', '.join(resolved_names)}"
            )

            # Create installer instances
            installers = {
                name: InstallerRegistry.get_installer(name)(
                    self.app_settings, self.logger
                )
                for name in resolved_names
            }

            # Keep track of successfully installed components for rollback
            installed_components: List[str] = []

            # Install each component
            for name in resolved_names:
                self.logger.info(f"Installing component: {name}")

                if not installers[name].install():
                    self.logger.error(f"Failed to install component: {name}")

                    # Rollback previously installed components in reverse order
                    self._rollback_installations(
                        installers, installed_components
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
                self._rollback_installations(installers, installed_components)

            return False

    def uninstall(self, installer_names: List[str]) -> bool:
        """
        Uninstall the specified components.

        Args:
            installer_names: A list of installer names.

        Returns:
            True if all uninstallations were successful, False otherwise.
        """
        try:
            # Resolve dependencies in reverse order for uninstallation
            resolved_names = self.resolve_dependencies(installer_names)
            resolved_names.reverse()

            self.logger.info(
                f"Uninstalling components in order: {', '.join(resolved_names)}"
            )

            # Create installer instances
            installers = {
                name: InstallerRegistry.get_installer(name)(
                    self.app_settings, self.logger
                )
                for name in resolved_names
            }

            # Uninstall each component
            for name in resolved_names:
                self.logger.info(f"Uninstalling component: {name}")

                if not installers[name].uninstall():
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

    def _rollback_installations(
        self,
        installers: Dict[str, Any],  # Use Any to avoid type conflicts
        installed_components: List[str],
    ) -> None:
        """
        Roll back installations in reverse order.

        Args:
            installers: A dictionary mapping installer names to installer instances.
            installed_components: A list of component names that were successfully installed.
        """
        # Reverse the list to roll back in reverse order of installation
        for name in reversed(installed_components):
            self.logger.info(
                f"Rolling back installation of component: {name}"
            )

            try:
                if not installers[name].rollback():
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
        try:
            # Create installer instances
            installers = {
                name: InstallerRegistry.get_installer(name)(
                    self.app_settings, self.logger
                )
                for name in installer_names
            }

            # Check installation status of each component
            status = {}
            for name in installer_names:
                self.logger.info(
                    f"Checking installation status of component: {name}"
                )
                status[name] = installers[name].is_installed()

                if status[name]:
                    self.logger.info(f"Component {name} is installed")
                else:
                    self.logger.info(f"Component {name} is not installed")

            return status

        except Exception as e:
            self.logger.error(f"Error checking installation status: {str(e)}")
            return {name: False for name in installer_names}
