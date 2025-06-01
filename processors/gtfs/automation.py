# processors/gtfs/automation.py
# -*- coding: utf-8 -*-
"""
Handles configuration of automated GTFS updates, typically via cron.
"""
import logging
import os
from pathlib import Path  # For project_root_path handling
from pwd import getpwnam  # For checking user existence
from shutil import which
from tempfile import NamedTemporaryFile
from typing import Optional, Dict

from common.command_utils import log_map_server, run_elevated_command

# setup.config is no longer imported directly for configuration values.

module_logger = logging.getLogger(__name__)

# Default GTFS log file for cron's stdout/stderr, if not specified by the caller.
# This is distinct from the application log file configured in environment.py.
DEFAULT_CRON_GTFS_STDOUT_LOG_FILE = "/var/log/gtfs_cron_output.log"


def configure_gtfs_update_cronjob(
        project_root_path: Path,
        feed_url: str,
        db_params: Dict[str, str],
        cron_user_name: Optional[str] = None,
        cron_output_log_file: Optional[str] = None,
        python_executable_override: Optional[str] = None,
        current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Sets up a cron job for daily GTFS updates.

    Args:
        project_root_path: Path object for the project's root directory.
        feed_url: The URL of the GTFS feed.
        db_params: Dictionary with database connection parameters
                   (e.g., PGPASSWORD, PGUSER, PGHOST, PGPORT, PGDATABASE).
                   Keys should match expected environment variable names.
        cron_user_name: Optional system user to run the cron job as.
                        Defaults to db_params['PGUSER'] if that user exists, else root.
        cron_output_log_file: Optional path for the cron job's stdout/stderr.
        python_executable_override: Optional specific path to the Python executable.
        current_logger: Optional logger instance.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(  # log_map_server will use common config.SYMBOLS
        "Configuring cron job for daily GTFS updates...",
        "info",
        logger_to_use,
    )

    effective_cron_log = cron_output_log_file or DEFAULT_CRON_GTFS_STDOUT_LOG_FILE

    py_exec_path = python_executable_override
    if not py_exec_path:
        # Prefer venv python if available within the project structure
        venv_python = project_root_path / ".venv" / "bin" / "python"  # Common venv path
        venv_python3 = project_root_path / ".venv" / "bin" / "python3"
        if venv_python3.is_file() and os.access(venv_python3, os.X_OK):
            py_exec_path = str(venv_python3)
        elif venv_python.is_file() and os.access(venv_python, os.X_OK):  # Fallback to 'python'
            py_exec_path = str(venv_python)

        if py_exec_path:
            log_map_server(f"Using project's venv Python for cron: {py_exec_path}", "info", logger_to_use)
        else:
            # Fallback to system python
            py_exec_path = which("python3") or which("python")
            if py_exec_path:
                log_map_server(f"Using system Python for cron: {py_exec_path}", "info", logger_to_use)

    if not py_exec_path:
        log_map_server("Python executable not found. Cannot set up GTFS cron job.", "error", logger_to_use)
        raise EnvironmentError("Python executable not found for GTFS cron job.")

    # Module path for `python -m processors.gtfs.update_gtfs`
    update_script_module_path = "processors.gtfs.update_gtfs"
    # Ensure the command changes to the project root so `python -m` works correctly
    cron_job_main_command = f"cd {str(project_root_path)} && {py_exec_path} -m {update_script_module_path}"

    # Determine user for cron job
    # Use PGUSER from db_params as the intended cron user, fallback to 'root'
    intended_cron_user = cron_user_name or db_params.get("PGUSER", "root")
    actual_cron_user_for_cmd = intended_cron_user  # User for `crontab -u`

    try:
        getpwnam(intended_cron_user)
        logger_to_use.info(f"System user '{intended_cron_user}' found. Cron job will target this user.")
    except KeyError:
        logger_to_use.warning(
            f"System user '{intended_cron_user}' not found. "
            "Cron job will be installed for the 'root' user instead."
        )
        actual_cron_user_for_cmd = "root"

    # Only use '-u' if not setting root's crontab (as root doesn't use -u for its own)
    use_user_flag_for_crontab_cmd = actual_cron_user_for_cmd != "root"

    # Environment variables for the cron job
    env_vars_for_cron_list = [
        f"GTFS_FEED_URL='{feed_url}'",
        f"PG_OSM_PASSWORD='{db_params.get('PGPASSWORD', '')}'",
        f"PG_OSM_USER='{db_params.get('PGUSER', '')}'",
        f"PG_OSM_HOST='{db_params.get('PGHOST', '')}'",
        f"PG_OSM_PORT='{str(db_params.get('PGPORT', ''))}'",  # Ensure string
        f"PG_OSM_DATABASE='{db_params.get('PGDATABASE', '')}'",
        # GTFS_PROCESSOR_LOG_FILE for the application's own logging is set by processors.gtfs.environment
        # This cron job primarily redirects stdout/stderr.
    ]
    env_vars_for_cron_str = "; ".join([f"export {var}" for var in env_vars_for_cron_list])

    cron_job_schedule = "0 3 * * *"  # Daily at 3 AM
    cron_job_line_content = f"{cron_job_schedule} {env_vars_for_cron_str}; {cron_job_main_command} >> {effective_cron_log} 2>&1"
    cron_job_comment_identifier = f"# GTFS Auto Update for project: {str(project_root_path)} module: {update_script_module_path}"

    temp_cron_file_path = ""
    try:
        crontab_list_cmd = ["crontab"]
        if use_user_flag_for_crontab_cmd:
            crontab_list_cmd.extend(["-u", actual_cron_user_for_cmd])
        crontab_list_cmd.append("-l")

        existing_crontab_result = run_elevated_command(
            crontab_list_cmd, check=False, capture_output=True, current_logger=logger_to_use
        )
        existing_crontab_content = existing_crontab_result.stdout if existing_crontab_result.returncode == 0 else ""

        # Filter out previous versions of this specific job
        new_crontab_lines = [
            line for line in existing_crontab_content.splitlines()
            if not (update_script_module_path in line and str(project_root_path) in line)  # More specific check
        ]

        new_crontab_lines.append(cron_job_comment_identifier)
        new_crontab_lines.append(cron_job_line_content)

        final_crontab_content = "\n".join(new_crontab_lines)
        if not final_crontab_content.endswith("\n"):  # Ensure trailing newline for crontab
            final_crontab_content += "\n"

        with NamedTemporaryFile(mode="w", delete=False, prefix="gtfscron_") as temp_f:
            temp_f.write(final_crontab_content)
            temp_cron_file_path = temp_f.name

        install_crontab_cmd = ["crontab"]
        if use_user_flag_for_crontab_cmd:
            install_crontab_cmd.extend(["-u", actual_cron_user_for_cmd])
        install_crontab_cmd.append(temp_cron_file_path)

        run_elevated_command(install_crontab_cmd, current_logger=logger_to_use)
        log_map_server(
            (f"Cron job for GTFS update configured for user '{actual_cron_user_for_cmd}'. "
             f"Command: {cron_job_main_command}"),  # Uses common config.SYMBOLS
            "success", logger_to_use
        )
        logger_to_use.debug(f"Cron job details:\n{cron_job_comment_identifier}\n{cron_job_line_content}")

    except Exception as e_cron:
        log_map_server(
            f"Failed to set up cron job for GTFS update: {e_cron}",  # Uses common config.SYMBOLS
            "error", logger_to_use
        )
        # Not re-raising, as cron job setup failure might be non-critical for some execution paths.
    finally:
        if temp_cron_file_path and os.path.exists(temp_cron_file_path):  # pragma: no cover
            os.unlink(temp_cron_file_path)