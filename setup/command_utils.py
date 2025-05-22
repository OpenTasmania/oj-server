# setup/command_utils.py
import logging
import os
import subprocess
import sys
import shutil  # For shutil.which
from typing import List, Optional

# Import from config within the same package.
# This provides SYMBOLS and LOG_PREFIX_DEFAULT (for logger fallback).
from . import config

# Each module should define its own logger.
# The main logger (configured in main.py using config.LOG_PREFIX) will typically be passed
# as 'current_logger' to functions in this module if specific formatting is desired.
module_logger = logging.getLogger(__name__)  # Logger for this specific module


def log_map_server(message: str, level: str = "info", current_logger: Optional[logging.Logger] = None) -> None:
    """
    Log a message. Uses the provided logger or falls back to this module's logger.
    The main application (main.py) is responsible for configuring the logger format
    (including the dynamic LOG_PREFIX from config). This function just emits messages.
    """
    effective_logger = current_logger if current_logger else module_logger

    # Fallback basicConfig: This is a last resort if no logger has been configured by the application.
    # It's generally better for the main application to set up all logging.
    # Check if the effective_logger (or its root ancestor) has any handlers.
    _logger_to_check_handlers = effective_logger
    has_handlers = False
    while _logger_to_check_handlers:
        if _logger_to_check_handlers.handlers:
            has_handlers = True
            break
        if not _logger_to_check_handlers.propagate:  # If propagation is off, stop here
            break
        _logger_to_check_handlers = _logger_to_check_handlers.parent

    if not has_handlers:
        # If no handlers are found anywhere up the chain, apply a very basic config.
        # This ensures *something* is printed, but might not have the desired app-level format.
        print(
            f"DEBUG: log_map_server in command_utils configuring basicConfig for logger '{effective_logger.name}' as no handlers found.",
            file=sys.stderr)
        logging.basicConfig(
            level=logging.INFO,
            format=f"[{config.LOG_PREFIX_DEFAULT}] %(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        # Mark that some configuration has happened to avoid repeating this.
        if effective_logger is module_logger:  # Only mark if it's this module's logger
            module_logger.is_fallback_configured = True  # Custom attribute

    if level == "info":
        effective_logger.info(message)
    elif level == "warning":
        effective_logger.warning(message)
    elif level == "error":
        effective_logger.error(message)
    elif level == "critical":
        effective_logger.critical(message)
    else:
        effective_logger.info(message)


def _get_elevated_command_prefix() -> List[str]:
    """Returns ['sudo'] if not root, otherwise an empty list."""
    return [] if os.geteuid() == 0 else ["sudo"]


def run_command(command: List[str] or str, check: bool = True, shell: bool = False,
                capture_output: bool = False, text: bool = True,
                cmd_input: Optional[str] = None,
                current_logger: Optional[logging.Logger] = None) -> subprocess.CompletedProcess:
    """
    Run a command, log its execution using config.SYMBOLS, and handle errors.
    """
    effective_logger = current_logger if current_logger else module_logger

    command_to_log_str: str
    command_to_run: List[str] or str

    if shell:
        if isinstance(command, list):
            command_to_run = " ".join(command)
        else:
            command_to_run = command  # command is already a string
        command_to_log_str = str(command_to_run)  # Ensure it's a string for logging
    else:  # not shell
        if isinstance(command, str):
            # This case (string command without shell=True) is tricky and often discouraged
            # as it relies on command.split() which may not handle arguments with spaces correctly.
            log_map_server(
                f"{config.SYMBOLS['warning']} Running string command '{command}' without shell=True. Consider list format for arguments.",
                "warning", effective_logger)
            command_to_run = command.split()
            command_to_log_str = command
        else:  # command is a list
            command_to_run = command
            command_to_log_str = " ".join(command)  # For logging purposes

    log_map_server(f"{config.SYMBOLS['gear']} Executing: {command_to_log_str}", "info", effective_logger)
    try:
        result = subprocess.run(
            command_to_run, check=check, shell=shell, capture_output=capture_output,
            text=text, input=cmd_input
        )
        # Log stdout/stderr for successful commands if captured and not raising an error (check=False)
        if capture_output and not check and result.returncode == 0:
            if result.stdout and result.stdout.strip():
                log_map_server(f"   stdout: {result.stdout.strip()}", "info", effective_logger)
            if result.stderr and result.stderr.strip():
                # Some tools use stderr for informational messages (e.g. curl progress)
                log_map_server(f"   stderr: {result.stderr.strip()}", "info", effective_logger)
        return result
    except subprocess.CalledProcessError as e:
        # For CalledProcessError, e.cmd, e.stdout, e.stderr are available
        stdout_info = e.stdout.strip() if e.stdout else "N/A"
        stderr_info = e.stderr.strip() if e.stderr else "N/A"
        cmd_executed_str = " ".join(e.cmd) if isinstance(e.cmd, list) else str(e.cmd)
        log_map_server(f"{config.SYMBOLS['error']} Command `{cmd_executed_str}` failed (rc {e.returncode}).", "error",
                       effective_logger)
        if stdout_info != "N/A": log_map_server(f"   stdout: {stdout_info}", "error", effective_logger)
        if stderr_info != "N/A": log_map_server(f"   stderr: {stderr_info}", "error", effective_logger)
        raise
    except FileNotFoundError as e:
        log_map_server(f"{config.SYMBOLS['error']} Command not found: {e.filename}. Ensure it's installed and in PATH.",
                       "error", effective_logger)
        raise
    except Exception as e:
        # Catch other potential errors like permission issues if not using sudo correctly (though less likely for run_command)
        log_map_server(f"{config.SYMBOLS['error']} Unexpected error running command `{command_to_log_str}`: {e}",
                       "error", effective_logger)
        # import traceback # For deeper debugging if necessary
        # log_map_server(traceback.format_exc(), "error", effective_logger)
        raise


def run_elevated_command(command: List[str], check: bool = True,
                         capture_output: bool = False, cmd_input: Optional[str] = None,
                         current_logger: Optional[logging.Logger] = None) -> subprocess.CompletedProcess:
    """
    Run a command that may require elevation, handling sudo correctly.
    Uses run_command internally.
    """
    prefix = _get_elevated_command_prefix()
    command_list = list(command)  # Ensure it's a list to prepend correctly
    elevated_command_list = prefix + command_list
    return run_command(
        elevated_command_list,
        check=check,
        shell=False,  # Elevated commands should not use shell=True for security
        capture_output=capture_output,
        text=True,  # Assuming text mode for stdout/stderr
        cmd_input=cmd_input,
        current_logger=current_logger
    )


def command_exists(command: str) -> bool:
    """Check if a command exists in PATH using shutil.which()."""
    return shutil.which(command) is not None


def check_package_installed(package: str, current_logger: Optional[logging.Logger] = None) -> bool:
    """Check if an apt package is installed using dpkg-query."""
    logger_to_use = current_logger if current_logger else module_logger
    try:
        # dpkg-query does not need sudo for querying.
        result = run_command(
            ["dpkg-query", "-W", "-f='${Status}'", package],
            check=False,  # dpkg-query returns non-zero if package is not known or not installed
            capture_output=True,
            text=True,
            current_logger=logger_to_use
        )
        # Expected output for an installed package contains "install ok installed" in its status line.
        # Return code 0 from dpkg-query -W means the package is known to the system.
        return result.returncode == 0 and "install ok installed" in result.stdout
    except FileNotFoundError:  # Should be caught by run_command if dpkg-query is missing
        log_map_server(f"{config.SYMBOLS['error']} dpkg-query command not found. Cannot check package '{package}'.",
                       "error", logger_to_use)
        return False
    except subprocess.CalledProcessError:  # Should not be hit if check=False in run_command
        return False  # Package not installed or error querying
    except Exception as e:  # Other unexpected errors
        log_map_server(f"{config.SYMBOLS['error']} Error checking if package '{package}' is installed: {e}", "error",
                       logger_to_use)
        return False