#!/usr/bin/env python3
"""
GTFS Daemon Entry Point
=======================

Entry point script for the GTFS to OpenJourney daemon container.
This script handles environment variable configuration and starts the daemon.
"""

import os
import sys
import json
from gtfs_daemon import GTFSDaemon


def get_config_from_env():
    """Get configuration from environment variables and config file."""

    # Database configuration from environment
    db_config = {
        "host": os.getenv("POSTGRES_HOST", "postgres-service"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "database": os.getenv("POSTGRES_DB", "openjourney"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
    }

    # Load GTFS feeds configuration
    config_file = os.getenv("GTFS_CONFIG_FILE", "/app/config.json")
    feeds_config = []

    try:
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                file_config = json.load(f)
                feeds_config = file_config.get("feeds", [])
        else:
            print(
                f"Warning: Config file {config_file} not found, using environment variables"
            )
    except Exception as e:
        print(f"Error loading config file: {e}")

    # If no feeds in config file, try environment variables
    if not feeds_config:
        gtfs_urls = os.getenv("GTFS_URLS", "").strip()
        if gtfs_urls:
            urls = [
                url.strip() for url in gtfs_urls.split(",") if url.strip()
            ]
            feeds_config = [
                {"url": url, "name": f"Feed_{i + 1}"}
                for i, url in enumerate(urls)
            ]

    # Build complete configuration
    config = {
        "database": db_config,
        "feeds": feeds_config,
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "max_retries": int(os.getenv("MAX_RETRIES", "3")),
        "retry_delay": int(os.getenv("RETRY_DELAY", "60")),
    }

    return config


def main():
    """Main entry point."""
    print("Starting GTFS to OpenJourney Daemon...")

    # Get configuration
    config = get_config_from_env()

    # Validate configuration
    if not config["feeds"]:
        print(
            "Error: No GTFS feeds configured. Please provide feeds in config.json or GTFS_URLS environment variable."
        )
        sys.exit(1)

    if not all(
        key in config["database"]
        for key in ["host", "port", "database", "user", "password"]
    ):
        print(
            "Error: Database configuration incomplete. Please check environment variables."
        )
        sys.exit(1)

    print(f"Configured {len(config['feeds'])} GTFS feeds:")
    for i, feed in enumerate(config["feeds"], 1):
        print(f"  {i}. {feed.get('name', 'Unnamed')} - {feed['url']}")

    print(
        f"Database: {config['database']['host']}:{config['database']['port']}/{config['database']['database']}"
    )

    # Create and run daemon
    try:
        daemon = GTFSDaemon(config)
        daemon.run_once()
        print("GTFS daemon completed successfully")
    except Exception as e:
        print(f"Error running GTFS daemon: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
