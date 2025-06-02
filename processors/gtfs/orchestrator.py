# processors/gtfs/orchestrator.py
# -*- coding: utf-8 -*-
"""
Main orchestrator for all GTFS-related setup and processing tasks.
"""

import logging
from typing import Optional

from common.command_utils import log_map_server
from setup.config_models import AppSettings  # Import AppSettings

from .automation import configure_gtfs_update_cronjob
from .environment import setup_gtfs_environment
from .runner import run_gtfs_etl_pipeline_and_verify

module_logger = logging.getLogger(__name__)


class GTFSConfigError(Exception):
    pass


def process_and_setup_gtfs(
    app_settings: AppSettings,  # Changed to accept AppSettings
    # Individual parameters like gtfs_feed_url, db_params, project_root, etc.
    # will be sourced from app_settings.
    orchestrator_logger: Optional[
        logging.Logger
    ] = None,  # Logger for this orchestrator's messages
) -> None:
    """
    Main public function to set up environment, run GTFS ETL, verify, and configure cron job.
    Uses app_settings for all configurations.
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

    # Validate essential parameters from app_settings
    if not app_settings.gtfs_feed_url:
        log_map_server(
            f"{symbols.get('error', '❌')} GTFS Feed URL is missing in configuration. Cannot proceed.",
            "error",
            effective_logger,
            app_settings,
        )
        raise GTFSConfigError("GTFS Feed URL is required in AppSettings.")
    # DB params are in app_settings.pg, no need to check individual keys here as Pydantic model ensures structure.

    try:
        # Step 1: Setup GTFS processing environment (logging for GTFS modules, OS env vars)
        # This setup_gtfs_environment will configure logging that subsequent GTFS modules use.
        log_map_server(
            f"{symbols.get('step', '➡️')} Step 1: Setting up GTFS environment (logging & OS vars)...",
            "info",
            effective_logger,
            app_settings,
        )
        # setup_gtfs_environment now takes app_settings directly
        setup_gtfs_environment(
            app_settings=app_settings,
            current_logger_for_setup=effective_logger,  # Pass logger for setup_gtfs_environment's own messages
        )
        log_map_server(
            f"{symbols.get('success', '✅')} GTFS environment setup complete.",
            "success",
            effective_logger,
            app_settings,
        )

        # Step 2: Run the ETL pipeline and verify
        # run_gtfs_etl_pipeline_and_verify now takes app_settings
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

        # Step 3: Configure cron job for automation
        # configure_gtfs_update_cronjob now takes app_settings
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
