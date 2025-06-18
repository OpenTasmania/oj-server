"""
Registry for component modules.

This module provides a registry for component modules to register themselves
and a decorator for registering component classes.
"""

from typing import Any, Dict, List, Optional, Set, Type

from installer.base_component import BaseComponent


class ComponentRegistry:
    """
    Registry for component modules.

    This class provides a registry for component modules to register themselves
    and methods for accessing registered components.
    """

    _registry: Dict[str, Type["BaseComponent"]] = {}

    @classmethod
    def register(cls, name: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Decorator for registering component classes.

        Args:
            name: The name of the component.
            metadata: Optional metadata for the component, such as dependencies,
                      estimated installation time, and required system resources.

        Returns:
            A decorator function that registers the component class.
        """

        def decorator(
            component_class: Type["BaseComponent"],
        ) -> Type["BaseComponent"]:
            if name in cls._registry:
                raise ValueError(
                    f"Component with name '{name}' already registered"
                )

            # Store metadata in the class if provided
            if metadata:
                component_class.metadata = metadata

            # Register the component class
            cls._registry[name] = component_class
            return component_class

        return decorator

    @classmethod
    def get_component(cls, name: str) -> Type["BaseComponent"]:
        """
        Get a component class by name.

        Args:
            name: The name of the component.

        Returns:
            The component class.

        Raises:
            KeyError: If no component with the given name is registered.
        """
        if name not in cls._registry:
            raise KeyError(f"No component registered with name '{name}'")

        return cls._registry[name]

    @classmethod
    def get_all_components(cls) -> Dict[str, Type["BaseComponent"]]:
        """
        Get all registered components.

        Returns:
            A dictionary mapping component names to component classes.
        """
        return cls._registry.copy()

    @classmethod
    def get_component_dependencies(cls, name: str) -> Set[str]:
        """
        Get the dependencies of a component.

        Args:
            name: The name of the component.

        Returns:
            A set of component names that the specified component depends on.

        Raises:
            KeyError: If no component with the given name is registered.
        """
        component_class = cls.get_component(name)
        metadata = getattr(component_class, "metadata", {})
        return set(metadata.get("dependencies", []))

    @classmethod
    def resolve_dependencies(cls, components: List[str]) -> List[str]:
        """
        Resolve dependencies for a list of components.

        Args:
            components: A list of component names.

        Returns:
            A list of component names in the order they should be processed.

        Raises:
            KeyError: If any of the components or their dependencies are not registered.
            ValueError: If there is a circular dependency.
        """
        result = []
        visited = set()
        temp_visited = set()

        def visit(component: str):
            if component in temp_visited:
                raise ValueError(
                    f"Circular dependency detected involving '{component}'"
                )

            if component in visited:
                return

            temp_visited.add(component)

            for dependency in cls.get_component_dependencies(component):
                visit(dependency)

            temp_visited.remove(component)
            visited.add(component)
            result.append(component)

        for component in components:
            if component not in visited:
                visit(component)

        return result


# For backward compatibility during migration
class InstallerRegistry(ComponentRegistry):
    """
    Legacy registry for installer modules.

    This class is maintained for backward compatibility during migration.
    It inherits from ComponentRegistry and provides aliases for the methods.
    """

    @classmethod
    def get_installer(cls, name: str) -> Type["BaseComponent"]:
        """Alias for get_component"""
        return cls.get_component(name)

    @classmethod
    def get_all_installers(cls) -> Dict[str, Type["BaseComponent"]]:
        """Alias for get_all_components"""
        return cls.get_all_components()

    @classmethod
    def get_installer_dependencies(cls, name: str) -> Set[str]:
        """Alias for get_component_dependencies"""
        return cls.get_component_dependencies(name)
