# setup/state_manager.py
"""
Manages the state file for tracking installation progress.
"""
import datetime
import logging
import os
import re
import subprocess  # Needed for CalledProcessError in this module's context
import tempfile

from .command_utils import run_elevated_command, log_map_server
from .config import STATE_FILE_PATH, SCRIPT_VERSION, SYMBOLS
from typing import List

# Each module can have its own logger, which will inherit formatting if main configures root or a parent.
# Or, we can pass the main logger instance around.
# For simplicity here, functions will accept a logger instance.
# If not passed, they could use a default module-level logger.
module_logger = logging.getLogger(__name__)


def initialize_state_system(current_logger=None) -> None:
    """
    Initialize the state system. Ensures state directory and file exist.
    Checks script version and clears state if mismatched.
    """
    logger_to_use = current_logger if current_logger else module_logger
    state_dir = os.path.dirname(STATE_FILE_PATH)

    if not os.path.isdir(state_dir):
        log_map_server(
            f"{SYMBOLS['info']} Creating state directory: {state_dir}",
            "info",
            logger_to_use,
        )
        run_elevated_command(
            ["mkdir", "-p", state_dir], current_logger=logger_to_use
        )
        run_elevated_command(
            ["chmod", "750", state_dir], current_logger=logger_to_use
        )  # Group access

    if not os.path.isfile(STATE_FILE_PATH):
        log_map_server(
            f"{SYMBOLS['info']} Initializing state file: {STATE_FILE_PATH}",
            "info",
            logger_to_use,
        )
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, prefix="mapstate_init_", suffix=".txt"
        ) as temp_f:
            temp_f.write(f"# Script Version: {SCRIPT_VERSION}\n")
            temp_file_path = temp_f.name
        try:
            run_elevated_command(
                ["cp", temp_file_path, STATE_FILE_PATH],
                current_logger=logger_to_use,
            )
            run_elevated_command(
                ["chmod", "640", STATE_FILE_PATH],
                current_logger=logger_to_use,
            )  # Group read
        finally:
            os.unlink(temp_file_path)
    else:
        try:
            # Grep needs capture_output=True to read its stdout
            result = run_elevated_command(
                ["grep", "^# Script Version:", STATE_FILE_PATH],
                capture_output=True,
                check=False,
                current_logger=logger_to_use,
            )
            if result.returncode == 0 and result.stdout:
                # Extract version more carefully
                stored_version_match = re.search(
                    r"^\# Script Version:\s*(\S+)",
                    result.stdout,
                    re.MULTILINE,
                )
                if stored_version_match:
                    stored_version = stored_version_match.group(1)
                    if stored_version != SCRIPT_VERSION:
                        log_map_server(
                            f"{SYMBOLS['warning']} Script version mismatch in state file. Stored: {stored_version}, Current: {SCRIPT_VERSION}",
                            "warning",
                            logger_to_use,
                        )
                        log_map_server(
                            f"{SYMBOLS['info']} Clearing state file due to version mismatch.",
                            "info",
                            logger_to_use,
                        )
                        clear_state_file(
                            write_version_only=True,
                            current_logger=logger_to_use,
                        )
                else:
                    log_map_server(
                        f"{SYMBOLS['warning']} State file version line not found or malformed. Re-initializing.",
                        "warning",
                        logger_to_use,
                    )
                    clear_state_file(
                        write_version_only=True, current_logger=logger_to_use
                    )
            elif (
                result.returncode == 1
            ):  # Grep found nothing (empty file or no version line)
                log_map_server(
                    f"{SYMBOLS['warning']} State file exists but is empty or has no version line. Re-initializing.",
                    "warning",
                    logger_to_use,
                )
                clear_state_file(
                    write_version_only=True, current_logger=logger_to_use
                )
            # If grep had other errors, run_elevated_command would raise an exception
        except Exception as e:
            log_map_server(
                f"{SYMBOLS['error']} Error checking script version in state file ({STATE_FILE_PATH}): {e}. Re-initializing.",
                "error",
                logger_to_use,
            )
            clear_state_file(
                write_version_only=True, current_logger=logger_to_use
            )


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


def clear_state_file(
    write_version_only: bool = False, current_logger=None
) -> None:
    """Clear the state file, optionally keeping only the version line."""
    logger_to_use = current_logger if current_logger else module_logger
    log_map_server(
        f"{SYMBOLS['info']} Clearing state file: {STATE_FILE_PATH}",
        "info",
        logger_to_use,
    )

    content_to_write = f"# Script Version: {SCRIPT_VERSION}\n"
    if not write_version_only:
        content_to_write += (
            f"# State cleared on {datetime.datetime.now().isoformat()}\n"
        )

    # Use a temporary file to prepare content, then sudo cp
    # This avoids needing sudo for basic file writing in Python, only for the final copy.
    temp_file_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, prefix="mapstate_clear_", suffix=".txt"
        ) as temp_f:
            temp_f.write(content_to_write)
            temp_file_path = temp_f.name

        run_elevated_command(
            ["cp", temp_file_path, STATE_FILE_PATH],
            current_logger=logger_to_use,
        )
        if not write_version_only:
            log_map_server(
                f"{SYMBOLS['success']} Progress state file cleared.",
                "success",
                logger_to_use,
            )
        else:
            log_map_server(
                f"{SYMBOLS['success']} Progress state file re-initialized with version.",
                "success",
                logger_to_use,
            )
    except Exception as e:
        log_map_server(
            f"{SYMBOLS['error']} Failed to clear state file: {e}",
            "error",
            logger_to_use,
        )
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


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
