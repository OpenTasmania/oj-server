# modular/installers/docker_installer.py
# -*- coding: utf-8 -*-
"""
Docker installer module.

This module provides a self-contained installer for Docker Engine.
"""

import getpass
import logging
import os
from typing import Optional

from common.command_utils import (
    check_package_installed,
    log_map_server,
    run_command,
    run_elevated_command,
)
from common.debian.apt_manager import AptManager
from common.system_utils import get_debian_codename
from modular.base_installer import BaseInstaller
from modular.registry import InstallerRegistry
from setup import config
from setup.config_models import AppSettings


@InstallerRegistry.register(
    name="docker",
    metadata={
        "dependencies": ["prerequisites"],  # Depends on core prerequisites
        "estimated_time": 120,  # Estimated installation time in seconds
        "required_resources": {
            "memory": 512,  # Required memory in MB
            "disk": 1024,  # Required disk space in MB
            "cpu": 1,  # Required CPU cores
        },
        "description": "Docker Engine container runtime",
    },
)
class DockerInstaller(BaseInstaller):
    """
    Installer for Docker Engine container runtime.

    This installer ensures that Docker Engine and its associated components
    are installed and properly configured.
    """

    def __init__(
        self,
        app_settings: AppSettings,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Docker installer.

        Args:
            app_settings: The application settings.
            logger: Optional logger instance. If not provided, a new logger will be created.
        """
        super().__init__(app_settings, logger)
        self.apt_manager = AptManager(logger=self.logger)

    def install(self) -> bool:
        """
        Install Docker Engine and its associated components.

        Returns:
            True if the installation was successful, False otherwise.
        """
        try:
            # Log the start of the installation
            log_map_server(
                f"{config.SYMBOLS['info']} Setting up Docker Engine...",
                "info",
                self.logger,
            )

            # Set up Docker GPG key
            if not self._setup_docker_gpg_key():
                return False

            # Configure Docker apt repository
            if not self._configure_docker_apt_repository():
                return False

            # Install Docker packages
            if not self._install_docker_packages():
                return False

            # Add user to docker group
            if not self._add_user_to_docker_group():
                # This is not a critical failure, so we'll just log a warning
                log_map_server(
                    f"{config.SYMBOLS['warning']} Could not add user to docker group. You may need to do this manually.",
                    "warning",
                    self.logger,
                )

            log_map_server(
                f"{config.SYMBOLS['success']} Docker Engine installed successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error installing Docker Engine: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def uninstall(self) -> bool:
        """
        Uninstall Docker Engine and its associated components.

        Returns:
            True if the uninstallation was successful, False otherwise.
        """
        try:
            # Log the start of the uninstallation
            log_map_server(
                f"{config.SYMBOLS['info']} Uninstalling Docker Engine...",
                "info",
                self.logger,
            )

            # Get Docker packages
            docker_settings = self.app_settings.docker
            packages = docker_settings.packages

            # Uninstall Docker packages
            self.apt_manager.purge(packages, self.app_settings)

            # Remove Docker apt repository
            self.apt_manager.remove_repository("docker", self.app_settings)

            # Remove Docker GPG key
            if os.path.exists(docker_settings.keyring_path):
                run_elevated_command(
                    ["rm", "-f", str(docker_settings.keyring_path)],
                    self.app_settings,
                    current_logger=self.logger,
                )

            # Clean up any remaining packages
            self.apt_manager.autoremove(
                purge=True, app_settings=self.app_settings
            )

            log_map_server(
                f"{config.SYMBOLS['success']} Docker Engine uninstalled successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error uninstalling Docker Engine: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def is_installed(self) -> bool:
        """
        Check if Docker Engine is installed.

        Returns:
            True if Docker Engine is installed, False otherwise.
        """
        # Get Docker packages
        docker_settings = self.app_settings.docker
        packages = docker_settings.packages

        # Check if all packages are installed
        for pkg in packages:
            if not check_package_installed(
                pkg,
                app_settings=self.app_settings,
                current_logger=self.logger,
            ):
                return False

        return True

    def _setup_docker_gpg_key(self) -> bool:
        """
        Set up the Docker GPG key.

        Returns:
            True if the setup was successful, False otherwise.
        """
        try:
            docker_settings = self.app_settings.docker

            log_map_server(
                f"{config.SYMBOLS['info']} Setting up Docker GPG key...",
                "info",
                self.logger,
            )

            self.apt_manager.add_gpg_key_from_url(
                str(docker_settings.key_url),
                str(docker_settings.keyring_path),
                self.app_settings,
            )

            log_map_server(
                f"{config.SYMBOLS['success']} Docker GPG key installed.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to download/install Docker GPG key: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def _configure_docker_apt_repository(self) -> bool:
        """
        Configure the Docker apt repository.

        Returns:
            True if the configuration was successful, False otherwise.
        """
        try:
            docker_settings = self.app_settings.docker

            log_map_server(
                f"{config.SYMBOLS['info']} Configuring Docker apt repository...",
                "info",
                self.logger,
            )

            # Get system architecture
            arch_result = run_command(
                ["dpkg", "--print-architecture"],
                self.app_settings,
                capture_output=True,
                check=True,
                current_logger=self.logger,
            )
            arch = arch_result.stdout.strip()

            # Get Debian codename
            codename = get_debian_codename(
                self.app_settings, current_logger=self.logger
            )
            if not codename:
                raise EnvironmentError(
                    "Could not determine Debian codename for Docker."
                )

            # Configure repository
            repo_details = {
                "Types": "deb",
                "URIs": str(docker_settings.repo_url),
                "Suites": codename,
                "Components": "stable",
                "Architectures": arch,
                "Signed-By": str(docker_settings.keyring_path),
            }

            self.apt_manager.add_repository(
                "docker", repo_details, self.app_settings, update_after=True
            )

            log_map_server(
                f"{config.SYMBOLS['success']} Docker apt source configured and updated.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Failed to configure Docker apt source: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def _install_docker_packages(self) -> bool:
        """
        Install Docker packages.

        Returns:
            True if the installation was successful, False otherwise.
        """
        try:
            docker_settings = self.app_settings.docker
            packages = docker_settings.packages

            log_map_server(
                f"{config.SYMBOLS['info']} Installing Docker packages: {', '.join(packages)}...",
                "info",
                self.logger,
            )

            self.apt_manager.install(
                packages, self.app_settings, update_first=False
            )

            # Verify that all packages were installed
            all_installed = True
            for pkg in packages:
                if not check_package_installed(
                    pkg,
                    app_settings=self.app_settings,
                    current_logger=self.logger,
                ):
                    log_map_server(
                        f"{config.SYMBOLS['error']} Package '{pkg}' is NOT installed.",
                        "error",
                        self.logger,
                    )
                    all_installed = False

            if not all_installed:
                log_map_server(
                    f"{config.SYMBOLS['error']} Failed to install all required Docker packages.",
                    "error",
                    self.logger,
                )
                return False

            log_map_server(
                f"{config.SYMBOLS['success']} Docker packages installed successfully.",
                "success",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} Error installing Docker packages: {str(e)}",
                "error",
                self.logger,
            )
            return False

    def _add_user_to_docker_group(self) -> bool:
        """
        Add the current user to the 'docker' group.

        Returns:
            True if the user was added successfully, False otherwise.
        """
        try:
            user = getpass.getuser()

            log_map_server(
                f"{config.SYMBOLS['info']} Adding user {user} to 'docker' group...",
                "info",
                self.logger,
            )

            run_elevated_command(
                ["usermod", "-aG", "docker", user],
                self.app_settings,
                current_logger=self.logger,
            )

            log_map_server(
                f"{config.SYMBOLS['success']} User {user} added to 'docker' group.",
                "success",
                self.logger,
            )

            log_map_server(
                f"{config.SYMBOLS['warning']} Log out and back in for this change to take full effect.",
                "warning",
                self.logger,
            )

            return True

        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['warning']} Could not add user {getpass.getuser()} to docker group: {str(e)}.",
                "warning",
                self.logger,
            )
            return False
