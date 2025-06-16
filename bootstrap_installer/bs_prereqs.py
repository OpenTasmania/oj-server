# ot-osm-osrm-server/bs_installer/bootstrap_prereqs.py
# -*- coding: utf-8 -*-
import logging
import os
import shutil
import subprocess
import sys

# Minimal logger for this very bootstrap phase
_bs_logger = logging.getLogger("BootstrapPrereqs")
if not _bs_logger.handlers:
    _bs_handler = logging.StreamHandler(sys.stderr)
    _bs_formatter = logging.Formatter(
        "[BOOTSTRAP-PREREQS] %(levelname)s: %(message)s"
    )
    _bs_handler.setFormatter(_bs_formatter)
    _bs_logger.addHandler(_bs_handler)
    _bs_logger.setLevel(logging.INFO)

# Simplified symbols for bootstrap logging
_BS_SYMBOLS = {
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "package": "📦",
}


def _bootstrap_cmd_exists(cmd_name: str) -> bool:
    """Minimalistic check if a command exists in PATH."""
    return shutil.which(cmd_name) is not None


def _check_python_module(module_name: str) -> bool:
    """Checks if a Python module can be imported."""
    try:
        __import__(module_name)
        _bs_logger.debug(f"Python module '{module_name}' is available.")
        return True
    except ImportError:
        _bs_logger.debug(f"Python module '{module_name}' is NOT available.")
        return False


def _is_apt_pkg_likely_present(package_name: str) -> bool:
    """
    A simple heuristic to check if an apt package *might* be present.
    This is not a definitive check like dpkg-query but helps avoid unnecessary apt install calls
    for packages that provide common tools.
    Returns True if it's likely present, False otherwise (meaning we should try to install it).
    """
    if package_name == "lsb-release":
        return _bootstrap_cmd_exists("lsb_release")
    if package_name == "build-essential":
        return _bootstrap_cmd_exists("gcc") and _bootstrap_cmd_exists("make")
    return False


def run_initial_bootstrap_checks() -> bool:
    """
    Checks and installs essential system prerequisites for the main installer script.
    Ensures pydantic, pydantic_settings, lsb-release, build-essential, and python3-dev.

    Returns:
        True if system package installations were attempted (caller should re-execute).
        False if all checked prerequisites were already met.
    Exits the script with an error code if critical installations fail.
    """
    _bs_logger.info("Running initial bootstrap prerequisite checks...")

    py_modules_to_apt = {
        "pydantic": "python3-pydantic",
        "pydantic_settings": "python3-pydantic-settings",
    }

    other_apt_packages_to_ensure = {
        "lsb-release": "lsb-release",
        "build-essential": "build-essential",
        "python3-dev": "python3-dev",
    }

    apt_packages_to_install_list = []
    install_attempt_needed = False

    for module_name, apt_pkg_name in py_modules_to_apt.items():
        if not _check_python_module(module_name):
            _bs_logger.info(
                f"Python module '{module_name}' (needed for installer) will be installed via apt package '{apt_pkg_name}'."
            )
            apt_packages_to_install_list.append(apt_pkg_name)
            install_attempt_needed = True

    for tool_feature, apt_pkg_name in other_apt_packages_to_ensure.items():
        if not _is_apt_pkg_likely_present(apt_pkg_name):
            _bs_logger.info(
                f"Essential tool/package '{tool_feature}' (apt package '{apt_pkg_name}') will be ensured via apt."
            )
            if apt_pkg_name not in apt_packages_to_install_list:
                apt_packages_to_install_list.append(apt_pkg_name)
            install_attempt_needed = True
        else:
            _bs_logger.info(
                f"Essential tool/package '{tool_feature}' (apt package '{apt_pkg_name}') appears to be present."
            )

    if not install_attempt_needed:
        _bs_logger.info(
            f"{_BS_SYMBOLS['success']} All checked initial bootstrap prerequisites appear to be met."
        )
        return False

    _bs_logger.info(
        f"The following system packages will be installed/ensured: {', '.join(apt_packages_to_install_list)}"
    )

    if not _bootstrap_cmd_exists("apt"):
        _bs_logger.error(
            "'apt' command not found. Cannot install required system packages."
        )
        _bs_logger.error(
            f"Please ensure these are installed manually: {', '.join(apt_packages_to_install_list)}, then re-run."
        )
        sys.exit(1)

    sudo_prefix = ["sudo"] if os.geteuid() != 0 else []

    try:
        _bs_logger.info("Updating apt package list (may require password)...")
        subprocess.check_call(
            sudo_prefix + ["apt", "update", "-y"],
        )

        _bs_logger.info(
            f"Installing/ensuring: {', '.join(apt_packages_to_install_list)} (may require password)..."
        )
        subprocess.check_call(
            sudo_prefix
            + ["apt", "install", "-y"]
            + apt_packages_to_install_list,
        )

        all_py_modules_verified = True
        for py_module in py_modules_to_apt.keys():
            if not _check_python_module(py_module):
                _bs_logger.error(
                    f"CRITICAL: Python module '{py_module}' still not importable after 'apt install' attempt."
                )
                all_py_modules_verified = False

        if all_py_modules_verified:
            _bs_logger.info(
                f"{_BS_SYMBOLS['success']} System package processing completed successfully."
            )
            _bs_logger.info(
                "It's recommended the main script re-executes to use any newly installed Python modules."
            )
            return True
        else:
            _bs_logger.error(
                "One or more critical Python modules for the installer failed to become available."
            )
            _bs_logger.error(
                "Please review 'apt' output, manually ensure prerequisites, and then re-run."
            )
            sys.exit(1)

    except subprocess.CalledProcessError as e:
        stderr_output = e.stderr.decode().strip() if e.stderr else "N/A"
        _bs_logger.error(
            f"Failed during apt command (rc: {e.returncode}): {e.cmd}"
        )
        if stderr_output != "N/A":
            _bs_logger.error(f"Apt stderr: {stderr_output}")
        _bs_logger.error(
            "Could not install/ensure system packages. Please do so manually and re-run."
        )
        sys.exit(1)
    except Exception as e:
        _bs_logger.error(
            f"An unexpected error occurred during bootstrap system package installation: {e}"
        )
        sys.exit(1)


if __name__ == "__main__":
    _bs_logger.info("Running bootstrap_prereqs.py directly for testing...")
    needs_rerun = run_initial_bootstrap_checks()
    if needs_rerun:
        _bs_logger.info(
            "Test run: Bootstrap checks indicated installations were made."
        )
    else:
        _bs_logger.info(
            "Test run: Bootstrap checks indicated no new installations were needed."
        )
