#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Static ETL Orchestrator for OpenJourney Server

This script implements Task 1: Build the Static ETL Orchestrator
- Reads the static_feeds list from config.yaml
- Dynamically loads and runs the correct processor based on the feed type
- Orchestrates the ETL process for static data feeds

Usage:
    python run_static_etl.py [--config CONFIG_FILE] [--feed FEED_NAME] [--dry-run]
"""

import argparse
import logging
import sys
import time
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
import importlib.util
import os

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from common.processor_interface import (
    ProcessorInterface,
    ProcessorError,
    ProcessorRegistry,
)
from common.metrics import get_metrics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class StaticETLOrchestrator:
    """
    Orchestrates the static ETL process for configured data feeds.

    This class is responsible for:
    - Loading configuration from config.yaml
    - Discovering and loading processor plugins
    - Running ETL processes for enabled feeds
    """

    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize the Static ETL Orchestrator.

        Args:
            config_path: Path to the configuration file
        """
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.processor_registry = ProcessorRegistry()
        self.metrics = get_metrics()
        self._load_processors()

    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file.

        Returns:
            Dictionary containing the configuration

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config file is invalid YAML
        """
        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {self.config_path}")
            return config or {}
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in configuration file: {e}")
            raise

    def _load_processors(self):
        """
        Discover and load processor plugins from the plugins directory.

        This method searches for processor classes in the plugins directory
        and registers them with the ProcessorRegistry.
        """
        plugins_dir = project_root / "plugins" / "Public"

        if not plugins_dir.exists():
            logger.warning(f"Plugins directory not found: {plugins_dir}")
            return

        logger.info(f"Searching for processors in: {plugins_dir}")

        # Search for processor files in plugin directories
        for plugin_dir in plugins_dir.iterdir():
            if plugin_dir.is_dir():
                self._load_processors_from_plugin(plugin_dir)

    def _load_processors_from_plugin(self, plugin_dir: Path):
        """
        Load processors from a specific plugin directory.

        Args:
            plugin_dir: Path to the plugin directory
        """
        # Look for processors in the processors subdirectory
        processors_dir = plugin_dir / "processors"
        if processors_dir.exists():
            for processor_file in processors_dir.glob("*_processor.py"):
                self._load_processor_from_file(processor_file)

    def _load_processor_from_file(self, processor_file: Path):
        """
        Load a processor class from a Python file.

        Args:
            processor_file: Path to the processor Python file
        """
        start_time = time.time()
        processor_type = processor_file.stem

        try:
            # Create module spec
            module_name = f"processors.{processor_file.stem}"
            spec = importlib.util.spec_from_file_location(
                module_name, processor_file
            )

            if spec and spec.loader:
                # Load the module
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

                # Find processor classes that inherit from ProcessorInterface
                for item_name in dir(module):
                    item = getattr(module, item_name)
                    if (
                        isinstance(item, type)
                        and issubclass(item, ProcessorInterface)
                        and item is not ProcessorInterface
                    ):
                        # Create processor instance with database config
                        db_config = self.config.get("postgres", {})
                        processor_instance = item(db_config)

                        # Register the processor
                        self.processor_registry.register(processor_instance)
                        logger.info(
                            f"Registered processor: {processor_instance.processor_name}"
                        )

                        # Record successful processor loading time
                        duration = time.time() - start_time
                        self.metrics.record_etl_processor_load_time(
                            processor_type, duration
                        )

        except Exception as e:
            logger.error(
                f"Failed to load processor from {processor_file}: {e}"
            )
            # Record processor loading error
            self.metrics.record_etl_error(
                "processor_load_error", processor_type
            )

    def get_static_feeds(self) -> List[Dict[str, Any]]:
        """
        Get the list of static feeds from configuration.

        Returns:
            List of static feed configurations
        """
        return self.config.get("static_feeds", []) or []

    def run_feed(
        self, feed_config: Dict[str, Any], dry_run: bool = False
    ) -> bool:
        """
        Run ETL process for a single feed.

        Args:
            feed_config: Configuration for the feed
            dry_run: If True, only validate without processing

        Returns:
            True if successful, False otherwise
        """
        feed_name = feed_config.get("name", "Unknown")
        feed_type = feed_config.get("type", "")
        feed_source = feed_config.get("source", "")

        logger.info(f"Processing feed: {feed_name} (type: {feed_type})")

        if not feed_config.get("enabled", False):
            logger.info(f"Feed {feed_name} is disabled, skipping")
            return True

        if dry_run:
            logger.info(
                f"DRY RUN: Would process {feed_name} from {feed_source}"
            )
            return True

        # Start timing for metrics
        start_time = time.time()

        try:
            # Find appropriate processor for this feed type
            processor = self._get_processor_for_type(feed_type)
            if not processor:
                logger.error(f"No processor found for feed type: {feed_type}")
                self.metrics.record_etl_error("no_processor_found", feed_name)
                self.metrics.record_etl_feed_processed("failed", feed_type)
                return False

            # Create source path from URL or file path
            source_path = (
                Path(feed_source)
                if not feed_source.startswith("http")
                else feed_source
            )

            # Run the ETL process
            source_info = {
                "name": feed_name,
                "type": feed_type,
                "source": feed_source,
                "description": feed_config.get("description", ""),
            }

            processor.process(source_path, source_info)

            # Record successful processing
            duration = time.time() - start_time
            self.metrics.record_etl_processing_time(
                feed_name, feed_type, duration
            )
            self.metrics.record_etl_feed_processed("success", feed_type)

            logger.info(f"Successfully processed feed: {feed_name}")
            return True

        except ProcessorError as e:
            logger.error(f"Processor error for feed {feed_name}: {e}")
            duration = time.time() - start_time
            self.metrics.record_etl_processing_time(
                feed_name, feed_type, duration
            )
            self.metrics.record_etl_error("processor_error", feed_name)
            self.metrics.record_etl_feed_processed("failed", feed_type)
            return False
        except Exception as e:
            logger.error(f"Unexpected error processing feed {feed_name}: {e}")
            duration = time.time() - start_time
            self.metrics.record_etl_processing_time(
                feed_name, feed_type, duration
            )
            self.metrics.record_etl_error("unexpected_error", feed_name)
            self.metrics.record_etl_feed_processed("failed", feed_type)
            return False

    def _get_processor_for_type(
        self, feed_type: str
    ) -> Optional[ProcessorInterface]:
        """
        Get the appropriate processor for a given feed type.

        Args:
            feed_type: The type of feed (e.g., 'gtfs', 'netex')

        Returns:
            ProcessorInterface instance or None if not found
        """
        # Map feed types to processor names
        type_mapping = {"gtfs": "GTFS", "netex": "NeTEx", "siri": "SIRI"}

        processor_name = type_mapping.get(feed_type.lower())
        if processor_name:
            return self.processor_registry.get_processor(processor_name)

        return None

    def run_all_feeds(self, dry_run: bool = False) -> bool:
        """
        Run ETL process for all enabled feeds.

        Args:
            dry_run: If True, only validate without processing

        Returns:
            True if all feeds processed successfully, False otherwise
        """
        feeds = self.get_static_feeds()

        if not feeds:
            logger.warning("No static feeds configured")
            return True

        logger.info(f"Found {len(feeds)} static feeds in configuration")

        success_count = 0
        for feed_config in feeds:
            if self.run_feed(feed_config, dry_run):
                success_count += 1

        logger.info(
            f"Processed {success_count}/{len(feeds)} feeds successfully"
        )
        return success_count == len(feeds)

    def run_specific_feed(
        self, feed_name: str, dry_run: bool = False
    ) -> bool:
        """
        Run ETL process for a specific feed by name.

        Args:
            feed_name: Name of the feed to process
            dry_run: If True, only validate without processing

        Returns:
            True if successful, False otherwise
        """
        feeds = self.get_static_feeds()

        for feed_config in feeds:
            if feed_config.get("name") == feed_name:
                return self.run_feed(feed_config, dry_run)

        logger.error(f"Feed not found: {feed_name}")
        return False

    def list_feeds(self):
        """List all configured static feeds."""
        feeds = self.get_static_feeds()

        if not feeds:
            print("No static feeds configured")
            return

        print("Configured static feeds:")
        print("-" * 50)

        for feed in feeds:
            status = "enabled" if feed.get("enabled", False) else "disabled"
            print(f"Name: {feed.get('name', 'Unknown')}")
            print(f"Type: {feed.get('type', 'Unknown')}")
            print(f"Source: {feed.get('source', 'Unknown')}")
            print(f"Status: {status}")
            print(f"Description: {feed.get('description', 'No description')}")
            print("-" * 50)

    def list_processors(self):
        """List all registered processors."""
        processors = self.processor_registry.list_processors()

        if not processors:
            print("No processors registered")
            return

        print("Registered processors:")
        print("-" * 50)

        for processor_name in processors:
            processor = self.processor_registry.get_processor(processor_name)
            if processor:
                formats = processor.supported_formats
                print(f"Name: {processor_name}")
                print(f"Supported formats: {', '.join(formats)}")
                print("-" * 50)


def main():
    """Main entry point for the static ETL orchestrator."""
    parser = argparse.ArgumentParser(
        description="OpenJourney Static ETL Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )

    parser.add_argument(
        "--feed", help="Process only the specified feed by name"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without processing feeds",
    )

    parser.add_argument(
        "--list-feeds",
        action="store_true",
        help="List all configured static feeds",
    )

    parser.add_argument(
        "--list-processors",
        action="store_true",
        help="List all registered processors",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Initialize orchestrator
        orchestrator = StaticETLOrchestrator(args.config)

        # Handle different command modes
        if args.list_feeds:
            orchestrator.list_feeds()
            return 0

        if args.list_processors:
            orchestrator.list_processors()
            return 0

        # Process feeds
        if args.feed:
            success = orchestrator.run_specific_feed(args.feed, args.dry_run)
        else:
            success = orchestrator.run_all_feeds(args.dry_run)

        return 0 if success else 1

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
