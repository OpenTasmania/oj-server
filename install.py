#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prerequisite installer for the Map Server Setup.

Ensures 'uv' (Python packager and virtual environment manager) is installed,
then creates a virtual environment, installs project dependencies,
and calls the main map server setup script, passing along all arguments.
"""

import getpass
import logging
import os
# import shutil # No longer directly needed after refactoring
import subprocess
import sys
from typing import List, Optional

# Common utility imports
from common.command_utils import (
    command_exists,
    run_command,
    run_elevated_command,
    _get_elevated_command_prefix,  # For checking if sudo is needed for apt calls
)
from common.system_utils import get_debian_codename

MAP_SERVER_INSTALLER_NAME = "installer.main_installer"
VENV_DIR = ".venv"

SYMBOLS_OUTER = {
    "success": "✅", "error": "❌", "warning": "⚠️", "info": "ℹ️",
    "step": "➡️", "gear": "⚙️", "package": "📦", "rocket": "🚀",
    "sparkles": "✨", "critical": "🔥", "link": "🔗",
    "python": "🐍"
}

outer_logger = logging.getLogger("PrereqInstaller")
outer_logger.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stdout)
_formatter = logging.Formatter(
    "[PREREQ-INSTALL] %(asctime)s - [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_handler.setFormatter(_formatter)
if not outer_logger.handlers:
    outer_logger.addHandler(_handler)
outer_logger.propagate = False


def log_prereq(message: str, level: str = "info") -> None:
    """Log messages for this prerequisite installer script."""
    if level == "critical":
        outer_logger.critical(message)
    elif level == "error":
        outer_logger.error(message)
    elif level == "warning":
        outer_logger.warning(message)
    else:
        outer_logger.info(message)


# _get_elevated_prefix_prereq is now imported from common.command_utils

# command_exists_prereq is replaced by command_exists from common.command_utils

# get_debian_codename_prereq is replaced by get_debian_codename from common.system_utils

# _run_cmd_prereq is removed; replaced by run_command and run_elevated_command


def ensure_pip_installed_prereq() -> bool:
    log_prereq(f"{SYMBOLS_OUTER.get('step', '->')} {SYMBOLS_OUTER.get('python', '🐍')} Checking for 'pip' command...",
               "info")
    if command_exists("pip3") or command_exists("pip"):  # Use common version
        pip_cmd = "pip3" if command_exists("pip3") else "pip"
        log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} '{pip_cmd}' command is already available.", "info")
        return True
    log_prereq(f"{SYMBOLS_OUTER.get('warning', '!!')} 'pip' command not found. Attempting to install 'python3-pip'...",
               "warning")
    if not command_exists("apt"):  # Use common version
        log_prereq(f"{SYMBOLS_OUTER.get('error', '!!')} 'apt' command not found. Please install pip manually.", "error")
        return False
    try:
        log_prereq(f"{SYMBOLS_OUTER.get('gear', '>>')} Updating apt cache...", "info")
        run_elevated_command(["apt", "update"], capture_output=True, current_logger=outer_logger)
        log_prereq(f"{SYMBOLS_OUTER.get('package', '>>')} Attempting to install 'python3-pip' using apt...", "info")
        run_elevated_command(["apt", "install", "-y", "python3-pip"], capture_output=True, current_logger=outer_logger)

        if command_exists("pip3") or command_exists("pip"):  # Use common version
            log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} 'pip' (or 'pip3') command is now available.", "info")
            return True
        else:
            log_prereq(
                f"{SYMBOLS_OUTER.get('warning', '!!')} 'python3-pip' installed, but 'pip'/'pip3' not immediately in PATH.",
                "warning")
            return True
    except Exception as e:
        log_prereq(f"{SYMBOLS_OUTER.get('error', '!!')} Failed to install 'python3-pip' via apt: {e}", "error")
        return False


def _install_uv_with_pipx_prereq() -> bool:
    log_prereq(f"{SYMBOLS_OUTER.get('info', '>>')} Attempting uv installation using pipx...", "info")

    if not command_exists("pipx"):  # Use common version
        log_prereq(f"{SYMBOLS_OUTER.get('warning', '!!')} pipx not found. Attempting to install pipx...", "warning")
        try:
            if not ensure_pip_installed_prereq():
                log_prereq(
                    f"{SYMBOLS_OUTER.get('error', '!!')} pip is required to install pipx if apt method fails. Aborting pipx install.",
                    "error")
                return False

            if command_exists("apt"):  # Use common version
                try:
                    run_elevated_command(["apt", "update"], current_logger=outer_logger)
                    run_elevated_command(["apt", "install", "-y", "pipx"], current_logger=outer_logger)
                    log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} pipx installed successfully via apt.", "info")
                except Exception:
                    log_prereq(f"{SYMBOLS_OUTER.get('warning', '!!')} Failed to install pipx via apt. Trying pip...",
                               "warning")

            if not command_exists("pipx"):  # Use common version
                pip_cmd = "pip3" if command_exists("pip3") else "pip"  # Use common version
                run_command([sys.executable, "-m", pip_cmd, "install", "--user", "pipx"], current_logger=outer_logger)
                run_command([sys.executable, "-m", "pipx", "ensurepath"], current_logger=outer_logger)
                log_prereq(
                    f"{SYMBOLS_OUTER.get('success', 'OK')} pipx installed for current user using {pip_cmd}. You may need to source your shell profile or open a new terminal.",
                    "info")
        except Exception as e:
            log_prereq(f"{SYMBOLS_OUTER.get('error', '!!')} Failed to install pipx: {e}", "error")
            return False

    pipx_bin_dir = os.path.expanduser("~/.local/bin")
    current_path = os.environ.get("PATH", "")
    if pipx_bin_dir not in current_path.split(os.pathsep):
        log_prereq(f"{SYMBOLS_OUTER.get('gear', '>>')} Adding '{pipx_bin_dir}' to PATH for current script session...",
                   "info")
        os.environ["PATH"] = f"{pipx_bin_dir}{os.pathsep}{current_path}"
        log_prereq(f"   New temporary PATH: {os.environ['PATH']}", "info")
        if not command_exists("pipx"):  # Use common version
            log_prereq(
                f"{SYMBOLS_OUTER.get('error', '!!')} pipx installed, but still not found in PATH. Manual PATH adjustment may be needed.",
                "error")
            return False

    log_prereq(
        f"{SYMBOLS_OUTER.get('rocket', '>>')} Attempting to install/upgrade 'uv' with pipx (as user '{getpass.getuser()}')...",
        "info")
    try:
        run_command(["pipx", "install", "uv"], capture_output=True, current_logger=outer_logger)
        log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' installed/upgraded successfully using pipx.", "info")
        return True
    except Exception as e:
        log_prereq(f"{SYMBOLS_OUTER.get('error', '!!')} Failed to install 'uv' using pipx: {e}", "error")
        return False


def install_uv_prereq() -> bool:
    log_prereq(f"{SYMBOLS_OUTER.get('step', '->')} Checking for 'uv' installation...", "info")
    if command_exists("uv"):  # Use common version
        log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' is already installed.", "info")
        try:
            run_command(["uv", "--version"], capture_output=True, current_logger=outer_logger)
        except Exception:
            pass
        return True

    log_prereq(f"{SYMBOLS_OUTER.get('info', '>>')} 'uv' not found in PATH. Attempting installation...", "info")
    # Use common version of get_debian_codename, passing the logger
    codename = get_debian_codename(current_logger=outer_logger)

    if codename in ["trixie", "forky", "sid"]:
        log_prereq(f"{SYMBOLS_OUTER.get('package', '>>')} Debian '{codename}' detected. Attempting 'apt install uv'...",
                   "info")
        try:
            run_elevated_command(["apt", "update"], current_logger=outer_logger)
            run_elevated_command(["apt", "install", "-y", "uv"], current_logger=outer_logger)
            log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' installed successfully via apt.", "info")
            return True
        except Exception as e:
            log_prereq(
                f"{SYMBOLS_OUTER.get('warning', '!!')} Failed to install 'uv' via apt on '{codename}': {e}. Falling back to pipx.",
                "warning")
            return _install_uv_with_pipx_prereq()
    else:
        log_prereq(
            f"{SYMBOLS_OUTER.get('package', '>>')} OS '{codename if codename else 'Unknown'}' detected. Using pipx to install 'uv'.",
            "info")
        return _install_uv_with_pipx_prereq()


def ensure_pg_config_or_libpq_dev_installed_prereq() -> bool:
    log_prereq(f"{SYMBOLS_OUTER.get('step', '->')} Checking for 'pg_config' (for psycopg compilation)...", "info")
    if command_exists("pg_config"):  # Use common version
        log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} 'pg_config' is available.", "info")
        return True
    log_prereq(f"{SYMBOLS_OUTER.get('warning', '!!')} 'pg_config' not found. Attempting to install 'libpq-dev'...",
               "warning")
    if not command_exists("apt"):  # Use common version
        log_prereq(f"{SYMBOLS_OUTER.get('error', '!!')} 'apt' not found. Cannot install 'libpq-dev'.", "error")
        return False
    try:
        run_elevated_command(["apt", "update"], capture_output=True, current_logger=outer_logger)
        run_elevated_command(["apt", "install", "-y", "libpq-dev"], capture_output=True, current_logger=outer_logger)
        if command_exists("pg_config"):  # Use common version
            log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} 'pg_config' now available after 'libpq-dev' install.",
                       "info")
            return True
        else:
            log_prereq(f"{SYMBOLS_OUTER.get('error', '!!')} 'libpq-dev' installed, but 'pg_config' still not found.",
                       "error")
            return False
    except Exception as e:
        log_prereq(f"{SYMBOLS_OUTER.get('error', '!!')} Failed to install 'libpq-dev' via apt: {e}", "error")
        return False


def get_venv_python_executable(project_root: str, venv_dir_name: str) -> str:
    return os.path.join(project_root, venv_dir_name, "bin", "python3")


def main() -> int:
    script_name = os.path.basename(sys.argv[0])
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)

    install_py_help_text = f"""
Usage: {script_name} [--help] <action_flag> [arguments_for_main_map_server_entry]

Prerequisite installer for the Map Server Setup.
This script performs the following actions:
1. Ensures 'uv' (Python packager and virtual environment manager) is installed.
2. Ensures 'libpq-dev' (for 'pg_config') is installed.
3. Creates a virtual environment in '{VENV_DIR}' using 'uv venv'.
4. Installs project dependencies from 'pyproject.toml' into the venv.
5. Based on the <action_flag>, proceeds to the main setup or exits.

Action Flags (mutually exclusive, one is required):
  --continue-install     After prerequisite and venv setup, run the main map server setup.
  --exit-on-complete     Exit successfully after prerequisite and venv setup.

Options for this script ({script_name}):
  -h, --help             Show this combined help message and exit.

Arguments for {MAP_SERVER_INSTALLER_NAME} (passed if --continue-install is used):
  (Displayed below if accessible)
"""

    if "--help" in sys.argv or "-h" in sys.argv:
        print(install_py_help_text)
        print("\n" + "=" * 80)
        print(f"Help information for the main setup module ({MAP_SERVER_INSTALLER_NAME}):")
        print("=" * 80)
        try:
            help_cmd_args = [sys.executable, "-m", MAP_SERVER_INSTALLER_NAME, "--help"]
            subprocess.run(help_cmd_args, check=False, cwd=project_root)
        except Exception as e_main_help:
            log_prereq(
                f"{SYMBOLS_OUTER.get('error', '!!')} Error trying to display help from {MAP_SERVER_INSTALLER_NAME}: {e_main_help}",
                "error")
            print(
                f"Could not display help from {MAP_SERVER_INSTALLER_NAME}. Its dependencies might need to be installed first via --continue-install.")
        return 0

    continue_install_flag = "--continue-install" in sys.argv
    exit_on_complete_flag = "--exit-on-complete" in sys.argv

    if not continue_install_flag and not exit_on_complete_flag:
        log_prereq(f"{SYMBOLS_OUTER.get('error', '!!')} Error: Specify --continue-install or --exit-on-complete.",
                   "critical")
        print(f"\nRun '{script_name} --help' for details.")
        return 1
    if continue_install_flag and exit_on_complete_flag:
        log_prereq(
            f"{SYMBOLS_OUTER.get('error', '!!')} Error: --continue-install and --exit-on-complete are mutually exclusive.",
            "critical")
        return 1

    if not install_uv_prereq():
        log_prereq(f"{SYMBOLS_OUTER.get('critical', '!!')} Failed to install 'uv'. Critical prerequisite. Aborting.",
                   "critical")
        return 1
    if not command_exists("uv"):  # Use common version
        log_prereq(f"{SYMBOLS_OUTER.get('critical', '!!')} 'uv' not found in PATH after install attempt. Aborting.",
                   "critical")
        return 1
    log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' command is available.", "info")

    if not ensure_pg_config_or_libpq_dev_installed_prereq():
        log_prereq(
            f"{SYMBOLS_OUTER.get('critical', '!!')} Failed to ensure 'pg_config' (via 'libpq-dev'). Python DB drivers may fail to build. Aborting.",
            "critical")
        return 1

    venv_path = os.path.join(project_root, VENV_DIR)
    venv_python_executable = get_venv_python_executable(project_root, VENV_DIR)

    log_prereq(f"{SYMBOLS_OUTER.get('step', '->')} Setting up virtual environment in '{venv_path}'...", "info")
    try:
        run_command(["uv", "venv", VENV_DIR, "--python", sys.executable], cwd=project_root, current_logger=outer_logger)
        log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} Virtual environment created at '{venv_path}'.", "info")

        log_prereq(f"{SYMBOLS_OUTER.get('package', '>>')} Installing project dependencies into '{VENV_DIR}'...", "info")
        run_command(["uv", "pip", "install", "."], cwd=project_root, current_logger=outer_logger)
        log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} Project dependencies installed into '{VENV_DIR}'.", "info")
    except Exception as e:
        log_prereq(
            f"{SYMBOLS_OUTER.get('critical', '!!')} Failed to set up virtual environment or install dependencies: {e}",
            "critical")
        return 1

    if exit_on_complete_flag:
        log_prereq(
            f"{SYMBOLS_OUTER.get('success', 'OK')} {SYMBOLS_OUTER.get('sparkles', '**')} Prerequisite and venv setup complete. Exiting.",
            "info")
        return 0

    if continue_install_flag:
        log_prereq(
            f"{SYMBOLS_OUTER.get('step', '->')} Proceeding to main map server setup using '{venv_python_executable}'...",
            "info")

        args_for_main_installer = [
            arg for arg in sys.argv[1:]
            if arg not in ["--continue-install", "--exit-on-complete"]
        ]

        cmd_to_run_main_installer = [venv_python_executable, "-m", MAP_SERVER_INSTALLER_NAME] + args_for_main_installer
        log_prereq(f"{SYMBOLS_OUTER.get('link', '>>')} Launching: {' '.join(cmd_to_run_main_installer)}", "info")
        try:
            # Use run_command from common_utils
            process_result = run_command(cmd_to_run_main_installer, check=False, cwd=project_root,
                                         current_logger=outer_logger)
            result_code = process_result.returncode
            if result_code == 0:
                log_prereq(
                    f"{SYMBOLS_OUTER.get('success', 'OK')} {SYMBOLS_OUTER.get('sparkles', '**')} Main map server setup ({MAP_SERVER_INSTALLER_NAME}) reported success!",
                    "info")
            else:
                log_prereq(
                    f"{SYMBOLS_OUTER.get('error', '!!')} Main map server setup ({MAP_SERVER_INSTALLER_NAME}) reported failure or no action (exit code {result_code}).",
                    "error")
            return result_code
        except Exception as e:
            log_prereq(f"{SYMBOLS_OUTER.get('critical', '!!')} Unexpected error launching main map server setup: {e}",
                       "critical")
            return 1
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        if not outer_logger.handlers:
            _handler_kb = logging.StreamHandler(sys.stdout)
            _formatter_kb = logging.Formatter("[PREREQ-INSTALL] %(asctime)s - %(levelname)s - %(message)s",
                                              datefmt="%Y-%m-%d %H:%M:%S")
            _handler_kb.setFormatter(_formatter_kb)
            outer_logger.addHandler(_handler_kb)
            outer_logger.setLevel(logging.INFO)
        log_prereq(f"\n{SYMBOLS_OUTER.get('warning', '!!')} Prerequisite installation interrupted by user. Exiting.",
                   "warning")
        sys.exit(130)
    except SystemExit as e:
        sys.exit(e.code)
    except Exception as e_global:
        if not outer_logger.handlers:
            _handler_ex = logging.StreamHandler(sys.stdout)
            _formatter_ex = logging.Formatter("[PREREQ-INSTALL] %(asctime)s - %(levelname)s - %(message)s",
                                              datefmt="%Y-%m-%d %H:%M:%S")
            _handler_ex.setFormatter(_formatter_ex)
            outer_logger.addHandler(_handler_ex)
            outer_logger.setLevel(logging.INFO)
        log_prereq(
            f"{SYMBOLS_OUTER.get('critical', '!!')} A critical unhandled error occurred in prerequisite installer: {e_global}",
            "critical")
        import traceback

        outer_logger.error(traceback.format_exc())
        sys.exit(1)