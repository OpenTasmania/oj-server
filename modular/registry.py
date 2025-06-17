"""
Registry for installer modules.

This module provides a registry for installer modules to register themselves
and a decorator for registering installer classes.
"""

from typing import Any, Dict, List, Optional, Set, Type

from modular.base_installer import BaseInstaller


class InstallerRegistry:
    """
    Registry for installer modules.

    This class provides a registry for installer modules to register themselves
    and methods for accessing registered installers.
    """

    _registry: Dict[str, Type["BaseInstaller"]] = {}

    @classmethod
    def register(cls, name: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Decorator for registering installer classes.

        Args:
            name: The name of the installer.
            metadata: Optional metadata for the installer, such as dependencies,
                      estimated installation time, and required system resources.

        Returns:
            A decorator function that registers the installer class.
        """

        def decorator(
            installer_class: Type["BaseInstaller"],
        ) -> Type["BaseInstaller"]:
            if name in cls._registry:
                raise ValueError(
                    f"Installer with name '{name}' already registered"
                )

            # Store metadata in the class if provided
            if metadata:
                installer_class.metadata = metadata

            # Register the installer class
            cls._registry[name] = installer_class
            return installer_class

        return decorator

    @classmethod
    def get_installer(cls, name: str) -> Type["BaseInstaller"]:
        """
        Get an installer class by name.

        Args:
            name: The name of the installer.

        Returns:
            The installer class.

        Raises:
            KeyError: If no installer with the given name is registered.
        """
        if name not in cls._registry:
            raise KeyError(f"No installer registered with name '{name}'")

        return cls._registry[name]

    @classmethod
    def get_all_installers(cls) -> Dict[str, Type["BaseInstaller"]]:
        """
        Get all registered installers.

        Returns:
            A dictionary mapping installer names to installer classes.
        """
        return cls._registry.copy()

    @classmethod
    def get_installer_dependencies(cls, name: str) -> Set[str]:
        """
        Get the dependencies of an installer.

        Args:
            name: The name of the installer.

        Returns:
            A set of installer names that the specified installer depends on.

        Raises:
            KeyError: If no installer with the given name is registered.
        """
        installer_class = cls.get_installer(name)
        metadata = getattr(installer_class, "metadata", {})
        return set(metadata.get("dependencies", []))

    @classmethod
    def resolve_dependencies(cls, installers: List[str]) -> List[str]:
        """
        Resolve dependencies for a list of installers.

        Args:
            installers: A list of installer names.

        Returns:
            A list of installer names in the order they should be installed.

        Raises:
            KeyError: If any of the installers or their dependencies are not registered.
            ValueError: If there is a circular dependency.
        """
        result = []
        visited = set()
        temp_visited = set()

        def visit(installer: str):
            if installer in temp_visited:
                raise ValueError(
                    f"Circular dependency detected involving '{installer}'"
                )

            if installer in visited:
                return

            temp_visited.add(installer)

            for dependency in cls.get_installer_dependencies(installer):
                visit(dependency)

            temp_visited.remove(installer)
            visited.add(installer)
            result.append(installer)

        for installer in installers:
            if installer not in visited:
                visit(installer)

        return result


# This comment is kept for reference:
# Previously there was a BaseInstaller stub class here to avoid circular imports,
# but now we import the actual BaseInstaller class from base_installer.py
