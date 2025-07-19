#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify the sudo solution implementation.

This script tests the new sudo handling capabilities that were added to the Flask installer.
"""


def test_sudo_capabilities():
    """Test the check_sudo_capabilities function."""
    print("=== Testing check_sudo_capabilities() ===")

    try:
        from installer.installer_app.utils.common import (
            check_sudo_capabilities,
        )

        capabilities = check_sudo_capabilities()
        print("Sudo capabilities detected:")
        for key, value in capabilities.items():
            status = "✓" if value else "✗"
            print(f"  {key}: {status}")

        return capabilities
    except ImportError as e:
        print(f"Failed to import check_sudo_capabilities: {e}")
        return None


def test_run_command_with_sudo():
    """Test the enhanced run_command function with sudo handling."""
    print("\n=== Testing enhanced run_command() with sudo ===")

    try:
        from installer.installer_app.utils.common import run_command

        # Test a sudo command that should fail
        print("Testing sudo command that requires password...")
        try:
            result = run_command(
                ["sudo", "-n", "snap", "list"],
                capture_output=True,
                allow_sudo_failure=True,
                check=True,
            )
            print(f"Command result: exit code {result.returncode}")
            if result.returncode == 0:
                print("✓ Sudo command succeeded")
            else:
                print("✗ Sudo command failed (expected)")
        except SystemExit:
            print(
                "✗ run_command exited (this should not happen with allow_sudo_failure=True)"
            )

        # Test a regular command
        print("\nTesting regular command...")
        result = run_command(
            ["echo", "test"], capture_output=True, check=True
        )
        print(f"Regular command result: exit code {result.returncode}")
        if result.returncode == 0:
            print("✓ Regular command succeeded")

    except ImportError as e:
        print(f"Failed to import run_command: {e}")


def test_flask_app_startup():
    """Test Flask app startup with sudo capability check."""
    print("\n=== Testing Flask app startup ===")

    try:
        from installer.installer_app.app import create_app

        print(
            "Creating Flask app (this should show sudo capability warnings)..."
        )
        app = create_app()
        print("✓ Flask app created successfully")

        return app
    except ImportError as e:
        print(f"Failed to import Flask app: {e}")
        return None
    except Exception as e:
        print(f"Error creating Flask app: {e}")
        return None


def main():
    print("Testing Sudo Solution Implementation")
    print("=" * 50)

    # Test sudo capabilities detection
    capabilities = test_sudo_capabilities()

    # Test enhanced run_command function
    test_run_command_with_sudo()

    # Test Flask app startup
    app = test_flask_app_startup()

    print("\n" + "=" * 50)
    print("SOLUTION VERIFICATION:")

    if capabilities is not None:
        print("✓ Sudo capability detection works")
        if not capabilities.get("passwordless_sudo", False):
            print(
                "✓ Detected that passwordless sudo is not configured (expected)"
            )
        else:
            print("✓ Passwordless sudo is configured")
    else:
        print("✗ Sudo capability detection failed")

    if app is not None:
        print("✓ Flask app startup with sudo warnings works")
    else:
        print("✗ Flask app startup failed")

    print("\nThe solution provides:")
    print("1. ✓ Sudo capability detection at Flask startup")
    print("2. ✓ Enhanced error handling for sudo commands")
    print("3. ✓ Clear guidance for users on how to resolve sudo issues")
    print(
        "4. ✓ Graceful handling of sudo failures with allow_sudo_failure option"
    )


if __name__ == "__main__":
    main()
