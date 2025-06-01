#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prerequisite installer for the Map Server Setup.

Ensures 'uv' (Python packager and virtual environment manager) is installed,
then creates a virtual environment, installs project dependencies,
and calls the main map server setup script, passing along all arguments.
"""

import getpass
import logging  # Keep logging import
import os

# import shutil # No longer directly needed
import subprocess
import sys

# Common utility imports
from common.command_utils import (
    command_exists,
    log_map_server,  # Import log_map_server
    run_command,
    run_elevated_command,
)
from common.core_utils import (
    setup_logging as common_setup_logging,  # New import
)
from common.system_utils import get_debian_codename

MAP_SERVER_INSTALLER_NAME = "installer.main_installer"
VENV_DIR = ".venv"

# SYMBOLS_OUTER can be merged with common config.SYMBOLS or kept if specific icons are needed
# For simplicity, let's assume we'll use config.SYMBOLS from the main app via log_map_server
# If not, this SYMBOLS_OUTER would need to be passed into log_map_server or have log_prereq reinstated.
# For now, log_map_server uses config.SYMBOLS internally.
SYMBOLS_OUTER = {  # This will be used directly in f-strings if log_map_server doesn't cover all cases
    "success": "✅", "error": "❌", "warning": "⚠️", "info": "ℹ️",
    "step": "➡️", "gear": "⚙️", "package": "📦", "rocket": "🚀",
    "sparkles": "✨", "critical": "🔥", "link": "🔗",
    "python": "🐍"
}


# REMOVE: outer_logger definition, handler, and formatter setup.
# REMOVE: log_prereq function. Logging will be done via common_setup_logging + log_map_server.

# Functions like ensure_pip_installed_prereq, _install_uv_with_pipx_prereq etc.
# will now use log_map_server for their logging.

def ensure_pip_installed_prereq(logger_instance: logging.Logger) -> bool:
    log_map_server(
        f"{SYMBOLS_OUTER.get('step', '->')} {SYMBOLS_OUTER.get('python', '🐍')} Checking for 'pip' command...",
        "info", current_logger=logger_instance)
    if command_exists("pip3") or command_exists("pip"):
        pip_cmd = "pip3" if command_exists("pip3") else "pip"
        log_map_server(f"{SYMBOLS_OUTER.get('success', 'OK')} '{pip_cmd}' command is already available.", "info",
                       current_logger=logger_instance)
        return True
    log_map_server(
        f"{SYMBOLS_OUTER.get('warning', '!!')} 'pip' command not found. Attempting to install 'python3-pip'...",
        "warning", current_logger=logger_instance)
    if not command_exists("apt"):
        log_map_server(f"{SYMBOLS_OUTER.get('error', '!!')} 'apt' command not found. Please install pip manually.",
                       "error", current_logger=logger_instance)
        return False
    try:
        log_map_server(f"{SYMBOLS_OUTER.get('gear', '>>')} Updating apt cache...", "info",
                       current_logger=logger_instance)
        run_elevated_command(["apt", "update"], capture_output=True, current_logger=logger_instance)
        log_map_server(f"{SYMBOLS_OUTER.get('package', '>>')} Attempting to install 'python3-pip' using apt...", "info",
                       current_logger=logger_instance)
        run_elevated_command(["apt", "install", "-y", "python3-pip"], capture_output=True,
                             current_logger=logger_instance)

        if command_exists("pip3") or command_exists("pip"):
            log_map_server(f"{SYMBOLS_OUTER.get('success', 'OK')} 'pip' (or 'pip3') command is now available.", "info",
                           current_logger=logger_instance)
            return True
        else:  # pragma: no cover
            log_map_server(
                f"{SYMBOLS_OUTER.get('warning', '!!')} 'python3-pip' installed, but 'pip'/'pip3' not immediately in PATH.",
                "warning", current_logger=logger_instance)
            return True  # It might be found by subsequent steps or after shell reload
    except Exception as e:
        log_map_server(f"{SYMBOLS_OUTER.get('error', '!!')} Failed to install 'python3-pip' via apt: {e}", "error",
                       current_logger=logger_instance)
        return False


def _install_uv_with_pipx_prereq(logger_instance: logging.Logger) -> bool:
    log_map_server(f"{SYMBOLS_OUTER.get('info', '>>')} Attempting uv installation using pipx...", "info",
                   current_logger=logger_instance)

    if not command_exists("pipx"):
        log_map_server(f"{SYMBOLS_OUTER.get('warning', '!!')} pipx not found. Attempting to install pipx...",
                       "warning", current_logger=logger_instance)
        try:
            if not ensure_pip_installed_prereq(logger_instance):  # Pass logger
                log_map_server(
                    f"{SYMBOLS_OUTER.get('error', '!!')} pip is required to install pipx if apt method fails. Aborting pipx install.",
                    "error", current_logger=logger_instance)
                return False

            if command_exists("apt"):
                try:
                    run_elevated_command(["apt", "update"], current_logger=logger_instance)
                    run_elevated_command(["apt", "install", "-y", "pipx"], current_logger=logger_instance)
                    log_map_server(f"{SYMBOLS_OUTER.get('success', 'OK')} pipx installed successfully via apt.", "info",
                                   current_logger=logger_instance)
                except Exception:  # pragma: no cover
                    log_map_server(
                        f"{SYMBOLS_OUTER.get('warning', '!!')} Failed to install pipx via apt. Trying pip...",
                        "warning", current_logger=logger_instance)

            if not command_exists("pipx"):  # pragma: no cover
                pip_cmd = "pip3" if command_exists("pip3") else "pip"
                run_command([sys.executable, "-m", pip_cmd, "install", "--user", "pipx"],
                            current_logger=logger_instance)
                run_command([sys.executable, "-m", "pipx", "ensurepath"], current_logger=logger_instance)
                log_map_server(
                    f"{SYMBOLS_OUTER.get('success', 'OK')} pipx installed for current user using {pip_cmd}. You may need to source your shell profile or open a new terminal.",
                    "info", current_logger=logger_instance)
        except Exception as e:  # pragma: no cover
            log_map_server(f"{SYMBOLS_OUTER.get('error', '!!')} Failed to install pipx: {e}", "error",
                           current_logger=logger_instance)
            return False

    pipx_bin_dir = os.path.expanduser("~/.local/bin")
    current_path = os.environ.get("PATH", "")
    if pipx_bin_dir not in current_path.split(os.pathsep):  # pragma: no cover
        log_map_server(
            f"{SYMBOLS_OUTER.get('gear', '>>')} Adding '{pipx_bin_dir}' to PATH for current script session...",
            "info", current_logger=logger_instance)
        os.environ["PATH"] = f"{pipx_bin_dir}{os.pathsep}{current_path}"
        log_map_server(f"   New temporary PATH: {os.environ['PATH']}", "debug",
                       current_logger=logger_instance)  # Debug for path
        if not command_exists("pipx"):
            log_map_server(
                f"{SYMBOLS_OUTER.get('error', '!!')} pipx installed, but still not found in PATH. Manual PATH adjustment may be needed.",
                "error", current_logger=logger_instance)
            return False

    log_map_server(
        f"{SYMBOLS_OUTER.get('rocket', '>>')} Attempting to install/upgrade 'uv' with pipx (as user '{getpass.getuser()}')...",
        "info", current_logger=logger_instance)
    try:
        run_command(["pipx", "install", "uv"], capture_output=True, current_logger=logger_instance)
        log_map_server(f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' installed/upgraded successfully using pipx.", "info",
                       current_logger=logger_instance)
        return True
    except Exception as e:
        log_map_server(f"{SYMBOLS_OUTER.get('error', '!!')} Failed to install 'uv' using pipx: {e}", "error",
                       current_logger=logger_instance)
        return False


def install_uv_prereq(logger_instance: logging.Logger) -> bool:
    log_map_server(f"{SYMBOLS_OUTER.get('step', '->')} Checking for 'uv' installation...", "info",
                   current_logger=logger_instance)
    if command_exists("uv"):
        log_map_server(f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' is already installed.", "info",
                       current_logger=logger_instance)
        try:
            run_command(["uv", "--version"], capture_output=True, current_logger=logger_instance)
        except Exception:  # pragma: no cover
            pass
        return True

    log_map_server(f"{SYMBOLS_OUTER.get('info', '>>')} 'uv' not found in PATH. Attempting installation...", "info",
                   current_logger=logger_instance)
    codename = get_debian_codename(current_logger=logger_instance)

    if codename in ["trixie", "forky", "sid"]:  # pragma: no cover
        log_map_server(
            f"{SYMBOLS_OUTER.get('package', '>>')} Debian '{codename}' detected. Attempting 'apt install uv'...",
            "info", current_logger=logger_instance)
        try:
            run_elevated_command(["apt", "update"], current_logger=logger_instance)
            run_elevated_command(["apt", "install", "-y", "uv"], current_logger=logger_instance)
            log_map_server(f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' installed successfully via apt.", "info",
                           current_logger=logger_instance)
            return True
        except Exception as e:
            log_map_server(
                f"{SYMBOLS_OUTER.get('warning', '!!')} Failed to install 'uv' via apt on '{codename}': {e}. Falling back to pipx.",
                "warning", current_logger=logger_instance)
            return _install_uv_with_pipx_prereq(logger_instance)  # Pass logger
    else:
        log_map_server(
            f"{SYMBOLS_OUTER.get('package', '>>')} OS '{codename if codename else 'Unknown'}' detected. Using pipx to install 'uv'.",
            "info", current_logger=logger_instance)
        return _install_uv_with_pipx_prereq(logger_instance)  # Pass logger


def ensure_pg_config_or_libpq_dev_installed_prereq(logger_instance: logging.Logger) -> bool:
    log_map_server(f"{SYMBOLS_OUTER.get('step', '->')} Checking for 'pg_config' (for psycopg compilation)...", "info",
                   current_logger=logger_instance)
    if command_exists("pg_config"):
        log_map_server(f"{SYMBOLS_OUTER.get('success', 'OK')} 'pg_config' is available.", "info",
                       current_logger=logger_instance)
        return True
    log_map_server(f"{SYMBOLS_OUTER.get('warning', '!!')} 'pg_config' not found. Attempting to install 'libpq-dev'...",
                   "warning", current_logger=logger_instance)
    if not command_exists("apt"):  # pragma: no cover
        log_map_server(f"{SYMBOLS_OUTER.get('error', '!!')} 'apt' not found. Cannot install 'libpq-dev'.", "error",
                       current_logger=logger_instance)
        return False
    try:
        run_elevated_command(["apt", "update"], capture_output=True, current_logger=logger_instance)
        run_elevated_command(["apt", "install", "-y", "libpq-dev"], capture_output=True, current_logger=logger_instance)
        if command_exists("pg_config"):
            log_map_server(f"{SYMBOLS_OUTER.get('success', 'OK')} 'pg_config' now available after 'libpq-dev' install.",
                           "info", current_logger=logger_instance)
            return True
        else:  # pragma: no cover
            log_map_server(
                f"{SYMBOLS_OUTER.get('error', '!!')} 'libpq-dev' installed, but 'pg_config' still not found.",
                "error", current_logger=logger_instance)
            return False
    except Exception as e:  # pragma: no cover
        log_map_server(f"{SYMBOLS_OUTER.get('error', '!!')} Failed to install 'libpq-dev' via apt: {e}", "error",
                       current_logger=logger_instance)
        return False


def get_venv_python_executable(project_root: str, venv_dir_name: str) -> str:
    return os.path.join(project_root, venv_dir_name, "bin", "python3")


def main() -> int:
    # Setup logging for this script using the common utility
    # This will be the first effective logging setup.
    common_setup_logging(
        log_level=logging.INFO,
        log_to_console=True,
        log_prefix="[PREREQ-INSTALL]"
    )
    # Get a named logger for this script to use with log_map_server
    # This ensures %(name)s in the log format shows "PrereqInstaller"
    prereq_script_logger = logging.getLogger("PrereqInstaller")

    script_name = os.path.basename(sys.argv[0])
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)  # For fetching main_installer help

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
            # Use subprocess.run directly as _run_cmd_prereq is removed
            subprocess.run(help_cmd_args, check=False, cwd=project_root)
        except Exception as e_main_help:
            log_map_server(
                f"{SYMBOLS_OUTER.get('error', '!!')} Error trying to display help from {MAP_SERVER_INSTALLER_NAME}: {e_main_help}",
                "error", current_logger=prereq_script_logger)
            print(
                f"Could not display help from {MAP_SERVER_INSTALLER_NAME}. Its dependencies might need to be installed first via --continue-install.")
        return 0

    continue_install_flag = "--continue-install" in sys.argv
    exit_on_complete_flag = "--exit-on-complete" in sys.argv

    if not continue_install_flag and not exit_on_complete_flag:
        log_map_server(f"{SYMBOLS_OUTER.get('error', '!!')} Error: Specify --continue-install or --exit-on-complete.",
                       "critical", current_logger=prereq_script_logger)
        print(f"\nRun '{script_name} --help' for details.")
        return 1
    if continue_install_flag and exit_on_complete_flag:  # pragma: no cover
        log_map_server(
            f"{SYMBOLS_OUTER.get('error', '!!')} Error: --continue-install and --exit-on-complete are mutually exclusive.",
            "critical", current_logger=prereq_script_logger)
        return 1

    if not install_uv_prereq(prereq_script_logger):  # Pass logger
        log_map_server(
            f"{SYMBOLS_OUTER.get('critical', '!!')} Failed to install 'uv'. Critical prerequisite. Aborting.",
            "critical", current_logger=prereq_script_logger)
        return 1
    if not command_exists("uv"):  # pragma: no cover
        log_map_server(f"{SYMBOLS_OUTER.get('critical', '!!')} 'uv' not found in PATH after install attempt. Aborting.",
                       "critical", current_logger=prereq_script_logger)
        return 1
    log_map_server(f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' command is available.", "info",
                   current_logger=prereq_script_logger)

    if not ensure_pg_config_or_libpq_dev_installed_prereq(prereq_script_logger):  # Pass logger
        log_map_server(
            f"{SYMBOLS_OUTER.get('critical', '!!')} Failed to ensure 'pg_config' (via 'libpq-dev'). Python DB drivers may fail to build. Aborting.",
            "critical", current_logger=prereq_script_logger)
        return 1

    venv_path = os.path.join(project_root, VENV_DIR)
    venv_python_executable = get_venv_python_executable(project_root, VENV_DIR)

    log_map_server(f"{SYMBOLS_OUTER.get('step', '->')} Setting up virtual environment in '{venv_path}'...", "info",
                   current_logger=prereq_script_logger)
    try:
        run_command(["uv", "venv", VENV_DIR, "--python", sys.executable], cwd=project_root,
                    current_logger=prereq_script_logger)
        log_map_server(f"{SYMBOLS_OUTER.get('success', 'OK')} Virtual environment created at '{venv_path}'.", "info",
                       current_logger=prereq_script_logger)

        log_map_server(f"{SYMBOLS_OUTER.get('package', '>>')} Installing project dependencies into '{VENV_DIR}'...",
                       "info", current_logger=prereq_script_logger)
        run_command(["uv", "pip", "install", "."], cwd=project_root, current_logger=prereq_script_logger)
        log_map_server(f"{SYMBOLS_OUTER.get('success', 'OK')} Project dependencies installed into '{VENV_DIR}'.",
                       "info", current_logger=prereq_script_logger)
    except Exception as e:
        log_map_server(
            f"{SYMBOLS_OUTER.get('critical', '!!')} Failed to set up virtual environment or install dependencies: {e}",
            "critical", current_logger=prereq_script_logger)
        return 1

    if exit_on_complete_flag:
        log_map_server(
            f"{SYMBOLS_OUTER.get('success', 'OK')} {SYMBOLS_OUTER.get('sparkles', '**')} Prerequisite and venv setup complete. Exiting.",
            "info", current_logger=prereq_script_logger)
        return 0

    if continue_install_flag:
        log_map_server(
            f"{SYMBOLS_OUTER.get('step', '->')} Proceeding to main map server setup using '{venv_python_executable}'...",
            "info", current_logger=prereq_script_logger)

        args_for_main_installer = [
            arg for arg in sys.argv[1:]
            if arg not in ["--continue-install", "--exit-on-complete"]
        ]

        cmd_to_run_main_installer = [venv_python_executable, "-m", MAP_SERVER_INSTALLER_NAME] + args_for_main_installer
        log_map_server(f"{SYMBOLS_OUTER.get('link', '>>')} Launching: {' '.join(cmd_to_run_main_installer)}", "debug",
                       current_logger=prereq_script_logger)  # Debug for launch command
        try:
            process_result = run_command(cmd_to_run_main_installer, check=False, cwd=project_root,
                                         current_logger=prereq_script_logger)
            result_code = process_result.returncode
            if result_code == 0:
                log_map_server(
                    f"{SYMBOLS_OUTER.get('success', 'OK')} {SYMBOLS_OUTER.get('sparkles', '**')} Main map server setup ({MAP_SERVER_INSTALLER_NAME}) reported success!",
                    "info", current_logger=prereq_script_logger)
            else:
                log_map_server(
                    f"{SYMBOLS_OUTER.get('error', '!!')} Main map server setup ({MAP_SERVER_INSTALLER_NAME}) reported failure or no action (exit code {result_code}).",
                    "error", current_logger=prereq_script_logger)
            return result_code
        except Exception as e:  # pragma: no cover
            log_map_server(
                f"{SYMBOLS_OUTER.get('critical', '!!')} Unexpected error launching main map server setup: {e}",
                "critical", current_logger=prereq_script_logger)
            return 1
    return 1  # Should not be reached


if __name__ == "__main__":  # pragma: no cover
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        # Ensure logger is available for this final message if interrupted early
        # This minimal setup is a last resort if main() didn't even start common_setup_logging
        temp_logger_ki = logging.getLogger("PrereqInstaller")
        if not temp_logger_ki.handlers:
            _handler_kb = logging.StreamHandler(sys.stderr)  # To stderr for interrupts
            _formatter_kb = logging.Formatter("[PREREQ-INSTALL] %(asctime)s - %(levelname)s - %(message)s",
                                              datefmt="%Y-%m-%d %H:%M:%S")
            _handler_kb.setFormatter(_formatter_kb)
            temp_logger_ki.addHandler(_handler_kb)
            temp_logger_ki.setLevel(logging.INFO)
        temp_logger_ki.warning(
            f"\n{SYMBOLS_OUTER.get('warning', '!!')} Prerequisite installation interrupted by user. Exiting.")
        sys.exit(130)
    except SystemExit as e:
        sys.exit(e.code)
    except Exception as e_global:
        temp_logger_ex = logging.getLogger("PrereqInstaller")
        if not temp_logger_ex.handlers:
            _handler_ex = logging.StreamHandler(sys.stderr)
            _formatter_ex = logging.Formatter("[PREREQ-INSTALL] %(asctime)s - %(levelname)s - %(message)s",
                                              datefmt="%Y-%m-%d %H:%M:%S")
            _handler_ex.setFormatter(_formatter_ex)
            temp_logger_ex.addHandler(_handler_ex)
            temp_logger_ex.setLevel(logging.INFO)
        temp_logger_ex.critical(
            f"{SYMBOLS_OUTER.get('critical', '!!')} A critical unhandled error occurred in prerequisite installer: {e_global}"
        )
        import traceback

        temp_logger_ex.error(traceback.format_exc())
        sys.exit(1)