# setup/state_manager.py
# -*- coding: utf-8 -*-
"""
Manages the state file for tracking installation progress.
"""

import datetime
import logging
import os
import re
import tempfile
from typing import List, Optional

# common.command_utils.log_map_server now takes app_settings
from common.command_utils import log_map_server, run_elevated_command

# get_current_script_hash is now imported from common.system_utils
from common.system_utils import (
    get_current_script_hash as common_get_current_script_hash,
)

# Import static_config for STATE_FILE_PATH, SCRIPT_VERSION, OSM_PROJECT_ROOT
from setup import config as static_config
from setup.config_models import AppSettings  # For type hinting

module_logger = logging.getLogger(__name__)


# Removed global CURRENT_SCRIPT_HASH cache from here, it's in common.system_utils.py
# Removed local calculate_project_hash and get_current_script_hash functions from here.


def initialize_state_system(
    app_settings: AppSettings,  # Added app_settings
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Initialize the state management system.
    Ensures state directory and file exist. Checks script hash.
    """
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    state_dir = (
        static_config.STATE_FILE_PATH.parent
    )  # STATE_FILE_PATH from static_config

    # Get current script hash using the common utility
    current_hash = common_get_current_script_hash(
        project_root_dir=static_config.OSM_PROJECT_ROOT,  # Pass static project root
        app_settings=app_settings,  # Pass app_settings for logging within
        logger_instance=logger_to_use,
    )
    if not current_hash:
        log_map_server(
            f"{symbols.get('critical', '🔥')} Could not calculate current SCRIPT_HASH. "
            "State management cannot proceed reliably.",
            "critical",
            logger_to_use,
            app_settings,
        )
        # Script might proceed with caution or exit depending on overall error handling strategy

    if not state_dir.is_dir():
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} Creating state directory: {state_dir}",
            "info",
            logger_to_use,
            app_settings,
        )
        run_elevated_command(
            ["mkdir", "-p", str(state_dir)],
            app_settings,
            current_logger=logger_to_use,
        )
        run_elevated_command(
            ["chmod", "750", str(state_dir)],
            app_settings,
            current_logger=logger_to_use,
        )

    state_file_header = f"# SCRIPT_HASH: {current_hash or 'UNKNOWN_HASH_INIT'}\n"  # Use calculated hash
    human_readable_version_line = f"# Human-readable Script Version: {static_config.SCRIPT_VERSION}\n"  # SCRIPT_VERSION from static_config

    state_file_exists_and_is_file = False
    try:
        result = run_elevated_command(
            ["test", "-f", str(static_config.STATE_FILE_PATH)],
            app_settings,
            check=False,
            capture_output=True,
            current_logger=logger_to_use,
        )
        state_file_exists_and_is_file = result.returncode == 0
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Exception while checking state file existence: {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )

    if not state_file_exists_and_is_file:
        log_map_server(
            f"{symbols.get('info', 'ℹ️')} State file {static_config.STATE_FILE_PATH} does not exist. Initializing.",
            "info",
            logger_to_use,
            app_settings,
        )
        temp_file_path = ""
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                delete=False,
                prefix="mapstate_init_",
                suffix=".txt",
                encoding="utf-8",
            ) as temp_f:
                temp_f.write(state_file_header)
                temp_f.write(human_readable_version_line)
                temp_file_path = temp_f.name
            run_elevated_command(
                ["cp", temp_file_path, str(static_config.STATE_FILE_PATH)],
                app_settings,
                current_logger=logger_to_use,
            )
            run_elevated_command(
                ["chmod", "640", str(static_config.STATE_FILE_PATH)],
                app_settings,
                current_logger=logger_to_use,
            )
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    else:
        try:
            result = run_elevated_command(
                [
                    "grep",
                    "^# SCRIPT_HASH:",
                    str(static_config.STATE_FILE_PATH),
                ],
                app_settings,
                capture_output=True,
                check=False,
                current_logger=logger_to_use,
            )
            stored_hash = None
            if result.returncode == 0 and result.stdout:
                stored_hash_match = re.search(
                    r"^# SCRIPT_HASH:\s*(\S+)", result.stdout, re.MULTILINE
                )
                if stored_hash_match:
                    stored_hash = stored_hash_match.group(1)

            if not current_hash or (stored_hash != current_hash):
                reason = (
                    "Could not calculate current hash"
                    if not current_hash
                    else f"SCRIPT_HASH mismatch. Stored: {stored_hash}, Current: {current_hash}"
                )
                log_map_server(
                    f"{symbols.get('warning', '!')} {reason}",
                    "warning",
                    logger_to_use,
                    app_settings,
                )
                log_map_server(
                    f"{symbols.get('info', 'ℹ️')} Clearing state file due to hash issue or mismatch.",
                    "info",
                    logger_to_use,
                    app_settings,
                )
                clear_state_file(
                    app_settings,
                    script_hash_to_write=current_hash,
                    current_logger=logger_to_use,
                )
        except Exception as e:
            log_map_server(
                f"{symbols.get('error', '❌')} Error checking SCRIPT_HASH in {static_config.STATE_FILE_PATH}: {e}. Re-initializing.",
                "error",
                logger_to_use,
                app_settings,
                exc_info=True,
            )
            clear_state_file(
                app_settings,
                script_hash_to_write=current_hash,
                current_logger=logger_to_use,
            )


def clear_state_file(
    app_settings: AppSettings,  # Added app_settings
    script_hash_to_write: Optional[str] = None,
    current_logger: Optional[logging.Logger] = None,
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    log_map_server(
        f"{symbols.get('info', 'ℹ️')} Clearing state file: {static_config.STATE_FILE_PATH}",
        "info",
        logger_to_use,
        app_settings,
    )

    effective_hash = script_hash_to_write
    if effective_hash is None:
        effective_hash = (
            common_get_current_script_hash(
                project_root_dir=static_config.OSM_PROJECT_ROOT,
                app_settings=app_settings,
                logger_instance=logger_to_use,
            )
            or "UNKNOWN_HASH_AT_CLEAR"
        )

    content_to_write = f"# SCRIPT_HASH: {effective_hash}\n"
    content_to_write += (
        f"# Human-readable Script Version: {static_config.SCRIPT_VERSION}\n"
    )
    content_to_write += f"# State cleared/re-initialized on {datetime.datetime.now().isoformat()}\n"

    temp_file_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            prefix="mapstate_clear_",
            suffix=".txt",
            encoding="utf-8",
        ) as temp_f:
            temp_f.write(content_to_write)
            temp_file_path = temp_f.name
        run_elevated_command(
            ["cp", temp_file_path, str(static_config.STATE_FILE_PATH)],
            app_settings,
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{symbols.get('success', '✅')} State file re-initialized with SCRIPT_HASH: {effective_hash}.",
            "success",
            logger_to_use,
            app_settings,
        )
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Failed to clear/re-initialize state file: {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


def mark_step_completed(
    step_tag: str,
    app_settings: AppSettings,  # Added app_settings
    current_logger: Optional[logging.Logger] = None,
) -> None:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    try:
        result = run_elevated_command(
            ["grep", "-Fxq", step_tag, str(static_config.STATE_FILE_PATH)],
            app_settings,
            check=False,
            capture_output=True,
            current_logger=logger_to_use,
        )
        if result.returncode != 0:
            log_map_server(
                f"{symbols.get('info', 'ℹ️')} Marking step '{step_tag}' as completed.",
                "info",
                logger_to_use,
                app_settings,
            )
            run_elevated_command(
                ["tee", "-a", str(static_config.STATE_FILE_PATH)],
                app_settings,
                cmd_input=f"{step_tag}\n",
                capture_output=False,
                current_logger=logger_to_use,
            )
        else:
            log_map_server(
                f"{symbols.get('info', 'ℹ️')} Step '{step_tag}' was already marked as completed.",
                "info",
                logger_to_use,
                app_settings,
            )
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Error marking step '{step_tag}': {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )


def is_step_completed(
    step_tag: str,
    app_settings: AppSettings,  # Added app_settings
    current_logger: Optional[logging.Logger] = None,
) -> bool:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    try:
        result = run_elevated_command(
            ["grep", "-Fxq", step_tag, str(static_config.STATE_FILE_PATH)],
            app_settings,
            check=False,
            capture_output=True,
            current_logger=logger_to_use,
        )
        return result.returncode == 0
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Error checking if step '{step_tag}' is completed: {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        return False


def view_completed_steps(
    app_settings: AppSettings,  # Added app_settings
    current_logger: Optional[logging.Logger] = None,
) -> List[str]:
    logger_to_use = current_logger if current_logger else module_logger
    symbols = app_settings.symbols
    try:
        result = run_elevated_command(
            ["grep", "-v", "^#", str(static_config.STATE_FILE_PATH)],
            app_settings,
            capture_output=True,
            check=False,
            current_logger=logger_to_use,
        )
        if result.returncode == 0 and result.stdout and result.stdout.strip():
            return [
                line
                for line in result.stdout.strip().split("\n")
                if line.strip()
            ]
        elif result.returncode == 1:
            return []  # No matching lines
        else:  # Grep failed
            log_map_server(
                f"{symbols.get('warning', '!')} `grep` command failed unexpectedly. Exit code: {result.returncode}",
                "warning",
                logger_to_use,
                app_settings,
            )
            if result.stderr:
                log_map_server(
                    f"   grep stderr: {result.stderr.strip()}",
                    "warning",
                    logger_to_use,
                    app_settings,
                )
            return []
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Unexpected error viewing completed steps: {e}",
            "error",
            logger_to_use,
            app_settings,
            exc_info=True,
        )
        return []
