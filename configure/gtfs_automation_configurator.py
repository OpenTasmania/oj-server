# configure/gtfs_automation_configurator.py
# -*- coding: utf-8 -*-
"""
Handles configuration of automated GTFS updates, typically via cron.
"""
import logging
import os
from getpass import getuser
from pwd import getpwnam  # For checking user existence
from shutil import which
from tempfile import NamedTemporaryFile
from typing import Optional

from common.command_utils import log_map_server, run_elevated_command
from setup import config

module_logger = logging.getLogger(__name__)

GTFS_LOG_FILE = "/var/log/gtfs_processor_app.log"  # Should match environment_setup


def configure_gtfs_update_cronjob(current_logger: Optional[logging.Logger] = None) -> None:
    """
    Sets up a cron job for daily GTFS updates.
    Environment variables for the cron job are sourced from the main config.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{config.SYMBOLS['step']} Configuring cron job for daily GTFS updates...",
        "info",
        logger_to_use,
    )

    python_executable = which("python3") or which("python")
    if not python_executable:
        log_map_server(f"{config.SYMBOLS['error']} Python executable not found. Cannot set up cron job.", "error",
                       logger_to_use)
        raise EnvironmentError("Python executable not found for GTFS cron job.")

    # Determine user for cron job
    # The GTFS scripts connect to DB as config.PGUSER.
    # The cron job should ideally run as a user who can execute the python script
    # and for whom the environment (like PATH to python_executable from a venv if used) is set.
    # Original script logic used config.PGUSER if system user exists, else root.
    intended_cron_user = config.PGUSER
    actual_cron_user = intended_cron_user
    use_user_flag_for_crontab = True  # For `crontab -u <user>`

    try:
        getpwnam(intended_cron_user)
        logger_to_use.info(f"System user '{intended_cron_user}' found. Cron job will be set for this user.")
    except KeyError:
        logger_to_use.warning(
            f"System user '{intended_cron_user}' (from config.PGUSER) not found. "
            "Cron job will be installed for the 'root' user instead. "
            "Ensure script paths and permissions are appropriate for root execution if this is the case."
        )
        actual_cron_user = "root"
        use_user_flag_for_crontab = False  # Root crontab doesn't use -u root

    # Path to the update script module for `python -m processors.gtfs.update_gtfs`
    update_script_module_path = "processors.gtfs.update_gtfs"

    # If running from a virtual environment, python_executable should ideally be the venv Python.
    # This script (main_installer.py) is likely run from the venv.
    # For cron, absolute path to venv python is more robust.
    # Assuming `install.py` ensures the main script runs from venv, sys.executable could be used here,
    # but `which("python3")` might find system python if venv not activated for cron's environment.
    # Best practice: provide full path to venv python for cron.
    # For now, using the `python_executable` found by `which`.

    # Get project root dynamically to build path to venv python for cron
    project_root = config.OSM_PROJECT_ROOT  # Assuming this points to ot-osm-osrm-server
    venv_python_executable = project_root / ".venv" / "bin" / "python"
    if not venv_python_executable.is_file():
        log_map_server(
            f"{config.SYMBOLS['warning']} Virtualenv python at {venv_python_executable} not found. Cron might use system python.",
            "warning", logger_to_use)
        # Fallback to system python found by `which`
        cron_python_exe = python_executable
    else:
        cron_python_exe = str(venv_python_executable)

    update_script_command = f"{cron_python_exe} -m {update_script_module_path}"

    # Environment variables needed by the cron job
    # These should match those set in setup_gtfs_logging_and_env_vars if the script relies on them
    env_vars_for_cron_list = [
        f"GTFS_FEED_URL='{config.GTFS_FEED_URL}'",
        f"PG_OSM_PASSWORD='{config.PGPASSWORD}'",  # Ensure PGPASSWORD is secure
        f"PG_OSM_USER='{config.PGUSER}'",
        f"PG_OSM_HOST='{config.PGHOST}'",
        f"PG_OSM_PORT='{config.PGPORT}'",
        f"PG_OSM_DATABASE='{config.PGDATABASE}'",
        f"GTFS_PROCESSOR_LOG_FILE='{GTFS_LOG_FILE}'"  # Ensure consistency
    ]
    # Add PATH if using venv python, to ensure dependent modules are found if cron has minimal PATH
    # Example: f"PATH='{venv_python_executable.parent}:{os.environ.get('PATH', '')}'"
    # Simpler: rely on `python -m` with venv python to handle paths.

    env_vars_for_cron_str = " ".join(env_vars_for_cron_list)

    cron_job_line = f"0 3 * * * export {env_vars_for_cron_str}; {update_script_command} >> {GTFS_LOG_FILE} 2>&1"

    temp_cron_path = ""
    try:
        crontab_l_cmd = ["crontab"]
        if use_user_flag_for_crontab:
            crontab_l_cmd.extend(["-u", actual_cron_user])
        crontab_l_cmd.append("-l")

        existing_crontab_result = run_elevated_command(
            crontab_l_cmd, check=False, capture_output=True, current_logger=logger_to_use
        )
        existing_crontab_content = existing_crontab_result.stdout if existing_crontab_result.returncode == 0 else ""

        new_crontab_lines = [
            line for line in existing_crontab_content.splitlines()
            if update_script_module_path not in line  # Avoid duplicate entries
        ]
        new_crontab_content = "\n".join(new_crontab_lines)
        if new_crontab_content and not new_crontab_content.endswith("\n"):
            new_crontab_content += "\n"
        new_crontab_content += cron_job_line + "\n"

        with NamedTemporaryFile(mode="w", delete=False, prefix="gtfscron_") as temp_f:
            temp_f.write(new_crontab_content)
            temp_cron_path = temp_f.name

        install_cron_cmd = ["crontab"]
        if use_user_flag_for_crontab:
            install_cron_cmd.extend(["-u", actual_cron_user])
        install_cron_cmd.append(temp_cron_path)

        run_elevated_command(install_cron_cmd, current_logger=logger_to_use)
        log_map_server(
            f"{config.SYMBOLS['success']} Cron job for GTFS update configured for user '{actual_cron_user}'. "
            f"Command: {update_script_command}",
            "success", logger_to_use
        )
    except Exception as e_cron:
        log_map_server(f"{config.SYMBOLS['error']} Failed to set up cron job for GTFS update: {e_cron}", "error",
                       logger_to_use)
        # Don't raise, cron job failure might be non-critical for some setups
    finally:
        if temp_cron_path and os.path.exists(temp_cron_path):
            os.unlink(temp_cron_path)