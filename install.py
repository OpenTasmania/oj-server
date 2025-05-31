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
import shutil
import subprocess
import sys
from typing import List, Optional

MAP_SERVER_INSTALLER_NAME = "installer.main_installer"
VENV_DIR = ".venv"

SYMBOLS_OUTER = {
    "success": "✅", "error": "❌", "warning": "⚠️", "info": "ℹ️",
    "step": "➡️", "gear": "⚙️", "package": "📦", "rocket": "🚀",
    "sparkles": "✨", "critical": "🔥", "link": "🔗",
    # Add a python symbol if missing from your config or use a generic one
    "python": "🐍"
}

outer_logger = logging.getLogger("PrereqInstaller")
outer_logger.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stdout)  # Changed to stdout for consistency with main logger
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


def _get_elevated_prefix_prereq() -> List[str]:
    return [] if os.geteuid() == 0 else ["sudo"]


def _run_cmd_prereq(
        command: List[str], check: bool = True, capture_output: bool = False,
        text: bool = True, cmd_input: Optional[str] = None, cwd: Optional[str] = None,
) -> subprocess.CompletedProcess:
    log_prereq(
        f"{SYMBOLS_OUTER.get('gear', '>>')} Executing: {' '.join(command)} "
        f"{f'(in {cwd})' if cwd else ''}", "info",
    )
    try:
        result = subprocess.run(
            command, check=check, capture_output=capture_output, text=text,
            input=cmd_input, cwd=cwd,
        )
        if capture_output and result.stdout and result.stdout.strip() and result.returncode == 0:
            log_prereq(f"   stdout: {result.stdout.strip()}", "info")
        if capture_output and result.stderr and result.stderr.strip() and result.returncode == 0:
            # Some commands use stderr for info, log as info if successful
            log_prereq(f"   stderr: {result.stderr.strip()}", "info")
        return result
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip() if e.stderr else (e.stdout.strip() if e.stdout else str(e))
        log_prereq(
            f"{SYMBOLS_OUTER.get('error', '!!')} Command `{' '.join(e.cmd)}` failed (rc {e.returncode}). Error: {err_msg}",
            "error")
        raise
    except FileNotFoundError as e:
        log_prereq(f"{SYMBOLS_OUTER.get('error', '!!')} Command not found: {e.filename}. Is it installed and in PATH?",
                   "error")
        raise
    except Exception as e:
        log_prereq(f"{SYMBOLS_OUTER.get('error', '!!')} Unexpected error running command `{' '.join(command)}`: {e}",
                   "error")
        raise


def command_exists_prereq(command: str) -> bool:
    return shutil.which(command) is not None


def get_debian_codename_prereq() -> Optional[str]:
    if not command_exists_prereq("lsb_release"):
        log_prereq(
            f"{SYMBOLS_OUTER.get('warning', '!!')} lsb_release command not found. Cannot determine Debian codename.",
            "warning")
        return None
    try:
        result = _run_cmd_prereq(["lsb_release", "-cs"], capture_output=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        log_prereq(f"{SYMBOLS_OUTER.get('warning', '!!')} Could not determine Debian codename: {e}", "warning")
        return None


def ensure_pip_installed_prereq() -> bool:
    log_prereq(f"{SYMBOLS_OUTER.get('step', '->')} {SYMBOLS_OUTER.get('python', '🐍')} Checking for 'pip' command...",
               "info")
    if command_exists_prereq("pip3") or command_exists_prereq("pip"):  # Check for pip3 as well
        pip_cmd = "pip3" if command_exists_prereq("pip3") else "pip"
        log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} '{pip_cmd}' command is already available.", "info")
        return True
    log_prereq(f"{SYMBOLS_OUTER.get('warning', '!!')} 'pip' command not found. Attempting to install 'python3-pip'...",
               "warning")
    if not command_exists_prereq("apt"):
        log_prereq(f"{SYMBOLS_OUTER.get('error', '!!')} 'apt' command not found. Please install pip manually.", "error")
        return False
    apt_prefix = _get_elevated_prefix_prereq()
    try:
        log_prereq(f"{SYMBOLS_OUTER.get('gear', '>>')} Updating apt cache...", "info")
        _run_cmd_prereq(apt_prefix + ["apt", "update"], capture_output=True)
        log_prereq(f"{SYMBOLS_OUTER.get('package', '>>')} Attempting to install 'python3-pip' using apt...", "info")
        _run_cmd_prereq(apt_prefix + ["apt", "install", "-y", "python3-pip"], capture_output=True)
        if command_exists_prereq("pip3") or command_exists_prereq("pip"):
            log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} 'pip' (or 'pip3') command is now available.", "info")
            return True
        else:
            log_prereq(
                f"{SYMBOLS_OUTER.get('warning', '!!')} 'python3-pip' installed, but 'pip'/'pip3' not immediately in PATH.",
                "warning")
            return True  # Often okay, pipx or other tools might find it
    except Exception as e:
        log_prereq(f"{SYMBOLS_OUTER.get('error', '!!')} Failed to install 'python3-pip' via apt: {e}", "error")
        return False


def _install_uv_with_pipx_prereq() -> bool:
    log_prereq(f"{SYMBOLS_OUTER.get('info', '>>')} Attempting uv installation using pipx...", "info")
    pipx_installed_by_this_script = False
    apt_prefix = _get_elevated_prefix_prereq()

    if not command_exists_prereq("pipx"):
        log_prereq(f"{SYMBOLS_OUTER.get('warning', '!!')} pipx not found. Attempting to install pipx via apt...",
                   "warning")
        try:
            # Ensure pip is available before trying to install pipx with it, if apt fails
            if not ensure_pip_installed_prereq():  # Ensure pip is there
                log_prereq(
                    f"{SYMBOLS_OUTER.get('error', '!!')} pip is required to install pipx if apt method fails. Aborting pipx install.",
                    "error")
                return False

            # First try apt for pipx (common on newer systems)
            if command_exists_prereq("apt"):
                try:
                    _run_cmd_prereq(apt_prefix + ["apt", "update"])  # Update if not done recently
                    _run_cmd_prereq(apt_prefix + ["apt", "install", "-y", "pipx"])
                    log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} pipx installed successfully via apt.", "info")
                    pipx_installed_by_this_script = True
                except Exception:
                    log_prereq(f"{SYMBOLS_OUTER.get('warning', '!!')} Failed to install pipx via apt. Trying pip...",
                               "warning")

            if not command_exists_prereq("pipx"):  # If apt install failed or wasn't available
                pip_cmd = "pip3" if command_exists_prereq("pip3") else "pip"
                # Install for the current user using pip
                _run_cmd_prereq([sys.executable, "-m", pip_cmd, "install", "--user", "pipx"])
                _run_cmd_prereq([sys.executable, "-m", "pipx", "ensurepath"])  # Add pipx path to user's PATH
                log_prereq(
                    f"{SYMBOLS_OUTER.get('success', 'OK')} pipx installed for current user using {pip_cmd}. You may need to source your shell profile or open a new terminal.",
                    "info")
                pipx_installed_by_this_script = True  # Even if by user pip
        except Exception as e:
            log_prereq(f"{SYMBOLS_OUTER.get('error', '!!')} Failed to install pipx: {e}", "error")
            return False

    # Add pipx binary dir to PATH for current session if it was just installed by user pip
    # This is crucial if pipx was installed via `pip install --user pipx`
    # and its bin dir isn't yet in the PATH for *this script's session*.
    pipx_bin_dir = os.path.expanduser("~/.local/bin")
    current_path = os.environ.get("PATH", "")
    if pipx_bin_dir not in current_path.split(os.pathsep):
        log_prereq(f"{SYMBOLS_OUTER.get('gear', '>>')} Adding '{pipx_bin_dir}' to PATH for current script session...",
                   "info")
        os.environ["PATH"] = f"{pipx_bin_dir}{os.pathsep}{current_path}"
        log_prereq(f"   New temporary PATH: {os.environ['PATH']}", "info")
        # Re-check if pipx is now found after path modification
        if not command_exists_prereq("pipx"):
            log_prereq(
                f"{SYMBOLS_OUTER.get('error', '!!')} pipx installed, but still not found in PATH. Manual PATH adjustment may be needed.",
                "error")
            return False

    log_prereq(
        f"{SYMBOLS_OUTER.get('rocket', '>>')} Attempting to install/upgrade 'uv' with pipx (as user '{getpass.getuser()}')...",
        "info")
    try:
        _run_cmd_prereq(["pipx", "install", "uv"], capture_output=True)
        log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' installed/upgraded successfully using pipx.", "info")
        return True
    except Exception as e:
        log_prereq(f"{SYMBOLS_OUTER.get('error', '!!')} Failed to install 'uv' using pipx: {e}", "error")
        return False


def install_uv_prereq() -> bool:
    log_prereq(f"{SYMBOLS_OUTER.get('step', '->')} Checking for 'uv' installation...", "info")
    if command_exists_prereq("uv"):
        log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' is already installed.", "info")
        try:
            _run_cmd_prereq(["uv", "--version"], capture_output=True)
        except Exception:
            pass
        return True

    log_prereq(f"{SYMBOLS_OUTER.get('info', '>>')} 'uv' not found in PATH. Attempting installation...", "info")
    codename = get_debian_codename_prereq()
    apt_prefix = _get_elevated_prefix_prereq()

    if codename in ["trixie", "forky", "sid"]:  # Debian Trixie (13), Forky (Dev), Sid (Unstable) might have uv
        log_prereq(f"{SYMBOLS_OUTER.get('package', '>>')} Debian '{codename}' detected. Attempting 'apt install uv'...",
                   "info")
        try:
            _run_cmd_prereq(apt_prefix + ["apt", "update"])
            _run_cmd_prereq(apt_prefix + ["apt", "install", "-y", "uv"])
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
    if command_exists_prereq("pg_config"):
        log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} 'pg_config' is available.", "info")
        return True
    log_prereq(f"{SYMBOLS_OUTER.get('warning', '!!')} 'pg_config' not found. Attempting to install 'libpq-dev'...",
               "warning")
    if not command_exists_prereq("apt"):
        log_prereq(f"{SYMBOLS_OUTER.get('error', '!!')} 'apt' not found. Cannot install 'libpq-dev'.", "error")
        return False
    apt_prefix = _get_elevated_prefix_prereq()
    try:
        _run_cmd_prereq(apt_prefix + ["apt", "update"], capture_output=True)
        _run_cmd_prereq(apt_prefix + ["apt", "install", "-y", "libpq-dev"], capture_output=True)
        if command_exists_prereq("pg_config"):
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
    return os.path.join(project_root, venv_dir_name, "bin", "python3")  # Prefer python3


def main() -> int:
    script_name = os.path.basename(sys.argv[0])
    project_root = os.path.dirname(os.path.abspath(__file__))

    # Add project root to Python path to help find setup.main_installer for --help
    # This is for the 'sys.executable -m setup.main_installer --help' call.
    # The main execution uses the venv Python, which handles its own paths.
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
            # Attempt to get help from main_installer using the Python that runs install.py
            # This might fail if main_installer has non-stdlib imports not in global site-packages
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
    if not command_exists_prereq("uv"):
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
        # Use the Python running install.py to create the venv with that version
        _run_cmd_prereq(["uv", "venv", VENV_DIR, "--python", sys.executable], cwd=project_root)
        log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} Virtual environment created at '{venv_path}'.", "info")

        log_prereq(f"{SYMBOLS_OUTER.get('package', '>>')} Installing project dependencies into '{VENV_DIR}'...", "info")
        # Use uv from PATH to install into the created venv
        _run_cmd_prereq(["uv", "pip", "install", "."],
                        cwd=project_root)  # uv automatically detects .venv if run from project_root
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

        # Filter out install.py specific arguments before passing to main_installer.py
        args_for_main_installer = [
            arg for arg in sys.argv[1:]
            if arg not in ["--continue-install", "--exit-on-complete"]
            # --help and -h are fine to pass if main_installer also has them,
            # or they will be caught by main_installer's argparse if not recognized.
        ]

        cmd_to_run_main_installer = [venv_python_executable, "-m", MAP_SERVER_INSTALLER_NAME] + args_for_main_installer
        log_prereq(f"{SYMBOLS_OUTER.get('link', '>>')} Launching: {' '.join(cmd_to_run_main_installer)}", "info")
        try:
            # Execute main_installer.py and let its exit code be the exit code of install.py
            # We use check=False because main_installer.py will return its own status code (0 for success, 1 for error, 2 for no action).
            # We want to propagate that specific status code.
            process_result = _run_cmd_prereq(cmd_to_run_main_installer, check=False, cwd=project_root)
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
    return 1  # Should not be reached if flags are handled correctly


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        # Ensure logger is available for this final message if interrupted early
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
    except SystemExit as e:  # Catch explicit sys.exit calls
        sys.exit(e.code)
    except Exception as e_global:
        if not outer_logger.handlers:  # Ensure logger for unexpected global errors
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