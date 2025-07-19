#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reproduction script to demonstrate the sudo limitation in the Flask installer.

This script simulates the issue where the Flask installer fails when trying to
execute sudo commands without proper privileges.
"""

import os
import subprocess
import sys


def test_sudo_commands():
    """Test various sudo commands that the Flask installer needs to execute."""

    print("=== Testing sudo command execution ===")
    print(f"Current user: {os.environ.get('USER', 'unknown')}")
    print(f"Current UID: {os.getuid()}")
    print()

    # Test commands that the Flask installer uses
    test_commands = [
        # From check_and_install_tools()
        ["sudo", "-n", "apt", "update"],
        ["sudo", "-n", "apt", "install", "-y", "wget"],
        # From get_kubectl_command()
        ["sudo", "-n", "snap", "install", "microk8s", "--classic"],
        [
            "sudo",
            "-n",
            "usermod",
            "-a",
            "-G",
            "microk8s",
            os.environ.get("USER", ""),
        ],
        [
            "sudo",
            "-n",
            "chown",
            "-f",
            "-R",
            os.environ.get("USER", ""),
            os.path.expanduser("~/.kube"),
        ],
    ]

    failed_commands = []

    for cmd in test_commands:
        print(f"Testing: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                print("  ✓ SUCCESS")
            else:
                print(f"  ✗ FAILED (exit code: {result.returncode})")
                if result.stderr:
                    print(f"    Error: {result.stderr.strip()}")
                failed_commands.append(cmd)
        except subprocess.TimeoutExpired:
            print("  ✗ FAILED (timeout - likely waiting for password)")
            failed_commands.append(cmd)
        except Exception as e:
            print(f"  ✗ FAILED (exception: {e})")
            failed_commands.append(cmd)
        print()

    print("=== Summary ===")
    if failed_commands:
        print(
            f"❌ {len(failed_commands)} out of {len(test_commands)} sudo commands failed"
        )
        print("\nFailed commands:")
        for cmd in failed_commands:
            print(f"  - {' '.join(cmd)}")
        print(
            "\nThis demonstrates the issue: Flask installer cannot execute sudo commands"
        )
        print(
            "when running as a regular user without passwordless sudo configuration."
        )
        return False
    else:
        print(f"✅ All {len(test_commands)} sudo commands succeeded")
        print("Passwordless sudo appears to be configured correctly.")
        return True


def test_flask_installer_simulation():
    """Simulate what happens when Flask installer tries to run sudo commands."""

    print("\n=== Simulating Flask installer sudo usage ===")

    # Import the actual functions to test them
    try:
        sys.path.insert(0, os.path.join(os.getcwd(), "installer"))
        from installer.installer_app.utils.common import (
            check_and_install_tools,
        )

        print("Testing check_and_install_tools() with a simple tool...")
        # Test with a tool that's likely not installed to trigger sudo apt install
        test_tools = [
            (
                "test-tool-that-does-not-exist",
                "wget",
                "test sudo functionality",
            )
        ]

        try:
            result = check_and_install_tools(test_tools)
            print(f"check_and_install_tools() result: {result}")
        except SystemExit as e:
            print(f"check_and_install_tools() exited with code: {e.code}")
        except Exception as e:
            print(f"check_and_install_tools() failed with exception: {e}")

    except ImportError as e:
        print(f"Could not import Flask installer modules: {e}")
        print("This is expected if running outside the project directory.")


if __name__ == "__main__":
    print("Flask Installer Sudo Issue Reproduction Script")
    print("=" * 50)

    # Test basic sudo functionality
    sudo_works = test_sudo_commands()

    # Test Flask installer functions
    test_flask_installer_simulation()

    print("\n" + "=" * 50)
    if not sudo_works:
        print(
            "CONCLUSION: The Flask installer will fail when trying to execute sudo commands."
        )
        print(
            "SOLUTION NEEDED: Implement a way for Flask to handle sudo command execution."
        )
        sys.exit(1)
    else:
        print(
            "CONCLUSION: Sudo commands work, Flask installer should function correctly."
        )
        sys.exit(0)
