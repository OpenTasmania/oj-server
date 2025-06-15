#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for the load_app_settings function.
"""

import argparse
import logging
import sys
from pathlib import Path

# Add the project root to the Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from common.core_utils import setup_logging
from setup.config_loader import load_app_settings

# Set up logging
setup_logging(
    log_level=logging.INFO,
    log_to_console=True,
    log_format_str="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("test_app_settings")


def test_load_app_settings():
    """Test the load_app_settings function."""
    # Create a mock CLI args object
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-file", default="config.yaml")
    cli_args = parser.parse_args([])

    # Load the app settings
    logger.info("Testing loading app settings...")
    app_settings = load_app_settings(
        cli_args=cli_args,
        config_file_path="config.yaml",
        current_logger=logger,
    )

    # Verify that the pg_tileserv settings were loaded from the service-specific config
    logger.info("Verifying pg_tileserv settings...")
    pg_tileserv_settings = app_settings.pg_tileserv

    # Check some specific values from our service-specific config
    assert pg_tileserv_settings.http_host == "0.0.0.0", (
        f"Expected http_host to be '0.0.0.0', got '{pg_tileserv_settings.http_host}'"
    )
    assert pg_tileserv_settings.http_port == 7800, (
        f"Expected http_port to be 7800, got {pg_tileserv_settings.http_port}"
    )
    assert str(pg_tileserv_settings.config_dir) == "/etc/pg_tileserv", (
        f"Expected config_dir to be '/etc/pg_tileserv', got '{pg_tileserv_settings.config_dir}'"
    )

    # Check that the template sections were loaded
    logger.info("Verifying pg_tileserv template sections...")
    assert pg_tileserv_settings.config_template is not None, (
        "Expected config_template to be loaded, but it was None"
    )
    assert pg_tileserv_settings.systemd_template is not None, (
        "Expected systemd_template to be loaded, but it was None"
    )

    # Check specific content in the templates
    assert "HttpHost" in pg_tileserv_settings.config_template, (
        "Expected 'HttpHost' in config_template, but it wasn't found"
    )
    assert "DatabaseURL" in pg_tileserv_settings.config_template, (
        "Expected 'DatabaseURL' in config_template, but it wasn't found"
    )
    assert "[Unit]" in pg_tileserv_settings.systemd_template, (
        "Expected '[Unit]' in systemd_template, but it wasn't found"
    )
    assert "[Service]" in pg_tileserv_settings.systemd_template, (
        "Expected '[Service]' in systemd_template, but it wasn't found"
    )
    assert "[Install]" in pg_tileserv_settings.systemd_template, (
        "Expected '[Install]' in systemd_template, but it wasn't found"
    )

    logger.info("pg_tileserv settings verified successfully")
    logger.info("All tests passed!")


if __name__ == "__main__":
    test_load_app_settings()
