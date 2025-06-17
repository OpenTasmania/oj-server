"""
Registry for configurator modules.

This module provides a registry for configurator modules to register themselves
and a decorator for registering configurator classes.
"""

from typing import Any, Dict, List, Optional, Set, Type

from modular.base_component import BaseComponent
from modular.registry import ComponentRegistry


# For backward compatibility during migration
class ConfiguratorRegistry:
    """
    Legacy registry for configurator modules.

    This class is maintained for backward compatibility during migration.
    It provides aliases to the ComponentRegistry methods.
    """

    _registry: Dict[str, Type["BaseComponent"]] = {}

    @classmethod
    def register(cls, name: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Decorator for registering configurator classes.

        Args:
            name: The name of the configurator.
            metadata: Optional metadata for the configurator, such as dependencies.

        Returns:
            A decorator function that registers the configurator class.
        """
        return ComponentRegistry.register(name, metadata)

    @classmethod
    def get_configurator(cls, name: str) -> Type["BaseComponent"]:
        """
        Get a configurator class by name.

        Args:
            name: The name of the configurator.

        Returns:
            The configurator class.

        Raises:
            KeyError: If no configurator with the given name is registered.
        """
        return ComponentRegistry.get_component(name)

    @classmethod
    def get_all_configurators(cls) -> Dict[str, Type["BaseComponent"]]:
        """
        Get all registered configurators.

        Returns:
            A dictionary mapping configurator names to configurator classes.
        """
        return ComponentRegistry.get_all_components()

    @classmethod
    def get_configurator_dependencies(cls, name: str) -> Set[str]:
        """
        Get the dependencies of a configurator.

        Args:
            name: The name of the configurator.

        Returns:
            A set of configurator names that the specified configurator depends on.

        Raises:
            KeyError: If no configurator with the given name is registered.
        """
        return ComponentRegistry.get_component_dependencies(name)

    @classmethod
    def resolve_dependencies(cls, configurators: List[str]) -> List[str]:
        """
        Resolve dependencies for a list of configurators.

        Args:
            configurators: A list of configurator names.

        Returns:
            A list of configurator names in the order they should be configured.

        Raises:
            KeyError: If any of the configurators or their dependencies are not registered.
            ValueError: If there is a circular dependency.
        """
        return ComponentRegistry.resolve_dependencies(configurators)
