#!/usr/bin/env python3
"""
Test script to verify the plugin dependency system works correctly.
This script tests that plugins can declare dependencies and the plugin manager installs them.
"""

import sys
from pathlib import Path

# Add the installer directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "installer"))


def test_plugin_dependency_system():
    """Test that the plugin dependency system works correctly."""
    print("Testing plugin dependency system...")

    try:
        # Import the plugin manager
        from installer.installer_app.utils.plugin_interface import (
            InstallerPlugin,
        )
        from installer.installer_app.utils.plugin_manager import PluginManager

        print("✓ Successfully imported plugin manager and interface")

        # Test that the plugin interface has the new method
        if hasattr(InstallerPlugin, "get_python_dependencies"):
            print("✓ Plugin interface has get_python_dependencies method")
        else:
            print("✗ Plugin interface missing get_python_dependencies method")
            return False

        # Test that the plugin manager has the dependency installation method
        if hasattr(PluginManager, "_install_plugin_dependencies"):
            print("✓ Plugin manager has _install_plugin_dependencies method")
        else:
            print(
                "✗ Plugin manager missing _install_plugin_dependencies method"
            )
            return False

        # Create a plugin manager instance (this will discover and load plugins)
        print("Creating plugin manager instance...")
        plugin_manager = PluginManager()

        print(
            f"✓ Plugin manager created, found {len(plugin_manager.plugins)} plugins"
        )

        # Check if GTFS plugin was loaded
        gtfs_plugin = None
        for plugin in plugin_manager.plugins:
            if plugin.name == "GTFSPlugin":
                gtfs_plugin = plugin
                break

        if gtfs_plugin:
            print("✓ GTFS plugin found and loaded")

            # Test that the GTFS plugin declares its dependencies
            dependencies = gtfs_plugin.get_python_dependencies()
            print(f"✓ GTFS plugin dependencies: {dependencies}")

            if "gtfs-kit>10.3.0,<11.0.0" in dependencies:
                print("✓ GTFS plugin correctly declares gtfs-kit dependency")
            else:
                print("✗ GTFS plugin missing gtfs-kit dependency")
                return False
        else:
            print("✗ GTFS plugin not found")
            return False

        print("✓ All tests passed!")
        return True

    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_gtfs_kit_availability():
    """Check if gtfs-kit is available after plugin loading."""
    print("\nChecking gtfs-kit availability...")

    try:
        import gtfs_kit as gk  # type: ignore

        print("✓ gtfs-kit is available and can be imported")
        print(f"✓ gtfs-kit version: {gk.__version__}")
        return True
    except ImportError as e:
        print(f"✗ gtfs-kit not available: {e}")
        return False


def main():
    """Main test function."""
    print("=" * 60)
    print("Plugin Dependency System Test")
    print("=" * 60)

    # Test the plugin dependency system
    system_test_passed = test_plugin_dependency_system()

    # Check gtfs-kit availability
    gtfs_kit_available = check_gtfs_kit_availability()

    print("\n" + "=" * 60)
    print("Test Results:")
    print(
        f"Plugin dependency system: {'PASS' if system_test_passed else 'FAIL'}"
    )
    print(
        f"gtfs-kit availability: {'PASS' if gtfs_kit_available else 'FAIL'}"
    )

    if system_test_passed and gtfs_kit_available:
        print(
            "✓ All tests passed! Plugin dependency system is working correctly."
        )
        return 0
    else:
        print("✗ Some tests failed. Please check the implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
