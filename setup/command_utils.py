# setup/command_utils.py
# -*- coding: utf-8 -*-
"""
Utilities for executing shell commands and logging their output.

This module provides functions to run commands with or without elevated
privileges, check for package installation, and log messages consistently
using a shared configuration.
"""

import logging
import os
import shutil  # For shutil.which
import subprocess
import sys
from typing import List, Optional, Union

# Import from config within the same package.
# This provides SYMBOLS and LOG_PREFIX_DEFAULT (for logger fallback).
from . import config

# Each module should define its own logger.
# The main logger (configured in main.py using config.LOG_PREFIX) will
# typically be passed as 'current_logger' to functions in this module if
# specific formatting is desired.
module_logger = logging.getLogger(__name__)


def log_map_server(
    message: str,
    level: str = "info",
    current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Log a message using the provided logger or a default module logger.

    The main application (main.py) is responsible for configuring the logger
    format (including the dynamic LOG_PREFIX from config). This function
    just emits messages.

    Args:
        message: The message string to log.
        level: The logging level ('info', 'warning', 'error', 'critical',
               'debug'). Defaults to 'info'.
        current_logger: Optional logger instance to use. If None, uses
                        the module's default logger.
    """
    effective_logger = current_logger if current_logger else module_logger

    # Fallback basicConfig: This is a last resort if no logger has been
    # configured by the application. It's generally better for the main
    # application to set up all logging.
    # Check if the effective_logger (or its root ancestor) has any handlers.
    _logger_to_check_handlers = effective_logger
    has_handlers = False
    while _logger_to_check_handlers:
        if _logger_to_check_handlers.handlers:
            has_handlers = True
            break
        if not _logger_to_check_handlers.propagate:
            # If propagation is off, stop here.
            break
        _logger_to_check_handlers = _logger_to_check_handlers.parent

    if not has_handlers:
        # If no handlers are found anywhere up the chain, apply a very basic
        # config. This ensures *something* is printed, but might not have the
        # desired app-level format.
        print(
            f"DEBUG: log_map_server in command_utils configuring "
            f"basicConfig for logger '{effective_logger.name}' as no "
            f"handlers found.",
            file=sys.stderr,
        )
        logging.basicConfig(
            level=logging.INFO,
            format=(
                f"[{config.LOG_PREFIX_DEFAULT}] %(asctime)s - "
                f"[%(levelname)s] - %(name)s - %(message)s"
            ),
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        # Mark that some configuration has happened to avoid repeating this.
        # Add a custom attribute to track if fallback was configured.
        if effective_logger is module_logger:
            module_logger.is_fallback_configured = True

    if level == "warning":
        effective_logger.warning(message)
    elif level == "error":
        effective_logger.error(message)
    elif level == "critical":
        effective_logger.critical(message)
    elif level == "debug":
        effective_logger.debug(message)
    else:  # Default to info
        effective_logger.info(message)


def _get_elevated_command_prefix() -> List[str]:
    """Return ['sudo'] if the current user is not root, otherwise an empty list."""
    return [] if os.geteuid() == 0 else ["sudo"]


def run_command(
    command: Union[List[str], str],
    check: bool = True,
    shell: bool = False,
    capture_output: bool = False,
    text: bool = True,
    cmd_input: Optional[str] = None,
    current_logger: Optional[logging.Logger] = None,
) -> subprocess.CompletedProcess:
    """
    Run a command, log its execution, and handle errors.

    Args:
        command: The command to run, as a list of strings or a single string.
                 If a string and `shell` is False, it will be split.
        check: If True, raise CalledProcessError on non-zero exit codes.
        shell: If True, execute the command through the shell.
        capture_output: If True, capture stdout and stderr.
        text: If True, decode stdout/stderr as text.
        cmd_input: Optional string to pass as standard input to the command.
        current_logger: Optional logger instance.

    Returns:
        A subprocess.CompletedProcess instance.

    Raises:
        subprocess.CalledProcessError: If `check` is True and the command
                                       returns a non-zero exit code.
        FileNotFoundError: If the command is not found.
        Exception: For other unexpected errors during command execution.
    """
    effective_logger = current_logger if current_logger else module_logger
    command_to_log_str: str
    command_to_run: Union[List[str], str]

    if shell:
        if isinstance(command, list):
            command_to_run = " ".join(command)
        else:
            command_to_run = command  # Command is already a string.
        command_to_log_str = str(command_to_run)
    else:  # Not shell
        if isinstance(command, str):
            # This case (string command without shell=True) is tricky as it
            # relies on command.split(), which may not handle arguments with
            # spaces correctly.
            log_map_server(
                f"{config.SYMBOLS['warning']} Running string command '{command}'"
                " without shell=True. Consider list format for arguments.",
                "warning",
                effective_logger,
            )
            command_to_run = command.split()
            command_to_log_str = command
        else:  # command is a list
            command_to_run = command
            command_to_log_str = " ".join(command)

    log_map_server(
        f"{config.SYMBOLS['gear']} Executing: {command_to_log_str}",
        "info",
        effective_logger,
    )
    try:
        result = subprocess.run(
            command_to_run,
            check=check,
            shell=shell,
            capture_output=capture_output,
            text=text,
            input=cmd_input,
        )
        # Log stdout/stderr for successful commands if captured and not
        # raising an error (check=False).
        if capture_output and not check and result.returncode == 0:
            if result.stdout and result.stdout.strip():
                log_map_server(
                    f"   stdout: {result.stdout.strip()}",
                    "debug",  # Typically detailed output, log as debug
                    effective_logger,
                )
            if result.stderr and result.stderr.strip():
                # Some tools use stderr for informational messages.
                log_map_server(
                    f"   stderr: {result.stderr.strip()}",
                    "debug",  # Log as debug unless it's an error
                    effective_logger,
                )
        return result
    except subprocess.CalledProcessError as e:
        stdout_info = e.stdout.strip() if e.stdout else "N/A"
        stderr_info = e.stderr.strip() if e.stderr else "N/A"
        cmd_executed_str = (
            " ".join(e.cmd) if isinstance(e.cmd, list) else str(e.cmd)
        )
        log_map_server(
            f"{config.SYMBOLS['error']} Command `{cmd_executed_str}` "
            f"failed (rc {e.returncode}).",
            "error",
            effective_logger,
        )
        if stdout_info != "N/A":
            log_map_server(
                f"   stdout: {stdout_info}", "error", effective_logger
            )
        if stderr_info != "N/A":
            log_map_server(
                f"   stderr: {stderr_info}", "error", effective_logger
            )
        raise
    except FileNotFoundError as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Command not found: {e.filename}. "
            "Ensure it's installed and in PATH.",
            "error",
            effective_logger,
        )
        raise
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Unexpected error running command "
            f"`{command_to_log_str}`: {e}",
            "error",
            effective_logger,
        )
        raise


def run_elevated_command(
    command: List[str],
    check: bool = True,
    capture_output: bool = False,
    cmd_input: Optional[str] = None,
    current_logger: Optional[logging.Logger] = None,
) -> subprocess.CompletedProcess:
    """
    Run a command that may require elevation, handling sudo correctly.

    Uses `run_command` internally. Elevated commands should not use `shell=True`
    for security reasons.

    Args:
        command: The command to run as a list of strings.
        check: If True, raise CalledProcessError on non-zero exit codes.
        capture_output: If True, capture stdout and stderr.
        cmd_input: Optional string to pass as standard input.
        current_logger: Optional logger instance.

    Returns:
        A subprocess.CompletedProcess instance.
    """
    prefix = _get_elevated_command_prefix()
    # Ensure command is a list to prepend correctly.
    elevated_command_list = prefix + list(command)
    return run_command(
        elevated_command_list,
        check=check,
        shell=False,  # Elevated commands should not use shell=True.
        capture_output=capture_output,
        text=True,  # Assuming text mode for stdout/stderr.
        cmd_input=cmd_input,
        current_logger=current_logger,
    )


def command_exists(command: str) -> bool:
    """
    Check if a command exists in the system's PATH using `shutil.which()`.

    Args:
        command: The name of the command to check.

    Returns:
        True if the command exists, False otherwise.
    """
    return shutil.which(command) is not None

def elevated_command_exists(command: str) -> bool:
    """
    Check if a command exists in the elevated system's PATH using `shutil.which()`.

    Args:
        command: The name of the command to check.

    Returns:
        True if the command exists, False otherwise.
    """
    return run_elevated_command(["which",f"{command}"]) is not None


def check_package_installed(
    package: str, current_logger: Optional[logging.Logger] = None
) -> bool:
    """
    Check if an apt package is installed using `dpkg-query`.

    Args:
        package: The name of the package to check.
        current_logger: Optional logger instance.

    Returns:
        True if the package is installed, False otherwise.
    """
    logger_to_use = current_logger if current_logger else module_logger
    try:
        # dpkg-query does not need sudo for querying.
        result = run_command(
            ["dpkg-query", "-W", "-f='${Status}'", package],
            check=False,  # dpkg-query returns non-zero if not installed.
            capture_output=True,
            text=True,
            current_logger=logger_to_use,
        )
        # Expected output for installed package contains "install ok installed".
        return (
            result.returncode == 0 and "install ok installed" in result.stdout
        )
    except FileNotFoundError:
        # This should be caught by run_command if dpkg-query is missing.
        log_map_server(
            f"{config.SYMBOLS['error']} dpkg-query command not found. "
            f"Cannot check package '{package}'.",
            "error",
            logger_to_use,
        )
        return False
    except subprocess.CalledProcessError:
        # Should not be hit if check=False in run_command.
        return False  # Package not installed or error querying.
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Error checking if package "
            f"'{package}' is installed: {e}",
            "error",
            logger_to_use,
        )
        return False
