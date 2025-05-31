# setup/state_manager.py
# -*- coding: utf-8 -*-
"""
Manages the state file for tracking installation progress.

This module provides functions to initialize the state system, clear the state
file, mark individual setup steps as completed, check if a step has been
completed, and view all completed steps. It also handles script versioning
by storing and checking a hash of the script files.
"""

import datetime
import logging
import os
import re
import subprocess
import tempfile
from typing import List, Optional

from common.command_utils import log_map_server, run_elevated_command
from common.system_utils import calculate_project_hash
from setup.config import (
    OSM_PROJECT_ROOT,
    SCRIPT_VERSION,
    STATE_FILE_PATH,
    SYMBOLS,
)

module_logger = logging.getLogger(__name__)

# Global variable to cache the calculated script hash.
CURRENT_SCRIPT_HASH: Optional[str] = None


def get_current_script_hash(
    logger_instance: Optional[logging.Logger] = None,
) -> Optional[str]:
    """
    Get the current script hash, calculating it if not already cached.

    The hash is calculated based on the content of Python files in the
    project, as defined by `OSM_PROJECT_ROOT` in the config.

    Args:
        logger_instance: Optional logger to use for messages.

    Returns:
        The calculated SHA256 hash of the script files, or None if calculation
        fails.
    """
    global CURRENT_SCRIPT_HASH
    if CURRENT_SCRIPT_HASH is None:
        CURRENT_SCRIPT_HASH = calculate_project_hash(
            OSM_PROJECT_ROOT, current_logger=logger_instance
        )
    return CURRENT_SCRIPT_HASH


def initialize_state_system(
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Initialize the state management system.

    Ensures the state directory and file exist. Checks the script hash stored
    in the state file against the current script hash and clears the state
    file if they mismatch or if the stored hash is missing.

    Args:
        current_logger: Optional logger instance to use.
    """
    logger_to_use = current_logger if current_logger else module_logger
    state_dir = STATE_FILE_PATH.parent

    current_hash = get_current_script_hash(logger_instance=logger_to_use)
    if not current_hash:
        log_map_server(
            f"{SYMBOLS['critical']} Could not calculate current SCRIPT_HASH. "
            "State management cannot proceed reliably.",
            "critical",
            logger_to_use,
        )
        # Proceeding with caution; state might be cleared if file exists
        # without hash or has an old hash. A more robust approach might
        # prevent script execution if hashing fails.

    if not state_dir.is_dir():
        log_map_server(
            f"{SYMBOLS['info']} Creating state directory: {state_dir}",
            "info",
            logger_to_use,
        )
        run_elevated_command(
            ["mkdir", "-p", str(state_dir)], current_logger=logger_to_use
        )
        run_elevated_command(
            ["chmod", "750", str(state_dir)], current_logger=logger_to_use
        )

    state_file_header = f"# SCRIPT_HASH: {current_hash or 'UNKNOWN_HASH'}\n"
    human_readable_version_line = (
        f"# Human-readable Script Version: {SCRIPT_VERSION}\n"
    )

    state_file_exists_and_is_file = False
    try:
        # Check if the state file exists and is a regular file.
        result = run_elevated_command(
            ["test", "-f", str(STATE_FILE_PATH)],
            check=False,  # Do not raise an error if test fails.
            capture_output=True,
            current_logger=logger_to_use,
        )
        if result.returncode == 0:
            state_file_exists_and_is_file = True
        elif result.returncode == 1:
            state_file_exists_and_is_file = False
        else:
            log_map_server(
                f"{SYMBOLS['warning']} Elevated 'test -f' command for "
                f"{STATE_FILE_PATH} returned unexpected code: "
                f"{result.returncode}. Stderr: {result.stderr}",
                "warning",
                logger_to_use,
            )
            state_file_exists_and_is_file = False
    except Exception as e:
        log_map_server(
            f"{SYMBOLS['error']} Exception while checking state file "
            f"existence with elevated privileges: {e}",
            "error",
            logger_to_use,
        )
        state_file_exists_and_is_file = False

    if not state_file_exists_and_is_file:
        log_map_server(
            f"{SYMBOLS['info']} State file {STATE_FILE_PATH} does not exist "
            "or is not a regular file. Initializing.",
            "info",
            logger_to_use,
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
                ["cp", temp_file_path, str(STATE_FILE_PATH)],
                current_logger=logger_to_use,
            )
            run_elevated_command(
                ["chmod", "640", str(STATE_FILE_PATH)],
                current_logger=logger_to_use,
            )
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    else:  # State file exists, check its hash.
        try:
            result = run_elevated_command(
                ["grep", "^# SCRIPT_HASH:", str(STATE_FILE_PATH)],
                capture_output=True,
                check=False,  # Don't fail if grep doesn't find it.
                current_logger=logger_to_use,
            )
            stored_hash = None
            if result.returncode == 0 and result.stdout:
                stored_hash_match = re.search(
                    r"^# SCRIPT_HASH:\s*(\S+)",
                    result.stdout,
                    re.MULTILINE,
                )
                if stored_hash_match:
                    stored_hash = stored_hash_match.group(1)

            if not current_hash or (stored_hash != current_hash):
                reason = (
                    "Could not calculate current hash"
                    if not current_hash
                    else "SCRIPT_HASH mismatch. "
                    f"Stored: {stored_hash}, Current: {current_hash}"
                )
                log_map_server(
                    f"{SYMBOLS['warning']} {reason}", "warning", logger_to_use
                )
                log_map_server(
                    f"{SYMBOLS['info']} Clearing state file due to hash "
                    "issue or mismatch.",
                    "info",
                    logger_to_use,
                )
                clear_state_file(
                    script_hash_to_write=current_hash,
                    current_logger=logger_to_use,
                )
            # If current_hash is valid and matches stored_hash, do nothing.
        except Exception as e:
            log_map_server(
                f"{SYMBOLS['error']} Error checking SCRIPT_HASH in state file "
                f"({STATE_FILE_PATH}): {e}. Re-initializing.",
                "error",
                logger_to_use,
            )
            clear_state_file(
                script_hash_to_write=current_hash,
                current_logger=logger_to_use,
            )


def clear_state_file(
    script_hash_to_write: Optional[str] = None,
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Clear the state file, writing only the SCRIPT_HASH and version.

    Args:
        script_hash_to_write: The script hash to write to the new state file.
                              If None, the current script hash will be
                              calculated and used.
        current_logger: Optional logger instance.
    """
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{SYMBOLS['info']} Clearing state file: {STATE_FILE_PATH}",
        "info",
        logger_to_use,
    )

    effective_hash = script_hash_to_write
    if effective_hash is None:  # If not passed, try to calculate it.
        effective_hash = (
            get_current_script_hash(logger_instance=logger_to_use)
            or "UNKNOWN_HASH_AT_CLEAR"
        )

    content_to_write = f"# SCRIPT_HASH: {effective_hash}\n"
    # Optionally, keep the human-readable version for reference.
    content_to_write += f"# Human-readable Script Version: {SCRIPT_VERSION}\n"
    content_to_write += (
        f"# State cleared/re-initialized on "
        f"{datetime.datetime.now().isoformat()}\n"
    )

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
            ["cp", temp_file_path, str(STATE_FILE_PATH)],
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{SYMBOLS['success']} State file re-initialized with SCRIPT_HASH: "
            f"{effective_hash}.",
            "success",
            logger_to_use,
        )
    except Exception as e:
        log_map_server(
            f"{SYMBOLS['error']} Failed to clear/re-initialize state file: {e}",
            "error",
            logger_to_use,
        )
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


def mark_step_completed(
    step_tag: str, current_logger: Optional[logging.Logger] = None
) -> None:
    """
    Mark a step as completed in the state file by appending its tag.

    If the step tag already exists, no action is taken.

    Args:
        step_tag: A unique string identifier for the setup step.
        current_logger: Optional logger instance.
    """
    logger_to_use = current_logger if current_logger else module_logger
    try:
        # Check if the step tag already exists in the file.
        # `grep -Fxq` means:
        #   -F: Treat pattern as a fixed string.
        #   -x: Match whole lines only.
        #   -q: Quiet mode (no output), exit status indicates match.
        result = run_elevated_command(
            ["grep", "-Fxq", step_tag, str(STATE_FILE_PATH)],
            check=False,  # Do not raise error if grep doesn't find the tag.
            capture_output=True,  # Though quiet, capture for completeness.
            current_logger=logger_to_use,
        )
        if result.returncode != 0:  # Step tag not found, so add it.
            log_map_server(
                f"{SYMBOLS['info']} Marking step '{step_tag}' as completed.",
                "info",
                logger_to_use,
            )
            # Append the step tag to the state file.
            run_elevated_command(
                ["tee", "-a", str(STATE_FILE_PATH)],
                cmd_input=f"{step_tag}\n",
                capture_output=False,  # No need to capture output for tee -a.
                current_logger=logger_to_use,
            )
        else:
            log_map_server(
                f"{SYMBOLS['info']} Step '{step_tag}' was already marked as "
                "completed.",
                "info",
                logger_to_use,
            )
    except Exception as e:
        log_map_server(
            f"{SYMBOLS['error']} Error marking step '{step_tag}': {e}",
            "error",
            logger_to_use,
        )


def is_step_completed(
    step_tag: str, current_logger: Optional[logging.Logger] = None
) -> bool:
    """
    Check if a step is marked as completed in the state file.

    Args:
        step_tag: The unique string identifier for the setup step.
        current_logger: Optional logger instance.

    Returns:
        True if the step tag is found in the state file, False otherwise or
        if an error occurs.
    """
    logger_to_use = current_logger if current_logger else module_logger
    try:
        result = run_elevated_command(
            ["grep", "-Fxq", step_tag, str(STATE_FILE_PATH)],
            check=False,
            capture_output=True,
            current_logger=logger_to_use,
        )
        return result.returncode == 0  # 0 means found, 1 means not found.
    except Exception as e:
        log_map_server(
            f"{SYMBOLS['error']} Error checking if step '{step_tag}' is "
            f"completed: {e}",
            "error",
            logger_to_use,
        )
        return False  # Assume not completed on error.


def view_completed_steps(
    current_logger: Optional[logging.Logger] = None,
) -> List[str]:
    """
    Retrieve a list of all step tags marked as completed in the state file.

    Excludes comment lines (lines starting with '#').

    Args:
        current_logger: Optional logger instance.

    Returns:
        A list of strings, where each string is a completed step tag.
        Returns an empty list if no steps are completed or if an error occurs.
    """
    logger_to_use = current_logger if current_logger else module_logger
    try:
        # Grep for lines NOT starting with '#'.
        result = run_elevated_command(
            ["grep", "-v", "^#", str(STATE_FILE_PATH)],
            capture_output=True,
            check=False,  # Don't fail if no non-comment lines are found.
            current_logger=logger_to_use,
        )

        if result.returncode == 0 and result.stdout and result.stdout.strip():
            # Grep succeeded and found lines.
            return [
                line
                for line in result.stdout.strip().split("\n")
                if line.strip()  # Ensure no empty strings from multiple newlines.
            ]
        elif result.returncode == 1:
            # Grep succeeded but found no matching lines (e.g., only comments).
            return []
        else:
            # Grep itself failed for some other reason.
            log_map_server(
                f"{SYMBOLS['warning']} `grep` command failed unexpectedly "
                f"while reading state file. Exit code: {result.returncode}",
                "warning",
                logger_to_use,
            )
            if result.stderr:
                log_map_server(
                    f"   grep stderr: {result.stderr.strip()}",
                    "warning",
                    logger_to_use,
                )
            return []
    except subprocess.CalledProcessError as e:
        # This should ideally be caught by run_elevated_command if check=True,
        # but defensive coding.
        log_map_server(
            f"{SYMBOLS['error']} CalledProcessError viewing completed steps: {e}",
            "error",
            logger_to_use,
        )
        return []
    except Exception as e:
        log_map_server(
            f"{SYMBOLS['error']} Unexpected error viewing completed steps: {e}",
            "error",
            logger_to_use,
        )
        return []
