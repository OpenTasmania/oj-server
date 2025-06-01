# common/command_utils.py
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
from typing import List, Optional, Union

# Assuming config.py is still in the 'setup' directory for now.
# If config.py moves to the project root, this would be:
# import config as app_config
# or from .. import config if common is a sub-package of a larger structure.
from setup import config  # For SYMBOLS and LOG_PREFIX_DEFAULT

module_logger = logging.getLogger(__name__)


def log_map_server(
        message: str,
        level: str = "info",
        current_logger: Optional[logging.Logger] = None,
) -> None:
    """
    Log a message using the provided logger or a default module logger.
    Assumes logging has been configured by an entry point.
    """
    effective_logger = current_logger if current_logger else module_logger

    # REMOVED: Fallback basicConfig block.
    # Logging should be configured by an entry-point script using
    # the common setup_logging function.

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
        cwd: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """
    Run a command, log its execution, and handle errors.
    """
    effective_logger = current_logger if current_logger else module_logger
    command_to_log_str: str
    command_to_run: Union[List[str], str]

    if shell: # pragma: no cover
        if isinstance(command, list):
            command_to_run = " ".join(command)
        else:
            command_to_run = command
        command_to_log_str = str(command_to_run)
    else:
        if isinstance(command, str): # pragma: no cover
            log_map_server(
                f"{config.SYMBOLS['warning']} Running string command '{command}'"
                " without shell=True. Consider list format for arguments.",
                "warning",
                effective_logger,
            )
            command_to_run = command.split()
            command_to_log_str = command
        else:
            command_to_run = command
            command_to_log_str = " ".join(command)

    log_map_server(
        f"{config.SYMBOLS['gear']} Executing: {command_to_log_str} "
        f"{f'(in {cwd})' if cwd else ''}",
        "info", # Changed from 'info' to 'debug' for less verbose default logging of commands
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
            cwd=cwd,
        )
        if capture_output:
            if result.stdout and result.stdout.strip():
                log_map_server( # Log output at DEBUG level
                    f"   stdout: {result.stdout.strip()}", "debug", effective_logger
                )
            # Log stderr if it's not an error condition (check=False and rc=0, or check=True and rc=0)
            if result.stderr and result.stderr.strip() and (not check or result.returncode == 0):
                log_map_server( # Log non-error stderr at DEBUG
                    f"   stderr: {result.stderr.strip()}", "debug", effective_logger
                )
        return result
    except subprocess.CalledProcessError as e:
        stdout_info = e.stdout.strip() if e.stdout and hasattr(e.stdout, 'strip') else "N/A"
        stderr_info = e.stderr.strip() if e.stderr and hasattr(e.stderr, 'strip') else "N/A"
        cmd_executed_str = " ".join(e.cmd) if isinstance(e.cmd, list) else str(e.cmd)

        log_map_server(
            f"{config.SYMBOLS['error']} Command `{cmd_executed_str}` failed (rc {e.returncode}).",
            "error",
            effective_logger,
        )
        if stdout_info != "N/A":
            log_map_server(f"   stdout: {stdout_info}", "error", effective_logger)
        if stderr_info != "N/A":
            log_map_server(f"   stderr: {stderr_info}", "error", effective_logger)
        raise
    except FileNotFoundError as e: # pragma: no cover
        log_map_server(
            f"{config.SYMBOLS['error']} Command not found: {e.filename}. Ensure it's installed and in PATH.",
            "error",
            effective_logger,
        )
        raise
    except Exception as e: # pragma: no cover
        log_map_server(
            f"{config.SYMBOLS['error']} Unexpected error running command `{command_to_log_str}`: {e}",
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
        cwd: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """
    Run a command that may require elevation, handling sudo correctly.
    """
    prefix = _get_elevated_command_prefix()
    elevated_command_list = prefix + list(command)
    return run_command(
        elevated_command_list,
        check=check,
        shell=False,
        capture_output=capture_output,
        text=True,
        cmd_input=cmd_input,
        current_logger=current_logger,
        cwd=cwd,
    )


def command_exists(command_name: str) -> bool:
    """
    Check if a command exists in the system's PATH using `shutil.which()`.
    """
    return shutil.which(command_name) is not None


def elevated_command_exists(command_name: str, current_logger: Optional[logging.Logger] = None) -> bool:
    """
    Check if a command exists when searched with elevated privileges.
    This is useful for commands that might only be in root's PATH.
    """
    try:
        run_elevated_command(["which", command_name], capture_output=True, check=True, current_logger=current_logger)
        return True
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError: # pragma: no cover
        log_map_server(f"Could not check for elevated command '{command_name}' as 'sudo' or 'which' may be missing.",
                       "warning", current_logger)
        return False


def check_package_installed(
        package_name: str, current_logger: Optional[logging.Logger] = None
) -> bool:
    """
    Check if an apt package is installed using `dpkg-query`.

    Args:
        package_name: The name of the package to check.
        current_logger: Optional logger instance.

    Returns:
        True if the package is installed, False otherwise.
    """
    logger_to_use = current_logger if current_logger else module_logger
    try:
        result = run_command(
            ["dpkg-query", "-W", "-f='${Status}'", package_name],
            check=False,
            capture_output=True,
            text=True,
            current_logger=logger_to_use, # Pass logger here
        )
        return (
                result.returncode == 0 and "install ok installed" in result.stdout
        )
    except FileNotFoundError: # pragma: no cover
        log_map_server(
            f"{config.SYMBOLS['error']} dpkg-query command not found. "
            f"Cannot check package '{package_name}'.",
            "error",
            logger_to_use,
        )
        return False
    except subprocess.CalledProcessError: # pragma: no cover
        # This should not be reached if check=False, but defensive.
        return False
    except Exception as e: # pragma: no cover
        log_map_server(
            f"{config.SYMBOLS['error']} Error checking if package "
            f"'{package_name}' is installed: {e}",
            "error",
            logger_to_use,
        )
        return False