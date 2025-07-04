"""
UFW (Uncomplicated Firewall) configurator module.
"""

import logging
from typing import Dict, List, Optional

from common.command_utils import run_elevated_command
from common.system_utils import systemd_reload
from installer.base_component import BaseComponent
from installer.components.ufw.ufw_installer import UfwInstaller
from installer.config_models import AppSettings
from installer.registry import ComponentRegistry


@ComponentRegistry.register(
    name="ufw",
    metadata={
        "dependencies": ["prerequisites"],
        "description": "UFW (Uncomplicated Firewall) configuration",
    },
)
class UfwConfigurator(BaseComponent):
    """
    Configurator for UFW (Uncomplicated Firewall).

    This configurator ensures that UFW is properly configured with the
    necessary firewall rules and service settings.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the UFW configurator.
        """
        super().__init__(app_settings, logger)
        self.installer = UfwInstaller(app_settings, self.logger)

    def install(self) -> bool:
        """Install UFW by delegating to the installer."""
        return self.installer.install()

    def uninstall(self) -> bool:
        """Uninstall UFW by delegating to the installer."""
        return self.installer.uninstall()

    def is_installed(self) -> bool:
        """Check if UFW is installed by delegating to the installer."""
        return self.installer.is_installed()

    def configure(self) -> bool:
        """
        Configure UFW with the necessary firewall rules.
        """
        try:
            self._apply_firewall_rules()
            self._activate_ufw_service()
            return True
        except Exception as e:
            self.logger.error(f"Error configuring UFW: {str(e)}")
            return False

    def unconfigure(self) -> bool:
        """
        Unconfigure UFW by resetting it to default state.
        """
        try:
            run_elevated_command(
                ["ufw", "--force", "reset"], self.app_settings
            )
            return True
        except Exception as e:
            self.logger.error(f"Error unconfiguring UFW: {str(e)}")
            return False

    def is_configured(self) -> bool:
        """
        Check if UFW is configured and active.
        """
        try:
            result = run_elevated_command(
                ["ufw", "status"],
                self.app_settings,
                capture_output=True,
                check=False,
            )
            return "Status: active" in result.stdout
        except Exception as e:
            self.logger.error(f"Error checking UFW configuration: {str(e)}")
            return False

    def _get_firewall_rules(self) -> Dict[str, List[str]]:
        """
        Get the firewall rules from the application settings.
        """
        return {
            "allow": self.app_settings.ufw.allow_rules,
            "deny": self.app_settings.ufw.deny_rules,
            "limit": self.app_settings.ufw.limit_rules,
        }

    def _apply_firewall_rules(self) -> None:
        """
        Apply the firewall rules using the ufw command.
        """
        rules = self._get_firewall_rules()
        for action, rule_list in rules.items():
            for rule in rule_list:
                run_elevated_command(
                    ["ufw", action] + rule.split(), self.app_settings
                )

    def _activate_ufw_service(self) -> None:
        """
        Enable and activate the UFW service.
        """
        systemd_reload(self.app_settings, self.logger)
        run_elevated_command(["ufw", "--force", "enable"], self.app_settings)
        run_elevated_command(
            ["systemctl", "enable", "ufw.service"], self.app_settings
        )
        run_elevated_command(
            ["systemctl", "restart", "ufw.service"], self.app_settings
        )
