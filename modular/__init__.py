"""
Modular installer framework.

This package provides a modular framework for installing and configuring
components of the OSM-OSRM Server.
"""

from modular.base_installer import BaseInstaller
from modular.orchestrator import InstallerOrchestrator
from modular.registry import InstallerRegistry

__all__ = ["BaseInstaller", "InstallerRegistry", "InstallerOrchestrator"]
