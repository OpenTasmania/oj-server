# dataproc/data_processing.py
# -*- coding: utf-8 -*-
"""
Orchestrates data preparation tasks like GTFS processing and raster tile pre-rendering.
"""
import logging
from typing import Optional, Dict # Added Dict
from pathlib import Path        # Added Path

from common.command_utils import log_map_server
# Import the new GTFS orchestrator
from processors.gtfs.orchestrator import process_and_setup_gtfs
# Import for raster pre-rendering (remains as is)
from dataproc.raster_processor import raster_tile_prerender
from setup import config  # For SYMBOLS and config values
from setup.cli_handler import cli_prompt_for_rerun
from setup.step_executor import execute_step

# REMOVE old GTFS-specific imports:
# from configure.gtfs_automation_configurator import configure_gtfs_update_cronjob
# from dataproc.gtfs_processor_runner import run_gtfs_etl_pipeline_and_verify
# from setup.gtfs_environment_setup import setup_gtfs_logging_and_env_vars

module_logger = logging.getLogger(__name__)


def data_prep_group(current_logger: Optional[logging.Logger] = None) -> bool:
    """
    Run all data preparation steps as a group.
    GTFS processing is now handled by a single call to the GTFS orchestrator.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"--- {config.SYMBOLS['info']} Starting Data Preparation Group ---",
        "info",
        logger_to_use,
    )
    overall_success = True

    # Construct db_params from global config for the GTFS orchestrator
    db_parameters_for_gtfs: Dict[str, str] = {
        "PGHOST": config.PGHOST,
        "PGPORT": str(config.PGPORT), # Ensure port is a string
        "PGDATABASE": config.PGDATABASE,
        "PGUSER": config.PGUSER,
        "PGPASSWORD": config.PGPASSWORD
    }

    # Define a wrapper function or lambda to call the GTFS orchestrator
    # This allows it to fit into the execute_step pattern
    def run_gtfs_orchestrator(cl: Optional[logging.Logger]):
        # Define default paths for log files if not globally configured elsewhere for GTFS specifically
        # These paths are specific to the GTFS module's operation.
        default_gtfs_app_log = "/var/log/gtfs_processor_app.log"
        default_gtfs_cron_log = "/var/log/gtfs_cron_output.log"

        process_and_setup_gtfs(
            gtfs_feed_url=config.GTFS_FEED_URL,
            db_params=db_parameters_for_gtfs,
            project_root=config.OSM_PROJECT_ROOT, # Assuming config.OSM_PROJECT_ROOT is a Path object
            gtfs_app_log_file=default_gtfs_app_log, # Or from a new GTFS specific config
            # gtfs_app_log_level=logging.INFO, # Default in orchestrator
            # gtfs_app_log_prefix="[GTFS-ETL]", # Default in orchestrator
            cron_run_user=config.PGUSER, # Default user for cron
            cron_job_output_log_file=default_gtfs_cron_log, # Or from new GTFS specific config
            # python_executable_for_cron=None, # Let orchestrator/automation find it
            orchestrator_logger=cl # Pass the logger from execute_step
        )

    # Define the sequence of data preparation steps
    step_definitions_in_group = [
        # GTFS Processing Sequence is now a single orchestrated step
        (
            "GTFS_PROCESSING_AND_SETUP", # New, single tag for all GTFS operations
            "Process GTFS Data and Configure Automation",
            run_gtfs_orchestrator # Wrapper function that calls the main GTFS orchestrator
        ),

        # Raster Tile Pre-rendering (remains as before)
        (
            "RASTER_PREP",
            "Pre-render Raster Tiles",
            raster_tile_prerender,
        ),
    ]

    for tag, desc, func_ref in step_definitions_in_group:
        if not execute_step(
                tag,
                desc,
                func_ref,
                logger_to_use, # This logger is for execute_step itself
                prompt_user_for_rerun=cli_prompt_for_rerun,
        ):
            overall_success = False
            log_map_server(
                f"{config.SYMBOLS['error']} Step '{desc}' ({tag}) failed. Aborting data prep group.",
                "error",
                logger_to_use,
            )
            break  # Stop on first failure within the group

    log_map_server(
        f"--- {config.SYMBOLS['info']} Data Preparation Group Finished (Overall Success: {overall_success}) ---",
        "info" if overall_success else "error",
        logger_to_use,
    )
    return overall_success