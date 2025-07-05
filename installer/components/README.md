# Component Development Guidelines

## Overview

This document provides guidelines for developing components for the OSM-OSRM Server installer. Components are self-contained modules that handle the installation and configuration of specific services or features.

## Component Structure

Each component should be organized as a subdirectory under `installer/components/` with the following structure:

```
installer/components/
└── component_name/
    ├── __init__.py
    └── component_name_installer.py
```

## Component Implementation

### Single Installer Approach

Components should follow a single installer approach, where both installation and configuration logic are contained within a single installer class. This simplifies the codebase and makes it easier to maintain.

Example:

```python
"""
Component installer module.

This module provides a self-contained installer for the component.
"""

import logging
from typing import Optional

from installer.base_component import BaseComponent
from installer.config_models import AppSettings
from installer.registry import InstallerRegistry


@InstallerRegistry.register(
    name="component_name",
    metadata={
        "dependencies": [],  # List dependencies on other components
        "estimated_time": 30,  # Estimated installation time in seconds
        "required_resources": {
            "memory": 128,  # Required memory in MB
            "disk": 256,  # Required disk space in MB
            "cpu": 1,  # Required CPU cores
        },
        "description": "Description of the component",
    },
)
class ComponentInstaller(BaseComponent):
    """
    Installer for the component.

    This installer ensures that the component is installed and properly configured.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the component installer.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)
        # Initialize any required resources

    def install(self) -> bool:
        """
        Install the component.

        Returns:
            True if the installation was successful, False otherwise.
        """
        try:
            # Installation logic here
            return True
        except Exception as e:
            self.logger.error(f"Error installing component: {str(e)}")
            return False

    def uninstall(self) -> bool:
        """
        Uninstall the component.

        Returns:
            True if the uninstallation was successful, False otherwise.
        """
        try:
            # Uninstallation logic here
            return True
        except Exception as e:
            self.logger.error(f"Error uninstalling component: {str(e)}")
            return False

    def is_installed(self) -> bool:
        """
        Check if the component is installed.

        Returns:
            True if the component is installed, False otherwise.
        """
        # Check if the component is installed
        return False

    def configure(self) -> bool:
        """
        Configure the component.

        Returns:
            True if the configuration was successful, False otherwise.
        """
        try:
            # Configuration logic here
            return True
        except Exception as e:
            self.logger.error(f"Error configuring component: {str(e)}")
            return False

    def unconfigure(self) -> bool:
        """
        Unconfigure the component.

        Returns:
            True if the unconfiguration was successful, False otherwise.
        """
        try:
            # Unconfiguration logic here
            return True
        except Exception as e:
            self.logger.error(f"Error unconfiguring component: {str(e)}")
            return False

    def is_configured(self) -> bool:
        """
        Check if the component is configured.

        Returns:
            True if the component is configured, False otherwise.
        """
        # Check if the component is configured
        return False
```

### Migrating from Separate Installer and Configurator

If you have a component with separate installer and configurator files, you should merge them into a single installer file following these steps:

1. Add all necessary imports from the configurator to the installer
2. Replace the simple configure() method with the more detailed one from the configurator
3. Add any helper methods from the configurator to the installer
4. Update the is_configured() method to use the more detailed implementation from the configurator
5. Remove the configurator file

## Best Practices

1. **Dependency Management**: Clearly specify dependencies in the component metadata to ensure proper installation order.
2. **Error Handling**: Use try-except blocks to handle errors gracefully and provide meaningful error messages.
3. **Logging**: Use the provided logger for all log messages to ensure consistent logging throughout the application.
4. **Configuration**: Use the app_settings object to access configuration values rather than hardcoding them.
5. **Idempotency**: Ensure that install() and configure() methods are idempotent, meaning they can be run multiple times without causing issues.
6. **Cleanup**: Implement proper cleanup in uninstall() and unconfigure() methods to remove all traces of the component.
7. **Status Checking**: Implement thorough checks in is_installed() and is_configured() methods to accurately report the component's status.

## Example Components

For reference, see the following example components:

- `installer/components/ufw/ufw_installer.py`: A simple firewall component
- `installer/components/apache/apache_installer.py`: A web server component
- `installer/components/postgres/postgres_installer.py`: A database component