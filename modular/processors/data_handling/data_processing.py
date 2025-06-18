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
)

from common.command_utils import log_map_server
from modular.processors.data_handling.raster_processor import (
    raster_tile_prerender,
)
from modular.processors.plugins.importers.transit.gtfs.gtfs_process import (
    run_gtfs_setup,
)
from setup import (
    config as static_config,
)
from setup.cli_handler import cli_prompt_for_rerun
from setup.config_models import AppSettings
from setup.step_executor import execute_step

module_logger = logging.getLogger(__name__)


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

StepFunctionType = Callable[[AppSettings, Optional[logging.Logger]], bool]


def data_prep_group(
    app_cfg: AppSettings, current_logger: Optional[logging.Logger] = None
) -> bool:
    """
    Executes a series of predefined data preparation steps as a part of the data preparation group.

    This function coordinates the execution of multiple data preparation steps,
    logging progress and errors as appropriate. It utilizes an application configuration
    and a logger (if provided) to perform step-wise operations. Each step's execution
    status will influence whether subsequent steps are executed or the process halts.

    Parameters:
    app_cfg: AppSettings
        The application configuration object containing all necessary settings
        and metadata for the data preparation steps.
    current_logger: Optional[logging.Logger]
        An optional logger instance to capture log messages during execution.
        Defaults to a module-level logger if not provided.

    Returns:
    bool
        A boolean indicating the success or failure of the entire data preparation group.
        True if all steps succeed; False if any step fails.
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

    def _run_gtfs_processing_step(
        ac: AppSettings, cl: Optional[logging.Logger]
    ) -> bool:  # Explicit return type
        """
        Groups and orchestrates data preparation steps for GTFS processing. This includes
        initiating necessary processes and ensuring proper setup is completed for GTFS
        application configuration.

        Parameters:
        ac (AppSettings): The application configuration required to set up
            and process GTFS data.
        cl (Optional[logging.Logger]): The logger instance to log
            the process details or information during the GTFS preparation.

        Returns:
        bool: Indicates whether the data preparation steps were completed
            successfully.

        """
        return run_gtfs_setup(app_settings=ac, logger=cl)

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
    ) in step_definitions:
        if not execute_step(
            tag,
            desc,
            func_ref,
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
