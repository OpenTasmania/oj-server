# modular_bootstrap/mb_bootstrap.py
# -*- coding: utf-8 -*-

import os
import subprocess
import sys
from pathlib import Path


def _check_and_install_system_prerequisites():
    """
    Ensure the system has the required python3-venv and python3-pip packages.
    """
    required_packages = ["python3-venv", "python3-pip", "libpq-dev"]
    for package in required_packages:
        check_command = ["dpkg", "-s", package]
        try:
            subprocess.run(
                check_command,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(
                f"System package '{package}' is required but not installed."
            )
            print(
                "Attempting to install it using 'apt'. "
                "This may require sudo privileges."
            )
            install_command = ["sudo", "apt-get", "install", "-y", package]
            try:
                subprocess.run(install_command, check=True)
                print(f"Successfully installed '{package}'.")
            except subprocess.CalledProcessError:
                print(f"Error: Failed to install '{package}'.")
                print("Please install it manually and run the script again.")
                print(f"Command failed: {' '.join(install_command)}")
                sys.exit(1)


def ensure_venv_and_dependencies():
    """
    Ensures the script is running in a virtual environment with all necessary
    dependencies installed, following a uv-based workflow.

    This function automates the following steps:
    1. Checks for and installs system-level prerequisites.
    2. Creates a virtual environment at '.venv' if it doesn't exist.
    3. Installs 'uv' into the virtual environment.
    4. Uses 'uv' to install all project dependencies from 'pyproject.toml'.
    5. Re-launches the original script inside the fully-prepared environment.
    """
    project_root = Path.cwd()
    while not (project_root / "pyproject.toml").exists():
        if project_root == project_root.parent:
            print(
                "Error: Could not find pyproject.toml. "
                "Please run the script from within the project directory."
            )
            sys.exit(1)
        project_root = project_root.parent

    venv_dir = project_root / ".venv"

    if sys.prefix == str(venv_dir):
        return

    _check_and_install_system_prerequisites()

    venv_python = venv_dir / "bin" / "python"
    venv_pip = venv_dir / "bin" / "pip"
    venv_uv = venv_dir / "bin" / "uv"

    if not venv_dir.exists():
        print(f"Creating virtual environment in: {venv_dir}")
        try:
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv_dir)],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            print("--- VENV CREATION FAILED ---")
            print(f"Failed to create virtual environment at {venv_dir}.")
            print("Exit Code:", e.returncode)
            print("\n--- STDOUT ---\n", e.stdout)
            print("\n--- STDERR ---\n", e.stderr)
            print("-----------------------------")
            sys.exit(1)

    print("Installing 'uv' into the virtual environment...")
    try:
        subprocess.run(
            [str(venv_pip), "install", "uv"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print("--- FAILED TO INSTALL UV ---")
        print("Failed to install 'uv' into the virtual environment.")
        print("Exit Code:", e.returncode)
        print("\n--- STDOUT ---\n", e.stdout)
        print("\n--- STDERR ---\n", e.stderr)
        print("----------------------------")
        sys.exit(1)

    print("Installing project dependencies with uv...")
    try:
        subprocess.run(
            [str(venv_uv), "pip", "install", "-e", "."],
            check=True,
            capture_output=True,
            text=True,
            cwd=project_root,
        )
    except subprocess.CalledProcessError as e:
        print("--- UV PIP INSTALL FAILED ---")
        print("Failed to install project dependencies with 'uv'.")
        print("Exit Code:", e.returncode)
        print("\n--- STDOUT ---\n", e.stdout)
        print("\n--- STDERR ---\n", e.stderr)
        print("-----------------------------")
        sys.exit(1)

    print("Re-launching the application inside the virtual environment...")
    script_to_run = sys.argv[0]
    os.execv(
        str(venv_python),
        [str(venv_python), script_to_run] + sys.argv[1:],
    )
