# common/command_utils.py
# -*- coding: utf-8 -*-
"""
Utilities for executing shell commands and logging their output.
"""

import logging
import os
import shutil
import subprocess
from typing import Dict, List, Optional, Union

# Import AppSettings for type hinting and SYMBOLS_DEFAULT for fallback
from setup.config_models import SYMBOLS_DEFAULT, AppSettings

module_logger = logging.getLogger(__name__)


def log_map_server(
    message: str,
    level: str = "info",
    current_logger: Optional[logging.Logger] = None,
    app_settings: Optional[AppSettings] = None,
    exc_info: bool = False,  # Add exc_info parameter, default to False
    # Alternative for exc_info type: exc_info: Any = False, to match logging's flexibility
) -> None:
    """
    Log a message using the provided logger or a default module logger.
    Uses symbols from app_settings if provided, otherwise default symbols.
    Can also log exception information if exc_info is True.
    """
    effective_logger = current_logger if current_logger else module_logger

    if level == "warning":
        effective_logger.warning(message, exc_info=exc_info)
    elif level == "error":
        effective_logger.error(
            message, exc_info=exc_info
        )  # Pass exc_info here
    elif level == "critical":
        effective_logger.critical(
            message, exc_info=exc_info
        )  # Pass exc_info here
    elif level == "debug":
        effective_logger.debug(
            message, exc_info=exc_info
        )  # Generally not used for exc_info, but possible
    else:  # Default to info
        effective_logger.info(
            message, exc_info=exc_info
        )  # Generally not used for exc_info, but possible


def _get_elevated_command_prefix() -> List[str]:
    return [] if os.geteuid() == 0 else ["sudo"]


def run_command(
    command: Union[List[str], str],
    app_settings: Optional[AppSettings],
    check: bool = True,
    shell: bool = False,
    capture_output: bool = False,
    text: bool = True,
    cmd_input: Optional[str] = None,
    current_logger: Optional[logging.Logger] = None,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    effective_logger = current_logger if current_logger else module_logger
    symbols = (
        app_settings.symbols
        if app_settings and app_settings.symbols
        else SYMBOLS_DEFAULT
    )
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
                f"{symbols.get('warning', '!')} Running string command '{command}' without shell=True. Consider list format.",
                "warning",
                effective_logger,
                app_settings,
            )
            command_to_run = (
                command.split()
            )  # Basic split, consider shlex for complex cases
            command_to_log_str = command
        else:
            command_to_run = command
            command_to_log_str = (
                subprocess.list2cmdline(command)
                if isinstance(command, list)
                else command
            )

    log_map_server(
        f"{symbols.get('gear', '⚙️')} Executing: {command_to_log_str} {f'(in {cwd})' if cwd else ''}",
        "info",
        effective_logger,
        app_settings,
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
            env=env,
        )
        if capture_output:
            if result.stdout and result.stdout.strip():
                log_map_server(
                    f"   stdout: {result.stdout.strip()}",
                    "info",
                    effective_logger,
                    app_settings,
                )
            if (
                result.stderr
                and result.stderr.strip()
                and (not check or result.returncode == 0)
            ):
                log_map_server(
                    f"   stderr: {result.stderr.strip()}",
                    "info",
                    effective_logger,
                    app_settings,
                )
        return result
    except subprocess.CalledProcessError as e:
        stdout_info = (
            e.stdout.strip()
            if e.stdout and hasattr(e.stdout, "strip")
            else "N/A"
        )
        stderr_info = (
            e.stderr.strip()
            if e.stderr and hasattr(e.stderr, "strip")
            else "N/A"
        )
        cmd_executed_str = (
            subprocess.list2cmdline(e.cmd)
            if isinstance(e.cmd, list)
            else str(e.cmd)
        )

        log_map_server(
            f"{symbols.get('error', '❌')} Command `{cmd_executed_str}` failed (rc {e.returncode}).",
            "error",
            effective_logger,
            app_settings,
        )
        if stdout_info != "N/A":
            log_map_server(
                f"   stdout: {stdout_info}",
                "error",
                effective_logger,
                app_settings,
            )
        if stderr_info != "N/A":
            log_map_server(
                f"   stderr: {stderr_info}",
                "error",
                effective_logger,
                app_settings,
            )
        raise
    except FileNotFoundError as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Command not found: {e.filename}. Ensure it's installed and in PATH.",
            "error",
            effective_logger,
            app_settings,
        )
        raise
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Unexpected error running command `{command_to_log_str}`: {e}",
            "error",
            effective_logger,
            app_settings,
            exc_info=True,
        )
        raise


def run_elevated_command(
    command: List[str],
    app_settings: Optional[AppSettings],
    check: bool = True,
    capture_output: bool = False,
    cmd_input: Optional[str] = None,
    current_logger: Optional[logging.Logger] = None,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,  # Added env parameter
) -> subprocess.CompletedProcess:
    prefix = _get_elevated_command_prefix()
    elevated_command_list = prefix + list(command)
    return run_command(
        elevated_command_list,
        app_settings,
        check=check,
        shell=False,
        capture_output=capture_output,
        text=True,
        cmd_input=cmd_input,
        current_logger=current_logger,
        cwd=cwd,
        env=env,
    )


def command_exists(command_name: str) -> bool:
    """Checks if a command exists in the system's PATH."""
    return shutil.which(command_name) is not None


def elevated_command_exists(
    command_name: str,
    app_settings: Optional[AppSettings],
    current_logger: Optional[logging.Logger] = None,
) -> bool:
    """Checks if a command exists when searched with elevated privileges."""
    try:
        run_elevated_command(
            ["which", command_name],
            app_settings,
            capture_output=True,
            check=True,
            current_logger=current_logger,
        )
        return True
    except subprocess.CalledProcessError:
        return False  # Command not found via elevated 'which'
    except FileNotFoundError:  # sudo or which might be missing
        symbols = (
            app_settings.symbols
            if app_settings and app_settings.symbols
            else SYMBOLS_DEFAULT
        )
        log_map_server(
            f"{symbols.get('warning', '!')} Could not check for elevated command '{command_name}' as 'sudo' or 'which' may be missing.",
            "warning",
            current_logger,
            app_settings,
        )
        return False
    except Exception as e:  # Other unexpected errors
        symbols = (
            app_settings.symbols
            if app_settings and app_settings.symbols
            else SYMBOLS_DEFAULT
        )
        log_map_server(
            f"{symbols.get('warning', '!')} Error checking elevated command '{command_name}': {e}",
            "warning",
            current_logger,
            app_settings,
        )
        return False


def check_package_installed(
    package_name: str,
    app_settings: Optional[AppSettings],
    current_logger: Optional[logging.Logger] = None,
) -> bool:
    """Checks if an apt package is installed using dpkg-query."""
    logger_to_use = current_logger if current_logger else module_logger
    symbols = (
        app_settings.symbols
        if app_settings and app_settings.symbols
        else SYMBOLS_DEFAULT
    )
    try:
        result = run_command(
            ["dpkg-query", "-W", "-f='${Status}'", package_name],
            app_settings,
            check=False,  # dpkg-query returns non-zero if package not found
            capture_output=True,
            text=True,
            current_logger=logger_to_use,
        )
        return (
            result.returncode == 0 and "install ok installed" in result.stdout
        )
    except FileNotFoundError:  # If dpkg-query itself is not found
        log_map_server(
            f"{symbols.get('error', '❌')} dpkg-query command not found. Cannot check package '{package_name}'.",
            "error",
            logger_to_use,
            app_settings,
        )
        return False
    except Exception as e:  # Other unexpected errors
        log_map_server(
            f"{symbols.get('error', '❌')} Error checking if package '{package_name}' is installed: {e}",
            "error",
            logger_to_use,
            app_settings,
        )
        return False
