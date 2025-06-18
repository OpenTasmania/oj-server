"""
Modular installer framework.

This package provides a modular framework for installing and configuring
components of the OSM-OSRM Server.
"""

from installer.base_component import BaseComponent
from installer.registry import InstallerRegistry

__all__ = ["BaseComponent", "InstallerRegistry"]
