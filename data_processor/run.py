# data_processor/run.py
import logging
import os
import sys

from common.core_utils import setup_logging

# When running in a container, the working directory is /app,
# and the Dockerfile copies the necessary modules.
# This allows for direct imports.
from installer.config_loader import load_app_settings
from installer.processors.plugins.importers.transit.gtfs.gtfs_process import (
    run_gtfs_setup,
)


def main():
    """Main function to run the GTFS data processing."""
    # Set up basic logging to console
    setup_logging(log_to_console=True)
    logger = logging.getLogger(__name__)
    logger.info("Starting GTFS data processing container...")

    # In a Kubernetes environment, this path will be mounted from a ConfigMap
    config_file = os.environ.get("CONFIG_FILE_PATH", "/config/config.yaml")
    logger.info(f"Loading configuration from: {config_file}")

    if not os.path.exists(config_file):
        logger.critical(
            f"Configuration file not found at {config_file}. Exiting."
        )
        sys.exit(1)

    # Load settings from the config file into an AppSettings object
    try:
        # No CLI args are passed in this containerized context
        app_settings = load_app_settings(
            cli_args=None, config_file_path=config_file
        )
    except Exception as e:
        logger.critical(
            f"Failed to load application settings: {e}", exc_info=True
        )
        sys.exit(1)

    # Now call the setup function with the correct AppSettings object
    logger.info("Configuration loaded. Starting GTFS setup process...")
    try:
        success = run_gtfs_setup(app_settings=app_settings, logger=logger)
        if success:
            logger.info("GTFS data processing finished successfully.")
            sys.exit(0)
        else:
            logger.error("GTFS data processing failed.")
            sys.exit(1)
    except Exception as e:
        logger.critical(
            f"An unexpected error occurred during GTFS processing: {e}",
            exc_info=True,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
