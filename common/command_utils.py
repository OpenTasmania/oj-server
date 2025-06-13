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
    exc_info: bool = False,
) -> None:
    """
    Logs messages to a server-specific logger at a defined logging level. It supports different logging levels
    and an option to include exception information.

    Args:
        message (str): The log message to be recorded.
        level (str): The severity level of the log message. Defaults to "info". Common options
            include "debug", "info", "warning", "error", and "critical".
        current_logger (Optional[logging.Logger]): A logger instance to use for logging. If not provided,
            a module-level logger will be used.
        app_settings (Optional[AppSettings]): Optional application settings that can influence logging behavior.
        exc_info (bool): Indicator to include exception details in the log. By default, this is set to False.

    Returns:
        None
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
        effective_logger.debug(message, exc_info=exc_info)
    else:
        effective_logger.info(message, exc_info=exc_info)


def _get_elevated_command_prefix() -> List[str]:
    """
    Determines the command prefix that ensures elevated privileges when required.

    This function checks the effective user ID (euid) to decide whether the current
    process already has root-level privileges. If the euid is not 0, indicating the
    process does not have root privileges, it returns a prefix (`["sudo"]`) to
    ensure commands are executed with elevated privileges. If the euid is 0, it
    returns an empty list as no additional prefix is necessary.

    Returns:
        List[str]: A list containing the prefix ["sudo"] if elevated privileges are
        needed, or an empty list if the process already has root privileges.
    """
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
    """
    Executes a system command and logs the process details and results, including both
    standard output and error, if specified. Captures and processes exceptions like
    command errors or unexpected runtime issues.

    Args:
        command (Union[List[str], str]): The system command to execute. This can be
            provided as a string or a list of strings. If shell mode is enabled and
            the input is a list, elements will be joined into a single string.
        app_settings (Optional[AppSettings]): An optional object containing application-specific
            configuration parameters, including logging symbols. If not provided, default
            settings will be used.
        check (bool): Whether to raise a CalledProcessError when a non-zero exit code is returned.
            Defaults to True.
        shell (bool): If True, the system command will be executed in a shell. Defaults to False.
        capture_output (bool): Whether to capture standard output and standard error. Defaults to False.
        text (bool): Indicates if the output streams should be interpreted as text. Defaults to True.
        cmd_input (Optional[str]): Input to be passed to the command's standard input. Defaults to None.
        current_logger (Optional[logging.Logger]): A logger to use for logging details. If not provided,
            a default logger will be used.
        cwd (Optional[str]): The current working directory from which to execute the command. If not
            provided, it inherits the current working directory of the parent process.
        env (Optional[Dict[str, str]]): A dictionary defining the environment variables for the command
            execution. Defaults to the inherited environment of the current process.

    Returns:
        subprocess.CompletedProcess: The completed process instance, containing information about the
            executed command, its return code, and captured output streams.

    Raises:
        subprocess.CalledProcessError: Raised if the process returns a non-zero exit code and the check
            parameter is set to True.
        FileNotFoundError: Raised if the specified command is not found on the system.
        Exception: Other unexpected exceptions that occur during command execution.

    Notes:
        - Logs warning messages when executing string commands without `shell=True`.
        - When capturing output, the method retrieves and logs both stdout and stderr information.
        - This function provides logging on various process events such as execution, success, and error.
    """
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
    env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    """
    Executes a command with elevated permissions. This function constructs the necessary
    command prefix for elevated execution and runs the given command. It supports various
    parameters such as logging, working directory, input, and environment variables for
    customization.

    Args:
        command: List[str]
            The command to execute, provided as a list of strings.
        app_settings: Optional[AppSettings]
            The application settings that may influence the command execution.
        check: bool
            If True, raises an exception if the command execution fails. Defaults to True.
        capture_output: bool
            If True, captures the output of the command. Defaults to False.
        cmd_input: Optional[str]
            The input to pass to the command via standard input. Defaults to None.
        current_logger: Optional[logging.Logger]
            A logger instance to log any output or errors during execution. Defaults to None.
        cwd: Optional[str]
            The working directory for the command execution. Defaults to None.
        env: Optional[Dict[str, str]]
            Additional environment variables to use during command execution. Defaults to None.

    Returns:
        subprocess.CompletedProcess
            The result of the command execution, containing the return code, stdout, and stderr.

    Raises:
        subprocess.CalledProcessError
            Raised if check is True and the executed command returns an error.

    """
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
    """
    Check if a command exists in the system's PATH.

    This function determines whether a given command is available by searching
    the system's PATH for an executable with the specified name.

    Parameters:
        command_name (str): The name of the command to check for existence.

    Returns:
        bool: True if the command is found in the system's PATH, False otherwise.
    """
    return shutil.which(command_name) is not None


def elevated_command_exists(
    command_name: str,
    app_settings: Optional[AppSettings],
    current_logger: Optional[logging.Logger] = None,
) -> bool:
    """
    Checks for the existence of a command using elevated privileges.

    This function attempts to verify if a given command is accessible by using
    the `which` command executed with elevated privileges. It logs warnings
    if required tools like `sudo` or `which` are missing or if there are other
    unexpected errors during execution. It returns a Boolean value indicating
    whether the command exists or not.

    Args:
        command_name: str
            The name of the command to be checked.
        app_settings: Optional[AppSettings]
            The application settings, which may provide symbols or other
            configuration details for logging purposes.
        current_logger: Optional[logging.Logger]
            A logger instance used to capture log messages during execution.

    Returns:
        bool: True if the command exists and can be found via elevated checks,
        otherwise False.
    """
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
        return False
    except FileNotFoundError:
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
    except Exception as e:
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
    """
    Checks if a given package is installed on the system using the `dpkg-query`
    command. The function can also optionally log messages and use custom
    application settings while performing the check.

    Attributes or configuration details like application-specific symbols,
    or a logger, can be passed to refine the operation or adjust logging.

    Args:
        package_name (str): The name of the package to check for installation status.
        app_settings (Optional[AppSettings]): Optional application settings containing
            configurations like symbols for different log types.
        current_logger (Optional[logging.Logger]): Logger to use for logging messages,
            if provided. Defaults to a module-level logger.

    Returns:
        bool: Returns True if the package is installed and returns a status indicating
        "install ok installed", otherwise False.

    Raises:
        None explicitly. Catches `FileNotFoundError` if `dpkg-query` is not available
        and general exceptions for any unexpected issues during the check.
    """
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
            check=False,
            capture_output=True,
            text=True,
            current_logger=logger_to_use,
        )
        return (
            result.returncode == 0 and "install ok installed" in result.stdout
        )
    except FileNotFoundError:
        log_map_server(
            f"{symbols.get('error', '❌')} dpkg-query command not found. Cannot check package '{package_name}'.",
            "error",
            logger_to_use,
            app_settings,
        )
        return False
    except Exception as e:
        log_map_server(
            f"{symbols.get('error', '❌')} Error checking if package '{package_name}' is installed: {e}",
            "error",
            logger_to_use,
            app_settings,
        )
        return False
