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

    @abstractmethod
    def on_install_complete(self):
        """Hook called after the installation is successfully completed."""
        pass

    @abstractmethod
    def on_error(self, error: Exception):
        """Hook called if an error occurs during installation."""
        pass
