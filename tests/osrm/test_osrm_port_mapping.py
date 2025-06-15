#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for OSRM port mapping functionality.
This script simulates creating OSRM routed service files for multiple regions
and verifies that each region gets a unique port.
"""

import logging
import sys
from pathlib import Path

# Add the project root to the Python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from common.core_utils import setup_logging
from setup.config_loader import load_app_settings
from setup.configure.osrm_configurator import get_next_available_port

# Set up logging
setup_logging(
    log_level=logging.INFO,
    log_to_console=True,
    log_format_str="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("test_osrm_port_mapping")


def test_port_assignment():
    """Test that port assignment works correctly."""
    # Load app settings
    app_settings = load_app_settings()

    # Get the default port
    default_port = app_settings.osrm_service.car_profile_default_host_port
    logger.info(f"Default port: {default_port}")

    # Test with empty region_port_map
    app_settings.osrm_service.region_port_map = {}

    # Get next available port (should be default port)
    port1 = get_next_available_port(app_settings, logger)
    logger.info(f"First port: {port1}")
    assert port1 == default_port, f"Expected {default_port}, got {port1}"

    # Add a region to the map
    app_settings.osrm_service.region_port_map["Region1"] = port1

    # Get next available port (should be default_port + 1)
    port2 = get_next_available_port(app_settings, logger)
    logger.info(f"Second port: {port2}")
    assert port2 == default_port + 1, (
        f"Expected {default_port + 1}, got {port2}"
    )

    # Add another region to the map
    app_settings.osrm_service.region_port_map["Region2"] = port2

    # Get next available port (should be default_port + 2)
    port3 = get_next_available_port(app_settings, logger)
    logger.info(f"Third port: {port3}")
    assert port3 == default_port + 2, (
        f"Expected {default_port + 2}, got {port3}"
    )

    # Add a region with a non-sequential port
    app_settings.osrm_service.region_port_map["Region3"] = default_port + 10

    # Get next available port (should still be default_port + 2)
    port4 = get_next_available_port(app_settings, logger)
    logger.info(f"Fourth port: {port4}")
    assert port4 == default_port + 2, (
        f"Expected {default_port + 2}, got {port4}"
    )

    logger.info("All port assignment tests passed!")
