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

# Define the name of the main installer module to be executed.
MAP_SERVER_MODULE_NAME = "setup.main_installer"
VENV_DIR = ".venv"  # Using .venv for default uv detection.

# --- Basic Configuration & Symbols ---
SYMBOLS_OUTER = {
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "step": "➡️",
    "gear": "⚙️",
    "package": "📦",
    "rocket": "🚀",
    "sparkles": "✨",
    "critical": "🔥",
    "link": "🔗",
}

# --- Logger for this prerequisite installer script ---
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


# --- Command Execution Utilities (Simplified for this script) ---
def _get_elevated_prefix_prereq() -> List[str]:
    """Return ['sudo'] if not root, otherwise an empty list."""
    return [] if os.geteuid() == 0 else ["sudo"]


def _run_cmd_prereq(
    command: List[str],
    check: bool = True,
    capture_output: bool = False,
    text: bool = True,
    cmd_input: Optional[str] = None,
    cwd: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """
    Run a command and log its execution.

    Args:
        command: The command to run as a list of strings.
        check: If True, raise CalledProcessError on non-zero exit.
        capture_output: If True, capture stdout and stderr.
        text: If True, decode stdout/stderr as text.
        cmd_input: Optional string to pass as stdin to the command.
        cwd: Optional working directory to run the command in.

    Returns:
        A subprocess.CompletedProcess instance.

    Raises:
        subprocess.CalledProcessError: If `check` is True and the command
                                       returns a non-zero exit code.
        FileNotFoundError: If the command is not found.
        Exception: For other unexpected errors.
    """
    log_prereq(
        f"{SYMBOLS_OUTER.get('gear', '>>')} Executing: {' '.join(command)} "
        f"{f'(in {cwd})' if cwd else ''}",
        "info",
    )
    try:
        result = subprocess.run(
            command,
            check=check,
            capture_output=capture_output,
            text=text,
            input=cmd_input,
            cwd=cwd,
        )
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
            and result.returncode == 0  # Only log non-failing stderr as info.
        ):
            log_prereq(f"   stderr: {result.stderr.strip()}", "info")
        return result
    except subprocess.CalledProcessError as e:
        err_msg = (
            e.stderr.strip()
            if e.stderr
            else (e.stdout.strip() if e.stdout else str(e))
        )
        log_prereq(
            f"{SYMBOLS_OUTER.get('error', '!!')} Command `{' '.join(e.cmd)}` "
            f"failed (rc {e.returncode}). Error: {err_msg}",
            "error",
        )
        raise
    except FileNotFoundError as e:
        log_prereq(
            f"{SYMBOLS_OUTER.get('error', '!!')} Command not found: "
            f"{e.filename}. Is it installed and in PATH?",
            "error",
        )
        raise
    except Exception as e:
        log_prereq(
            f"{SYMBOLS_OUTER.get('error', '!!')} Unexpected error running "
            f"command `{' '.join(command)}`: {e}",
            "error",
        )
        raise


def command_exists_prereq(command: str) -> bool:
    """Check if a command exists in the system's PATH."""
    return shutil.which(command) is not None


def get_debian_codename_prereq() -> Optional[str]:
    """
    Determine the Debian codename using lsb_release.

    Returns:
        The Debian codename as a string, or None if it cannot be determined.
    """
    if not command_exists_prereq("lsb_release"):
        log_prereq(
            f"{SYMBOLS_OUTER.get('warning', '!!')} lsb_release command not "
            "found. Cannot determine Debian codename.",
            "warning",
        )
        return None
    try:
        result = _run_cmd_prereq(
            ["lsb_release", "-cs"], capture_output=True, check=True
        )
        return result.stdout.strip()
    except Exception as e:
        log_prereq(
            f"{SYMBOLS_OUTER.get('warning', '!!')} Could not determine Debian "
            f"codename: {e}",
            "warning",
        )
        return None


def ensure_pip_installed_prereq() -> bool:
    """
    Ensure 'pip' (Python package installer) is available.
    If not found, attempts to install 'python3-pip' using apt.

    Returns:
        True if 'pip' is available or successfully installed, False otherwise.
    """
    log_prereq(
        f"{SYMBOLS_OUTER.get('step', '->')} {SYMBOLS_OUTER.get('python', '🐍')} "
        "Checking for 'pip' command...",
        "info",
    )
    if command_exists_prereq("pip"):
        log_prereq(
            f"{SYMBOLS_OUTER.get('success', 'OK')} 'pip' command is "
            "already available.",
            "info",
        )
        return True

    log_prereq(
        f"{SYMBOLS_OUTER.get('warning', '!!')} 'pip' command not found. "
        "Attempting to install 'python3-pip'...",
        "warning",
    )

    if not command_exists_prereq("apt"):
        log_prereq(
            f"{SYMBOLS_OUTER.get('error', '!!')} 'apt' command not found. "
            "Cannot attempt to install 'python3-pip'. "
            "Please install pip manually for your system.",
            "error",
        )
        return False

    apt_prefix = _get_elevated_prefix_prereq()
    try:
        log_prereq(
            f"{SYMBOLS_OUTER.get('gear', '>>')} Updating apt cache (this may "
            "take a moment)...",
            "info",
        )
        _run_cmd_prereq(apt_prefix + ["apt", "update"], capture_output=True)
        log_prereq(
            f"{SYMBOLS_OUTER.get('package', '>>')} Attempting to install "
            "'python3-pip' using apt...",
            "info",
        )
        _run_cmd_prereq(
            apt_prefix + ["apt", "install", "-y", "python3-pip"],
            capture_output=True,
        )
        log_prereq(
            f"{SYMBOLS_OUTER.get('success', 'OK')} 'python3-pip' installation "
            "via apt initiated.",
            "info",
        )
        if command_exists_prereq("pip"):
            log_prereq(
                f"{SYMBOLS_OUTER.get('success', 'OK')} 'pip' command is now "
                "available after installation.",
                "info",
            )
            return True
        else:
            log_prereq(
                f"{SYMBOLS_OUTER.get('warning', '!!')} 'python3-pip' was "
                "reportedly installed by apt, but 'pip' command is still not "
                "immediately found in PATH. This might be okay if 'pip3' is "
                "available or PATH updates, or if tools adapt.",
                "warning",
            )
            return True
    except subprocess.CalledProcessError as e:
        log_prereq(
            f"{SYMBOLS_OUTER.get('error', '!!')} Failed to install "
            f"'python3-pip' via apt: {e}. Error: {e.stderr or e.stdout or str(e)}",
            "error",
        )
        return False
    except FileNotFoundError:
        log_prereq(
            f"{SYMBOLS_OUTER.get('error', '!!')} 'apt' command was not found "
            "during execution. Cannot install 'python3-pip'.",
            "error",
        )
        return False
    except Exception as e:
        log_prereq(
            f"{SYMBOLS_OUTER.get('error', '!!')} An unexpected error "
            f"occurred while trying to install 'python3-pip': {e}",
            "error",
        )
        return False


# --- UV Installation Logic ---
def _install_uv_with_pipx_prereq() -> bool:
    """
    Install 'uv' using pipx, including pipx itself if needed.

    Returns:
        True if 'uv' was successfully installed, False otherwise.
    """
    log_prereq(
        f"{SYMBOLS_OUTER.get('info', '>>')} Attempting uv installation "
        "using pipx...",
        "info",
    )
    pipx_installed_by_this_script = False
    apt_prefix = _get_elevated_prefix_prereq()

    if not command_exists_prereq("pipx"):
        log_prereq(
            f"{SYMBOLS_OUTER.get('warning', '!!')} pipx not found. "
            "Attempting to install pipx via apt...",
            "warning",
        )
        try:
            _run_cmd_prereq(apt_prefix + ["apt", "update"])
            _run_cmd_prereq(apt_prefix + ["apt", "install", "-y", "pipx"])
            log_prereq(
                f"{SYMBOLS_OUTER.get('success', 'OK')} pipx installed "
                "successfully via apt.",
                "info",
            )
            pipx_installed_by_this_script = True
        except Exception as e:
            log_prereq(
                f"{SYMBOLS_OUTER.get('error', '!!')} Failed to install pipx: "
                f"{e}",
                "error",
            )
            return False

    if pipx_installed_by_this_script:
        log_prereq(
            f"{SYMBOLS_OUTER.get('info', '>>')} pipx was just installed. "
            "Running 'pipx ensurepath' to update PATH for future shells...",
            "info",
        )
        try:
            _run_cmd_prereq(
                ["pipx", "ensurepath"], check=False, capture_output=True
            )
            log_prereq(
                f"{SYMBOLS_OUTER.get('success', 'OK')} 'pipx ensurepath' "
                "executed. You may need to open a new terminal or source "
                "your shell profile.",
                "info",
            )
        except Exception as e:
            log_prereq(
                f"{SYMBOLS_OUTER.get('warning', '!!')} 'pipx ensurepath' "
                f"encountered an issue: {e}. This might be okay if PATH is "
                "already configured.",
                "warning",
            )

    log_prereq(
        f"{SYMBOLS_OUTER.get('rocket', '>>')} Attempting to install/upgrade "
        f"'uv' with pipx (as user '{getpass.getuser()}')...",
        "info",
    )
    try:
        _run_cmd_prereq(["pipx", "install", "uv"], capture_output=True)
        log_prereq(
            f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' installed/upgraded "
            "successfully using pipx.",
            "info",
        )

        pipx_bin_dir = os.path.expanduser("~/.local/bin")
        current_path = os.environ.get("PATH", "")
        if pipx_bin_dir not in current_path.split(os.pathsep):
            log_prereq(
                f"{SYMBOLS_OUTER.get('gear', '>>')} Adding '{pipx_bin_dir}' "
                "to PATH for current script session...",
                "info",
            )
            os.environ["PATH"] = f"{pipx_bin_dir}{os.pathsep}{current_path}"
            log_prereq(f"   New temporary PATH: {os.environ['PATH']}", "info")
        return True
    except Exception as e:
        log_prereq(
            f"{SYMBOLS_OUTER.get('error', '!!')} Failed to install 'uv' "
            f"using pipx: {e}",
            "error",
        )
        return False


def install_uv_prereq() -> bool:
    """
    Ensure 'uv' is installed.

    Attempts to install 'uv' via apt for Debian Trixie+ or Sid.
    Falls back to using pipx for other systems or if apt install fails.

    Returns:
        True if 'uv' is installed or successfully installed, False otherwise.
    """
    log_prereq(
        f"{SYMBOLS_OUTER.get('step', '->')} Checking for 'uv' "
        "installation...",
        "info",
    )
    if command_exists_prereq("uv"):
        log_prereq(
            f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' is already installed.",
            "info",
        )
        try:
            uv_version_result = _run_cmd_prereq(
                ["uv", "--version"], capture_output=True
            )
            log_prereq(
                f"   uv version: {uv_version_result.stdout.strip()}", "info"
            )
        except Exception:
            # If version check fails, it's not critical, 'uv' command exists.
            pass
        return True

    log_prereq(
        f"{SYMBOLS_OUTER.get('info', '>>')} 'uv' not found in PATH. "
        "Attempting installation...",
        "info",
    )
    codename = get_debian_codename_prereq()
    apt_prefix = _get_elevated_prefix_prereq()

    # Debian versions where 'uv' might be in apt.
    if codename in ["trixie", "forky", "sid"]:
        log_prereq(
            f"{SYMBOLS_OUTER.get('package', '>>')} Debian '{codename}' "
            "detected. Attempting 'apt install uv'...",
            "info",
        )
        try:
            _run_cmd_prereq(apt_prefix + ["apt", "update"])
            _run_cmd_prereq(apt_prefix + ["apt", "install", "-y", "uv"])
            log_prereq(
                f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' installed "
                "successfully via apt.",
                "info",
            )
            return True
        except Exception as e:
            log_prereq(
                f"{SYMBOLS_OUTER.get('warning', '!!')} Failed to install 'uv' "
                f"via apt on '{codename}': {e}. Falling back to pipx.",
                "warning",
            )
            return _install_uv_with_pipx_prereq()
    else:
        if codename:
            log_prereq(
                f"{SYMBOLS_OUTER.get('package', '>>')} Debian '{codename}' "
                "detected (or other). Using pipx to install 'uv'.",
                "info",
            )
        else:
            log_prereq(
                f"{SYMBOLS_OUTER.get('package', '>>')} OS not detected as "
                "Trixie/Sid, or detection failed. Using pipx for 'uv'.",
                "info",
            )
        return _install_uv_with_pipx_prereq()


def get_venv_python_executable(project_root: str, venv_dir_name: str) -> str:
    """Return the path to the Python executable in the virtual environment."""
    return os.path.join(project_root, venv_dir_name, "bin", "python")


def main() -> int:
    """
    Main function for the prerequisite installer.

    Installs 'uv', creates a virtual environment, installs dependencies,
    and then calls the main map server setup function using the venv's Python.

    Returns:
        0 on success, 1 on failure.
    """
    script_name = os.path.basename(sys.argv[0])
    # Assumes install.py is in the project root, and pyproject.toml is also
    # there.
    project_root = os.path.dirname(os.path.abspath(__file__))

    install_py_help_text = f"""
Usage: {script_name} [--help] <action_flag> \
[arguments_for_main_map_server_entry]

Prerequisite installer for the Map Server Setup.
This script performs the following actions:
1. Ensures 'uv' (Python packager and virtual environment manager) is installed.
2. Creates a virtual environment in '{VENV_DIR}' using 'uv venv'.
3. Installs project dependencies from 'pyproject.toml' (expected in the same
   directory as this script) into the venv using 'uv pip install .'.
4. Based on the <action_flag> provided, it either continues to the main
   setup or exits.

Action Flags (mutually exclusive, one is required):
  --continue-install     After prerequisite and venv setup, proceed to run the
                         main map server setup ('{MAP_SERVER_MODULE_NAME}')
                         using the virtual environment's Python.
  --exit-on-complete     Exit successfully after prerequisite and venv setup
                         is complete. Does not run the main map server setup.

Options for this script ({script_name}):
  -h, --help             Show this combined help message (including help for
                         the main setup script if --continue-install is used)
                         and exit.

Arguments for {MAP_SERVER_MODULE_NAME} \
(passed if --continue-install is used):
  (These are arguments for '{MAP_SERVER_MODULE_NAME}' and will be dynamically
   fetched and listed below if possible)
"""

    if "--help" in sys.argv or "-h" in sys.argv:
        print(install_py_help_text)
        print("\n" + "=" * 80)
        print(
            f"Help information for the main setup module "
            f"({MAP_SERVER_MODULE_NAME}):"
        )
        print("=" * 80)
        try:
            # Attempt to run the main installer with --help using current python
            # This might fail if deps are missing, but should show its own
            # argparse help.
            help_cmd_args = [
                sys.executable,
                "-m",
                MAP_SERVER_MODULE_NAME,
                "--help",
            ]
            # Let it handle its own SystemExit for help.
            subprocess.run(help_cmd_args, check=False)
            return 0
        except Exception as e_main_help:
            log_prereq(
                f"{SYMBOLS_OUTER.get('error', '!!')} Error trying to display "
                f"help from {MAP_SERVER_MODULE_NAME}: {e_main_help}",
                "error",
            )
            print(
                f"Could not display help from {MAP_SERVER_MODULE_NAME}. "
                "It might require dependencies to be installed first."
            )
            return 1

    continue_install_flag = "--continue-install" in sys.argv
    exit_on_complete_flag = "--exit-on-complete" in sys.argv

    if not continue_install_flag and not exit_on_complete_flag:
        log_prereq(
            f"{SYMBOLS_OUTER.get('error', '!!')} Error: You must specify "
            "either --continue-install or --exit-on-complete.",
            "critical",
        )
        print(
            f"\nUsage: {script_name} [--help] (--continue-install | "
            "--exit-on-complete) [options_for_main_setup...]"
        )
        print(f"Run '{script_name} --help' for full details.")
        return 1

    if continue_install_flag and exit_on_complete_flag:
        log_prereq(
            f"{SYMBOLS_OUTER.get('error', '!!')} Error: --continue-install "
            "and --exit-on-complete are mutually exclusive.",
            "critical",
        )
        print(
            f"\nUsage: {script_name} [--help] (--continue-install | "
            "--exit-on-complete) [options_for_main_setup...]"
        )
        print(f"Run '{script_name} --help' for more details.")
        return 1

    if not ensure_pip_installed_prereq():
        if not command_exists_prereq("pip") and not command_exists_prereq(
            "pip3"
        ):
            log_prereq(
                f"{SYMBOLS_OUTER.get('critical', '!!')} Failed to ensure 'pip' "
                "is available. 'pip' is a critical prerequisite for potentially "
                "installing other tools like 'pipx'. Aborting.",
                "critical",
            )
            return 1
        else:
            log_prereq(
                f"{SYMBOLS_OUTER.get('warning', '!!')} 'ensure_pip_installed_prereq' "
                "returned False, but a pip command ('pip' or 'pip3') was found. "
                "Proceeding with caution.",
                "warning",
            )

    log_prereq(
        f"{SYMBOLS_OUTER.get('step', '->')} Ensuring 'uv' (Python "
        "environment manager) is installed...",
        "info",
    )
    if not install_uv_prereq():
        log_prereq(
            f"{SYMBOLS_OUTER.get('critical', '!!')} Failed to install 'uv'. "
            "This is a critical prerequisite. Aborting.",
            "critical",
        )
        return 1

    if not command_exists_prereq("uv"):
        log_prereq(
            f"{SYMBOLS_OUTER.get('critical', '!!')} 'uv' command not found "
            "in PATH even after installation attempt. Aborting.",
            "critical",
        )
        log_prereq(
            "   You may need to open a new terminal or source your shell "
            "profile (`~/.bashrc`, `~/.zshrc`, etc.).",
            "critical",
        )
        return 1
    log_prereq(
        f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' command is available "
        "in PATH.",
        "info",
    )

    venv_path = os.path.join(project_root, VENV_DIR)
    venv_python_executable = get_venv_python_executable(
        project_root, VENV_DIR
    )

    log_prereq(
        f"{SYMBOLS_OUTER.get('step', '->')} Setting up virtual environment "
        f"in '{venv_path}' using 'uv'...",
        "info",
    )
    try:
        _run_cmd_prereq(
            ["uv", "venv", VENV_DIR, "--python", sys.executable],
            cwd=project_root,
        )
        log_prereq(
            f"{SYMBOLS_OUTER.get('success', 'OK')} Virtual environment "
            f"created at '{venv_path}'.",
            "info",
        )

        log_prereq(
            f"{SYMBOLS_OUTER.get('package', '>>')} Installing project "
            f"dependencies from 'pyproject.toml' into '{VENV_DIR}'...",
            "info",
        )
        # uv should detect .venv in cwd.
        _run_cmd_prereq(["uv", "pip", "install", "."], cwd=project_root)
        log_prereq(
            f"{SYMBOLS_OUTER.get('success', 'OK')} Project dependencies "
            f"installed into '{VENV_DIR}'.",
            "info",
        )

    except subprocess.CalledProcessError as e:
        log_prereq(
            f"{SYMBOLS_OUTER.get('critical', '!!')} Failed to set up virtual "
            f"environment or install dependencies: {e}",
            "critical",
        )
        return 1
    except Exception as e:
        log_prereq(
            f"{SYMBOLS_OUTER.get('critical', '!!')} An unexpected error "
            f"occurred during venv setup: {e}",
            "critical",
        )
        return 1

    if exit_on_complete_flag:
        log_prereq(
            f"{SYMBOLS_OUTER.get('success', 'OK')} "
            f"{SYMBOLS_OUTER.get('sparkles', '**')} Overall process: "
            "Prerequisites and virtual environment setup complete. Exiting as "
            "per --exit-on-complete.",
            "info",
        )
        return 0

    if continue_install_flag:
        log_prereq(
            f"{SYMBOLS_OUTER.get('step', '->')} Proceeding to main map "
            f"server setup using Python from '{venv_python_executable}'...",
            "info",
        )
        args_for_map_server_setup = [
            arg
            for arg in sys.argv[1:]
            if arg
            not in [
                "--continue-install",
                "--exit-on-complete",
                "--help",
                "-h",
            ]
        ]
        cmd_to_run_main_installer = [
            venv_python_executable,
            "-m",
            MAP_SERVER_MODULE_NAME,
        ] + args_for_map_server_setup

        log_prereq(
            f"{SYMBOLS_OUTER.get('link', '>>')} Launching: "
            f"{' '.join(cmd_to_run_main_installer)}",
            "info",
        )

        try:
            process_result = _run_cmd_prereq(
                cmd_to_run_main_installer, check=False, cwd=project_root
            )
            result_code = process_result.returncode

            if result_code == 0:
                log_prereq(
                    f"{SYMBOLS_OUTER.get('success', 'OK')} "
                    f"{SYMBOLS_OUTER.get('sparkles', '**')} Overall process: "
                    f"Main map server setup ({MAP_SERVER_MODULE_NAME}) "
                    "reported success!",
                    "info",
                )
                return 0
            else:
                log_prereq(
                    f"{SYMBOLS_OUTER.get('critical', '!!')} "
                    f"{SYMBOLS_OUTER.get('error', '!!')} Overall process: "
                    f"Main map server setup ({MAP_SERVER_MODULE_NAME}) "
                    f"reported failure (exit code {result_code}).",
                    "error",
                )
                return 1
        except subprocess.CalledProcessError as e:
            log_prereq(
                f"{SYMBOLS_OUTER.get('critical', '!!')} Failed to execute "
                f"main map server setup: {e}",
                "critical",
            )
            return 1
        except Exception as e:
            log_prereq(
                f"{SYMBOLS_OUTER.get('critical', '!!')} Unexpected error "
                f"launching main map server setup: {e}",
                "critical",
            )
            return 1

    return 1  # Should not be reached.


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        # Basic logger setup if not done before interruption.
        if not outer_logger.handlers:
            _handler_kb = logging.StreamHandler(sys.stdout)
            _formatter_kb = logging.Formatter(
                "[PREREQ-INSTALL] %(asctime)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            _handler_kb.setFormatter(_formatter_kb)
            outer_logger.addHandler(_handler_kb)
            outer_logger.setLevel(logging.INFO)
        log_prereq(
            f"\n{SYMBOLS_OUTER.get('warning', '!!')} Prerequisite "
            "installation process interrupted by user (Ctrl+C). Exiting.",
            "warning",
        )
        sys.exit(130)
    except SystemExit as e:  # Allow planned exits (e.g. from help).
        sys.exit(e.code)
    except Exception as e_global:  # Catch-all for truly unexpected errors.
        if not outer_logger.handlers:  # Basic logger setup if not done.
            _handler_ex = logging.StreamHandler(sys.stdout)
            _formatter_ex = logging.Formatter(
                "[PREREQ-INSTALL] %(asctime)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            _handler_ex.setFormatter(_formatter_ex)
            outer_logger.addHandler(_handler_ex)
            outer_logger.setLevel(logging.INFO)
        log_prereq(
            f"{SYMBOLS_OUTER.get('critical', '!!')} A critical unhandled "
            f"error occurred in prerequisite installer: {e_global}",
            "critical",
        )
        import traceback

        outer_logger.error(traceback.format_exc())
        sys.exit(1)
