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
import sys
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
    """
    effective_logger = current_logger if current_logger else module_logger

    # Fallback basicConfig if no handlers are configured up the chain
    _logger_to_check_handlers = effective_logger
    has_handlers = False
    while _logger_to_check_handlers:
        if _logger_to_check_handlers.handlers:
            has_handlers = True
            break
        if not _logger_to_check_handlers.propagate:
            break
        _logger_to_check_handlers = _logger_to_check_handlers.parent

    if not has_handlers:
        logging.basicConfig(
            level=logging.INFO,
            format=(
                f"[{config.LOG_PREFIX_DEFAULT}] %(asctime)s - "
                f"[%(levelname)s] - %(name)s - %(message)s"
            ),
            datefmt="%Y-%m-%d %H:%M:%S",
        )

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
        cwd: Optional[str] = None,  # Added cwd parameter for consistency
) -> subprocess.CompletedProcess:
    """
    Run a command, log its execution, and handle errors.
    """
    effective_logger = current_logger if current_logger else module_logger
    command_to_log_str: str
    command_to_run: Union[List[str], str]

    if shell:
        if isinstance(command, list):
            command_to_run = " ".join(command)
        else:
            command_to_run = command
        command_to_log_str = str(command_to_run)
    else:
        if isinstance(command, str):
            log_map_server(
                f"{config.SYMBOLS['warning']} Running string command '{command}'"
                " without shell=True. Consider list format for arguments.",
                "warning",
                effective_logger,
            )
            command_to_run = command.split()  # Basic split, might not handle spaces in args
            command_to_log_str = command
        else:
            command_to_run = command
            command_to_log_str = " ".join(command)

    log_map_server(
        f"{config.SYMBOLS['gear']} Executing: {command_to_log_str} "
        f"{f'(in {cwd})' if cwd else ''}",
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
            cwd=cwd,
        )
        if capture_output:  # Log output even for successful commands if captured
            if result.stdout and result.stdout.strip():
                log_map_server(
                    f"   stdout: {result.stdout.strip()}", "debug", effective_logger
                )
            # Log stderr if it's not an error condition (check=False and rc=0, or check=True and rc=0)
            if result.stderr and result.stderr.strip() and (not check or result.returncode == 0):
                log_map_server(
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
    except FileNotFoundError as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Command not found: {e.filename}. Ensure it's installed and in PATH.",
            "error",
            effective_logger,
        )
        raise
    except Exception as e:
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
        cwd: Optional[str] = None,  # Added cwd parameter
) -> subprocess.CompletedProcess:
    """
    Run a command that may require elevation, handling sudo correctly.
    """
    prefix = _get_elevated_command_prefix()
    elevated_command_list = prefix + list(command)
    return run_command(
        elevated_command_list,
        check=check,
        shell=False,  # Elevated commands should generally not use shell=True
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
        # Use 'which' command via run_elevated_command.
        # 'which' returns 0 if found, 1 if not found.
        run_elevated_command(["which", command_name], capture_output=True, check=True, current_logger=current_logger)
        return True
    except subprocess.CalledProcessError:
        # 'which' command returned non-zero (not found) or other error.
        return False
    except FileNotFoundError:
        # 'sudo' or 'which' itself was not found.
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
        # dpkg-query does not need sudo for querying installation status.
        result = run_command(
            ["dpkg-query", "-W", "-f='${Status}'", package_name],
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
        log_map_server(
            f"{config.SYMBOLS['error']} dpkg-query command not found. "
            f"Cannot check package '{package_name}'.",
            "error",
            logger_to_use,
        )
        return False
    # CalledProcessError should not occur due to check=False, but defensive:
    except subprocess.CalledProcessError:
        return False
    except Exception as e:
        log_map_server(
            f"{config.SYMBOLS['error']} Error checking if package "
            f"'{package_name}' is installed: {e}",
            "error",
            logger_to_use,
        )
        return False