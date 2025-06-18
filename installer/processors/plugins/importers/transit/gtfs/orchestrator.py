# processors/gtfs/orchestrator.py
# -*- coding: utf-8 -*-
"""
Main orchestrator for all GTFS-related setup and processing tasks.
"""

import logging
from typing import Optional

from common.command_utils import log_map_server
from installer.config_models import AppSettings  # Import AppSettings

from .automation import configure_gtfs_update_cronjob
from .environment import setup_gtfs_environment
from .runner import run_gtfs_etl_pipeline_and_verify

module_logger = logging.getLogger(__name__)


class GTFSConfigError(Exception):
    """
    Custom exception indicating a configuration error specific to GTFS handling.

    This exception is raised when there is a problem with the configuration
    used for GTFS (General Transit Feed Specification) processing. It can
    be used to signal errors such as missing configuration values, improper
    settings, or other related issues. This class is intended to encapsulate
    errors specific to GTFS configuration, making them easier to identify and
    handle in an application.
    """

    pass


def process_and_setup_gtfs(
    app_settings: AppSettings,
    orchestrator_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Processes and sets up a General Transit Feed Specification (GTFS) environment
    by validating configuration, running an ETL pipeline, and configuring cron jobs
    for automation. This function ensures the essential parameters, such as the
    GTFS feed URL, are configured correctly in `app_settings`. The setup process
    includes configuring the environment, executing the ETL pipeline, and verifying
    its results, followed by scheduling updates with a cron job. Uses an optional
    logger for detailed logging of operations during the setup.

    Parameters:
        app_settings (AppSettings): Configuration settings for GTFS processing,
            including symbols, GTFS feed URL, and database parameters.
        orchestrator_logger (Optional[logging.Logger]): Logger instance for
            recording messages during the GTFS setup. If not provided, a default
            module logger is used.

    Raises:
        GTFSConfigError: If the required GTFS feed URL is missing in the configuration.
        RuntimeError: If a runtime error occurs during the GTFS processing.
        Exception: For any other unexpected errors encountered during the setup process.

    Returns:
        None
    """
    effective_logger = (
        orchestrator_logger if orchestrator_logger else module_logger
    )
    symbols = app_settings.symbols  # Use symbols from app_settings

    log_map_server(
        f"{symbols.get('rocket', '🚀')} Starting full GTFS setup and processing...",
        "info",
        effective_logger,
        app_settings,
    )

    if not app_settings.gtfs_feed_url:
        log_map_server(
            f"{symbols.get('error', '❌')} GTFS Feed URL is missing in configuration. Cannot proceed.",
            "error",
            effective_logger,
            app_settings,
        )
        raise GTFSConfigError("GTFS Feed URL is required in AppSettings.")

    try:
        log_map_server(
            f"{symbols.get('step', '➡️')} Step 1: Setting up GTFS environment (logging & OS vars)...",
            "info",
            effective_logger,
            app_settings,
        )
        setup_gtfs_environment(
            app_settings=app_settings,
            current_logger_for_setup=effective_logger,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} GTFS environment setup complete.",
            "success",
            effective_logger,
            app_settings,
        )

        log_map_server(
            f"{symbols.get('step', '➡️')} Step 2: Running GTFS ETL pipeline and verification...",
            "info",
            effective_logger,
            app_settings,
        )
        run_gtfs_etl_pipeline_and_verify(
            app_settings=app_settings, current_logger=effective_logger
        )
        log_map_server(
            f"{symbols.get('success', '✅')} GTFS ETL pipeline and verification complete.",
            "success",
            effective_logger,
            app_settings,
        )

        log_map_server(
            f"{symbols.get('step', '➡️')} Step 3: Configuring GTFS update cron job...",
            "info",
            effective_logger,
            app_settings,
        )
        configure_gtfs_update_cronjob(
            app_settings=app_settings, current_logger=effective_logger
        )
        log_map_server(
            f"{symbols.get('success', '✅')} GTFS update cron job configuration complete.",
            "success",
            effective_logger,
            app_settings,
        )

        log_map_server(
            f"{symbols.get('sparkles', '✨')} Full GTFS setup and processing completed successfully.",
            "success",
            effective_logger,
            app_settings,
        )

    except GTFSConfigError as e:
        log_map_server(
            f"{symbols.get('critical', '🔥')} GTFS Configuration Error: {e}",
            "critical",
            effective_logger,
            app_settings,
        )
        raise
    except RuntimeError as e:
        log_map_server(
            f"{symbols.get('critical', '🔥')} GTFS Processing Runtime Error: {e}",
            "critical",
            effective_logger,
            app_settings,
        )
        raise
    except Exception as e:
        log_map_server(
            f"{symbols.get('critical', '🔥')} An unexpected error occurred during GTFS setup: {e}",
            "critical",
            effective_logger,
            app_settings,
            exc_info=True,
        )
        raise
