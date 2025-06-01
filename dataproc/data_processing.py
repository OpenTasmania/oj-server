# dataproc/data_processing.py
# -*- coding: utf-8 -*-
"""
Orchestrates data preparation tasks like GTFS processing and raster tile pre-rendering.
"""
import logging
from pathlib import Path
from typing import Dict, Optional

from common.command_utils import log_map_server
from dataproc.raster_processor import raster_tile_prerender  # Local import
from processors.gtfs.orchestrator import (
    process_and_setup_gtfs,  # GTFS main orchestrator
)
from setup import config as static_config  # For OSM_PROJECT_ROOT
from setup.cli_handler import cli_prompt_for_rerun
from setup.config_models import AppSettings
from setup.step_executor import execute_step

module_logger = logging.getLogger(__name__)

# Define tag for GTFS processing if not already globally available via static_config
# It's better if main_installer.py defines all tags used by execute_step.
# Assuming GTFS_PROCESS_AND_SETUP_TAG is defined in main_installer and static_config
GTFS_PROCESSING_TAG = getattr(static_config, 'GTFS_PROCESS_AND_SETUP_TAG', "GTFS_PROCESSING_AND_SETUP")
RASTER_PREP_TAG = "RASTER_PREP"  # Ensure this matches the tag in main_installer.py


def data_prep_group(app_cfg: AppSettings, current_logger: Optional[logging.Logger] = None) -> bool:
    """
    Run all data preparation steps as a group.
    Uses app_cfg for all configurations.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_cfg.symbols
    log_map_server(f"--- {symbols.get('info', 'ℹ️')} Starting Data Preparation Group ---", "info", logger_to_use, app_cfg)
    overall_success = True

    # Wrapper for GTFS processing to match execute_step signature (AppSettings, Logger)
    def _run_gtfs_processing_step(ac: AppSettings, cl: Optional[logging.Logger]):
        db_params_dict: Dict[str, str] = {
            "PGHOST": ac.pg.host, "PGPORT": str(ac.pg.port),
            "PGDATABASE": ac.pg.database, "PGUSER": ac.pg.user,
            "PGPASSWORD": ac.pg.password
        }
        # Consider making these log paths configurable via AppSettings.gtfs or a dedicated GTFS config section
        gtfs_app_log = "/var/log/gtfs_processor_app.log"
        cron_output_log = "/var/log/gtfs_cron_output.log"
        project_root = Path(static_config.OSM_PROJECT_ROOT)

        process_and_setup_gtfs(
            gtfs_feed_url=str(ac.gtfs_feed_url),
            db_params=db_params_dict,
            project_root=project_root,
            gtfs_app_log_file=gtfs_app_log,  # Log file for GTFS app's own detailed logging
            # gtfs_app_log_level, gtfs_app_log_prefix can be passed if needed, defaults in orchestrator
            cron_run_user=ac.pg.user,
            cron_job_output_log_file=cron_output_log,
            # python_executable_for_cron can be passed if needed
            orchestrator_logger=cl  # Logger for messages from process_and_setup_gtfs itself
        )

    step_definitions = [
        (GTFS_PROCESSING_TAG, "Process GTFS Data and Configure Automation", _run_gtfs_processing_step),
        (RASTER_PREP_TAG, "Pre-render Raster Tiles", raster_tile_prerender),
    ]

    for tag, desc, func_ref in step_definitions:
        # Ensure cli_prompt_for_rerun is passed correctly
        if not execute_step(tag, desc, func_ref, app_cfg, logger_to_use,
                            lambda prompt, ac_prompt, cl_prompt: cli_prompt_for_rerun(prompt, app_settings=ac_prompt, current_logger_instance=cl_prompt)):
            overall_success = False
            log_map_server(f"{symbols.get('error', '❌')} Step '{desc}' ({tag}) failed. Aborting data prep group.", "error", logger_to_use, app_cfg)
            break

    log_map_server(
        f"--- {symbols.get('info', 'ℹ️')} Data Preparation Group Finished (Success: {overall_success}) ---",
        "info" if overall_success else "error", logger_to_use, app_cfg)
    return overall_success