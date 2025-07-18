#!/usr/bin/env python3
"""
Test script for GTFS to OpenJourney Daemon
==========================================

This script tests the GTFS daemon functionality locally before deployment.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gtfs_daemon import GTFSDaemon, GTFSToOpenJourneyConverter


def test_config_loading():
    """Test configuration loading."""
    print("Testing configuration loading...")

    test_config = {
        "feeds": [
            {
                "name": "Test Feed",
                "url": "https://www.transport.act.gov.au/googletransit/google_transit.zip",
            }
        ],
        "database": {
            "host": "localhost",
            "port": 5432,
            "database": "test_db",
            "user": "test_user",
            "password": "test_pass",
        },
        "log_level": "INFO",
        "max_retries": 2,
        "retry_delay": 30,
    }

    daemon = GTFSDaemon(test_config)

    assert daemon.feeds == test_config["feeds"]
    assert daemon.db_config == test_config["database"]
    assert daemon.max_retries == 2
    assert daemon.retry_delay == 30

    print("✓ Configuration loading test passed")


def test_converter_initialization():
    """Test GTFS to OpenJourney converter initialization."""
    print("Testing converter initialization...")

    converter = GTFSToOpenJourneyConverter()
    assert converter is not None

    print("✓ Converter initialization test passed")


def test_download_function():
    """Test GTFS download function (without actually downloading)."""
    print("Testing download function structure...")

    daemon = GTFSDaemon({
        "feeds": [],
        "database": {},
        "max_retries": 1,
        "retry_delay": 1,
    })

    # Test that the method exists and is callable
    assert hasattr(daemon, "download_gtfs_from_url")
    assert callable(daemon.download_gtfs_from_url)

    print("✓ Download function structure test passed")


def test_route_type_mapping():
    """Test GTFS route type to OpenJourney transit mode mapping."""
    print("Testing route type mapping...")

    converter = GTFSToOpenJourneyConverter()

    # Test known mappings
    assert converter._map_gtfs_route_type(0) == "tram"
    assert converter._map_gtfs_route_type(1) == "subway"
    assert converter._map_gtfs_route_type(2) == "rail"
    assert converter._map_gtfs_route_type(3) == "bus"
    assert converter._map_gtfs_route_type(4) == "ferry"

    # Test unknown type defaults to bus
    assert converter._map_gtfs_route_type(999) == "bus"

    print("✓ Route type mapping test passed")


def test_config_file_format():
    """Test that the config.json file is valid."""
    print("Testing config.json file format...")

    config_path = Path(__file__).parent / "config.json"

    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)

        # Validate required fields
        assert "feeds" in config
        assert isinstance(config["feeds"], list)
        assert len(config["feeds"]) > 0

        for feed in config["feeds"]:
            assert "name" in feed
            assert "url" in feed
            assert feed["url"].startswith("http")

        print("✓ Config file format test passed")
    else:
        print("⚠ Config file not found, skipping test")


def test_environment_variable_handling():
    """Test environment variable handling in run_daemon.py."""
    print("Testing environment variable handling...")

    # Set test environment variables
    os.environ["POSTGRES_HOST"] = "test-host"
    os.environ["POSTGRES_PORT"] = "5433"
    os.environ["LOG_LEVEL"] = "DEBUG"
    os.environ["GTFS_URLS"] = (
        "http://example.com/feed1.zip,http://example.com/feed2.zip"
    )

    # Import and test the function
    from run_daemon import get_config_from_env

    config = get_config_from_env()

    assert config["database"]["host"] == "test-host"
    assert config["database"]["port"] == 5433
    assert config["log_level"] == "DEBUG"

    # Clean up environment variables
    del os.environ["POSTGRES_HOST"]
    del os.environ["POSTGRES_PORT"]
    del os.environ["LOG_LEVEL"]
    del os.environ["GTFS_URLS"]

    print("✓ Environment variable handling test passed")


def run_all_tests():
    """Run all tests."""
    print("Running GTFS Daemon Tests")
    print("=" * 50)

    try:
        test_config_loading()
        test_converter_initialization()
        test_download_function()
        test_route_type_mapping()
        test_config_file_format()
        test_environment_variable_handling()

        print("\n" + "=" * 50)
        print("🎉 All tests passed! GTFS daemon is ready for deployment.")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
