#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for Prometheus metrics implementation.

This script tests the metrics collection functionality for both the static ETL
pipeline and GTFS daemon to ensure Task 2 is properly implemented.
"""

import sys
import time
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from prometheus_client import generate_latest

from common.metrics import get_metrics, start_metrics_server


def test_metrics_initialization():
    """
    Tests the initialization of the `get_metrics` function and checks if it is executed
    without errors. Captures any exceptions during the execution and prints the
    appropriate success or failure message for the metrics initialization process.

    Returns:
        bool: True if metrics were initialized successfully, False otherwise.
    """
    print("Testing metrics initialization...")

    try:
        metrics = get_metrics()
        assert metrics is not None
        print("✓ Metrics initialized successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to initialize metrics: {e}")
        return False


def test_etl_metrics():
    """Test ETL pipeline metrics collection."""
    print("\nTesting ETL pipeline metrics...")

    try:
        metrics = get_metrics()

        # Test processor loading metrics
        metrics.record_etl_processor_load_time("gtfs_processor", 1.5)
        print("✓ Processor loading time metric recorded")

        # Test feed processing metrics
        metrics.record_etl_processing_time("test_feed", "gtfs", 30.2)
        metrics.record_etl_feed_processed("success", "gtfs")
        print("✓ Feed processing metrics recorded")

        # Test records processed metrics
        metrics.record_etl_records_processed("test_feed", "routes", 150)
        metrics.record_etl_records_processed("test_feed", "stops", 500)
        print("✓ Records processed metrics recorded")

        # Test error metrics
        metrics.record_etl_error("processor_error", "test_feed")
        print("✓ Error metrics recorded")

        return True
    except Exception as e:
        print(f"✗ Failed to record ETL metrics: {e}")
        return False


def test_gtfs_daemon_metrics():
    """Test GTFS daemon metrics collection."""
    print("\nTesting GTFS daemon metrics...")

    try:
        metrics = get_metrics()

        # Test download metrics
        metrics.record_gtfs_download_time("test_gtfs_feed", 45.3)
        print("✓ Download time metric recorded")

        # Test conversion metrics
        metrics.record_gtfs_conversion_time("test_gtfs_feed", 12.7)
        print("✓ Conversion time metric recorded")

        # Test database operation metrics
        metrics.record_gtfs_database_operation("write_routes", "success")
        metrics.record_gtfs_database_operation("write_stops", "failed")
        print("✓ Database operation metrics recorded")

        # Test feed processing metrics
        metrics.record_gtfs_feed_processed("success", "test_gtfs_feed")
        print("✓ Feed processing metrics recorded")

        # Test retry metrics
        metrics.record_gtfs_retry_attempt("test_gtfs_feed", "download_failed")
        print("✓ Retry attempt metrics recorded")

        # Test active feeds gauge
        metrics.set_gtfs_active_feeds(3)
        print("✓ Active feeds gauge set")

        return True
    except Exception as e:
        print(f"✗ Failed to record GTFS daemon metrics: {e}")
        return False


def test_metrics_export():
    """Test that metrics can be exported in Prometheus format."""
    print("\nTesting metrics export...")

    try:
        # Generate metrics output
        metrics_output = generate_latest()

        if not metrics_output:
            print("✗ No metrics output generated")
            return False

        # Check for expected metric names
        output_str = metrics_output.decode("utf-8")
        expected_metrics = [
            "openjourney_etl_feeds_processed_total",
            "openjourney_etl_processing_duration_seconds",
            "openjourney_gtfs_feeds_processed_total",
            "openjourney_gtfs_download_duration_seconds",
            "openjourney_system_info",
        ]

        missing_metrics = []
        for metric in expected_metrics:
            if metric not in output_str:
                missing_metrics.append(metric)

        if missing_metrics:
            print(f"✗ Missing expected metrics: {missing_metrics}")
            return False

        print("✓ All expected metrics found in export")
        print(f"✓ Metrics export size: {len(metrics_output)} bytes")

        return True
    except Exception as e:
        print(f"✗ Failed to export metrics: {e}")
        return False


def test_metrics_server():
    """Test that the metrics server can be started."""
    print("\nTesting metrics server...")

    try:
        # Try to start metrics server on a test port
        test_port = 9090
        start_metrics_server(port=test_port, addr="127.0.0.1")
        print(f"✓ Metrics server started on port {test_port}")

        # Give it a moment to start
        time.sleep(1)

        return True
    except Exception as e:
        print(f"✗ Failed to start metrics server: {e}")
        return False


def main():
    """Run all metrics tests."""
    print("=" * 60)
    print("PROMETHEUS METRICS IMPLEMENTATION TEST")
    print("=" * 60)

    tests = [
        test_metrics_initialization,
        test_etl_metrics,
        test_gtfs_daemon_metrics,
        test_metrics_export,
        test_metrics_server,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1

    print("\n" + "=" * 60)
    print(f"TEST RESULTS: {passed}/{total} tests passed")

    if passed == total:
        print(
            "✓ All tests passed! Task 2 implementation is working correctly."
        )
        print("\nMetrics are now available for:")
        print("- Static ETL Pipeline processing")
        print("- GTFS Daemon operations")
        print("- System information")
        print(
            "\nMetrics can be scraped by Prometheus from the metrics server endpoint."
        )
    else:
        print("✗ Some tests failed. Please check the implementation.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
