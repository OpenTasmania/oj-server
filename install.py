#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Installation script for map server setup
This script checks for required Python packages and installs them if needed
before running the main install_map_server.py script.
It also installs 'uv' (via apt or pipx), which is critical on Debian 12.
Handles sudo execution gracefully for apt commands.
"""

import logging
import os
import shutil
import subprocess
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Essential Python packages
REQUIRED_PACKAGES = [
    "python3", "python3-pip", "python3-venv", "python3-dev",
    "python3-yaml", "python3-pandas", "python3-psycopg2", "python3-psycopg",
    "python3-pydantic"
]

SYMBOLS = {
    "success": "✅", "error": "❌", "warning": "⚠️", "info": "ℹ️", "step": "➡️",
    "gear": "⚙️", "package": "📦", "rocket": "🚀", "sparkles": "✨", "critical": "🔥"
}


def log(message, level="info"):
    if level == "info":
        logger.info(message)
    elif level == "warning":
        logger.warning(message)
    elif level == "error":
        logger.error(message)
    elif level == "critical":
        logger.critical(message)
    else:
        logger.info(message)


def check_package_installed(package):
    try:
        result = subprocess.run(
            ["dpkg-query", "-W", "-f='${Status}'", package],
            check=False, capture_output=True, text=True
        )
        return result.returncode == 0 and "install ok installed" in result.stdout
    except FileNotFoundError:
        log(f"{SYMBOLS['error']} dpkg-query command not found. Cannot check package '{package}'.", level="error")
        return False
    except Exception as e:
        log(f"{SYMBOLS['error']} Error checking if {package} is installed: {e}", level="error")
        return False


def _install_uv_with_pipx():
    log(f"{SYMBOLS['info']} Attempting uv installation using pipx...")
    pipx_was_installed_by_this_script = False
    # For installing pipx itself via apt:
    apt_cmd_prefix_for_pipx = _get_elevated_command_prefix()

    if not command_exists("pipx"):
        log(f"{SYMBOLS['warning']} pipx is not installed. Attempting to install pipx via apt...")
        try:
            # Assuming apt update ran in install_packages if other packages were installed.
            # If REQUIRED_PACKAGES was empty, an update here might be beneficial.
            # For robustness, let's ensure apt update is called if we are about to install pipx.
            if apt_cmd_prefix_for_pipx:  # Implies we might need sudo, good time to ensure cache is fresh
                update_cmd = apt_cmd_prefix_for_pipx + ["apt", "update"]
                log(f"{SYMBOLS['gear']} Ensuring apt package list is up-to-date (`{' '.join(update_cmd)}`)...")
                subprocess.run(update_cmd, check=True, capture_output=True)

            pipx_install_cmd_apt = apt_cmd_prefix_for_pipx + ["apt", "install", "pipx", "-y"]
            log(f"{SYMBOLS['gear']} Installing pipx (`{' '.join(pipx_install_cmd_apt)}`)...")
            subprocess.run(pipx_install_cmd_apt, check=True, capture_output=True)
            log(f"{SYMBOLS['success']} pipx installed successfully via apt.")
            pipx_was_installed_by_this_script = True
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode().strip() if e.stderr else (e.stdout.decode().strip() if e.stdout else str(e))
            log(f"{SYMBOLS['error']} Failed to install pipx using apt. Command: `{' '.join(e.cmd)}`. Error: {err_msg}",
                level="error")
            log(f"   {SYMBOLS['info']} Please try installing pipx manually and re-run this script.")
            return False
        except Exception as e:
            log(f"{SYMBOLS['error']} Unexpected error during pipx installation via apt: {e}", level="error")
            return False

    # pipx ensurepath and pipx install uv MUST run as the current user, not with sudo.
    # The os.getlogin() is a nice touch for logging but can fail in some environments (e.g. cron)
    # A simple "current user" is usually fine.
    user_exec_context = f"as user '{os.getlogin()}'" if hasattr(os, 'getlogin') and callable(
        os.getlogin) else "as current user"

    if pipx_was_installed_by_this_script:
        log(f"--------------------------------------------------------------------------------")
        log(f"{SYMBOLS['info']} IMPORTANT: pipx was just installed by this script.")
        log(f"{SYMBOLS['gear']} Running 'pipx ensurepath' ({user_exec_context}) to configure shell PATH.")
        log(f"--------------------------------------------------------------------------------")
        try:
            ensurepath_result = subprocess.run(["pipx", "ensurepath"], check=False, capture_output=True, text=True)
            if ensurepath_result.stdout and ensurepath_result.stdout.strip():
                log(f"{SYMBOLS['info']} pipx ensurepath stdout:\n{ensurepath_result.stdout.strip()}")
            if ensurepath_result.stderr and ensurepath_result.stderr.strip():
                log(f"{SYMBOLS['info']} pipx ensurepath stderr (may contain info):\n{ensurepath_result.stderr.strip()}")  # pipx can output to stderr
            if ensurepath_result.returncode == 0:
                log(f"{SYMBOLS['success']} 'pipx ensurepath' command completed successfully or reported paths are already configured.")
            else:
                log(f"{SYMBOLS['warning']} 'pipx ensurepath' command finished with exit code {ensurepath_result.returncode}. Check output if issues persist.",
                    level="warning")
        except FileNotFoundError:  # pipx itself not found
            log(f"{SYMBOLS['error']} 'pipx' command not found immediately after apt installation. This is unexpected.",
                level="error")
            return False
        except Exception as e:
            log(f"{SYMBOLS['warning']} 'pipx ensurepath' command encountered an issue: {e}. This might be okay.",
                level="warning")

    log(f"{SYMBOLS['rocket']} Attempting to install/upgrade 'uv' with pipx ({user_exec_context})...")
    try:
        pipx_install_cmd_uv = ["pipx", "install", "uv"]
        result = subprocess.run(pipx_install_cmd_uv, check=True, capture_output=True, text=True)
        if result.stdout and result.stdout.strip(): log(
            f"{SYMBOLS['info']} pipx install uv stdout:\n{result.stdout.strip()}")
        if result.stderr and result.stderr.strip(): log(
            f"{SYMBOLS['info']} pipx install uv stderr (may contain info):\n{result.stderr.strip()}")
        log(f"{SYMBOLS['success']} uv installed/upgraded successfully using pipx.")

        pipx_bin_dir = os.path.expanduser("~/.local/bin")
        current_path = os.environ.get('PATH', '')
        if pipx_bin_dir not in current_path.split(os.pathsep):
            log(f"{SYMBOLS['gear']} Adding '{pipx_bin_dir}' to PATH for current script session...")
            os.environ['PATH'] = pipx_bin_dir + os.pathsep + current_path
        else:
            log(f"{SYMBOLS['info']} '{pipx_bin_dir}' is already in PATH for current script session.")

        log(f"--------------------------------------------------------------------------------")
        log(f"{SYMBOLS['sparkles']} IMPORTANT: 'uv' has been installed using pipx (likely to ~/.local/bin/).")
        log(f"   For 'uv' command to be accessible in new terminals, ensure your shell's PATH is configured (pipx ensurepath helps).")
        log(f"   You might need to: 1. Open a NEW terminal. 2. Or, 'source ~/.bashrc' (or similar).")
        log(f"--------------------------------------------------------------------------------")
        return True
    except FileNotFoundError:
        log(f"{SYMBOLS['error']} 'pipx' command not found when trying to 'pipx install uv'.", level="error")
        return False
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.strip() if e.stderr else e.stdout.strip()
        log(f"{SYMBOLS['error']} Failed to install uv using pipx. Command: `{' '.join(e.cmd)}`. Error:\n{err_msg}",
            level="error")
        return False
    except Exception as e:
        log(f"{SYMBOLS['error']} Unexpected error during 'pipx install uv': {e}", level="error")
        return False


def _get_elevated_command_prefix():
    """Returns ['sudo'] if not root, otherwise an empty list for apt commands."""
    return [] if os.geteuid() == 0 else ["sudo"]


def install_packages(packages_to_install):
    """Install packages using apt, handling sudo correctly."""
    cmd_prefix = _get_elevated_command_prefix()
    try:
        update_cmd = cmd_prefix + ["apt", "update"]
        log(f"{SYMBOLS['gear']} Updating apt package list (`{' '.join(update_cmd)}`)...")
        subprocess.run(update_cmd, check=True, capture_output=True)

        install_cmd = cmd_prefix + ["apt", "install", "--yes"] + packages_to_install
        log(f"{SYMBOLS['package']} Installing system packages (`{' '.join(install_cmd)}`)...")
        subprocess.run(install_cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        # Use e.cmd to show the exact command that failed
        err_msg = e.stderr.decode().strip() if e.stderr else (e.stdout.decode().strip() if e.stdout else str(e))
        log(f"{SYMBOLS['error']} Failed to install system packages. Command: `{' '.join(e.cmd)}`. Error: {err_msg}",
            level="error")
        return False
    except FileNotFoundError as e:
        log(f"{SYMBOLS['error']} Command failed: {e.filename} not found. This is highly unexpected on Debian.",
            level="error")
        return False
    except Exception as e:
        log(f"{SYMBOLS['error']} Unexpected error during system package installation: {e}", level="error")
        return False


def get_debian_codename():
    try:
        result = subprocess.run(
            ["lsb_release", "-cs"],
            check=True, capture_output=True, text=True
        )
        return result.stdout.strip()
    except FileNotFoundError:
        log(f"{SYMBOLS['warning']} lsb_release command not found. Cannot determine Debian codename.", level="warning")
        return None
    except subprocess.CalledProcessError as e:
        log(f"{SYMBOLS['warning']} Could not determine Debian codename: {e.stderr.decode() if e.stderr else e.stdout.decode()}",
            level="warning")
        return None
    except Exception as e:
        log(f"{SYMBOLS['warning']} Unexpected error getting Debian codename: {e}", level="warning")
        return None


def command_exists(command):
    return shutil.which(command) is not None


def install_uv():
    log(f"{SYMBOLS['step']} Checking for uv...")
    if command_exists("uv"):
        log(f"{SYMBOLS['success']} uv is already installed.")
        try:
            result = subprocess.run(["uv", "--version"], capture_output=True, text=True, check=True)
            log(f"{SYMBOLS['info']} uv version: {result.stdout.strip()}")
        except Exception as e:
            log(f"{SYMBOLS['warning']} Could not get uv version: {e}", level="warning")
        return True

    log(f"{SYMBOLS['info']} uv is not installed (or not in initial PATH). Attempting installation...")
    codename = get_debian_codename()
    apt_cmd_prefix_for_uv = _get_elevated_command_prefix()

    if codename in ["trixie", "forky", "sid"]:
        log(f"{SYMBOLS['rocket']} Debian '{codename}' detected. Attempting to install uv using apt...")
        try:
            # Assuming apt update ran in install_packages if other packages were installed.
            # For robustness, an update could be added here if it's the only apt operation.
            uv_install_cmd_apt = apt_cmd_prefix_for_uv + ["apt", "install", "uv", "-y"]
            log(f"{SYMBOLS['gear']} Installing uv (`{' '.join(uv_install_cmd_apt)}`)...")
            subprocess.run(uv_install_cmd_apt, check=True, capture_output=True)
            log(f"{SYMBOLS['success']} uv installed successfully via apt.")
            return True
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode().strip() if e.stderr else (e.stdout.decode().strip() if e.stdout else str(e))
            log(f"{SYMBOLS['warning']} apt installation of uv failed on '{codename}'. Command: `{' '.join(e.cmd)}`. Error: {err_msg}",
                level="warning")
            log(f"   {SYMBOLS['info']} Will fall back to trying installation with pipx.")
        except Exception as e:
            log(f"{SYMBOLS['warning']} Unexpected error during apt uv installation on '{codename}': {e}",
                level="warning")
            log(f"   {SYMBOLS['info']} Will fall back to trying installation with pipx.")

    if codename and codename not in ["trixie", "forky", "sid"]:
        log(f"{SYMBOLS['package']} Debian '{codename}' or other OS detected. Will install uv using pipx.")
    elif codename is None:
        log(f"{SYMBOLS['warning']} Could not determine OS version. Attempting uv using pipx as fallback.",
            level="warning")

    return _install_uv_with_pipx()


def run_map_server_install():
    try:
        log(f"{SYMBOLS['rocket']} Running install_map_server.py...")
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "install_map_server.py")
        subprocess.run([sys.executable, script_path], check=True)
        return True
    except FileNotFoundError:
        log(f"{SYMBOLS['error']} Script 'install_map_server.py' not found in '{os.path.dirname(os.path.abspath(__file__))}'.",
            level="error")
        return False
    except subprocess.CalledProcessError as e:
        log(f"{SYMBOLS['error']} Error running install_map_server.py. Exited with code {e.returncode}.", level="error")
        return False
    except Exception as e:
        log(f"{SYMBOLS['error']} Unexpected error running install_map_server.py: {e}", level="error")
        return False


def main():
    log(f"{SYMBOLS['sparkles']} Starting installation process...")

    # Initial check for sudo needs
    preliminary_check_pkgs_missing = any(not check_package_installed(p) for p in REQUIRED_PACKAGES)

    if os.geteuid() != 0:
        # A simple check; more detailed logic could determine if pipx/uv via apt are needed too.
        if preliminary_check_pkgs_missing:
            log(f"{SYMBOLS['info']} This script may need to install/update system packages using 'apt'.")
            log(f"   You might be prompted for your 'sudo' password for these operations.")
    else:
        log(f"{SYMBOLS['info']} Script is running as root. 'sudo' will not be prepended by this script for apt commands.")

    log(f"{SYMBOLS['step']} Step 1: Checking for required system packages (apt)...")
    # Re-check missing packages properly for the installation decision
    missing_packages_list = [p for p in REQUIRED_PACKAGES if not check_package_installed(p)]

    if missing_packages_list:
        log(f"{SYMBOLS['warning']} Missing required system packages: {', '.join(missing_packages_list)}",
            level="warning")
        try:
            user_input = input(
                f"{SYMBOLS['info']} Would you like to install these system packages now? (y/N): ").strip().lower()
        except EOFError:
            user_input = 'n'  # Default to 'no' in non-interactive environments
            log(f"{SYMBOLS['warning']} No user input detected (EOF), defaulting to 'N'.", level="warning")

        if user_input == 'y':
            if install_packages(missing_packages_list):
                log(f"{SYMBOLS['success']} All required system packages installed successfully.")
            else:
                log(f"{SYMBOLS['critical']} Failed to install some system packages. Please install them manually and try again.",
                    level="critical")
                return 1
        else:
            log(f"{SYMBOLS['info']} Installation cancelled by user or non-interactive mode. Please install required packages manually and try again.")
            return 1
    else:
        log(f"{SYMBOLS['success']} All required system packages are already installed.")

    log(f"{SYMBOLS['step']} Step 2: Checking and attempting to install uv...")
    uv_installed_successfully = install_uv()

    if not uv_installed_successfully:
        current_debian_codename = get_debian_codename()
        if current_debian_codename == "bookworm":
            log(f"{SYMBOLS['critical']} CRITICAL: uv installation failed on Debian 12 (Bookworm).", level="critical")
            log(f"   Script cannot continue as uv is essential on Bookworm.", level="critical")
            return 1
        else:
            log(f"{SYMBOLS['warning']} uv installation not successful (OS: {current_debian_codename if current_debian_codename else 'Unknown'}).",
                level="warning")
            log(f"   {SYMBOLS['info']} Continuing, but 'install_map_server.py' might fail if it needs uv.")
    else:
        log(f"{SYMBOLS['success']} uv check/installation process complete.")
        if command_exists("uv"):
            log(f"{SYMBOLS['info']} Confirmed: 'uv' command is now available in the current script's PATH.")
        else:
            log(f"{SYMBOLS['warning']} Reminder: 'uv' installed, but might not be in PATH for new terminals yet. Ensure `~/.local/bin` is in PATH (you may need to open a new terminal).",
                level="warning")

    log(f"{SYMBOLS['step']} Step 3: Starting main map server setup (running install_map_server.py)...")
    if run_map_server_install():
        log(f"{SYMBOLS['success']} {SYMBOLS['sparkles']} Map server installation script completed successfully! {SYMBOLS['sparkles']}")
        return 0
    else:
        log(f"{SYMBOLS['critical']} Map server installation script failed.", level="critical")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log(f"\n{SYMBOLS['warning']} Installation process interrupted by user (Ctrl+C). Exiting.", level="warning")
        sys.exit(130)  # Standard exit code for SIGINT (Ctrl+C)
