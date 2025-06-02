# processors/gtfs/automation.py
# -*- coding: utf-8 -*-
"""
Handles configuration of automated GTFS updates, typically via cron.
"""

import logging
import os
from pathlib import Path
from pwd import getpwnam
from shutil import which
from tempfile import NamedTemporaryFile
from typing import Optional

from common.command_utils import log_map_server, run_elevated_command
from setup import config as static_config  # For OSM_PROJECT_ROOT
from setup.config_models import AppSettings  # Import AppSettings

module_logger = logging.getLogger(__name__)

DEFAULT_CRON_GTFS_STDOUT_LOG_FILE = "/var/log/gtfs_cron_output.log"


def configure_gtfs_update_cronjob(
    app_settings: AppSettings,  # Changed to accept AppSettings
    # project_root_path, feed_url, db_params will be sourced from app_settings
    # cron_user_name, cron_output_log_file, python_executable_override can also be part of AppSettings.gtfs or AppSettings.automation
    current_logger: Optional[logging.Logger] = None,
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols

    # Extract values from app_settings
    # Assuming these might be nested under app_settings.gtfs or app_settings.automation in a more complete model
    project_root_path = Path(static_config.OSM_PROJECT_ROOT)  # Static path
    feed_url = str(app_settings.gtfs_feed_url)
    db_params = {  # For cron job environment
        "PGPASSWORD": app_settings.pg.password,
        "PGUSER": app_settings.pg.user,
        "PGHOST": app_settings.pg.host,
        "PGPORT": str(app_settings.pg.port),
        "PGDATABASE": app_settings.pg.database,  # Or map to PG_GIS_DB if update_gtfs expects that
    }
    # These could be fields in AppSettings.gtfs.automation
    cron_run_user = (
        getattr(app_settings.gtfs, "cron_user", app_settings.pg.user)
        if hasattr(app_settings, "gtfs")
        else app_settings.pg.user
    )
    cron_output_log_file = (
        getattr(
            app_settings.gtfs,
            "cron_log_file",
            DEFAULT_CRON_GTFS_STDOUT_LOG_FILE,
        )
        if hasattr(app_settings, "gtfs")
        else DEFAULT_CRON_GTFS_STDOUT_LOG_FILE
    )
    python_executable_override = (
        getattr(app_settings.gtfs, "cron_python_exe", None)
        if hasattr(app_settings, "gtfs")
        else None
    )

    log_map_server(
        f"{symbols.get('gear', '⚙️')} Configuring cron job for daily GTFS updates...",
        "info",
        logger_to_use,
        app_settings,
    )
    effective_cron_log = cron_output_log_file

    py_exec_path = python_executable_override
    if not py_exec_path:
        venv_py3 = project_root_path / ".venv" / "bin" / "python3"
        venv_py = project_root_path / ".venv" / "bin" / "python"
        if venv_py3.is_file() and os.access(venv_py3, os.X_OK):
            py_exec_path = str(venv_py3)
        elif venv_py.is_file() and os.access(venv_py, os.X_OK):
            py_exec_path = str(venv_py)
        if py_exec_path:
            log_map_server(
                f"Using project venv Python for cron: {py_exec_path}",
                "info",
                logger_to_use,
                app_settings,
            )
        else:
            py_exec_path = which("python3") or which("python")
            if py_exec_path:
                log_map_server(
                    f"Using system Python for cron: {py_exec_path}",
                    "info",
                    logger_to_use,
                    app_settings,
                )
    if not py_exec_path:
        log_map_server(
            f"{symbols.get('error', '❌')} Python executable not found. Cannot set up GTFS cron job.",
            "error",
            logger_to_use,
            app_settings,
        )
        raise EnvironmentError(
            "Python executable not found for GTFS cron job."
        )

    update_script_module_path = "processors.gtfs.update_gtfs"  # Relative to project root for python -m
    cron_job_main_cmd = f"cd {str(project_root_path)} && {py_exec_path} -m {update_script_module_path}"

    intended_cron_user = cron_run_user
    actual_cron_user_cmd = intended_cron_user
    try:
        getpwnam(intended_cron_user)
        logger_to_use.info(
            f"System user '{intended_cron_user}' found. Cron job targets this user."
        )
    except KeyError:
        logger_to_use.warning(
            f"System user '{intended_cron_user}' not found. Cron job for 'root' instead."
        )
        actual_cron_user_cmd = "root"
    use_user_flag_crontab = actual_cron_user_cmd != "root"

    env_vars_list = [
        f"GTFS_FEED_URL='{feed_url}'",
        # update_gtfs.py sets these for its child main_pipeline based on its DB_PARAMS/ENV
        # So we need to ensure update_gtfs.py can get these.
        # It reads PG_OSM_USER etc. from ENV.
        f"PG_OSM_PASSWORD='{db_params.get('PGPASSWORD', '')}'",
        f"PG_OSM_USER='{db_params.get('PGUSER', '')}'",
        f"PG_GIS_DB='{db_params.get('PGDATABASE', '')}'",  # update_gtfs.py maps PGDATABASE to PG_GIS_DB
        f"PG_HOST='{db_params.get('PGHOST', '')}'",
        f"PG_PORT='{db_params.get('PGPORT', '')}'",
        # Pass log level for update_gtfs.py CLI if needed, e.g. from app_settings.gtfs.cron_log_level
        # For now, update_gtfs.py defaults to INFO for its own logging.
    ]
    env_vars_str = "; ".join([f"export {var}" for var in env_vars_list])

    cron_schedule = "0 3 * * *"  # Daily at 3 AM
    cron_job_line = f"{cron_schedule} {env_vars_str}; {cron_job_main_cmd} >> {effective_cron_log} 2>&1"
    cron_comment_id = f"# GTFS Auto Update for project: {str(project_root_path)} module: {update_script_module_path}"

    temp_cron_file = ""
    try:
        crontab_list_cmd = ["crontab"]
        if use_user_flag_crontab:
            crontab_list_cmd.extend(["-u", actual_cron_user_cmd])
        crontab_list_cmd.append("-l")

        existing_crontab_res = run_elevated_command(
            crontab_list_cmd,
            app_settings,
            check=False,
            capture_output=True,
            current_logger=logger_to_use,
        )
        existing_content = (
            existing_crontab_res.stdout
            if existing_crontab_res.returncode == 0
            else ""
        )

        new_lines = [
            line
            for line in existing_content.splitlines()
            if not (
                update_script_module_path in line
                and str(project_root_path) in line
            )
        ]
        new_lines.extend([cron_comment_id, cron_job_line])
        final_content = "\n".join(new_lines) + "\n"

        with NamedTemporaryFile(
            mode="w", delete=False, prefix="gtfscron_"
        ) as temp_f:
            temp_f.write(final_content)
            temp_cron_file = temp_f.name

        install_cmd = ["crontab"]
        if use_user_flag_crontab:
            install_cmd.extend(["-u", actual_cron_user_cmd])
        install_cmd.append(temp_cron_file)
        run_elevated_command(
            install_cmd, app_settings, current_logger=logger_to_use
        )

        log_map_server(
            f"{symbols.get('success', '✅')} Cron job for GTFS update configured for user '{actual_cron_user_cmd}'.",
            "success",
            logger_to_use,
            app_settings,
        )
        logger_to_use.debug(
            f"Cron job details:\n{cron_comment_id}\n{cron_job_line}"
        )
    except Exception as e_cron:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to set up cron job for GTFS update: {e_cron}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
    finally:
        if temp_cron_file and os.path.exists(temp_cron_file):
            os.unlink(temp_cron_file)
