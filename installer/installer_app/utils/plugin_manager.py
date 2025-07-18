# -*- coding: utf-8 -*-
# installer/plugin_manager.py
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import List

from .plugin_interface import InstallerPlugin


class PluginManager:
    """
    Manages the discovery, registration, and execution of plugins.

    The PluginManager is responsible for loading plugins from a specified directory,
    registering them, installing their dependencies, and providing functionality
    to run specific hooks implemented by the plugins.

    Attributes:
    plugin_dir (Path): The directory where the plugin files are located.
    plugins (List[InstallerPlugin]): The list of registered installer plugins.

    Parameters:
    plugin_dir: The path to the directory where plugins are stored. Defaults to "plugins".

    Methods:
    run_hook: Executes a specific hook on all registered plugins.
    """

    def __init__(self, plugin_dir: str = "plugins"):
        self.plugin_dir = Path(plugin_dir)
        self.plugins: List[InstallerPlugin] = []
        self._discover_and_register_plugins()

    def _discover_and_register_plugins(self):
        """
        Discovers and registers plugins by scanning a directory for plugin files.

        This method checks if the plugin directory is valid and, if so, searches recursively
        for Python files named "plugin.py". Upon finding each valid file, it attempts to
        load the respective plugin.

        Raises:
            FileNotFoundError: If any plugin file cannot be accessed during registration.
        """
        if not self.plugin_dir.is_dir():
            return

        # Recursively search for plugin.py files
        for plugin_file in self.plugin_dir.rglob("plugin.py"):
            if plugin_file.is_file():
                self._load_plugin(plugin_file)

    def _load_plugin(self, path: Path):
        """
        Loads a plugin from the given file path, registers it, and resolves its dependencies.

        This method dynamically imports a Python module defined at the given file path
        and checks for a class within the module that inherits from the `InstallerPlugin`
        base class (excluding the base class itself). If such a class is found, an instance
        of the plugin is created, its dependencies are resolved, and it is added to the
        list of registered plugins. If the loading operation fails, an error message is logged.

        Parameters:
        path (Path): The file path of the plugin module to load.

        Raises:
        Exception: If an error occurs during module import or plugin registration.
        """
        try:
            spec = importlib.util.spec_from_file_location(
                f"plugins.{path.parent.name}", path
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)

                # Look for a class that inherits from InstallerPlugin
                for item in dir(module):
                    obj = getattr(module, item)
                    if (
                        isinstance(obj, type)
                        and issubclass(obj, InstallerPlugin)
                        and obj is not InstallerPlugin
                    ):
                        plugin_instance = obj()
                        self._install_plugin_dependencies(plugin_instance)
                        self.plugins.append(plugin_instance)
                        print(
                            f"Successfully registered plugin: {plugin_instance.name}"
                        )

        except Exception as e:
            print(f"Failed to load plugin from {path}: {e}")

    def _install_plugin_dependencies(self, plugin: InstallerPlugin):
        """
        Installs the dependencies of a given plugin by invoking pip commands
        programmatically through subprocess. Fetches the required dependencies
        from the plugin and ensures their proper installation.

        Parameters:
        plugin: InstallerPlugin
            The plugin instance for which python dependencies need
            to be installed.

        Raises:
        Exception
            If there is any issue during the dependency installation
            process, it raises the exception after logging the failure.
        """
        try:
            dependencies = plugin.get_python_dependencies()
            if dependencies:
                print(
                    f"Installing dependencies for plugin {plugin.name}: {dependencies}"
                )
                for dependency in dependencies:
                    subprocess.check_call([
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        dependency,
                    ])
                print(
                    f"Successfully installed dependencies for plugin {plugin.name}"
                )
        except Exception as e:
            print(
                f"Failed to install dependencies for plugin {plugin.name}: {e}"
            )
            raise

    def run_hook(self, hook_name: str, *args, **kwargs):
        """
        Executes a specified hook method for all registered plugins. Hooks can either be used to modify
        data in a chaining manner or as simple notification hooks.

        Parameters:
            hook_name: str
                The name of the hook method to be executed on each plugin.
            *args: Any
                Positional arguments to be passed to the hook method.
            **kwargs: Any
                Keyword arguments to be passed to the hook method.

        Returns:
            Any:
                Returns the modified data when the hook is one that modifies data (e.g., "post_config_load",
                "pre_apply_k8s"). For other hooks, no value is returned.

        Raises:
            AttributeError:
                If the specified hook method does not exist in a plugin.
        """
        # For hooks that modify data, we chain the calls
        if hook_name in ["post_config_load", "pre_apply_k8s"]:
            data = args[0]
            for plugin in self.plugins:
                data = getattr(plugin, hook_name)(data, **kwargs)
            return data
        else:
            # For simple notification hooks
            for plugin in self.plugins:
                getattr(plugin, hook_name)(*args, **kwargs)
