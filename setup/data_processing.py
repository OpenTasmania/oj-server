# setup/data_processing.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Functions for data preparation, including GTFS processing and raster tile
pre-rendering. This module now imports shared utilities from core_utils.
"""

import datetime
import logging
import os # Added for os.cpu_count()
import subprocess # Added for CalledProcessError
from getpass import getuser
from grp import getgrgid
from logging import INFO
# from os import environ, getgid, unlink # environ, getgid, unlink already imported below
from os import environ, getgid, unlink as os_unlink # renamed unlink to avoid conflict with local var
from os.path import exists
from pwd import getpwnam
from shutil import which
from tempfile import NamedTemporaryFile
from typing import Dict, Optional
from pathlib import Path

from setup import config, core_utils
from setup.cli_handler import cli_prompt_for_rerun
from common.command_utils import (
    log_map_server,
    run_command,
    run_elevated_command,
)
from setup.step_executor import execute_step

try:
    from processors.gtfs import (
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

OSM_CARTO_DIR = "/opt/openstreetmap-carto"

def gtfs_data_prep(current_logger: logging.Logger = None) -> None:
    # ... (gtfs_data_prep content remains the same)
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
        core_utils.setup_logging(
            log_level=INFO,
            log_file=gtfs_log_file,
            log_to_console=True,
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

    except ImportError as e:
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

    update_script_module_path = "processors.gtfs.update_gtfs"
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
            if update_script_module_path not in line
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
            os_unlink(temp_cron_path)


def raster_tile_prerender(current_logger: logging.Logger = None) -> None:
    """
    Pre-render raster tiles using render_list for different zoom level ranges.
    Ensures renderd service is active before starting.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Starting raster tile pre-rendering...",
        "info",
        logger_to_use,
    )

    # Check if renderd service is active
    try:
        renderd_status_cmd = ["systemctl", "is-active", "renderd.service"]
        result = run_elevated_command(
            renderd_status_cmd,
            capture_output=True,
            check=False, # Don't raise error, check status manually
            current_logger=logger_to_use
        )
        if result.returncode != 0 or result.stdout.strip() != "active":
            log_map_server(
                f"{config.SYMBOLS['error']} renderd service is not active (status: {result.stdout.strip()}). "
                "Cannot pre-render tiles. Please ensure renderd is set up and running.",
                "error",
                logger_to_use,
            )
            # Optionally, try to start it:
            # log_map_server(f"{config.SYMBOLS['info']} Attempting to start renderd service...", "info", logger_to_use)
            # run_elevated_command(["systemctl", "start", "renderd.service"], current_logger=logger_to_use)
            # result = run_elevated_command(renderd_status_cmd, capture_output=True, check=False, current_logger=logger_to_use)
            # if result.returncode != 0 or result.stdout.strip() != "active":
            #     log_map_server(f"{config.SYMBOLS['error']} Failed to start renderd. Aborting tile pre-rendering.", "error", logger_to_use)
            #     return # Or raise an exception
            raise RuntimeError("renderd service is not active. Cannot pre-render tiles.")
        log_map_server(
            f"{config.SYMBOLS['success']} renderd service is active. Proceeding with tile pre-rendering.",
            "success",
            logger_to_use,
        )
    except subprocess.CalledProcessError as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Error checking renderd status: {e.stderr or e.stdout or e}",
            "error",
            logger_to_use,
        )
        raise RuntimeError(f"Error checking renderd status: {e}")
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Unexpected error checking renderd status: {e}",
            "error",
            logger_to_use,
        )
        raise

    num_threads = str(os.cpu_count() or 1) # Get number of processors for --num-threads

    render_list_base_cmd = [
        "render_list",
        "--all",
        "--num-threads", num_threads,
        "--socket=/var/run/renderd/renderd.sock"
    ]

    # Stage 1: Low-resolution tiles (Zoom 0-5)
    log_map_server(
        f"{config.SYMBOLS['info']} Queuing low-resolution raster tiles (Zoom 0-5) for rendering...",
        "info",
        logger_to_use,
    )
    cmd_low_res = render_list_base_cmd + ["--min-zoom=0", "--max-zoom=5"]
    try:
        run_elevated_command(cmd_low_res, current_logger=logger_to_use)
        log_map_server(
            f"{config.SYMBOLS['success']} Successfully queued low-resolution tiles (Zoom 0-5). "
            "renderd will process these in the background.",
            "success",
            logger_to_use,
        )
    except subprocess.CalledProcessError as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to queue low-resolution tiles: {e.stderr or e.stdout or e}",
            "error",
            logger_to_use,
        )
        # Decide if we should proceed to high-res or stop
        log_map_server(
            f"{config.SYMBOLS['warning']} Continuing to queue high-resolution tiles despite low-resolution queueing error.",
            "warning",
            logger_to_use,
        ) # For now, let's try to queue high-res anyway.
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Unexpected error queuing low-resolution tiles: {e}",
            "error",
            logger_to_use,
        )
        raise # More critical unexpected error

    # Stage 2: High-resolution tiles (Zoom 6-12)
    log_map_server(
        f"{config.SYMBOLS['info']} Queuing high-resolution raster tiles (Zoom 6-12) for rendering...",
        "info",
        logger_to_use,
    )
    cmd_high_res = render_list_base_cmd + ["--min-zoom=6", "--max-zoom=12"]
    try:
        run_elevated_command(cmd_high_res, current_logger=logger_to_use)
        log_map_server(
            f"{config.SYMBOLS['success']} Successfully queued high-resolution tiles (Zoom 6-12). "
            "renderd will process these in the background.",
            "success",
            logger_to_use,
        )
    except subprocess.CalledProcessError as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Failed to queue high-resolution tiles: {e.stderr or e.stdout or e}",
            "error",
            logger_to_use,
        )
        # If high-res fails, it's still an overall failure of this step for now.
        raise RuntimeError(f"Failed to queue high-resolution tiles: {e}")
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Unexpected error queuing high-resolution tiles: {e}",
            "error",
            logger_to_use,
        )
        raise

    log_map_server(
        f"{config.SYMBOLS['info']} All tile rendering tasks have been queued. "
        "Monitor renderd logs and system load for progress. This can take a very long time.",
        "info",
        logger_to_use,
    )


def data_prep_group(current_logger: logging.Logger) -> bool:
    """
    Run all data preparation steps as a group.
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
        (
            "RASTER_PREP", # Tag remains RASTER_PREP
            "Pre-render Raster Tiles", # Description updated
            raster_tile_prerender, # Function name changed
        ),
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


def import_pbf_to_postgis_flex(
        pbf_file_path: str,
        db_config_dict: Dict[str, str],
        flat_nodes_storage_dir: str,  # e.g., /opt/osm_data
        current_logger: Optional[logging.Logger] = None,
        osm2pgsql_cache_mb: Optional[int] = None,
) -> bool:
    """Imports a PBF file into PostGIS using osm2pgsql with the Flex backend."""
    logger_to_use = current_logger if current_logger else module_logger
    region_name = Path(pbf_file_path).stem.replace(".osm", "")  # Get basename without .osm.pbf
    log_map_server(
        f"{config.SYMBOLS['info']} Starting PostGIS import for {region_name} ({pbf_file_path}) using osm2pgsql (Flex backend)...",
        "info", logger_to_use
    )

    lua_script_path = Path(OSM_CARTO_DIR) / "openstreetmap-carto.lua"  # Path to style lua
    # Or use openstreetmap-carto-flex.lua if that's preferred and exists
    # lua_script_path_flex = Path(OSM_CARTO_DIR) / "openstreetmap-carto-flex.lua"
    # if lua_script_path_flex.is_file():
    #    lua_script_path = lua_script_path_flex

    if not lua_script_path.is_file():
        log_map_server(f"{config.SYMBOLS['critical']} OSM-Carto Lua script not found at {lua_script_path}.", "critical",
                       logger_to_use)
        return False

    num_processes = str(os.cpu_count() or 1)
    cache_size = str(osm2pgsql_cache_mb or os.environ.get("OSM2PGSQL_CACHE_DEFAULT", "20000"))  # Default 20GB

    flat_nodes_file = Path(flat_nodes_storage_dir) / f"flat-nodes-{region_name}-{datetime.date.today().isoformat()}.bin"

    # Ensure PGPASSWORD is set in environment for osm2pgsql
    process_env = os.environ.copy()
    if "password" in db_config_dict and db_config_dict["password"]:
        process_env["PGPASSWORD"] = db_config_dict["password"]

    osm2pgsql_cmd = [
        "osm2pgsql", "--verbose", "--create", "--slim", "-C", cache_size,
        "--host", db_config_dict.get("host", "localhost"),
        "--port", str(db_config_dict.get("port", "5432")),
        "--username", db_config_dict.get("user", config.PGUSER),
        "--database", db_config_dict.get("dbname", config.PGDATABASE),
        "--hstore", "--multi-geometry", "--tag-transform-script", str(lua_script_path),
        "--style", str(lua_script_path),  # Flex style often same as transform
        "--output=flex", "--number-processes", num_processes,
        "--flat-nodes", str(flat_nodes_file),
        pbf_file_path
    ]
    log_map_server(f"{config.SYMBOLS['debug']} osm2pgsql command: {' '.join(osm2pgsql_cmd)}", "debug", logger_to_use)

    try:
        # osm2pgsql can take a long time. User running this script needs appropriate DB perms.
        completed_process = subprocess.run(
            osm2pgsql_cmd, env=process_env, check=False, capture_output=True, text=True
        )
        if completed_process.stdout: logger_to_use.debug(
            f"osm2pgsql STDOUT for {region_name}:\n{completed_process.stdout}")
        if completed_process.stderr:
            log_level_stderr = "error" if completed_process.returncode != 0 else "debug"
            logger_to_use.log(getattr(logging, log_level_stderr.upper()),
                              f"osm2pgsql STDERR for {region_name}:\n{completed_process.stderr}")

        if completed_process.returncode == 0:
            log_map_server(f"{config.SYMBOLS['success']} osm2pgsql import for {region_name} completed successfully.",
                           "success", logger_to_use)
            return True
        else:
            log_map_server(
                f"{config.SYMBOLS['critical']} osm2pgsql import for {region_name} FAILED (RC: {completed_process.returncode}).",
                "critical", logger_to_use)
            return False
    except FileNotFoundError:
        log_map_server(f"{config.SYMBOLS['critical']} osm2pgsql command not found. Is it installed and in PATH?",
                       "critical", logger_to_use)
        return False
    except Exception as e:
        log_map_server(f"{config.SYMBOLS['critical']} Unexpected error during osm2pgsql for {region_name}: {e}",
                       "critical", logger_to_use)
        return False