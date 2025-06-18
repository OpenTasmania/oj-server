"""
Sample component that demonstrates how to use the new BaseComponent class.

This component serves as an example for migrating existing installers and configurators
to the new unified component system.
"""

import logging
import os
from typing import Optional

from installer.base_component import BaseComponent
from installer.config_models import AppSettings
from installer.registry import ComponentRegistry


@ComponentRegistry.register(
    "sample",
    {
        "dependencies": [],
        "estimated_time": 10,
        "required_resources": {
            "memory": 64,
            "disk": 128,
            "cpu": 1,
        },
        "description": "Sample component that demonstrates the new unified component system.",
    },
)
class SampleComponent(BaseComponent):
    """
    Sample component that demonstrates how to use the new BaseComponent class.

    This component implements all the required methods of the BaseComponent class
    and serves as an example for migrating existing installers and configurators.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the sample component.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)
        self.sample_file = os.path.join(
            os.path.expanduser("~"), ".sample_component"
        )
        self.sample_config_file = os.path.join(
            os.path.expanduser("~"), ".sample_component_config"
        )

    def install(self) -> bool:
        """
        Install the sample component.

        This method creates a sample file to simulate installation.

        Returns:
            True if the installation was successful, False otherwise.
        """
        self.logger.info("Installing sample component...")

        try:
            # Create a sample file to simulate installation
            with open(self.sample_file, "w") as f:
                f.write("Sample component installed")

            self.logger.info("Sample component installed successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to install sample component: {str(e)}")
            return False

    def configure(self) -> bool:
        """
        Configure the sample component.

        This method creates a sample configuration file to simulate configuration.

        Returns:
            True if the configuration was successful, False otherwise.
        """
        self.logger.info("Configuring sample component...")

        if not self.is_installed():
            self.logger.error(
                "Cannot configure sample component: not installed"
            )
            return False

        try:
            # Create a sample configuration file to simulate configuration
            with open(self.sample_config_file, "w") as f:
                f.write("Sample component configured")

            self.logger.info("Sample component configured successfully")
            return True
        except Exception as e:
            self.logger.error(
                f"Failed to configure sample component: {str(e)}"
            )
            return False

    def uninstall(self) -> bool:
        """
        Uninstall the sample component.

        This method removes the sample file to simulate uninstallation.

        Returns:
            True if the uninstallation was successful, False otherwise.
        """
        self.logger.info("Uninstalling sample component...")

        try:
            # Remove the sample file to simulate uninstallation
            if os.path.exists(self.sample_file):
                os.remove(self.sample_file)

            # Also remove the configuration file if it exists
            if os.path.exists(self.sample_config_file):
                os.remove(self.sample_config_file)

            self.logger.info("Sample component uninstalled successfully")
            return True
        except Exception as e:
            self.logger.error(
                f"Failed to uninstall sample component: {str(e)}"
            )
            return False

    def unconfigure(self) -> bool:
        """
        Unconfigure the sample component.

        This method removes the sample configuration file to simulate unconfiguration.

        Returns:
            True if the unconfiguration was successful, False otherwise.
        """
        self.logger.info("Unconfiguring sample component...")

        try:
            # Remove the sample configuration file to simulate unconfiguration
            if os.path.exists(self.sample_config_file):
                os.remove(self.sample_config_file)

            self.logger.info("Sample component unconfigured successfully")
            return True
        except Exception as e:
            self.logger.error(
                f"Failed to unconfigure sample component: {str(e)}"
            )
            return False

    def is_installed(self) -> bool:
        """
        Check if the sample component is installed.

        Returns:
            True if the component is installed, False otherwise.
        """
        return os.path.exists(self.sample_file)

    def is_configured(self) -> bool:
        """
        Check if the sample component is configured.

        Returns:
            True if the component is configured, False otherwise.
        """
        return os.path.exists(self.sample_config_file)
