# installer/plugin_manager.py
import importlib.util
import sys
from pathlib import Path
from typing import List

from .plugin_interface import InstallerPlugin


class PluginManager:
    def __init__(self, plugin_dir: str = "plugins"):
        self.plugin_dir = Path(plugin_dir)
        self.plugins: List[InstallerPlugin] = []
        self._discover_and_register_plugins()

    def _discover_and_register_plugins(self):
        if not self.plugin_dir.is_dir():
            return

        # Recursively search for plugin.py files
        for plugin_file in self.plugin_dir.rglob("plugin.py"):
            if plugin_file.is_file():
                self._load_plugin(plugin_file)

    def _load_plugin(self, path: Path):
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
                        self.plugins.append(obj())
                        print(f"Successfully registered plugin: {obj().name}")

        except Exception as e:
            print(f"Failed to load plugin from {path}: {e}")

    def run_hook(self, hook_name: str, *args, **kwargs):
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
