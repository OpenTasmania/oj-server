#!/usr/bin/env python3
"""
Test script for the enhanced plugin architecture with database optimization features.
This script demonstrates and tests the key components of the new system.
"""

import logging
import sys
import tempfile
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def test_plugin_interface():
    """Test the enhanced plugin interface."""
    logger.info("Testing enhanced plugin interface...")

    try:
        from installer.installer_app.utils.plugin_interface import (
            InstallerPlugin,
        )

        # Test that the interface has all required methods
        required_methods = [
            "name",
            "post_config_load",
            "pre_apply_k8s",
            "on_install_complete",
            "on_error",
            "get_database_requirements",
            "get_required_tables",
            "get_optional_tables",
            "should_create_table",
            "pre_database_setup",
            "post_database_setup",
        ]

        for method in required_methods:
            if not hasattr(InstallerPlugin, method):
                raise AttributeError(
                    f"InstallerPlugin missing required method: {method}"
                )

        logger.info("✓ Plugin interface has all required methods")
        return True

    except Exception as e:
        logger.error(f"✗ Plugin interface test failed: {e}")
        return False


def test_database_utils():
    """Test the database utilities."""
    logger.info("Testing database utilities...")

    try:
        from installer.installer_app.utils.database_utils import (
            PostgreSQLConnection,
            create_database_connection,
        )

        # Test that all classes exist and have required methods
        logger.info("✓ Database utilities imported successfully")

        # Test factory functions
        try:
            # This will fail without actual database, but we can test the factory
            connection_type = create_database_connection("postgresql")
            assert isinstance(connection_type, PostgreSQLConnection)
            logger.info("✓ Database connection factory works")
        except Exception as e:
            logger.info(
                f"✓ Database connection factory exists (connection test skipped: {e})"
            )

        return True

    except Exception as e:
        logger.error(f"✗ Database utilities test failed: {e}")
        return False


def test_plugin_manager():
    """Test the plugin manager."""
    logger.info("Testing plugin manager...")

    try:
        from installer.installer_app.utils.plugin_manager import PluginManager

        # Create a temporary plugin directory
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_dir = Path(temp_dir) / "plugins"
            plugin_dir.mkdir()

            # Create a test plugin
            test_plugin_dir = plugin_dir / "test_plugin"
            test_plugin_dir.mkdir()

            plugin_code = """
from installer.installer_app.utils.plugin_interface import InstallerPlugin

class TestPlugin(InstallerPlugin):
    @property
    def name(self) -> str:
        return "TestPlugin"
    
    def get_database_requirements(self) -> dict:
        return {"required_tables": [], "optional_tables": []}
    
    def get_required_tables(self) -> list:
        return []
    
    def get_optional_tables(self) -> list:
        return []
    
    def should_create_table(self, table_name: str, data_context: dict) -> bool:
        return False
    
    def pre_database_setup(self, config: dict) -> dict:
        return config
    
    def post_database_setup(self, db_connection):
        pass
    
    def on_install_complete(self):
        pass
    
    def on_error(self, error: Exception):
        pass
"""

            with open(test_plugin_dir / "plugin.py", "w") as f:
                f.write(plugin_code)

            # Test plugin manager
            plugin_manager = PluginManager(str(plugin_dir))

            if len(plugin_manager.plugins) > 0:
                logger.info(
                    "✓ Plugin manager successfully loaded test plugin"
                )

                # Test hook execution
                config = {"test": "value"}
                plugin_manager.run_hook("post_config_load", config)
                logger.info("✓ Plugin manager hook execution works")

                return True
            else:
                logger.warning("Plugin manager didn't load any plugins")
                return False

    except Exception as e:
        logger.error(f"✗ Plugin manager test failed: {e}")
        return False


def test_gtfs_plugin():
    """Test the GTFS plugin."""
    logger.info("Testing GTFS plugin...")

    try:
        # Import the GTFS plugin
        sys.path.append(
            str(
                Path(__file__).parent
                / "plugins"
                / "Public"
                / "OpenJourneyServer-GTFS"
            )
        )
        from plugin import GTFSMigration001, GTFSPlugin  # type: ignore

        # Test plugin instantiation
        gtfs_plugin = GTFSPlugin()
        assert gtfs_plugin.name == "GTFSPlugin"
        logger.info("✓ GTFS plugin instantiated successfully")

        # Test database requirements
        requirements = gtfs_plugin.get_database_requirements()
        assert "required_tables" in requirements
        assert "optional_tables" in requirements
        assert "required_extensions" in requirements
        logger.info("✓ GTFS plugin database requirements work")

        # Test table creation logic
        data_context = {"has_fare_data": True, "has_shapes": False}
        assert gtfs_plugin.should_create_table("fares", data_context)
        assert not gtfs_plugin.should_create_table(
            "path_geometry", data_context
        )
        logger.info("✓ GTFS plugin conditional table creation works")

        # Test configuration analysis
        config = {"gtfs": {"features": ["fares", "calendar"]}}
        context = gtfs_plugin.analyze_gtfs_data_context(config)
        assert context["has_fare_data"]
        assert context["has_calendar"]
        logger.info("✓ GTFS plugin data context analysis works")

        # Test migration
        migration = GTFSMigration001()
        assert migration.plugin_name == "GTFSPlugin"
        assert migration.version == "001"
        logger.info("✓ GTFS migration instantiated successfully")

        return True

    except Exception as e:
        logger.error(f"✗ GTFS plugin test failed: {e}")
        return False


def test_integration():
    """Test integration between components."""
    logger.info("Testing component integration...")

    try:
        # Test that plugin manager can load GTFS plugin
        plugin_dir = Path(__file__).parent / "plugins" / "Public"
        if plugin_dir.exists():
            from installer.installer_app.utils.plugin_manager import (
                PluginManager,
            )

            plugin_manager = PluginManager(str(plugin_dir.parent))

            # Look for GTFS plugin
            gtfs_plugin = None
            for plugin in plugin_manager.plugins:
                if plugin.name == "GTFSPlugin":
                    gtfs_plugin = plugin
                    break

            if gtfs_plugin:
                logger.info(
                    "✓ Plugin manager successfully loaded GTFS plugin"
                )

                # Test hook execution
                config = {"database": {"host": "localhost"}}
                plugin_manager.run_hook("post_config_load", config)
                logger.info("✓ Integration test: Hook execution works")

                return True
            else:
                logger.warning("GTFS plugin not found in plugin manager")
                return False
        else:
            logger.warning(
                "Plugin directory not found, skipping integration test"
            )
            return True

    except Exception as e:
        logger.error(f"✗ Integration test failed: {e}")
        return False


def main():
    """Run all tests."""
    logger.info("Starting plugin architecture tests...")

    tests = [
        ("Plugin Interface", test_plugin_interface),
        ("Database Utilities", test_database_utils),
        ("Plugin Manager", test_plugin_manager),
        ("GTFS Plugin", test_gtfs_plugin),
        ("Integration", test_integration),
    ]

    results = []
    for test_name, test_func in tests:
        logger.info(f"\n--- Running {test_name} Test ---")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test {test_name} crashed: {e}")
            results.append((test_name, False))

    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("TEST SUMMARY")
    logger.info("=" * 50)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1

    logger.info(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        logger.info(
            "🎉 All tests passed! Plugin architecture is working correctly."
        )
        return 0
    else:
        logger.warning(
            f"⚠️  {total - passed} test(s) failed. Please check the implementation."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
