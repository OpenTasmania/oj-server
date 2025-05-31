# setup/data_processing.py
# -*- coding: utf-8 -*-
"""
Orchestrates data preparation tasks like GTFS processing and raster tile pre-rendering.
"""
import logging
from typing import Optional  # Added Optional

# No longer need detailed GTFS imports here, as they are in their respective modules.
# We will import the new granular functions for the data_prep_group.

from setup import config  # For SYMBOLS
from setup.cli_handler import cli_prompt_for_rerun
# Assuming common.command_utils for log_map_server
from common.command_utils import log_map_server
from setup.step_executor import execute_step

# Import the new granular GTFS functions
from setup.gtfs_environment_setup import setup_gtfs_logging_and_env_vars
from dataproc.gtfs_processor_runner import run_gtfs_etl_pipeline_and_verify
from configure.gtfs_automation_configurator import configure_gtfs_update_cronjob

# Import the refactored raster_tile_prerender
from dataproc.raster_processor import raster_tile_prerender

module_logger = logging.getLogger(__name__)  # Added module_logger definition


# The old monolithic gtfs_data_prep function is now removed,
# its logic is split into the three imported GTFS functions above.

def data_prep_group(current_logger: Optional[logging.Logger] = None) -> bool:
    """
    Run all data preparation steps as a group. This now calls the
    refactored granular steps for GTFS processing and raster pre-rendering.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"--- {config.SYMBOLS['info']} Starting Data Preparation Group ---",
        "info",
        logger_to_use,
    )
    overall_success = True

    # Define the sequence of data preparation steps
    # These now point to the more granular functions or their orchestrators
    step_definitions_in_group = [
        # GTFS Processing Sequence
        ("SETUP_GTFS_ENV", "Setup GTFS Environment (Logging & Env Vars)", setup_gtfs_logging_and_env_vars),
        ("DATAPROC_GTFS_ETL", "Run GTFS ETL Pipeline and Verify Data", run_gtfs_etl_pipeline_and_verify),
        ("CONFIG_GTFS_CRON", "Configure GTFS Update Cron Job", configure_gtfs_update_cronjob),

        # Raster Tile Pre-rendering
        (
            "RASTER_PREP",  # This is the existing tag for raster pre-rendering
            "Pre-render Raster Tiles",
            raster_tile_prerender,  # From dataproc.raster_processor
        ),
    ]

    for tag, desc, func_ref in step_definitions_in_group:
        if not execute_step(
                tag,
                desc,
                func_ref,
                logger_to_use,
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