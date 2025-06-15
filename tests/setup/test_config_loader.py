#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for the config_loader module.
"""

import logging
import sys
from pathlib import Path

# Add the project root to the Python path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from common.core_utils import setup_logging
from setup.config_loader import load_service_config

# Set up logging
setup_logging(
    log_level=logging.INFO,
    log_to_console=True,
    log_format_str="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("test_config_loader")


def test_load_service_config():
    """Test the load_service_config function."""
    # Test loading a service config that exists in config_files
    logger.info("Testing loading pg_tileserv config from config_files...")
    pg_tileserv_config = load_service_config(
        "pg_tileserv", PROJECT_ROOT, current_logger=logger
    )
    logger.info(f"Loaded pg_tileserv config: {pg_tileserv_config}")

    # Test loading a service config that doesn't exist in config_files
    logger.info("Testing loading a non-existent service config...")
    try:
        non_existent_config = load_service_config(
            "non_existent_service", PROJECT_ROOT, current_logger=logger
        )
        logger.info(
            f"Loaded non-existent service config: {non_existent_config}"
        )
    except Exception as e:
        logger.error(f"Error loading non-existent service config: {e}")


if __name__ == "__main__":
    test_load_service_config()
