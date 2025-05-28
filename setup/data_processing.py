# setup/data_processing.py
# -*- coding: utf-8 -*-
"""
Functions for data preparation, including GTFS processing and placeholders
for tile rendering and website setup.
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

from setup import config
from setup.cli_handler import cli_prompt_for_rerun
from setup.command_utils import (
    log_map_server,
    run_command,
    run_elevated_command,
)
from setup.step_executor import execute_step

# Attempt to import GTFS processing modules.
# These are optional and the script can proceed with warnings if they're
# not found, though GTFS processing will fail.
try:
    from processors.gtfs import (
        main_pipeline as gtfs_main_pipeline,
    )
    from processors.gtfs import (
        utils as gtfs_utils,
    )
except ImportError as e:
    gtfs_main_pipeline = None
    gtfs_utils = None
    logging.getLogger(__name__).warning(
        f"Could not import processors.gtfs module at load time: {e}. "
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
        ImportError: If the `gtfs_processor` modules cannot be imported.
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
            # Fallback to GID if group name is not found
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

    # Set environment variables for the GTFS processor
    environ["GTFS_FEED_URL"] = config.GTFS_FEED_URL
    environ["PG_OSM_PASSWORD"] = config.PGPASSWORD
    environ["PG_OSM_USER"] = config.PGUSER
    environ["PG_OSM_HOST"] = config.PGHOST
    environ["PG_OSM_PORT"] = config.PGPORT
    environ["PG_OSM_DATABASE"] = config.PGDATABASE

    if not gtfs_main_pipeline or not gtfs_utils:
        log_map_server(
            f"{config.SYMBOLS['error']} `gtfs_processor` modules "
            "(main_pipeline, utils) were not imported successfully.",
            "error",
            logger_to_use,
        )
        log_map_server(
            "   This script needs `gtfs_processor` to be in its Python "
            "environment.",
            "error",
            logger_to_use,
        )
        log_map_server(
            "   NEXT STEP: Refactor this to use `uv` to run `gtfs_processor` "
            "in an isolated environment.",
            "error",
            logger_to_use,
        )
        raise ImportError(
            "gtfs_processor modules not available. Cannot run GTFS ETL."
        )

    try:
        log_map_server(
            f"{config.SYMBOLS['info']} Setting up logging for "
            "gtfs_processor module...",
            "info",
            logger_to_use,
        )
        gtfs_utils.setup_logging(
            log_level=INFO,
            log_file=gtfs_log_file,
            log_to_console=True,
        )

        log_map_server(
            f"{config.SYMBOLS['rocket']} Running GTFS ETL pipeline with URL: "
            f"{config.GTFS_FEED_URL}. Check {gtfs_log_file} for detailed "
            "logs.",
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
                # Verify counts from gtfs_stops table
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
                # Verify counts from gtfs_routes table
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

    except ImportError as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Critical error importing/using "
            f"`gtfs_processor`: {e}",
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

    # Configure cron job for daily GTFS updates.
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

    # Determine the target user for the cron job.
    intended_cron_user = config.PGUSER  # This is 'osmuser'.
    actual_cron_user = intended_cron_user
    use_user_flag_for_crontab = True

    try:
        getpwnam(intended_cron_user)
        logger_to_use.info(
            f"System user '{intended_cron_user}' found. Cron job will be set "
            "for this user."
        )
    except KeyError:
        logger_to_use.warning(
            f"System user '{intended_cron_user}' (from config.PGUSER) not "
            "found. The cron job will be installed for the 'root' user "
            "instead."
        )
        actual_cron_user = "root"  # Fallback to root.
        # When running as root for root's crontab, -u root is not needed.
        use_user_flag_for_crontab = False

    update_script_command = (
        # Ensure this path is correct if running as different user.
        f"{python_executable} -m gtfs_processor.update_gtfs"
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
        # Construct the crontab -l command.
        crontab_l_cmd = ["crontab"]
        if use_user_flag_for_crontab:
            crontab_l_cmd.extend(["-u", actual_cron_user])
        crontab_l_cmd.append("-l")

        existing_crontab_result = run_elevated_command(
            crontab_l_cmd,
            check=False,  # Allow failure if user has no crontab yet.
            capture_output=True,
            current_logger=logger_to_use,
        )
        existing_crontab_content = (
            existing_crontab_result.stdout
            if existing_crontab_result.returncode == 0
            else ""
        )

        # Avoid duplicate job entries.
        new_crontab_lines = [
            line
            for line in existing_crontab_content.splitlines()
            if "gtfs_processor.update_gtfs" not in line
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

        # Construct the crontab install command.
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
        # Optionally re-raise if this is critical.
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
    # TODO: Add actual logic for raster tile preparation.


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
    # TODO: Add actual logic for website preparation.


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
