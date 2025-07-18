#!/usr/bin/env python3
"""
Test script to verify plugin migration was successful.
This script tests that all migrated plugins can be loaded and their basic functionality works.
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_plugin_loading():
    """Test that all migrated plugins can be loaded."""

    # List of newly migrated plugins to test
    migrated_plugins = [
        "plugins.Public.OpenJourneyServer-pgAdmin.plugin",
        "plugins.Public.OpenJourneyServer-pgAgent.plugin",
        "plugins.Public.OpenJourneyServer-Apache.plugin",
        "plugins.Public.OpenJourneyServer-pg_tileserv.plugin",
        "plugins.Public.OpenJourneyServer-Dataprocessing.plugin",
        "plugins.Private.OpenJourneyServer-OSRM.plugin",
    ]

    results = {}

    for plugin_module in migrated_plugins:
        try:
            # Import the plugin module
            module = __import__(plugin_module, fromlist=["get_plugin"])

            # Get the plugin instance
            plugin_instance = module.get_plugin()

            # Test basic plugin methods
            plugin_name = plugin_instance.name
            db_requirements = plugin_instance.get_database_requirements()

            # Test configuration loading
            test_config = {}
            updated_config = plugin_instance.post_config_load(test_config)

            results[plugin_module] = {
                "status": "SUCCESS",
                "name": plugin_name,
                "db_requirements": db_requirements,
                "config_updated": len(updated_config) > 0,
            }

            print(f"✓ {plugin_module}: {plugin_name} loaded successfully")

        except ImportError as e:
            results[plugin_module] = {
                "status": "IMPORT_ERROR",
                "error": str(e),
            }
            print(f"✗ {plugin_module}: Import failed - {e}")

        except Exception as e:
            results[plugin_module] = {"status": "ERROR", "error": str(e)}
            print(f"✗ {plugin_module}: Error - {e}")

    return results


def test_kubernetes_manifests():
    """Test that Kubernetes manifests were moved correctly."""

    plugin_dirs = [
        "plugins/Public/OpenJourneyServer-pgAdmin/kubernetes",
        "plugins/Public/OpenJourneyServer-pgAgent/kubernetes",
        "plugins/Public/OpenJourneyServer-Apache/kubernetes",
        "plugins/Public/OpenJourneyServer-pg_tileserv/kubernetes",
        "plugins/Public/OpenJourneyServer-Dataprocessing/kubernetes",
        "plugins/Private/OpenJourneyServer-OSRM/kubernetes",
    ]

    results = {}

    for plugin_dir in plugin_dirs:
        plugin_path = Path(plugin_dir)

        if plugin_path.exists():
            yaml_files = list(plugin_path.glob("*.yaml"))
            results[plugin_dir] = {
                "status": "SUCCESS",
                "yaml_files": len(yaml_files),
                "files": [f.name for f in yaml_files],
            }
            print(f"✓ {plugin_dir}: {len(yaml_files)} YAML files found")
        else:
            results[plugin_dir] = {
                "status": "MISSING",
                "error": "Directory not found",
            }
            print(f"✗ {plugin_dir}: Directory not found")

    return results


def main():
    """Run all plugin migration tests."""
    print("Testing Plugin Migration")
    print("=" * 50)

    print("\n1. Testing Plugin Loading...")
    plugin_results = test_plugin_loading()

    print("\n2. Testing Kubernetes Manifests...")
    manifest_results = test_kubernetes_manifests()

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    # Plugin loading summary
    successful_plugins = sum(
        1 for r in plugin_results.values() if r["status"] == "SUCCESS"
    )
    total_plugins = len(plugin_results)
    print(f"Plugin Loading: {successful_plugins}/{total_plugins} successful")

    # Manifest summary
    successful_manifests = sum(
        1 for r in manifest_results.values() if r["status"] == "SUCCESS"
    )
    total_manifests = len(manifest_results)
    print(
        f"Kubernetes Manifests: {successful_manifests}/{total_manifests} directories found"
    )

    # Overall status
    if (
        successful_plugins == total_plugins
        and successful_manifests == total_manifests
    ):
        print("\n🎉 Plugin migration completed successfully!")
        return 0
    else:
        print("\n⚠️  Some issues found in plugin migration")
        return 1


if __name__ == "__main__":
    sys.exit(main())
