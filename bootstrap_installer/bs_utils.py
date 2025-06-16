# ot-osm-osrm-server/bs_installer/bs_utils.py
# -*- coding: utf-8 -*-
import logging
import os
import shutil
import subprocess
import sys

# Symbols for bootstrap logging
BS_SYMBOLS = {
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "package": "📦",
    "debug": "🐛",
    "gear": "⚙️",
}


def get_bs_logger(name: str) -> logging.Logger:
    """Creates and configures a logger for bootstrap modules."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter(
            f"[BOOTSTRAP:{name.upper()}] %(levelname)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def bootstrap_cmd_exists(cmd_name: str) -> bool:
    """Minimalistic check if a command exists in PATH."""
    return shutil.which(cmd_name) is not None


def check_python_module(module_name: str, logger: logging.Logger) -> bool:
    """Checks if a Python module can be imported."""
    try:
        __import__(module_name)
        logger.debug(f"Python module '{module_name}' is available.")
        return True
    except ImportError:
        logger.debug(f"Python module '{module_name}' is NOT available.")
        return False


def is_apt_package_installed_dpkg(
    package_name: str, logger: logging.Logger
) -> bool:
    """Checks if a Debian package is installed using dpkg-query."""
    if not bootstrap_cmd_exists("dpkg-query"):
        logger.warning(
            f"{BS_SYMBOLS['warning']} 'dpkg-query' command not found. Cannot accurately check if '{package_name}' is installed. Assuming not for safety."
        )
        return False
    try:
        process = subprocess.run(
            ["dpkg-query", "-W", "-f=${Status}", package_name],
            capture_output=True,
            text=True,
            check=False,
        )
        logger.debug(
            f"dpkg-query for {package_name}: rc={process.returncode}, stdout='{process.stdout.strip()}', stderr='{process.stderr.strip()}'"
        )
        return (
            process.returncode == 0
            and "install ok installed" in process.stdout
        )
    except Exception as e:
        logger.error(
            f"{BS_SYMBOLS['error']} Error checking package '{package_name}' with dpkg-query: {e}"
        )
        return False  # Assume not installed on error


def apt_install_packages(
    packages: list[str], logger: logging.Logger, apt_updated_already: bool
) -> bool:
    """
    Attempts to install a list of apt packages.
    Returns True if apt update was run in this call, False otherwise (or if no packages).
    Exits on critical failure.
    """
    if not packages:
        logger.debug(
            "apt_install_packages called with no packages to install."
        )
        return apt_updated_already

    logger.info(
        f"{BS_SYMBOLS['info']} Preparing to install/ensure apt packages: {', '.join(packages)}."
    )

    if not bootstrap_cmd_exists("apt"):
        logger.error(
            f"{BS_SYMBOLS['error']} 'apt' command not found. Cannot install system packages."
        )
        logger.error(
            f"Please ensure apt is available and then install manually: {', '.join(packages)}"
        )
        sys.exit(1)

    sudo_prefix = ["sudo"] if os.geteuid() != 0 else []

    current_apt_update_status = apt_updated_already
    try:
        if not apt_updated_already:
            logger.info(
                f"{BS_SYMBOLS['gear']} Updating apt package list (may require password for sudo)..."
            )
            subprocess.check_call(
                sudo_prefix + ["apt", "update", "-y"],
            )
            current_apt_update_status = True
        else:
            logger.info(
                f"{BS_SYMBOLS['info']} Apt update was already performed in this bootstrap run or not needed by this call."
            )

        logger.info(
            f"{BS_SYMBOLS['package']} Attempting to install/ensure: {', '.join(packages)} (may require password for sudo)..."
        )
        subprocess.check_call(
            sudo_prefix + ["apt", "install", "-y"] + packages,
        )
        logger.info(
            f"{BS_SYMBOLS['success']} Successfully processed apt packages: {', '.join(packages)}."
        )
        return current_apt_update_status
    except subprocess.CalledProcessError as e:
        stderr_output = (
            e.stderr.decode().strip()
            if hasattr(e, "stderr") and e.stderr
            else "N/A"
        )
        logger.error(
            f"{BS_SYMBOLS['error']} Failed during apt command (rc: {e.returncode}): {e.cmd}"
        )
        if stderr_output != "N/A":
            logger.error(f"Apt stderr: {stderr_output}")
        logger.error(
            f"Could not install/ensure system packages: {', '.join(packages)}. Please do so manually and re-run."
        )
        sys.exit(1)
    except Exception as e_unexp:
        logger.error(
            f"{BS_SYMBOLS['error']} An unexpected error occurred during apt installation of {', '.join(packages)}: {e_unexp}"
        )
        sys.exit(1)
