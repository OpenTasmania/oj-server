# processors/plugins/importers/transit/gtfs/gtfs_process.py
# -*- coding: utf-8 -*-
"""
Defines the GTFS setup and processing orchestration using the centralized orchestrator.
"""

import logging
from typing import Optional

from common.orchestrator import Orchestrator
from setup.config_models import AppSettings

from .automation import configure_gtfs_update_cronjob
from .environment import setup_gtfs_environment
from .runner import run_gtfs_etl_pipeline_and_verify


class GTFSConfigError(Exception):
    """Raised when there is a configuration error in the GTFS setup."""

    pass


def run_gtfs_setup(
    app_settings: AppSettings, logger: Optional[logging.Logger] = None
) -> bool:
    """
    Configures and runs the GTFS setup and processing orchestration.

    Args:
        app_settings: Configuration settings for GTFS processing,
            including symbols, GTFS feed URL, and database parameters.
        logger: Logger instance for recording messages during the GTFS setup.
            If not provided, a default module logger is used.

    Returns:
        True if the orchestration completed successfully, False otherwise.

    Raises:
        GTFSConfigError: If the required GTFS feed URL is missing in the configuration.
    """
    effective_logger = logger or logging.getLogger(__name__)

    if not app_settings.gtfs_feed_url:
        effective_logger.critical("GTFS Feed URL is missing. Halting.")
        raise GTFSConfigError("GTFS Feed URL is required in AppSettings.")

    orchestrator = Orchestrator(app_settings, effective_logger)

    # Define the tasks
    orchestrator.add_task("Setup GTFS Environment", setup_gtfs_environment)
    orchestrator.add_task(
        "Run GTFS ETL Pipeline", run_gtfs_etl_pipeline_and_verify
    )
    orchestrator.add_task(
        "Configure GTFS Update Cron Job", configure_gtfs_update_cronjob
    )

    # Run the orchestration
    return orchestrator.run()
