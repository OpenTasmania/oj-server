# dataproc/data_processing.py
# -*- coding: utf-8 -*-
"""
Orchestrates data preparation tasks like GTFS processing and raster tile pre-rendering.
"""

import logging
from typing import (
    Callable,
    List,
    Optional,
    Tuple,
)  # Added Callable, List, Tuple

from common.command_utils import log_map_server
from dataproc.raster_processor import raster_tile_prerender
from processors.gtfs.orchestrator import (
    process_and_setup_gtfs,
)
from setup import (
    config as static_config,  # Used by main_installer for OSM_PROJECT_ROOT, potentially for tags
)
from setup.cli_handler import cli_prompt_for_rerun
from setup.config_models import AppSettings
from setup.step_executor import execute_step

module_logger = logging.getLogger(__name__)

# Define tag for GTFS processing if not already globally available via static_config
GTFS_PROCESSING_TAG = getattr(
    static_config,
    "GTFS_PROCESS_AND_SETUP_TAG",
    "GTFS_PROCESS_AND_SETUP",
)
RASTER_PREP_TAG = getattr(
    static_config,
    "RASTER_PREP_TAG",
    "RASTER_PREP",
)

# Define a type alias for the expected step function signature
StepFunctionType = Callable[[AppSettings, Optional[logging.Logger]], None]


def data_prep_group(
    app_cfg: AppSettings, current_logger: Optional[logging.Logger] = None
) -> bool:
    """
    Run all data preparation steps as a group.
    Uses app_cfg for all configurations.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_cfg.symbols
    log_map_server(
        f"--- {symbols.get('info', 'ℹ️')} Starting Data Preparation Group ---",
        "info",
        logger_to_use,
        app_cfg,
    )
    overall_success = True

    # Wrapper for GTFS processing to match execute_step signature
    def _run_gtfs_processing_step(
        ac: AppSettings, cl: Optional[logging.Logger]
    ) -> None:  # Explicit return type
        """
        Calls the main GTFS processing orchestrator.
        It relies on `app_settings` (passed as 'ac') for all its configurations.
        """
        process_and_setup_gtfs(app_settings=ac, orchestrator_logger=cl)

    # Type hint the list of step definitions
    step_definitions: List[Tuple[str, str, StepFunctionType]] = [
        (
            GTFS_PROCESSING_TAG,
            "Process GTFS Data and Configure Automation",
            _run_gtfs_processing_step,
        ),
        (RASTER_PREP_TAG, "Pre-render Raster Tiles", raster_tile_prerender),
    ]

    for (
        tag,
        desc,
        func_ref,
    ) in step_definitions:  # func_ref is now StepFunctionType
        if not execute_step(
            tag,
            desc,
            func_ref,  # This will be correctly typed
            app_cfg,
            logger_to_use,
            lambda prompt_msg,
            settings_for_prompt,
            logger_for_prompt: cli_prompt_for_rerun(
                prompt_msg,
                app_settings=settings_for_prompt,
                current_logger_instance=logger_for_prompt,
            ),
        ):
            overall_success = False
            log_map_server(
                f"{symbols.get('error', '❌')} Step '{desc}' ({tag}) failed. Aborting data prep group.",
                "error",
                logger_to_use,
                app_cfg,
            )
            break

    log_map_server(
        f"--- {symbols.get('info', 'ℹ️')} Data Preparation Group Finished (Success: {overall_success}) ---",
        "info" if overall_success else "error",
        logger_to_use,
        app_cfg,
    )
    return overall_success
