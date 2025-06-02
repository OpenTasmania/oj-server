# tests/test_install.py
import subprocess
import sys
from pathlib import Path

# Assuming the tests directory is at the same level as the 'installer' and 'ot-osm-osrm-server' root
PROJECT_ROOT = Path(__file__).parent.parent
INSTALL_SCRIPT_PATH = PROJECT_ROOT / "install.py"


def test_install_script_help_output():
    """
    Tests the output of 'python install.py --help' to ensure it displays
    both its own help and the help from the main_installer module.
    """
    if not INSTALL_SCRIPT_PATH.is_file():
        raise FileNotFoundError(
            f"install.py not found at {INSTALL_SCRIPT_PATH}"
        )

    # Construct the command
    command = [sys.executable, str(INSTALL_SCRIPT_PATH), "--help"]

    # Execute the command
    result = subprocess.run(
        command, capture_output=True, text=True, check=False
    )

    # Check stdout for key phrases from install.py's help
    assert "Usage: install.py [--help] <action_flag>" in result.stdout, (
        "install.py usage string missing."
    )
    assert (
        "Ensures 'uv' (Python packager and virtual environment manager) is installed."
        in result.stdout
    ), "install.py 'uv' description missing."
    assert "--continue-install" in result.stdout, (
        "install.py '--continue-install' flag help missing."
    )
    assert "--exit-on-complete" in result.stdout, (
        "install.py '--exit-on-complete' flag help missing."
    )
    assert (
        "Arguments for installer.main_installer (passed if --continue-install is used):"
        in result.stdout
    ), "install.py delegation message to main_installer help missing."

    # Check stdout for key phrases indicating main_installer.py's help was called
    # These are based on the example output in your README.md
    assert (
        "Help information for the main setup module (installer.main_installer):"
        in result.stdout
    ), "Header for main_installer.py help missing."
    assert "usage: main_installer.py [-h]" in result.stdout, (
        "main_installer.py usage string missing."
    )
    assert "Map Server Installer Script" in result.stdout, (
        "main_installer.py description string missing from help output."
    )
    assert "--admin-group-ip ADMIN_GROUP_IP" in result.stdout, (
        "Example main_installer.py argument '--admin-group-ip' missing."
    )
    assert "--full" in result.stdout, (
        "Example main_installer.py argument '--full' missing."
    )
    assert "--view-config" in result.stdout, (
        "Example main_installer.py argument '--view-config' missing."
    )

    # Check that the script exits successfully (return code 0) for --help
    assert result.returncode == 0, (
        f"install.py --help exited with code {result.returncode}"
    )
