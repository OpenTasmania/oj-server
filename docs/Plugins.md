# OpenJourney Server Plugin Architecture

## 1. Overview

This document describes the enhanced plugin architecture for the OpenJourney Server installer and data processing system. This system allows developers to extend and customize both the installation process and database management without modifying the core code. The architecture implements database optimization features including lazy table creation, conditional row insertion, and intelligent resource management.

Key features of the enhanced plugin architecture:
- **Lazy Table Creation**: Tables are only created when actually needed
- **Conditional Database Operations**: Optional tables and features are created based on data context
- **Database Optimization**: Plugins only create the database objects they require
- **Migration System**: Structured database schema management and versioning
- **Resource Efficiency**: Reduces database bloat and improves startup performance

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

    def get_database_requirements(self) -> dict:
        return {
            "required_tables": [],
            "optional_tables": [],
            "required_extensions": [],
            "estimated_row_count": {}
        }

    def get_required_tables(self) -> list:
        return []

    def get_optional_tables(self) -> list:
        return []

    def should_create_table(self, table_name: str, data_context: dict) -> bool:
        return False

    def pre_database_setup(self, config: dict) -> dict:
        return config

    def post_database_setup(self, db_connection):
        pass
```

## 4. Database Optimization Features

The enhanced plugin architecture includes powerful database optimization features that allow plugins to create only the database objects they actually need.

### 4.1. Lazy Table Creation

Tables are created only when they are actually needed, based on the data context and plugin requirements:

- **Required Tables**: Always created for core functionality
- **Optional Tables**: Created only when specific data or features are present
- **Conditional Creation**: Based on configuration settings and data analysis

### 4.2. Database Requirements Declaration

Plugins declare their database requirements through the `get_database_requirements()` method:

```python
def get_database_requirements(self) -> Dict[str, Any]:
    return {
        "required_tables": ["routes", "stops"],           # Always created
        "optional_tables": ["fares", "transfers"],        # Created conditionally
        "required_extensions": ["postgis"],               # Database extensions needed
        "estimated_row_count": {                          # For capacity planning
            "routes": 1000,
            "stops": 5000
        }
    }
```

### 4.3. Data Context Analysis

Plugins analyze the data context to determine which optional tables to create:

```python
def should_create_table(self, table_name: str, data_context: dict) -> bool:
    # Create fares table only if fare data is present
    if table_name == "fares":
        return data_context.get("has_fare_data", False)
    return False
```

### 4.4. Database Utilities

The `install_kubernetes.database_utils` module provides comprehensive database management:

```python
from installer.database_utils import get_database_manager, DatabaseManager

# Get database manager
db_manager = get_database_manager(config)

# Check if table exists
if db_manager.table_exists("routes", "openjourney"):
    print("Routes table exists")

# Create schema
db_manager.create_schema("openjourney")

# Create extension
db_manager.create_extension("postgis")
```

### 4.5. Migration System

The migration system provides structured database schema management:

```python
from installer.database_utils import Migration, MigrationManager

class MyMigration001(Migration):
    def __init__(self):
        super().__init__("initial_schema", "001", "MyPlugin")
    
    def up(self, db_manager: DatabaseManager):
        # Apply migration
        db_manager.connection.execute("CREATE TABLE ...")
    
    def down(self, db_manager: DatabaseManager):
        # Rollback migration
        db_manager.connection.execute("DROP TABLE ...")

# Apply migration
migration_manager = MigrationManager(db_manager)
migration_manager.apply_migration(MyMigration001())
```

## 5. Advanced Plugin Example: GTFS Plugin

Here's a complete example of an advanced plugin that implements database optimization:

```python
# /plugins/gtfs_plugin/plugin.py

from installer.plugin_interface import InstallerPlugin
from installer.database_utils import get_database_manager, DatabaseManager

class GTFSPlugin(InstallerPlugin):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._db_manager = None
        self._created_tables = set()

    @property
    def name(self) -> str:
        return "GTFSPlugin"

    def get_database_requirements(self) -> Dict[str, Any]:
        return {
            "required_tables": ["data_sources", "routes", "stops", "segments"],
            "optional_tables": ["fares", "transfers", "path_geometry"],
            "required_extensions": ["postgis"],
            "estimated_row_count": {
                "routes": 1000,
                "stops": 5000,
                "segments": 10000
            }
        }

    def should_create_table(self, table_name: str, data_context: dict) -> bool:
        # Create optional tables based on data context
        conditions = {
            "fares": data_context.get("has_fare_data", False),
            "transfers": data_context.get("has_transfers", False),
            "path_geometry": data_context.get("has_shapes", False)
        }
        return conditions.get(table_name, False)

    def ensure_tables_exist(self, db_manager: DatabaseManager, data_context: dict):
        # Create schema
        if not db_manager.schema_exists("openjourney"):
            db_manager.create_schema("openjourney")

        # Create required extensions
        if not db_manager.extension_exists("postgis"):
            db_manager.create_extension("postgis")

        # Get existing tables
        existing_tables = set(db_manager.get_tables("openjourney"))
        
        # Determine which tables to create
        required_tables = set(self.get_required_tables())
        optional_tables = set(self.get_optional_tables())
        
        tables_to_create = required_tables - existing_tables
        
        # Add optional tables if conditions are met
        for table in optional_tables:
            if table not in existing_tables and self.should_create_table(table, data_context):
                tables_to_create.add(table)

        # Create missing tables
        for table in tables_to_create:
            self.create_table(db_manager, table)

    def pre_database_setup(self, config: dict) -> dict:
        # Analyze data context
        data_context = self.analyze_gtfs_data_context(config)
        config["gtfs_data_context"] = data_context
        return config

    def post_database_setup(self, db_connection):
        # Setup database schema based on context
        db_manager = self.get_database_manager(config)
        data_context = config.get("gtfs_data_context", {})
        self.ensure_tables_exist(db_manager, data_context)
```

## 6. Configuration-Driven Features

Plugins can use configuration to control which features are enabled:

```yaml
# config.yaml
plugins:
  gtfs_processor:
    enabled: true
    features:
      - routes
      - stops
      - segments
      - fares      # Optional - only create if fare data exists
      - transfers  # Optional - only create if transfer data exists
```

## 7. Security Considerations

- **Code Execution**: The plugin architecture executes Python code from the `/plugins/` directory. You should only use
  plugins from trusted sources.
- **Permissions**: Plugins run with the same permissions as the main installer script. This means that they can read and
  write files, access the network, and execute shell commands.
- **Database Access**: Plugins have direct database access through the DatabaseManager. Ensure proper validation and sanitization of data.
