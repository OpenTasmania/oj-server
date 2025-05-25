#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prerequisite installer for the Map Server Setup.
Ensures 'uv' (Python packager and virtual environment manager) is installed,
then calls the main map server setup script, passing along all arguments.
"""

import getpass
import logging
import os
import shutil
import subprocess
import sys
from typing import List, Optional

from setup.main_installer import main_map_server_entry

# Define the name of the main installer module
MAP_SERVER_LAUNCHER_SCRIPT_NAME = "setup/main_installer.py"

# --- Basic Configuration & Symbols ---
SYMBOLS_OUTER = {
    "success": "✅", "error": "❌", "warning": "⚠️", "info": "ℹ️",
    "step": "➡️", "gear": "⚙️", "package": "📦", "rocket": "🚀",
    "sparkles": "✨", "critical": "🔥"
}

# --- Logger for this prerequisite installer script ---
outer_logger = logging.getLogger("PrereqInstaller")
outer_logger.setLevel(logging.INFO)
_handler = logging.StreamHandler(
    sys.stdout
)  # Renamed to avoid conflict if script is re-run in same session
_formatter = logging.Formatter(
    "[PREREQ-INSTALL] %(asctime)s - [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_handler.setFormatter(_formatter)
if not outer_logger.handlers:
    outer_logger.addHandler(_handler)
outer_logger.propagate = False


def log_prereq(message: str, level: str = "info"):
    """Log messages for this prerequisite installer script."""
    if level == "critical":
        outer_logger.critical(message)
    elif level == "error":
        outer_logger.error(message)
    elif level == "warning":
        outer_logger.warning(message)
    else:
        outer_logger.info(message)


# --- Command Execution Utilities (Simplified for this script) ---
def _get_elevated_prefix_prereq() -> List[str]:
    return [] if os.geteuid() == 0 else ["sudo"]


def _run_cmd_prereq(command: List[str], check: bool = True, capture_output: bool = False, text: bool = True,
                    cmd_input: Optional[str] = None) -> subprocess.CompletedProcess:
    log_prereq(f"{SYMBOLS_OUTER.get('gear', '>>')} Executing: {' '.join(command)}", "info")
    try:
        result = subprocess.run(
            command,
            check=check,
            capture_output=capture_output,
            text=text,
            input=cmd_input,
        )
        # Log stdout/stderr for successful commands if captured, useful for debugging
        if (
                capture_output
                and result.stdout
                and result.stdout.strip()
                and result.returncode == 0
        ):
            log_prereq(f"   stdout: {result.stdout.strip()}", "info")
        if (
                capture_output
                and result.stderr
                and result.stderr.strip()
                and result.returncode == 0
        ):
            log_prereq(
                f"   stderr: {result.stderr.strip()}", "info"
            )  # Some tools use stderr for info
        return result
    except subprocess.CalledProcessError as e:
        err_msg = (
            e.stderr.strip()
            if e.stderr
            else (e.stdout.strip() if e.stdout else str(e))
        )
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
        result = _run_cmd_prereq(
            ["lsb_release", "-cs"], capture_output=True, check=True
        )
        return result.stdout.strip()
    except Exception as e:
        log_prereq(f"{SYMBOLS_OUTER.get('warning', '!!')} Could not determine Debian codename: {e}", "warning")
        return None


# --- UV Installation Logic ---
def _install_uv_with_pipx_prereq() -> bool:
    """Installs uv using pipx, including pipx itself if needed."""
    log_prereq(f"{SYMBOLS_OUTER.get('info', '>>')} Attempting uv installation using pipx...", "info")
    pipx_installed_by_this_script = False
    apt_prefix = _get_elevated_prefix_prereq()

    if not command_exists_prereq("pipx"):
        log_prereq(f"{SYMBOLS_OUTER.get('warning', '!!')} pipx not found. Attempting to install pipx via apt...",
                   "warning")
        try:
            # Ensure apt update runs before trying to install a new package
            _run_cmd_prereq(apt_prefix + ["apt", "update"])
            _run_cmd_prereq(apt_prefix + ["apt", "install", "-y", "pipx"])
            log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} pipx installed successfully via apt.", "info")
            pipx_installed_by_this_script = True
        except Exception as e:
            log_prereq(f"{SYMBOLS_OUTER.get('error', '!!')} Failed to install pipx: {e}", "error")
            return False

    if pipx_installed_by_this_script:
        log_prereq(
            f"{SYMBOLS_OUTER.get('info', '>>')} pipx was just installed. Running 'pipx ensurepath' to update PATH for future shells...",
            "info")
        try:
            # pipx ensurepath should run as the current user
            _run_cmd_prereq(
                ["pipx", "ensurepath"], check=False, capture_output=True
            )
            log_prereq(
                f"{SYMBOLS_OUTER.get('success', 'OK')} 'pipx ensurepath' executed. You may need to open a new terminal or source your shell profile.",
                "info")
        except Exception as e:
            log_prereq(
                f"{SYMBOLS_OUTER.get('warning', '!!')} 'pipx ensurepath' encountered an issue: {e}. This might be okay if PATH is already configured.",
                "warning")

    log_prereq(
        f"{SYMBOLS_OUTER.get('rocket', '>>')} Attempting to install/upgrade 'uv' with pipx (as user '{getpass.getuser()}')...",
        "info")
    try:
        # pipx install should run as the current user
        _run_cmd_prereq(["pipx", "install", "uv"], capture_output=True)
        log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' installed/upgraded successfully using pipx.", "info")

        pipx_bin_dir = os.path.expanduser("~/.local/bin")
        current_path = os.environ.get("PATH", "")
        if pipx_bin_dir not in current_path.split(os.pathsep):
            log_prereq(
                f"{SYMBOLS_OUTER.get('gear', '>>')} Adding '{pipx_bin_dir}' to PATH for current script session...",
                "info")
            os.environ['PATH'] = f"{pipx_bin_dir}{os.pathsep}{current_path}"
            log_prereq(f"   New temporary PATH: {os.environ['PATH']}", "info")  # For debugging PATH
        return True
    except Exception as e:
        log_prereq(f"{SYMBOLS_OUTER.get('error', '!!')} Failed to install 'uv' using pipx: {e}", "error")
        return False


def install_uv_prereq() -> bool:
    """Ensures 'uv' is installed, using apt for Trixie+ or pipx otherwise."""
    log_prereq(f"{SYMBOLS_OUTER.get('step', '->')} Checking for 'uv' installation...", "info")
    if command_exists_prereq("uv"):
        log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' is already installed.", "info")
        try:
            uv_version_result = _run_cmd_prereq(
                ["uv", "--version"], capture_output=True
            )
            log_prereq(
                f"   uv version: {uv_version_result.stdout.strip()}", "info"
            )
        except Exception:
            pass
        return True

    log_prereq(f"{SYMBOLS_OUTER.get('info', '>>')} 'uv' not found in PATH. Attempting installation...", "info")
    codename = get_debian_codename_prereq()
    apt_prefix = _get_elevated_prefix_prereq()

    if codename in ["trixie", "forky", "sid"]:
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
        if codename:
            log_prereq(
                f"{SYMBOLS_OUTER.get('package', '>>')} Debian '{codename}' detected. Using pipx to install 'uv'.",
                "info")
        else:
            log_prereq(
                f"{SYMBOLS_OUTER.get('package', '>>')} OS not detected as Trixie/Sid, or detection failed. Using pipx for 'uv'.",
                "info")
        return _install_uv_with_pipx_prereq()


# --- Main Application Logic ---
def run_main_map_server_setup(args_to_pass: List[str]) -> bool:
    """
    DEPRECATED: This function is no longer used. The main_map_server_entry function is called directly instead.

    Runs the main map server setup script (launcher for the 'setup' package)
    and returns True on success (exit code 0 from child), False otherwise.
    """
    # MAP_SERVER_LAUNCHER_SCRIPT_NAME should be in the same directory as this script
    script_path = MAP_SERVER_LAUNCHER_SCRIPT_NAME

    if not os.path.isfile(script_path):
        log_prereq(
            f"{SYMBOLS_OUTER.get('critical', '!!')} CRITICAL: Launcher script '{MAP_SERVER_LAUNCHER_SCRIPT_NAME}' not found at '{script_path}'.",
            "critical")
        return False

    cmd_to_run = [sys.executable, script_path] + args_to_pass

    log_prereq(f"{SYMBOLS_OUTER.get('rocket', '>>')} Running: {' '.join(cmd_to_run)}", "info")  # This log is key

    try:
        process = subprocess.run(
            cmd_to_run, check=False
        )  # check=False allows us to inspect returncode

        if process.returncode == 0:
            log_prereq(
                f"{SYMBOLS_OUTER.get('success', 'OK')} Script '{MAP_SERVER_LAUNCHER_SCRIPT_NAME}' reported success (exit code 0).",
                "info")
            return True
        else:
            # This will catch exit code 2 from setup/main.py if no action was taken
            log_prereq(
                f"{SYMBOLS_OUTER.get('error', '!!')} Script '{MAP_SERVER_LAUNCHER_SCRIPT_NAME}' reported an issue or took no definitive action (exit code {process.returncode}).",
                "error")
            return False
    except Exception as e:
        log_prereq(
            f"{SYMBOLS_OUTER.get('critical', '!!')} Failed to execute script '{MAP_SERVER_LAUNCHER_SCRIPT_NAME}': {e}",
            "critical")
        return False


def main():
    """
    Main function for the prerequisite installer.
    Installs 'uv' and then calls the main map server setup function.
    """
    script_name = os.path.basename(sys.argv[0])
    if "--help" in sys.argv:
        help_text = f"""
    Usage: {script_name} [--help] <action_flag> [arguments_for_main_map_server_entry]

    Prerequisite installer for the Map Server Setup.

    This script performs the following actions:
    1. Ensures 'uv' (Python packager and virtual environment manager) is installed.
       - On Debian Trixie/Sid (and derivatives like Forky), it attempts 'apt install uv'.
       - Otherwise, or if 'apt' fails, it uses 'pipx' (installing 'pipx' via 'apt' if needed).
    2. Based on the <action_flag> provided:
       - If '--continue-install' is used, it calls the main map server setup function: 'main_map_server_entry'.
       - If '--exit-on-complete' is used, it exits after prerequisite installation.

    One of the action flags (--continue-install or --exit-on-complete) MUST be provided.
    They are mutually exclusive.

    All arguments other than '--help', '--continue-install', and '--exit-on-complete'
    will be passed directly to 'main_map_server_entry' function if '--continue-install' is used.

    Options:
      --help                 Show this help message and exit.
      --continue-install     After prerequisite installation, proceed to run the
                             main map server setup function ('main_map_server_entry').
      --exit-on-complete     Exit successfully after prerequisite installation is complete.
                             Does not run 'main_map_server_entry' function.

    Example:
      To install prerequisites and then run the main setup with specific arguments:
      {script_name} --continue-install --data-dir /path/to/data

      To only install/verify prerequisites and then stop:
      {script_name} --exit-on-complete
    """
        # Parse and validate action flags
    continue_install_flag = "--continue-install" in sys.argv
    exit_on_complete_flag = "--exit-on-complete" in sys.argv

    if not continue_install_flag and not exit_on_complete_flag:
        log_prereq(
            f"{SYMBOLS_OUTER.get('error', '')} Error: You must specify either --continue-install or --exit-on-complete.",
            "critical",
        )
        print(
            f"\nUsage: {script_name} [--help] (--continue-install | --exit-on-complete) [arguments_for_main_map_server_entry]")
        print(f"Run '{script_name} --help' for more details.")
        return 1

    if continue_install_flag and exit_on_complete_flag:
        log_prereq(
            f"{SYMBOLS_OUTER.get('error', '')} Error: --continue-install and --exit-on-complete are mutually exclusive.",
            "critical",
        )
        print(
            f"\nUsage: {script_name} [--help] (--continue-install | --exit-on-complete) [arguments_for_main_map_server_entry]")
        print(f"Run '{script_name} --help' for more details.")
        return 1

    log_prereq(f"{SYMBOLS_OUTER.get('step', '->')} Ensuring 'uv' (Python environment manager) is installed...", "info")
    if not install_uv_prereq():
        log_prereq(
            f"{SYMBOLS_OUTER.get('critical', '!!')} Failed to install 'uv'. This is a critical prerequisite. Aborting.",
            "critical")
        return 1  # Exit with failure

    if command_exists_prereq("uv"):
        log_prereq(f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' command is now available in the current script's PATH.",
                   "info")
    else:
        log_prereq(
            f"{SYMBOLS_OUTER.get('warning', '!!')} 'uv' command still not found in PATH after installation attempt. You may need to open a new terminal or source your shell profile for 'uv' to be available for manual use. The main setup script might still function if it uses absolute paths or manages environments internally.",
            "warning")

    if continue_install_flag:
        log_prereq(
            f"{SYMBOLS_OUTER.get('step', '->')} Proceeding to main map server setup (via main_map_server_entry function)...",
            "info",
        )
        # Forward all command line arguments from this script to the next one,
        # excluding the flags handled by this script.
        args_for_map_server_setup = [
            arg for arg in sys.argv[1:] if arg not in ["--continue-install", "--exit-on-complete"]
        ]

        result = main_map_server_entry(args_for_map_server_setup)
        if result == 0:
            log_prereq(
                f"{SYMBOLS_OUTER.get('success', 'OK')} {SYMBOLS_OUTER.get('sparkles', '**')} Overall process: Main map server setup reported success! {SYMBOLS_OUTER.get('sparkles', '**')}",
                "info",
            )
            return 0  # Overall success
        else:
            log_prereq(
                f"{SYMBOLS_OUTER.get('critical', '!!')} {SYMBOLS_OUTER.get('error', '!!')} Overall process: Main map server setup function reported failure or took no definitive action (exit code {result}).",
                "error",
            )
            return 1  # Overall failure
    else:
        log_prereq(
            f"{SYMBOLS_OUTER.get('success', 'OK')} {SYMBOLS_OUTER.get('sparkles', '**')} Overall process: Prerequisites installed successfully, not proceeding to main map server setup.",
            "info",
        )
        return 0  # Overall success


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        # Ensure log_prereq can be called even if logger setup was minimal
        if not outer_logger.handlers:  # Basic safety for the logger
            _handler_kb = logging.StreamHandler(sys.stdout)
            _formatter_kb = logging.Formatter(
                "[PREREQ-INSTALL] %(asctime)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            _handler_kb.setFormatter(_formatter_kb)
            outer_logger.addHandler(_handler_kb)
            outer_logger.setLevel(logging.INFO)
        log_prereq(
            f"\n{SYMBOLS_OUTER.get('warning', '!!')} Prerequisite installation process interrupted by user (Ctrl+C). Exiting.",
            "warning")
        sys.exit(130)
    except Exception as e_global:
        if not outer_logger.handlers:  # Basic safety for the logger
            _handler_ex = logging.StreamHandler(sys.stdout)
            _formatter_ex = logging.Formatter(f"[PREREQ-INSTALL] %(asctime)s - %(levelname)s - %(message)s",
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
