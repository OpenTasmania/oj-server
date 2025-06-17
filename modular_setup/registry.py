"""
Registry for configurator modules.

This module provides a registry for configurator modules to register themselves
and a decorator for registering configurator classes.
"""

from typing import Any, Dict, List, Optional, Set, Type

from modular_setup.base_configurator import BaseConfigurator


class ConfiguratorRegistry:
    """
    Registry for configurator modules.

    This class provides a registry for configurator modules to register themselves
    and methods for accessing registered configurators.
    """

    _registry: Dict[str, Type["BaseConfigurator"]] = {}

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

        def decorator(
            configurator_class: Type["BaseConfigurator"],
        ) -> Type["BaseConfigurator"]:
            if name in cls._registry:
                raise ValueError(
                    f"Configurator with name '{name}' already registered"
                )

            # Store metadata in the class if provided
            if metadata:
                configurator_class.metadata = metadata

            # Register the configurator class
            cls._registry[name] = configurator_class
            return configurator_class

        return decorator

    @classmethod
    def get_configurator(cls, name: str) -> Type["BaseConfigurator"]:
        """
        Get a configurator class by name.

        Args:
            name: The name of the configurator.

        Returns:
            The configurator class.

        Raises:
            KeyError: If no configurator with the given name is registered.
        """
        if name not in cls._registry:
            raise KeyError(f"No configurator registered with name '{name}'")

        return cls._registry[name]

    @classmethod
    def get_all_configurators(cls) -> Dict[str, Type["BaseConfigurator"]]:
        """
        Get all registered configurators.

        Returns:
            A dictionary mapping configurator names to configurator classes.
        """
        return cls._registry.copy()

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
        configurator_class = cls.get_configurator(name)
        metadata = getattr(configurator_class, "metadata", {})
        return set(metadata.get("dependencies", []))

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
        result = []
        visited = set()
        temp_visited = set()

        def visit(configurator: str):
            if configurator in temp_visited:
                raise ValueError(
                    f"Circular dependency detected involving '{configurator}'"
                )

            if configurator in visited:
                return

            temp_visited.add(configurator)

            for dependency in cls.get_configurator_dependencies(configurator):
                visit(dependency)

            temp_visited.remove(configurator)
            visited.add(configurator)
            result.append(configurator)

        for configurator in configurators:
            if configurator not in visited:
                visit(configurator)

        return result
