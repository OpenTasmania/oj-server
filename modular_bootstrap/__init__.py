# modular_bootstrap/__init__.py
# -*- coding: utf-8 -*-
"""
Modular Bootstrap package for the OSM-OSRM Server.

This package contains modules for ensuring that all prerequisites are met
before the modular setup script is executed. It is a self-contained bootstrap
process that mirrors the functionality of the existing bootstrap_installer
but is completely isolated within the modular_bootstrap directory.
"""

from modular_bootstrap.orchestrator import run_modular_bootstrap

__all__ = ["run_modular_bootstrap"]
