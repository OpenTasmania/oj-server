# setup/state_manager.py
"""
Manages the state file for tracking installation progress.
"""
import datetime
import logging
import os
import re
import subprocess
import tempfile
from typing import List
from typing import Optional

from setup.command_utils import run_elevated_command, log_map_server
from setup.config import STATE_FILE_PATH, SCRIPT_VERSION, SYMBOLS, OSM_PROJECT_ROOT
from setup.helpers import calculate_project_hash

# Each module can have its own logger, which will inherit formatting if main configures root or a parent.
# Or, we can pass the main logger instance around.
# For simplicity here, functions will accept a logger instance.
# If not passed, they could use a default module-level logger.
module_logger = logging.getLogger(__name__)

CURRENT_SCRIPT_HASH = None


def get_current_script_hash(logger_instance=None) -> Optional[str]:
    """Gets the current script hash, calculating it if not already done."""
    global CURRENT_SCRIPT_HASH
    if CURRENT_SCRIPT_HASH is None:
        CURRENT_SCRIPT_HASH = calculate_project_hash(OSM_PROJECT_ROOT, current_logger=logger_instance)
    return CURRENT_SCRIPT_HASH


def initialize_state_system(current_logger=None) -> None:
    """
    Initialize the state system. Ensures state directory and file exist.
    Checks script hash and clears state if mismatched.
    """
    logger_to_use = current_logger if current_logger else module_logger
    state_dir = STATE_FILE_PATH.parent  # Use Path object's parent

    # Get current script hash
    current_hash = get_current_script_hash(logger_instance=logger_to_use)
    if not current_hash:
        log_map_server(
            f"{SYMBOLS['critical']} Could not calculate current SCRIPT_HASH. State management cannot proceed reliably.",
            "critical",
            logger_to_use
        )
        # Decide behavior: raise error, or proceed with caution (state might be invalid)
        # For now, let's try to proceed but state might be cleared if file exists without hash
        # or has an old hash.
        # A more robust approach might be to prevent the script from running if hash fails.

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

    state_file_exists_and_is_file = False
    try:
        result = run_elevated_command(
            ["test", "-f", str(STATE_FILE_PATH)],
            check=False,
            capture_output=True,
            current_logger=logger_to_use
        )
        if result.returncode == 0:
            state_file_exists_and_is_file = True
        elif result.returncode == 1:
            state_file_exists_and_is_file = False
        else:
            log_map_server(
                f"{SYMBOLS['warning']} Elevated 'test -f' command for {STATE_FILE_PATH} returned unexpected code: {result.returncode}. Stderr: {result.stderr}",
                "warning",
                logger_to_use
            )
            state_file_exists_and_is_file = False

    except Exception as e:
        log_map_server(
            f"{SYMBOLS['error']} Exception while checking state file existence with elevated privileges: {e}",
            "error",
            logger_to_use
        )
        state_file_exists_and_is_file = False

    if not state_file_exists_and_is_file:
        log_map_server(
            f"{SYMBOLS['info']} State file {STATE_FILE_PATH} does not exist or is not a regular file. Initializing.",
            "info",
            logger_to_use,
        )
        with tempfile.NamedTemporaryFile(
                mode="w", delete=False, prefix="mapstate_init_", suffix=".txt"
        ) as temp_f:
            temp_f.write(state_file_header)
            temp_f.write(f"# Human-readable Script Version: {SCRIPT_VERSION}\n")
            temp_file_path = temp_f.name
        try:
            run_elevated_command(
                ["cp", temp_file_path, str(STATE_FILE_PATH)],
                current_logger=logger_to_use,
            )
            run_elevated_command(
                ["chmod", "640", str(STATE_FILE_PATH)],
                current_logger=logger_to_use,
            )
        finally:
            if os.path.exists(temp_file_path):  # Check existence before unlinking
                os.unlink(temp_file_path)
    else:  # State file exists, check hash
        try:
            result = run_elevated_command(
                ["grep", "^# SCRIPT_HASH:", str(STATE_FILE_PATH)],
                capture_output=True,
                check=False,  # Don't fail if grep doesn't find it
                current_logger=logger_to_use,
            )
            stored_hash = None
            if result.returncode == 0 and result.stdout:
                stored_hash_match = re.search(
                    r"^\# SCRIPT_HASH:\s*(\S+)",
                    result.stdout,
                    re.MULTILINE,
                )
                if stored_hash_match:
                    stored_hash = stored_hash_match.group(1)

            if not current_hash or (stored_hash != current_hash):
                log_message_reason = "Could not calculate current hash" if not current_hash else \
                    f"SCRIPT_HASH mismatch. Stored: {stored_hash}, Current: {current_hash}"
                log_map_server(
                    f"{SYMBOLS['warning']} {log_message_reason}",
                    "warning",
                    logger_to_use,
                )
                log_map_server(
                    f"{SYMBOLS['info']} Clearing state file due to hash issue or mismatch.",
                    "info",
                    logger_to_use,
                )
                # Pass current_hash (or a placeholder if None) to clear_state_file
                clear_state_file(
                    script_hash_to_write=current_hash, current_logger=logger_to_use
                )
            # If current_hash is valid and matches stored_hash, do nothing.
        except Exception as e:
            log_map_server(
                f"{SYMBOLS['error']} Error checking SCRIPT_HASH in state file ({STATE_FILE_PATH}): {e}. Re-initializing.",
                "error",
                logger_to_use,
            )
            clear_state_file(
                script_hash_to_write=current_hash, current_logger=logger_to_use
            )


def clear_state_file(script_hash_to_write: Optional[str] = None, current_logger=None) -> None:
    """Clear the state file, writing only the SCRIPT_HASH and optionally SCRIPT_VERSION."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{SYMBOLS['info']} Clearing state file: {STATE_FILE_PATH}",
        "info",
        logger_to_use,
    )

    effective_hash = script_hash_to_write
    if effective_hash is None:  # If not passed, try to calculate it
        effective_hash = get_current_script_hash(logger_instance=logger_to_use) or "UNKNOWN_HASH_AT_CLEAR"

    content_to_write = f"# SCRIPT_HASH: {effective_hash}\n"
    # Optionally, keep the human-readable version for reference
    content_to_write += f"# Human-readable Script Version: {SCRIPT_VERSION}\n"
    content_to_write += (
        f"# State cleared/re-initialized on {datetime.datetime.now().isoformat()}\n"
    )

    temp_file_path = ""
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", delete=False, prefix="mapstate_clear_", suffix=".txt"
        ) as temp_f:
            temp_f.write(content_to_write)
            temp_file_path = temp_f.name

        run_elevated_command(
            ["cp", temp_file_path, str(STATE_FILE_PATH)],
            current_logger=logger_to_use,
        )
        log_map_server(
            f"{SYMBOLS['success']} State file re-initialized with SCRIPT_HASH: {effective_hash}.",
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


def mark_step_completed(step_tag: str, current_logger=None) -> None:
    """Mark a step as completed in the state file."""
    logger_to_use = current_logger if current_logger else module_logger
    try:
        # grep -Fxq means fixed string, exact match, quiet.
        result = run_elevated_command(
            ["grep", "-Fxq", step_tag, STATE_FILE_PATH],
            check=False,
            capture_output=True,
            current_logger=logger_to_use,
        )
        if result.returncode != 0:  # Step tag not found, so add it
            log_map_server(
                f"{SYMBOLS['info']} Marking step '{step_tag}' as completed.",
                "info",
                logger_to_use,
            )
            run_elevated_command(
                ["tee", "-a", STATE_FILE_PATH],
                cmd_input=f"{step_tag}\n",
                capture_output=False,
                current_logger=logger_to_use,
            )
        else:
            log_map_server(
                f"{SYMBOLS['info']} Step '{step_tag}' was already marked as completed.",
                "info",
                logger_to_use,
            )
    except Exception as e:
        log_map_server(
            f"{SYMBOLS['error']} Error marking step '{step_tag}': {e}",
            "error",
            logger_to_use,
        )


def is_step_completed(step_tag: str, current_logger=None) -> bool:
    """Check if a step is marked as completed in the state file."""
    logger_to_use = current_logger if current_logger else module_logger
    try:
        result = run_elevated_command(
            ["grep", "-Fxq", step_tag, STATE_FILE_PATH],
            check=False,
            capture_output=True,
            current_logger=logger_to_use,
        )
        return result.returncode == 0
    except Exception as e:
        log_map_server(
            f"{SYMBOLS['error']} Error checking if step '{step_tag}' is completed: {e}",
            "error",
            logger_to_use,
        )
        return False  # Assume not completed on error


def view_completed_steps(current_logger=None) -> List[str]:
    """View the steps marked as completed in the state file."""
    logger_to_use = current_logger if current_logger else module_logger
    try:
        # Grep for lines NOT starting with #
        result = run_elevated_command(
            ["grep", "-v", "^#", STATE_FILE_PATH],
            capture_output=True,
            check=False,
            current_logger=logger_to_use,
        )

        if result.returncode == 0 and result.stdout and result.stdout.strip():
            # Grep succeeded and found lines
            return [
                line
                for line in result.stdout.strip().split("\n")
                if line.strip()
            ]
        elif result.returncode == 1:
            # Grep succeeded but found no matching lines (e.g., only comment lines or empty file)
            return []
        else:
            # Grep itself failed for some other reason (e.g., file not readable even with sudo, though unlikely)
            log_map_server(
                f"{SYMBOLS['warning']} `grep` command failed unexpectedly while reading state file. Exit code: {result.returncode}",
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
    except (
            subprocess.CalledProcessError
    ) as e:  # Should be caught by run_elevated_command, but defensive
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
