# -*- coding: utf-8 -*-
# installer/plugin_interface.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List


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

    @abstractmethod
    def get_database_requirements(self) -> Dict[str, Any]:
        """Return database requirements for this plugin."""
        pass

    @abstractmethod
    def get_required_tables(self) -> List[str]:
        """Return list of table names this plugin requires."""
        pass

    @abstractmethod
    def get_optional_tables(self) -> List[str]:
        """Return list of optional table names this plugin might use."""
        pass

    @abstractmethod
    def should_create_table(
        self, table_name: str, data_context: dict
    ) -> bool:
        """Determine if a specific table should be created based on data context."""
        pass

    @abstractmethod
    def pre_database_setup(self, config: dict) -> dict:
        """Hook called before database setup."""
        pass

    @abstractmethod
    def post_database_setup(self, db_connection):
        """Hook called after database is ready."""
        pass
