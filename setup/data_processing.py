# setup/data_processing.py
"""
Functions for data preparation: GTFS processing, tile rendering, website setup.
"""
import getpass
import logging
import os
import shutil  # For shutil.which
import tempfile

from . import config  # For config.GTFS_FEED_URL, config.SYMBOLS etc.
# Corrected import: SYMBOLS removed from here
from .command_utils import run_command, run_elevated_command, log_map_server
from .ui import execute_step  # To call individual steps if this module had sub-steps

# Attempt to import gtfs_processor modules, but handle failure gracefully
try:
    from processors.gtfs import utils as gtfs_utils, main_pipeline as gtfs_main_pipeline
except ImportError as e:
    gtfs_main_pipeline = None
    gtfs_utils = None
    logging.getLogger(__name__).warning(  # Use a basic logger if this module is imported early
        f"Could not import gtfs_processor modules at load time: {e}. GTFS processing will likely fail.")

module_logger = logging.getLogger(__name__)


def gtfs_data_prep(current_logger=None) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    # Use config.SYMBOLS for direct access
    log_map_server(f"{config.SYMBOLS['step']} Preparing GTFS data...", "info", logger_to_use)

    gtfs_log_file = "/var/log/gtfs_processor_app.log"
    try:
        run_elevated_command(["touch", gtfs_log_file], current_logger=logger_to_use)
        current_user = getpass.getuser()
        current_group = getpass.getgrgid(os.getgid()).gr_name
        run_elevated_command(["chown", f"{current_user}:{current_group}", gtfs_log_file], current_logger=logger_to_use)
        log_map_server(f"{config.SYMBOLS['info']} Ensured GTFS log file exists and is writable: {gtfs_log_file}",
                       "info", logger_to_use)
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['warning']} Could not create/chown GTFS log file {gtfs_log_file}: {e}. Logging might fail.",
            "warning", logger_to_use)

    os.environ["GTFS_FEED_URL"] = config.GTFS_FEED_URL
    os.environ["PG_OSM_PASSWORD"] = config.PGPASSWORD
    os.environ["PG_OSM_USER"] = config.PGUSER
    os.environ["PG_OSM_HOST"] = config.PGHOST
    os.environ["PG_OSM_PORT"] = config.PGPORT
    os.environ["PG_OSM_DATABASE"] = config.PGDATABASE

    if not gtfs_main_pipeline or not gtfs_utils:
        log_map_server(
            f"{config.SYMBOLS['error']} `gtfs_processor` modules (main_pipeline, utils) were not imported successfully.",
            "error", logger_to_use)
        log_map_server(
            f"   This script needs `gtfs_processor` to be in its Python environment.",
            "error", logger_to_use)
        log_map_server(
            f"   NEXT STEP: Refactor this to use `uv` to run `gtfs_processor` in an isolated environment.",
            "error", logger_to_use)
        raise ImportError("gtfs_processor modules not available. Cannot run GTFS ETL.")

    try:
        log_map_server(f"{config.SYMBOLS['info']} Setting up logging for gtfs_processor module...", "info",
                       logger_to_use)
        gtfs_utils.setup_logging(
            log_level=logging.INFO,
            log_file=gtfs_log_file,
            log_to_console=True
        )

        log_map_server(
            f"{config.SYMBOLS['rocket']} Running GTFS ETL pipeline with URL: {config.GTFS_FEED_URL}. Check {gtfs_log_file} for detailed logs.",
            "info", logger_to_use)

        success = gtfs_main_pipeline.run_full_gtfs_etl_pipeline()

        if success:
            log_map_server(f"{config.SYMBOLS['success']} GTFS ETL pipeline completed successfully.", "success",
                           logger_to_use)
            log_map_server(f"{config.SYMBOLS['info']} Verifying data import (counts from tables)...", "info",
                           logger_to_use)
            try:
                run_command(
                    ["psql", "-h", config.PGHOST, "-p", config.PGPORT, "-U", config.PGUSER, "-d", config.PGDATABASE,
                     "-c", "SELECT COUNT(*) FROM gtfs_stops;"], capture_output=True, current_logger=logger_to_use)
                run_command(
                    ["psql", "-h", config.PGHOST, "-p", config.PGPORT, "-U", config.PGUSER, "-d", config.PGDATABASE,
                     "-c", "SELECT COUNT(*) FROM gtfs_routes;"], capture_output=True, current_logger=logger_to_use)
            except Exception as e_psql:
                log_map_server(f"{config.SYMBOLS['warning']} Could not verify GTFS counts with psql: {e_psql}",
                               "warning", logger_to_use)
        else:
            log_map_server(f"{config.SYMBOLS['error']} GTFS ETL pipeline FAILED. Check {gtfs_log_file}.", "error",
                           logger_to_use)
            raise RuntimeError("GTFS ETL Pipeline Failed.")

    except ImportError as e:
        log_map_server(f"{config.SYMBOLS['error']} Critical error importing/using `gtfs_processor`: {e}", "error",
                       logger_to_use)
        raise
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['error']} An unexpected error occurred during GTFS processing: {e}", "error",
                       logger_to_use)
        raise

    log_map_server(f"{config.SYMBOLS['gear']} Setting up cron job for daily GTFS updates...", "info", logger_to_use)
    python_executable = shutil.which("python3") or shutil.which("python")
    if not python_executable:
        log_map_server(f"{config.SYMBOLS['error']} Python executable not found. Cannot set up cron job.", "error",
                       logger_to_use)
        return

    cron_user_for_gtfs = config.PGUSER
    update_script_command = f"{python_executable} -m gtfs_processor.update_gtfs"
    env_vars_for_cron = f"GTFS_FEED_URL='{config.GTFS_FEED_URL}' PG_OSM_PASSWORD='{config.PGPASSWORD}' PG_OSM_USER='{config.PGUSER}' PG_OSM_HOST='{config.PGHOST}' PG_OSM_PORT='{config.PGPORT}' PG_OSM_DATABASE='{config.PGDATABASE}'"
    cron_job_line = f"0 3 * * * {env_vars_for_cron} {update_script_command} >> {gtfs_log_file} 2>&1"

    temp_cron_path = ""
    try:
        crontab_l_cmd = ["crontab", "-u", cron_user_for_gtfs, "-l"]
        existing_crontab_result = run_elevated_command(crontab_l_cmd, check=False, capture_output=True,
                                                       current_logger=logger_to_use)
        existing_crontab_content = existing_crontab_result.stdout if existing_crontab_result.returncode == 0 else ""

        new_crontab_lines = [line for line in existing_crontab_content.splitlines() if
                             "gtfs_processor.update_gtfs" not in line]
        new_crontab_content = "\n".join(new_crontab_lines)
        if new_crontab_content and not new_crontab_content.endswith("\n"):
            new_crontab_content += "\n"
        new_crontab_content += cron_job_line + "\n"

        with tempfile.NamedTemporaryFile(mode='w', delete=False, prefix="gtfscron_") as temp_f:
            temp_f.write(new_crontab_content)
            temp_cron_path = temp_f.name

        run_elevated_command(["crontab", "-u", cron_user_for_gtfs, temp_cron_path], current_logger=logger_to_use)
        log_map_server(
            f"{config.SYMBOLS['success']} Cron job for GTFS update configured for user {cron_user_for_gtfs}.",
            "success", logger_to_use)
    except Exception as e_cron:
        log_map_server(f"{config.SYMBOLS['error']} Failed to set up cron job for GTFS update: {e_cron}", "error",
                       logger_to_use)
    finally:
        if temp_cron_path and os.path.exists(temp_cron_path):
            os.unlink(temp_cron_path)


# Define raster_tile_prep and website_prep similarly, using config.SYMBOLS
def raster_tile_prep(current_logger=None):
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Placeholder for Raster Tile Prep", "info", logger_to_use)
    # ... Add actual logic ...


def website_prep(current_logger=None):
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"{config.SYMBOLS['step']} Placeholder for Website Prep", "info", logger_to_use)
    # ... Add actual logic ...


def data_prep_group(current_logger) -> bool:
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(f"--- {config.SYMBOLS['info']} Starting Data Preparation Group ---", "info", logger_to_use)
    overall_success = True

    step_definitions_in_group = [
        ("GTFS_PREP", "Prepare GTFS Data (Download & Import)", gtfs_data_prep),
        ("RASTER_PREP", "Pre-render Raster Tiles", raster_tile_prep),
        ("WEBSITE_PREP", "Prepare Test Website", website_prep),
    ]
    for tag, desc, func in step_definitions_in_group:
        if not execute_step(tag, desc, func, logger_to_use):  # execute_step from ui.py
            overall_success = False
            log_map_server(f"{config.SYMBOLS['error']} Step '{desc}' failed. Aborting data prep group.", "error",
                           logger_to_use)
            break

    log_map_server(
        f"--- {config.SYMBOLS['info']} Data Preparation Group Finished (Overall Success: {overall_success}) ---",
        "info" if overall_success else "error", logger_to_use)
    return overall_success