"""
Modular installer framework.

This package provides a modular framework for installing and configuring
components of the OSM-OSRM Server.
"""

from installer.base_installer import BaseInstaller
from installer.orchestrator import InstallerOrchestrator
from installer.registry import InstallerRegistry

__all__ = ["BaseInstaller", "InstallerRegistry", "InstallerOrchestrator"]
