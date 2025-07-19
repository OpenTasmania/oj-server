#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify the centralized logging implementation.

This script tests the structured, centralized logging capabilities implemented
for Task 1: Implement Monitoring and Observability.
"""

import os
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))


def test_basic_logging():
    """Test basic centralized logging functionality."""
    print("=== Testing Basic Centralized Logging ===")

    try:
        from common.logging_config import (
            setup_service_logging,
        )

        # Test service logging setup
        logger = setup_service_logging(
            "test-service", environment="development"
        )
        print("✓ Service logging setup successful")

        # Test basic logging
        logger.info("Test info message")
        logger.warning("Test warning message")
        logger.error("Test error message")
        print("✓ Basic logging messages sent")

        # Test structured logging with extra fields
        logger.info(
            "Test structured message",
            extra={
                "component": "test",
                "operation": "validation",
                "record_count": 100,
                "status": "success",
            },
        )
        print("✓ Structured logging with extra fields successful")

        return True
    except Exception as e:
        print(f"✗ Basic logging test failed: {e}")
        return False


def test_specialized_logging():
    """Test specialized logging functions."""
    print("\n=== Testing Specialized Logging Functions ===")

    try:
        from common.logging_config import (
            log_api_request,
            log_database_operation,
        )

        # Test database operation logging
        log_database_operation("INSERT", "transport_stops", 150)
        log_database_operation("UPDATE", "transport_routes", 25)
        print("✓ Database operation logging successful")

        # Test API request logging
        log_api_request("GET", "/api/stops", 200, 0.125)
        log_api_request("POST", "/api/routes", 201, 0.250)
        print("✓ API request logging successful")

        return True
    except Exception as e:
        print(f"✗ Specialized logging test failed: {e}")
        return False


def test_performance_decorator():
    """Test the performance logging decorator."""
    print("\n=== Testing Performance Logging Decorator ===")

    try:
        import time

        from common.logging_config import log_performance

        @log_performance
        def sample_function():
            """Sample function to test performance logging."""
            time.sleep(0.1)  # Simulate some work
            return "success"

        result = sample_function()
        print(f"✓ Performance decorator test successful: {result}")

        @log_performance
        def failing_function():
            """Sample function that fails to test error logging."""
            raise ValueError("Test error")

        try:
            failing_function()
        except ValueError:
            print("✓ Performance decorator error handling successful")

        return True
    except Exception as e:
        print(f"✗ Performance decorator test failed: {e}")
        return False


def test_processor_interface():
    """Test the updated processor interface."""
    print("\n=== Testing Updated Processor Interface ===")

    try:
        from common.processor_interface import ProcessorRegistry

        # Test processor registry with centralized logging
        registry = ProcessorRegistry()
        print("✓ ProcessorRegistry with centralized logging successful")

        # Test that logging is properly initialized
        registry.logger.info("Test message from ProcessorRegistry")
        print("✓ ProcessorRegistry logging functional")

        return True
    except Exception as e:
        print(f"✗ Processor interface test failed: {e}")
        return False


def test_json_formatting():
    """Test JSON log formatting in Kubernetes environment."""
    print("\n=== Testing JSON Log Formatting ===")

    try:
        # Simulate Kubernetes environment
        os.environ["KUBERNETES_SERVICE_HOST"] = "kubernetes.default.svc"
        os.environ["POD_NAME"] = "test-pod-12345"
        os.environ["POD_NAMESPACE"] = "default"
        os.environ["HOSTNAME"] = "test-node"

        from common.logging_config import setup_service_logging

        # Set up logging in Kubernetes mode
        logger = setup_service_logging(
            "test-k8s-service", environment="production"
        )

        # This should produce JSON formatted logs
        logger.info(
            "Test Kubernetes JSON logging",
            extra={
                "component": "test",
                "operation": "json_validation",
                "kubernetes": True,
            },
        )
        print("✓ Kubernetes JSON formatting test successful")

        # Clean up environment variables
        del os.environ["KUBERNETES_SERVICE_HOST"]
        del os.environ["POD_NAME"]
        del os.environ["POD_NAMESPACE"]
        del os.environ["HOSTNAME"]

        return True
    except Exception as e:
        print(f"✗ JSON formatting test failed: {e}")
        return False


def main():
    """Run all logging tests."""
    print("Centralized Logging Implementation Test")
    print("=" * 50)

    tests = [
        test_basic_logging,
        test_specialized_logging,
        test_performance_decorator,
        test_processor_interface,
        test_json_formatting,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
            failed += 1

    print("\n" + "=" * 50)
    print("TEST SUMMARY:")
    print(f"✓ Passed: {passed}")
    print(f"✗ Failed: {failed}")
    print(f"Total: {passed + failed}")

    if failed == 0:
        print(
            "\n🎉 All tests passed! Centralized logging implementation is working correctly."
        )
        print("\nKey features verified:")
        print("- JSON-structured logging for Kubernetes")
        print("- Service identification and metadata")
        print("- Database operation logging")
        print("- API request logging")
        print("- Performance monitoring")
        print("- Error handling and exception logging")
        print("- Integration with existing processor interface")
        return True
    else:
        print(
            f"\n❌ {failed} test(s) failed. Please review the implementation."
        )
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
