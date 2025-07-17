# Installer Plugin Architecture

## 1. Overview

This document describes the plugin architecture for the OpenJourney Server installer. This system allows developers to
extend and customize the installation process without modifying the core installer code. This is useful for adding new
features, integrating with external systems, or applying site-specific configurations.

## 2. How it Works

Plugins are Python modules that are placed in the `/plugins/` directory. The installer automatically discovers and loads
these plugins at startup. Each plugin can implement a set of "hooks," which are methods that are called at specific
points during the installation process. These hooks allow plugins to inspect and modify the installer's configuration
and behavior.

### 2.1. Plugin Directory

- The `/plugins/` directory is the main container for all plugins.
- It is recommended to create subdirectories for each plugin to keep the code organized.
- The `/plugins/private/` subdirectory is specifically intended for proprietary or private plugins. This directory is
  included in the project's `.gitignore` file, which means that any plugins placed here will not be tracked by Git and
  will not be accidentally committed to the main repository.
- The `/plugins/public/` subdirectory is intended for open-source or publicly shareable plugins.

### 2.2. Plugin Discovery

The installer automatically scans the `/plugins/` directory for subdirectories. For each subdirectory, it looks for a
file named `plugin.py`. This file is the entry point for the plugin, and it is expected to contain a class that
implements the `InstallerPlugin` interface.

### 2.3. The `InstallerPlugin` Interface

To ensure that all plugins are compatible with the installer, each plugin must implement the `InstallerPlugin`
interface. This interface is defined in the `installer.plugin_interface` module and it specifies the hooks that a plugin
can implement.

Here is the definition of the `InstallerPlugin` interface:

```python
# installer/plugin_interface.py
from abc import ABC, abstractmethod


class InstallerPlugin(ABC):
    """Abstract Base Class for an installer plugin."""

    @property
    @abstractmethod
    def name(self) -> str:
        """A unique name for the plugin."""
        pass

    def post_config_load(self, config: dict) -> dict:
        """
        Hook called after the main configuration is loaded.
        Plugins can modify and return the configuration object.
        """
        return config

    def pre_apply_k8s(self, manifests: dict) -> dict:
        """
        Hook called before Kubernetes manifests are applied.
        Plugins can modify the dictionary of manifests.
        """
        return manifests

    def on_install_complete(self):
        """Hook called after the installation is successfully completed."""
        pass

    def on_error(self, error: Exception):
        """Hook called if an error occurs during installation."""
        pass
```

### 2.4. Execution Hooks

The following hooks are available for plugins to implement:

- `post_config_load(config)`: This hook is called after the main configuration file (`config.yaml`) has been loaded. It
  allows plugins to read, modify, or add to the configuration before it is used by the installer.
- `pre_apply_k8s(manifests)`: This hook is called just before the Kubernetes manifests are applied to the cluster. It
  allows plugins to inspect and modify the manifests before they are deployed.
- `on_install_complete()`: This hook is called after the installation has completed successfully.
- `on_error(exception)`: This hook is called if an error occurs during the installation process.

## 3. Creating a Plugin

To create a plugin, you need to:

1. Create a new subdirectory in the `/plugins/` directory.
2. Inside the new subdirectory, create a file named `plugin.py`.
3. In `plugin.py`, create a class that inherits from `InstallerPlugin` and implements the desired hooks.

Here is an example of a simple plugin that logs a message after the configuration has been loaded:

```python
# /plugins/my_plugin/plugin.py

from installer.plugin_interface import InstallerPlugin


class MyPlugin(InstallerPlugin):
    @property
    def name(self) -> str:
        return "MyPlugin"

    def post_config_load(self, config: dict) -> dict:
        print("MyPlugin: The configuration has been loaded!")
        return config
```

## 4. Security Considerations

- **Code Execution**: The plugin architecture executes Python code from the `/plugins/` directory. You should only use
  plugins from trusted sources.
- **Permissions**: Plugins run with the same permissions as the main installer script. This means that they can read and
  write files, access the network, and execute shell commands.
