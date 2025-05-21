#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Installation script for map server setup
This script checks for required Python packages and installs them if needed
before running the main install_map_server.py script.
"""

import logging
import os
import subprocess
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[INSTALL] %(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Essential Python packages required for install_map_server.py
REQUIRED_PACKAGES = [
    "python3",
    "python3-pip",
    "python3-venv",
    "python3-dev",
    "python3-yaml",
    "python3-pandas",
    "python3-psycopg2",
    "python3-psycopg",
    "python3-pydantic"
]


def log(message):
    """Log a message with the configured prefix."""
    logger.info(message)


def check_package_installed(package):
    """Check if a package is installed using dpkg."""
    try:
        result = subprocess.run(
            ["dpkg", "-s", package],
            check=False,
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        log(f"Error checking if {package} is installed: {e}")
        return False


def install_packages(packages):
    """Install packages using apt."""
    try:
        log(f"Installing packages: {', '.join(packages)}")
        cmd = ["sudo", "apt", "install", "--yes"] + packages
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        log(f"Failed to install packages: {e}")
        return False
    except Exception as e:
        log(f"Unexpected error during package installation: {e}")
        return False


def run_map_server_install():
    """Run the main install_map_server.py script."""
    try:
        log("Running install_map_server.py...")
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "install_map_server.py")
        subprocess.run([sys.executable, script_path], check=True)
        return True
    except subprocess.CalledProcessError as e:
        log(f"Error running install_map_server.py: {e}")
        return False
    except Exception as e:
        log(f"Unexpected error running install_map_server.py: {e}")
        return False


def main():
    """Main function to check prerequisites and run installation."""
    log("Checking for required Python packages...")

    missing_packages = []
    for package in REQUIRED_PACKAGES:
        if not check_package_installed(package):
            missing_packages.append(package)

    if missing_packages:
        log(f"Missing required packages: {', '.join(missing_packages)}")
        user_input = input("Would you like to install these packages now? (y/N): ").strip().lower()

        if user_input == 'y':
            if install_packages(missing_packages):
                log("All required packages installed successfully.")
            else:
                log("Failed to install some packages. Please install them manually and try again.")
                return 1
        else:
            log("Installation cancelled. Please install the required packages manually and try again.")
            return 1
    else:
        log("All required Python packages are already installed.")

    # Run the main installation script
    log("Starting map server installation...")
    if run_map_server_install():
        log("Map server installation completed.")
        return 0
    else:
        log("Map server installation failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
