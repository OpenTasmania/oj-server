# -*- coding: utf-8 -*-
# installer/plugin_interface.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class InstallerPlugin(ABC):
    """
    Defines the interface for an installer plugin.

    This abstract base class is intended to be subclassed to create custom installer plugins.
    It provides a framework for defining various hooks, configurations, and behaviors required
    during the installation and post-installation processes of a plugin or application.

    The class specifies abstract methods and properties that must be overridden by derived
    classes to define their specific functionality. It also provides default implementation
    for certain methods that can be optionally overridden for custom behavior.

    Attributes:
        name (str): Abstract property that should be implemented by subclasses to
                    represent the name associated with the plugin.

    Methods:
        post_config_load(config: dict) -> dict
            Modifies or processes the configuration dictionary after it has been loaded.

        pre_apply_k8s(manifests: dict) -> dict
            Prepares and processes Kubernetes manifests before applying them.

        on_install_complete()
            Abstract hook for executing logic post-installation.

        on_error(error: Exception)
            Abstract method for handling errors during execution.

        get_python_dependencies() -> List[str]
            Retrieves a list of Python dependencies required for the plugin.

        get_database_requirements() -> Dict[str, Any]
            Abstract method to define database requirements.

        get_required_tables() -> List[str]
            Abstract method to retrieve names of required tables.

        get_optional_tables() -> List[str]
            Abstract method to retrieve names of optional tables.

        should_create_table(table_name: str, data_context: dict) -> bool
            Abstract method to determine whether a table should be created.

        pre_database_setup(config: dict) -> dict
            Abstract method to prepare configurations before database initialization.

        post_database_setup(db_connection)
            Abstract hook for performing actions after database setup is complete.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Defines an abstract property `name`. This property is intended to be implemented
        by subclasses and should provide the name of the object as a string.

        Attributes:
            name (str): The name associated with the object.

        """
        pass

    def post_config_load(self, config: dict) -> dict:
        """
        This function is executed after the configuration is loaded. It allows for
        post-processing or modification of the loaded configuration as needed before
        returning it for further use.

        Args:
            config (dict): A dictionary containing configuration data that has been
            loaded.

        Returns:
            dict: The possibly modified configuration dictionary post-processing.
        """
        return config

    def pre_apply_k8s(self, manifests: dict) -> dict:
        """
        Prepares Kubernetes manifests before applying them.

        This method processes the provided Kubernetes manifests and returns them, potentially
        modifying them in the process. It is intended for use cases where pre-apply hook
        operations are needed on manifests.

        Args:
            manifests (dict): A dictionary containing Kubernetes manifests.

        Returns:
            dict: A dictionary with the processed Kubernetes manifests.
        """
        return manifests

    @abstractmethod
    def on_install_complete(self):
        """
        An abstract method intended to be implemented by subclasses. This method
        serves as a template for defining behavior that should be executed once
        the installation process is complete.

        Raises:
            NotImplementedError: If the method is not overridden in a derived class.
        """
        pass

    @abstractmethod
    def on_error(self, error: Exception):
        """
        An abstract method to handle errors that occur during execution.

        This method is intended to be overridden in subclasses to provide specific
        error handling logic when an exception is encountered.

        Args:
            error (Exception): The exception object representing the error to be
            handled.
        """
        pass

    def get_python_dependencies(self) -> List[str]:
        """
        Retrieve a list of Python dependencies required for this plugin.

        This method can be overridden in subclasses to specify plugin-specific
        Python package dependencies that should be installed when the plugin
        is loaded.

        Returns:
            List[str]: A list of strings representing Python dependencies.
                      Each string should be in pip-compatible format (e.g., "package>=1.0.0").
                      Default implementation returns an empty list.
        """
        return []

    @abstractmethod
    def get_database_requirements(self) -> Dict[str, Any]:
        """
        An abstract method that must be implemented by subclasses to define the
        specific database requirements. This method should be overridden to
        specify the necessary configuration, parameters, or other details
        required for proper interaction with a database.

        Raises:
            NotImplementedError: If the method is not implemented in the
            subclass.

        Returns:
            Dict[str, Any]: A dictionary containing the database requirements
            needed for establishing a connection or performing operations.
        """
        pass

    @abstractmethod
    def get_required_tables(self) -> List[str]:
        """
        Represents an abstract method to retrieve a list of required table names for
        a specific implementation.

        Methods
        -------
        get_required_tables()
            Abstract method that, when implemented, returns a list of required database
            table names.

        Returns
        -------
        List[str]
            A list of strings where each string represents the name of a required
            database table.
        """
        pass

    @abstractmethod
    def get_optional_tables(self) -> List[str]:
        """
        Defines an abstract method for retrieving a list of optional table names. This method
        is meant to be implemented by subclasses to provide a specific implementation for
        returning optional database table names.

        Raises:
            NotImplementedError: If the method is not implemented by a subclass.

        Returns:
            List[str]: A list of optional table names.
        """
        pass

    @abstractmethod
    def should_create_table(
        self, table_name: str, data_context: dict
    ) -> bool:
        """
        Determines whether a table should be created based on the provided table name
        and context.

        This is an abstract method and should be implemented by subclasses to define
        the custom logic for determining the need to create a table.

        Parameters:
            table_name: str
                The name of the table to be evaluated.
            data_context: dict
                The context containing data or configurations relevant for deciding
                whether the table should be created.

        Returns:
            bool
                True if the table should be created, otherwise False.
        """
        pass

    @abstractmethod
    def pre_database_setup(self, config: dict) -> dict:
        """
        Defines the abstract method required to set up configurations before database initialization.

        This method is intended to be implemented in subclasses.
        Its purpose is to handle all preliminary customizations or configurations necessary
        before proceeding with the database setup process.

        Args:
            config (dict): A dictionary containing configuration settings required
                           for pre-database setup processes.

        Returns:
            dict: The updated or modified configuration dictionary after applying any
                  necessary adjustments or preconditions.
        """
        pass

    @abstractmethod
    def post_database_setup(self, db_connection):
        """
        An abstract method that serves as a hook for performing additional setup processes after the
        database connection has been initialized. This method is intended to be overridden in
        subclasses to implement custom database setup logic, ensuring the database is prepared for
        further operations.

        Args:
            db_connection: The initialized database connection object. Typically, subclasses will
            utilize this connection to finalize configurations, run migrations, or set up specific
            settings required for the application.

        Raises:
            NotImplementedError: If the subclass does not implement this abstract method.
        """
        pass
