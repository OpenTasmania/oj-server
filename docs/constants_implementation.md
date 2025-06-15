# Constants Implementation Plan

## Overview

This document outlines the plan for implementing a centralized constants management system in the OSM-OSRM Server project. The primary goal is to move constants from various parts of the codebase into a single, dedicated file for easier maintenance and configuration.

## Current State

Currently, the project manages constants in several ways:

1. **Hard-coded in Python files**: Many constants are defined at the top of `setup/config_models.py` as default values.
2. **Configuration in config.yaml**: The main configuration file contains settings that override defaults.
3. **Service-specific config files**: Some services have their own configuration files in the `config_files` directory.
4. **Commented code**: Some features (like pgadmin tools) are disabled via comments in the code and settings in config.yaml.

## Implementation Plan

### Phase 1: Create Constants File Structure

1. **Create constants.yaml in /common directory**:
   - Move the empty `constants.yaml` file from `config_files/` to `/common/`
   - Define the initial structure with sections for different types of constants

2. **Implement Constants Loading Mechanism**:
   - Create a utility function in `/common/` to load constants from the YAML file
   - Ensure the constants are accessible throughout the application
   - Update the configuration loading system to incorporate constants

### Phase 2: Move PgAdmin Configuration to Constants

1. **Define PgAdmin Constants**:
   - Add a `features` section to `constants.yaml` with a `pgadmin_enabled` flag
   - Set the default value to `false` to maintain current behavior

2. **Update PgAdmin Installation Logic**:
   - Modify `installer/pgadmin_installer.py` to check the constant instead of the config setting
   - Update `main_installer.py` to uncomment the pgadmin-related imports and use the constant

3. **Update Configuration Models**:
   - Update `setup/config_models.py` to use the constant for the default value of `PgAdminSettings.install`

### Phase 3: Move Other Major Constants

1. **Identify Constants to Move**:
   - Default values from `setup/config_models.py`
   - Service configuration defaults
   - System-wide settings

2. **Organize Constants by Category**:
   - Features: Flags that enable/disable features
   - Defaults: Default values for configuration settings
   - Paths: File and directory paths
   - URLs: Default URLs for external resources
   - Templates: Default templates for configuration files

3. **Update Code to Use Constants**:
   - Modify code to reference constants from the centralized file
   - Ensure backward compatibility with existing configuration

## Constants File Structure

The structure for `constants.yaml` is:

```yaml
# /common/constants.yaml
# Central constants file for the OSM-OSRM Server project

# Feature flags
features:
  pgadmin_enabled: false
  pgagent_enabled: true

# Default values
defaults:
  admin_group_ip: "192.168.128.0/22"
  gtfs_feed_url: "https://www.transport.act.gov.au/googletransit/google_transit.zip"
  vm_ip_or_domain: "example.com"
  pg_tileserv_binary_location: "https://postgisftw.s3.amazonaws.com/pg_tileserv_latest_linux.zip"
  log_prefix: "[MAP-SETUP]"

  # Database defaults
  postgres:
    host: "127.0.0.1"
    port: 5432
    database: "gis"
    user: "osmuser"
    password: "yourStrongPasswordHere"

  # Container defaults
  container:
    runtime_command: "docker"
    osrm_image_tag: "osrm/osrm-backend:latest"

  # OSRM defaults
  osrm:
    data_base_dir: "/opt/osm_data"
    processed_dir: "/opt/osrm_processed_data"
    base_pbf_url: "https://download.geofabrik.de/australia-oceania/australia-latest.osm.pbf"
    base_pbf_filename: "australia-latest.osm.pbf"
    car_profile_port: 5000
    max_table_size_routed: 8000
    profile_lua_in_container: "/opt/car.lua"

  # Web server defaults
  apache:
    listen_port: 8080

  # Package preseeding
  package_preseeding:
    tzdata:
      areas: "select Australia"
      zones_australia: "select Hobart"
    unattended_upgrades:
      enable_auto_updates: "true boolean"

# Tasks and Steps definitions
# Steps make up tasks, and tasks can contain steps, tasks, or both
# Tasks cannot reference themselves (circular references)
tasks:
  # PostgreSQL Tools Task Group
  postgresql_tools:
    name: "PostgreSQL Tools"
    description: "PostgreSQL administration and management tools"
    enabled: false
    steps:
      - pgadmin
      - pgagent

  # Individual Tasks
  pgadmin:
    name: "pgAdmin"
    description: "Install pgAdmin web interface for PostgreSQL"
    enabled: false
    steps:
      - install_pgadmin_packages

  pgagent:
    name: "pgAgent"
    description: "Install pgAgent job scheduler for PostgreSQL"
    enabled: true
    steps:
      - install_pgagent_packages

# Steps definitions
steps:
  install_pgadmin_packages:
    name: "Install pgAdmin Packages"
    description: "Install pgAdmin packages from apt repositories"
    command: "sudo apt-get install -y pgadmin4"

  install_pgagent_packages:
    name: "Install pgAgent Packages"
    description: "Install pgAgent packages from apt repositories"
    command: "sudo apt-get install -y pgagent"
```

## Implementation Details

### Constants Loading Mechanism

The `/common/constants_loader.py` file provides utilities for loading and accessing constants from the constants.yaml file:

```python
import os
from pathlib import Path
import logging
import yaml
from typing import Any, Dict, List, Optional, Set

# Constants file path
CONSTANTS_FILE = Path(__file__).parent / "constants.yaml"

# Cache for loaded constants
_constants_cache: Optional[Dict[str, Any]] = None

# Set up logger
module_logger = logging.getLogger(__name__)

def get_constants() -> Dict[str, Any]:
    """
    Load constants from the YAML file.
    Returns a dictionary of constants.

    Returns:
        Dict[str, Any]: A dictionary containing all constants from the YAML file.

    Raises:
        FileNotFoundError: If the constants file doesn't exist.
        yaml.YAMLError: If there's an error parsing the YAML file.
    """
    global _constants_cache

    if _constants_cache is not None:
        return _constants_cache

    if not CONSTANTS_FILE.exists():
        raise FileNotFoundError(f"Constants file not found at {CONSTANTS_FILE}")

    try:
        with open(CONSTANTS_FILE, "r", encoding="utf-8") as f:
            _constants_cache = yaml.safe_load(f)

        if _constants_cache is None:
            # If the file is empty or contains only comments
            _constants_cache = {}

        module_logger.info(f"Loaded constants from {CONSTANTS_FILE}")
        return _constants_cache
    except yaml.YAMLError as e:
        module_logger.error(f"Error parsing constants file {CONSTANTS_FILE}: {e}")
        raise
    except Exception as e:
        module_logger.error(f"Error loading constants file {CONSTANTS_FILE}: {e}")
        raise

def get_constant(path: str, default: Any = None) -> Any:
    """
    Get a constant value by its path.

    Args:
        path: Dot-separated path to the constant (e.g., "features.pgadmin_enabled")
        default: Default value to return if the constant is not found

    Returns:
        The constant value or the default if not found
    """
    try:
        constants = get_constants()

        parts = path.split(".")
        current = constants

        for part in parts:
            if not isinstance(current, dict) or part not in current:
                module_logger.debug(f"Constant '{path}' not found, using default: {default}")
                return default
            current = current[part]

        return current
    except Exception as e:
        module_logger.warning(f"Error retrieving constant '{path}': {e}. Using default: {default}")
        return default

def is_feature_enabled(feature_name: str, default: bool = False) -> bool:
    """
    Check if a feature is enabled in the constants.

    Args:
        feature_name: The name of the feature to check
        default: Default value to return if the feature flag is not found

    Returns:
        True if the feature is enabled, False otherwise
    """
    return get_constant(f"features.{feature_name}", default)

def get_task(task_name: str) -> Optional[Dict[str, Any]]:
    """
    Get a task by name.

    Args:
        task_name: The name of the task to get

    Returns:
        The task dictionary or None if not found
    """
    tasks = get_constant("tasks", {})
    return tasks.get(task_name)

def get_step(step_name: str) -> Optional[Dict[str, Any]]:
    """
    Get a step by name.

    Args:
        step_name: The name of the step to get

    Returns:
        The step dictionary or None if not found
    """
    steps = get_constant("steps", {})
    return steps.get(step_name)

def is_task_enabled(task_name: str) -> bool:
    """
    Check if a task is enabled.

    Args:
        task_name: The name of the task to check

    Returns:
        True if the task is enabled, False otherwise
    """
    task = get_task(task_name)
    if task is None:
        module_logger.warning(f"Task '{task_name}' not found")
        return False

    return task.get("enabled", False)

def get_task_steps(task_name: str, visited: Optional[Set[str]] = None) -> List[str]:
    """
    Get all steps for a task, including steps from sub-tasks.

    Args:
        task_name: The name of the task to get steps for
        visited: Set of already visited tasks (used to detect circular references)

    Returns:
        List of step names

    Raises:
        ValueError: If a circular reference is detected
    """
    if visited is None:
        visited = set()

    # Check for circular references
    if task_name in visited:
        raise ValueError(f"Circular reference detected in task '{task_name}'")

    visited.add(task_name)

    task = get_task(task_name)
    if task is None:
        module_logger.warning(f"Task '{task_name}' not found")
        return []

    steps = []
    task_steps = task.get("steps", [])

    for step in task_steps:
        # If the step is a task, get its steps recursively
        if get_task(step) is not None:
            steps.extend(get_task_steps(step, visited.copy()))
        else:
            steps.append(step)

    return steps

def validate_tasks() -> bool:
    """
    Validate that there are no circular references in tasks.

    Returns:
        True if validation passes, False otherwise
    """
    tasks = get_constant("tasks", {})

    for task_name in tasks:
        try:
            get_task_steps(task_name)
        except ValueError as e:
            module_logger.error(f"Task validation failed: {e}")
            return False

    return True
```

### Integration with Configuration System

Update `setup/config_loader.py` to incorporate constants:

1. Import the constants loader:
   ```python
   from common.constants_loader import get_constant
   ```

2. Use constants for default values in `load_app_settings`:
   ```python
   # Example: Use constant for pgadmin.install default
   if "pgadmin" not in current_values_dict:
       current_values_dict["pgadmin"] = {}

   if "install" not in current_values_dict["pgadmin"]:
       current_values_dict["pgadmin"]["install"] = get_constant("features.pgadmin_enabled", False)
   ```

### Updating PgAdmin Installation

Modify `installer/pgadmin_installer.py`:

```python
from common.constants_loader import get_constant

def install_pgadmin(
    app_settings: AppSettings,
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Installs pgAdmin if enabled in the constants or configuration.
    """
    logger_to_use = current_logger if current_logger else module_logger

    # Check both the constant and the config setting
    pgadmin_enabled = get_constant("features.pgadmin_enabled", False)

    if not pgadmin_enabled or not app_settings.pgadmin.install:
        log_map_server(
            f"{config.SYMBOLS['info']} pgAdmin installation is disabled. Skipping.",
            "info",
            logger_to_use,
        )
        return

    # Rest of the installation code...
```

## Migration Strategy

1. **Incremental Implementation**:
   - Start with pgadmin configuration as a proof of concept
   - Gradually move other constants in subsequent phases

2. **Testing**:
   - Test each phase thoroughly to ensure constants are correctly loaded and used
   - Verify that existing functionality continues to work as expected

3. **Documentation**:
   - Update project documentation to reflect the new constants system
   - Provide examples of how to use and modify constants

## Future Considerations

1. **Environment Variable Override**:
   - Consider allowing environment variables to override constants
   - This would provide flexibility for deployment in different environments

2. **Constants Validation**:
   - Implement validation for constants to ensure they meet expected formats and constraints

3. **Dynamic Constants**:
   - Consider supporting dynamic constants that can change at runtime
   - This would be useful for features that need to be toggled without restarting the application

## Conclusion

This implementation plan provides a structured approach to centralizing constants in the OSM-OSRM Server project. By moving constants to a dedicated file, we improve maintainability, make configuration more explicit, and provide a single source of truth for important values in the system.

The plan focuses first on addressing the immediate need to move pgadmin configuration to constants, followed by a broader migration of other constants. This approach allows for incremental implementation and testing, reducing the risk of introducing bugs or breaking existing functionality.
