#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Functions for data preparation, including GTFS processing and placeholders
for tile rendering and website setup. This module now imports shared utilities
from core_utils.
"""

import logging
from getpass import getuser
from grp import getgrgid
from logging import INFO
from os import environ, getgid, unlink
from os.path import exists
from pwd import getpwnam
from shutil import which
from tempfile import NamedTemporaryFile

from setup import config, core_utils
from setup.cli_handler import cli_prompt_for_rerun
from setup.command_utils import (
    log_map_server,
    run_command,
    run_elevated_command,
)
from setup.step_executor import execute_step

try:
    from processors.gtfs import (  # Relative import for processors package
        main_pipeline as gtfs_main_pipeline,
    )

    gtfs_processor_available = True
except ImportError as e:
    gtfs_main_pipeline = None
    gtfs_processor_available = False
    logging.getLogger(__name__).warning(
        f"Could not import processors.gtfs.main_pipeline at load time: {e}. "
        "GTFS processing will likely fail."
    )

module_logger = logging.getLogger(__name__)


def gtfs_data_prep(current_logger: logging.Logger = None) -> None:
    """
    Prepare GTFS data: set up logging, environment variables,
    run the ETL pipeline, and configure a cron job for updates.

    Args:
        current_logger: The logger instance to use. Defaults to module_logger.

    Raises:
        ImportError: If the `gtfs_processor.main_pipeline` cannot be imported.
        RuntimeError: If the GTFS ETL pipeline fails.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Preparing GTFS data...",
        "info",
        logger_to_use,
    )

    gtfs_log_file = "/var/log/gtfs_processor_app.log"
    try:
        run_elevated_command(
            ["touch", gtfs_log_file], current_logger=logger_to_use
        )
        current_user_name = getuser()
        try:
            current_group_info = getgrgid(getgid())
            current_group_name = current_group_info.gr_name
        except KeyError:
            current_group_name = str(getgid())
        run_elevated_command(
            [
                "chown",
                f"{current_user_name}:{current_group_name}",
                gtfs_log_file,
            ],
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['info']} Ensured GTFS log file exists and is "
            f"writable: {gtfs_log_file}",
            "info",
            logger_to_use,
        )
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['warning']} Could not create/chown GTFS log "
            f"file {gtfs_log_file}: {e}. Logging might fail.",
            "warning",
            logger_to_use,
        )

    environ["GTFS_FEED_URL"] = config.GTFS_FEED_URL
    environ["PG_OSM_PASSWORD"] = config.PGPASSWORD
    environ["PG_OSM_USER"] = config.PGUSER
    environ["PG_OSM_HOST"] = config.PGHOST
    environ["PG_OSM_PORT"] = config.PGPORT
    environ["PG_OSM_DATABASE"] = config.PGDATABASE

    if not gtfs_processor_available or not gtfs_main_pipeline:
        log_map_server(
            f"{config.SYMBOLS['error']} `processors.gtfs.main_pipeline` "
            "was not imported successfully.",
            "error",
            logger_to_use,
        )
        raise ImportError(
            "processors.gtfs.main_pipeline not available. Cannot run GTFS ETL."
        )

    try:
        log_map_server(
            f"{config.SYMBOLS['info']} Setting up logging using core_utils for "
            "subsequent GTFS processing operations...",
            "info",
            logger_to_use,
        )
        # MODIFIED: Call setup_logging from core_utils
        # This configures logging globally; the GTFS processor modules will use this configuration.
        core_utils.setup_logging(
            log_level=INFO,
            log_file=gtfs_log_file,  # GTFS operations will log here
            log_to_console=True,  # GTFS operations will also log to console
        )

        log_map_server(
            f"{config.SYMBOLS['rocket']} Running GTFS ETL pipeline with URL: "
            f"{config.GTFS_FEED_URL}. Check {gtfs_log_file} for detailed "
            "logs from the GTFS processor.",
            "info",
            logger_to_use,
        )

        success = gtfs_main_pipeline.run_full_gtfs_etl_pipeline()

        if success:
            log_map_server(
                f"{config.SYMBOLS['success']} GTFS ETL pipeline completed "
                "successfully.",
                "success",
                logger_to_use,
            )
            log_map_server(
                f"{config.SYMBOLS['info']} Verifying data import (counts "
                "from tables)...",
                "info",
                logger_to_use,
            )
            try:
                run_command(
                    [
                        "psql",
                        "-h",
                        config.PGHOST,
                        "-p",
                        config.PGPORT,
                        "-U",
                        config.PGUSER,
                        "-d",
                        config.PGDATABASE,
                        "-c",
                        "SELECT COUNT(*) FROM gtfs_stops;",
                    ],
                    capture_output=True,
                    current_logger=logger_to_use,
                )
                run_command(
                    [
                        "psql",
                        "-h",
                        config.PGHOST,
                        "-p",
                        config.PGPORT,
                        "-U",
                        config.PGUSER,
                        "-d",
                        config.PGDATABASE,
                        "-c",
                        "SELECT COUNT(*) FROM gtfs_routes;",
                    ],
                    capture_output=True,
                    current_logger=logger_to_use,
                )
            except Exception as e_psql:
                log_map_server(
                    f"{config.SYMBOLS['warning']} Could not verify GTFS "
                    f"counts with psql: {e_psql}",
                    "warning",
                    logger_to_use,
                )
        else:
            log_map_server(
                f"{config.SYMBOLS['error']} GTFS ETL pipeline FAILED. "
                f"Check {gtfs_log_file}.",
                "error",
                logger_to_use,
            )
            raise RuntimeError("GTFS ETL Pipeline Failed.")

    except ImportError as e:  # Should be caught by the check above, but defensive
        log_map_server(
            f"{config.SYMBOLS['error']} Critical error importing/using "
            f"`processors.gtfs.main_pipeline`: {e}",
            "error",
            logger_to_use,
        )
        raise
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} An unexpected error occurred during "
            f"GTFS processing: {e}",
            "error",
            logger_to_use,
        )
        raise

    log_map_server(
        f"{config.SYMBOLS['gear']} Setting up cron job for daily GTFS "
        "updates...",
        "info",
        logger_to_use,
    )
    python_executable = which("python3") or which("python")
    if not python_executable:
        log_map_server(
            f"{config.SYMBOLS['error']} Python executable not found. "
            "Cannot set up cron job.",
            "error",
            logger_to_use,
        )
        return

    intended_cron_user = config.PGUSER
    actual_cron_user = intended_cron_user
    use_user_flag_for_crontab = True

    try:
        getpwnam(intended_cron_user)
        logger_to_use.info(
            f"System user '{intended_cron_user}' found. Cron job will be set for this user."
        )
    except KeyError:
        logger_to_use.warning(
            f"System user '{intended_cron_user}' (from config.PGUSER) not "
            "found. Cron job will be installed for the 'root' user instead."
        )
        actual_cron_user = "root"
        use_user_flag_for_crontab = False

    # The command should point to the entrypoint in processors.gtfs, often update_gtfs.py if it's the CLI
    # Assuming your project structure allows running `python -m processors.gtfs.update_gtfs`
    # Path to the python executable in your virtual environment might be more robust if not using system python for cron
    # For simplicity, using the found python_executable.
    # The `update_gtfs.py` script is now a CLI wrapper for main_pipeline.py
    update_script_module_path = "processors.gtfs.update_gtfs"  # Using the module path

    update_script_command = (
        f"{python_executable} -m {update_script_module_path}"
    )
    env_vars_for_cron = (
        f"GTFS_FEED_URL='{config.GTFS_FEED_URL}' "
        f"PG_OSM_PASSWORD='{config.PGPASSWORD}' "
        f"PG_OSM_USER='{config.PGUSER}' "
        f"PG_OSM_HOST='{config.PGHOST}' "
        f"PG_OSM_PORT='{config.PGPORT}' "
        f"PG_OSM_DATABASE='{config.PGDATABASE}'"
    )
    cron_job_line = (
        f"0 3 * * * {env_vars_for_cron} {update_script_command} "
        f">> {gtfs_log_file} 2>&1"
    )

    temp_cron_path = ""
    try:
        crontab_l_cmd = ["crontab"]
        if use_user_flag_for_crontab:
            crontab_l_cmd.extend(["-u", actual_cron_user])
        crontab_l_cmd.append("-l")

        existing_crontab_result = run_elevated_command(
            crontab_l_cmd,
            check=False,
            capture_output=True,
            current_logger=logger_to_use,
        )
        existing_crontab_content = (
            existing_crontab_result.stdout
            if existing_crontab_result.returncode == 0
            else ""
        )

        new_crontab_lines = [
            line
            for line in existing_crontab_content.splitlines()
            if update_script_module_path not in line  # Check against module path
        ]
        new_crontab_content = "\n".join(new_crontab_lines)
        if new_crontab_content and not new_crontab_content.endswith("\n"):
            new_crontab_content += "\n"
        new_crontab_content += cron_job_line + "\n"

        with NamedTemporaryFile(
                mode="w", delete=False, prefix="gtfscron_"
        ) as temp_f:
            temp_f.write(new_crontab_content)
            temp_cron_path = temp_f.name

        install_cron_cmd = ["crontab"]
        if use_user_flag_for_crontab:
            install_cron_cmd.extend(["-u", actual_cron_user])
        install_cron_cmd.append(temp_cron_path)

        run_elevated_command(
            install_cron_cmd,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{config.SYMBOLS['success']} Cron job for GTFS update configured "
            f"for user '{actual_cron_user}'.",
            "success",
            logger_to_use,
        )
    except Exception as e_cron:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to set up cron job for GTFS "
            f"update: {e_cron}",
            "error",
            logger_to_use,
        )
    finally:
        if temp_cron_path and exists(temp_cron_path):
            unlink(temp_cron_path)


def raster_tile_prep(current_logger: logging.Logger = None) -> None:
    """
    Placeholder for Raster Tile Preparation.

    Args:
        current_logger: The logger instance to use. Defaults to module_logger.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Placeholder for Raster Tile Prep",
        "info",
        logger_to_use,
    )


def website_prep(current_logger: logging.Logger = None) -> None:
    """
    Placeholder for Website Preparation.

    Args:
        current_logger: The logger instance to use. Defaults to module_logger.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Placeholder for Website Prep",
        "info",
        logger_to_use,
    )


def data_prep_group(current_logger: logging.Logger) -> bool:
    """
    Run all data preparation steps as a group.

    Args:
        current_logger: The logger instance to use.

    Returns:
        True if all steps in the group succeed, False otherwise.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"--- {config.SYMBOLS['info']} Starting Data Preparation Group ---",
        "info",
        logger_to_use,
    )
    overall_success = True

    step_definitions_in_group = [
        (
            "GTFS_PREP",
            "Prepare GTFS Data (Download & Import)",
            gtfs_data_prep,
        ),
        ("RASTER_PREP", "Pre-render Raster Tiles", raster_tile_prep),
        ("WEBSITE_PREP", "Prepare Test Website", website_prep),
    ]
    for tag, desc, func in step_definitions_in_group:
        if not execute_step(
                tag,
                desc,
                func,
                logger_to_use,
                prompt_user_for_rerun=cli_prompt_for_rerun,
        ):
            overall_success = False
            log_map_server(
                f"{config.SYMBOLS['error']} Step '{desc}' failed. Aborting "
                "data prep group.",
                "error",
                logger_to_use,
            )
            break

    log_map_server(
        f"--- {config.SYMBOLS['info']} Data Preparation Group Finished "
        f"(Overall Success: {overall_success}) ---",
        "info" if overall_success else "error",
        logger_to_use,
    )
    return overall_success