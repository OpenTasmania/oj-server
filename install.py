#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prerequisite installer for the Map Server Setup.

Ensures 'uv' (Python packager and virtual environment manager) is installed,
then creates a virtual environment, installs project dependencies,
and calls the main map server setup script, passing along all arguments.
"""

import argparse
import getpass
import logging
import os
import subprocess
import sys

_install_py_dir = os.path.dirname(os.path.abspath(__file__))
_project_root_for_bs_import = _install_py_dir

if _project_root_for_bs_import not in sys.path:
    sys.path.insert(0, _project_root_for_bs_import)

_early_bootstrap_logger_install_py = logging.getLogger(
    "InstallPyBootstrapCall"
)
if not _early_bootstrap_logger_install_py.handlers:
    _h_install_py = logging.StreamHandler(sys.stderr)
    _h_install_py.setFormatter(
        logging.Formatter("[INSTALL.PY-BOOTSTRAP] %(levelname)s: %(message)s")
    )
    _early_bootstrap_logger_install_py.addHandler(_h_install_py)
    _early_bootstrap_logger_install_py.setLevel(logging.INFO)

try:
    from bootstrap_installer.bootstrap_process import (
        run_bootstrap_orchestration,
    )
except ImportError as e_bootstrap_import:  # pragma: no cover
    _early_bootstrap_logger_install_py.critical(
        f"Could not import the bootstrap_process module: {e_bootstrap_import}"
    )
    _early_bootstrap_logger_install_py.critical(
        "Ensure 'bootstrap_installer' directory with '__init__.py' and 'bootstrap_process.py' exists at the project root (e.g., where install.py is) and is in Python path."
    )
    _early_bootstrap_logger_install_py.critical(
        f"Current sys.path: {str(sys.path)}"
    )
    sys.exit(1)

success, context = run_bootstrap_orchestration(
    None, _early_bootstrap_logger_install_py
)
if context.get("any_install_attempted", False):  # pragma: no cover
    _early_bootstrap_logger_install_py.info(
        f"Re-executing '{os.path.basename(sys.argv[0])}' due to bootstrap system package installations..."
    )
    try:
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e_exec_main:
        _early_bootstrap_logger_install_py.critical(
            f"FATAL: Failed to re-execute script: {e_exec_main}. Please re-run manually."
        )
        sys.exit(1)

_early_bootstrap_logger_install_py.info(
    "Initial system prerequisite checks completed successfully. Proceeding with main installer script logic."
)

from common.command_utils import (  # noqa: E402
    command_exists,
    log_map_server,
    run_command,
    run_elevated_command,
)
from common.core_utils import (  # noqa: E402
    setup_logging as common_setup_logging,
)
from common.system_utils import get_debian_codename  # noqa: E402

MAP_SERVER_INSTALLER_NAME = "installer.main_installer"
VENV_DIR = ".venv"

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
    "python": "🐍",
    "yaml": "📜",
}


def _install_uv_with_pipx_prereq(
    logger_instance: logging.Logger,
) -> bool:  # pragma: no cover
    """
    Attempts to install and/or upgrade the 'uv' package using the pipx utility. If pipx is
    not available on the system, an attempt will be made to install pipx either via the
    apt package manager or pip, depending on the system configuration and available tools.
    Adjustments to the system PATH environment variable are handled automatically for the
    current session if needed.

    Parameters:
        logger_instance (logging.Logger): An instance of a logger to record informational
        logs, warnings, and errors during the installation process.

    Returns:
        bool: True if the installation of 'uv' was successful, False otherwise.

    Raises:
        Exception: If installation steps encounter failures that the function cannot recover.
    """
    log_map_server(
        f"{SYMBOLS_OUTER.get('info', '>>')} Attempting uv installation using pipx...",
        "info",
        current_logger=logger_instance,
        app_settings=None,
    )

    if not command_exists("pipx"):
        log_map_server(
            f"{SYMBOLS_OUTER.get('warning', '!!')} pipx not found. Attempting to install pipx...",
            "warning",
            current_logger=logger_instance,
            app_settings=None,
        )
        try:
            if not ensure_pip_installed_prereq(logger_instance):
                log_map_server(
                    f"{SYMBOLS_OUTER.get('error', '!!')} pip is required to install pipx if apt method fails. Aborting pipx install.",
                    "error",
                    current_logger=logger_instance,
                    app_settings=None,
                )
                return False

            if command_exists("apt"):
                try:
                    run_elevated_command(
                        ["apt", "update"],
                        app_settings=None,
                        current_logger=logger_instance,
                    )
                    run_elevated_command(
                        ["apt", "install", "-y", "pipx"],
                        app_settings=None,
                        current_logger=logger_instance,
                    )
                    log_map_server(
                        f"{SYMBOLS_OUTER.get('success', 'OK')} pipx installed successfully via apt.",
                        "info",
                        current_logger=logger_instance,
                        app_settings=None,
                    )
                except Exception:
                    log_map_server(
                        f"{SYMBOLS_OUTER.get('warning', '!!')} Failed to install pipx via apt. Trying pip...",
                        "warning",
                        current_logger=logger_instance,
                        app_settings=None,
                    )

            if not command_exists("pipx"):
                pip_cmd = "pip3" if command_exists("pip3") else "pip"
                run_command(
                    [
                        sys.executable,
                        "-m",
                        pip_cmd,
                        "install",
                        "--user",
                        "pipx",
                    ],
                    app_settings=None,
                    current_logger=logger_instance,
                )
                run_command(
                    [sys.executable, "-m", "pipx", "ensurepath"],
                    app_settings=None,
                    current_logger=logger_instance,
                )
                log_map_server(
                    f"{SYMBOLS_OUTER.get('success', 'OK')} pipx installed for current user using {pip_cmd}. You may need to source your shell profile or open a new terminal.",
                    "info",
                    current_logger=logger_instance,
                    app_settings=None,
                )
        except Exception as e:
            log_map_server(
                f"{SYMBOLS_OUTER.get('error', '!!')} Failed to install pipx: {e}",
                "error",
                current_logger=logger_instance,
                app_settings=None,
            )
            return False

    pipx_bin_dir = os.path.expanduser("~/.local/bin")
    current_path = os.environ.get("PATH", "")
    if pipx_bin_dir not in current_path.split(os.pathsep):
        log_map_server(
            f"{SYMBOLS_OUTER.get('gear', '>>')} Adding '{pipx_bin_dir}' to PATH for current script session...",
            "info",
            current_logger=logger_instance,
            app_settings=None,
        )
        os.environ["PATH"] = f"{pipx_bin_dir}{os.pathsep}{current_path}"
        log_map_server(
            f"   New temporary PATH: {os.environ['PATH']}",
            "debug",
            current_logger=logger_instance,
            app_settings=None,
        )
        if not command_exists("pipx"):
            log_map_server(
                f"{SYMBOLS_OUTER.get('error', '!!')} pipx installed, but still not found in PATH. Manual PATH adjustment may be needed.",
                "error",
                current_logger=logger_instance,
                app_settings=None,
            )
            return False

    log_map_server(
        f"{SYMBOLS_OUTER.get('rocket', '>>')} Attempting to install/upgrade 'uv' with pipx (as user '{getpass.getuser()}')...",
        "info",
        current_logger=logger_instance,
        app_settings=None,
    )
    try:
        run_command(
            ["pipx", "install", "uv"],
            app_settings=None,
            capture_output=True,
            current_logger=logger_instance,
        )
        log_map_server(
            f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' installed/upgraded successfully using pipx.",
            "info",
            current_logger=logger_instance,
            app_settings=None,
        )
        return True
    except Exception as e:
        log_map_server(
            f"{SYMBOLS_OUTER.get('error', '!!')} Failed to install 'uv' using pipx: {e}",
            "error",
            current_logger=logger_instance,
            app_settings=None,
        )
        return False


def ensure_pip_installed_prereq(logger_instance: logging.Logger) -> bool:
    """
    Checks and ensures the 'pip' command is available on the system, attempting installation
    via the package manager if not found. It first checks the availability of 'pip' or 'pip3'
    and logs the corresponding state. If unavailable, it tries to install 'python3-pip'
    using 'apt'. If 'apt' is not present or the installation fails, the process logs an error
    and returns a failure state.

    Parameters:
        logger_instance (logging.Logger): The logger instance used for logging
        operational details.

    Returns:
        bool: True if the 'pip' command exists or gets successfully installed;
        False otherwise.
    """
    log_map_server(
        f"{SYMBOLS_OUTER.get('step', '->')} {SYMBOLS_OUTER.get('python', '🐍')} Checking for 'pip' command...",
        "info",
        current_logger=logger_instance,
        app_settings=None,
    )
    if command_exists("pip3") or command_exists("pip"):
        pip_cmd = "pip3" if command_exists("pip3") else "pip"
        log_map_server(
            f"{SYMBOLS_OUTER.get('success', 'OK')} '{pip_cmd}' command is already available.",
            "info",
            current_logger=logger_instance,
            app_settings=None,
        )
        return True
    log_map_server(
        f"{SYMBOLS_OUTER.get('warning', '!!')} 'pip' command not found. Attempting to install 'python3-pip'...",
        "warning",
        current_logger=logger_instance,
        app_settings=None,
    )
    if not command_exists("apt"):  # pragma: no cover
        log_map_server(
            f"{SYMBOLS_OUTER.get('error', '!!')} 'apt' command not found. Please install pip manually.",
            "error",
            current_logger=logger_instance,
            app_settings=None,
        )
        return False
    try:
        log_map_server(
            f"{SYMBOLS_OUTER.get('gear', '>>')} Updating apt cache...",
            "info",
            current_logger=logger_instance,
            app_settings=None,
        )
        run_elevated_command(
            ["apt", "update"],
            app_settings=None,
            capture_output=True,
            current_logger=logger_instance,
        )
        log_map_server(
            f"{SYMBOLS_OUTER.get('package', '>>')} Attempting to install 'python3-pip' using apt...",
            "info",
            current_logger=logger_instance,
            app_settings=None,
        )
        run_elevated_command(
            ["apt", "install", "-y", "python3-pip"],
            app_settings=None,
            capture_output=True,
            current_logger=logger_instance,
        )

        if command_exists("pip3") or command_exists("pip"):
            log_map_server(
                f"{SYMBOLS_OUTER.get('success', 'OK')} 'pip' (or 'pip3') command is now available.",
                "info",
                current_logger=logger_instance,
                app_settings=None,
            )
            return True
        else:  # pragma: no cover
            log_map_server(
                f"{SYMBOLS_OUTER.get('warning', '!!')} 'python3-pip' installed, but 'pip'/'pip3' not immediately in PATH.",
                "warning",
                current_logger=logger_instance,
                app_settings=None,
            )
            return True
    except Exception as e:  # pragma: no cover
        log_map_server(
            f"{SYMBOLS_OUTER.get('error', '!!')} Failed to install 'python3-pip' via apt: {e}",
            "error",
            current_logger=logger_instance,
            app_settings=None,
        )
        return False


def install_uv_prereq(logger_instance: logging.Logger) -> bool:
    """
    Checks for the installation of 'uv' in the system and installs it if not present.

    This function attempts to detect if the 'uv' executable is available in the system's PATH.
    If found, it verifies the installation by fetching its version. If not found, the function
    proceeds to install 'uv' using an appropriate installation method depending on the detected
    system configuration. For Debian distributions with specific codenames ('trixie', 'forky',
    'sid'), it attempts installation through `apt`. For other operating systems or in case of
    installation failure via `apt`, it falls back to using `pipx` for installation.

    Parameters:
        logger_instance (logging.Logger): Logger instance for logging messages and errors.

    Returns:
        bool: Returns True if 'uv' is installed successfully or is already present,
        otherwise False.
    """
    log_map_server(
        f"{SYMBOLS_OUTER.get('step', '->')} Checking for 'uv' installation...",
        "info",
        current_logger=logger_instance,
        app_settings=None,
    )
    if command_exists("uv"):
        log_map_server(
            f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' is already installed.",
            "info",
            current_logger=logger_instance,
            app_settings=None,
        )
        try:  # pragma: no cover
            run_command(
                ["uv", "--version"],
                app_settings=None,
                capture_output=True,
                current_logger=logger_instance,
            )
        except Exception:
            pass
        return True

    log_map_server(
        f"{SYMBOLS_OUTER.get('info', '>>')} 'uv' not found in PATH. Attempting installation...",
        "info",
        current_logger=logger_instance,
        app_settings=None,
    )
    codename = get_debian_codename(
        app_settings=None, current_logger=logger_instance
    )

    if codename in ["trixie", "forky", "sid"]:  # pragma: no cover
        log_map_server(
            f"{SYMBOLS_OUTER.get('package', '>>')} Debian '{codename}' detected. Attempting 'apt install uv'...",
            "info",
            current_logger=logger_instance,
            app_settings=None,
        )
        try:
            run_elevated_command(
                ["apt", "update"],
                app_settings=None,
                current_logger=logger_instance,
            )
            run_elevated_command(
                ["apt", "install", "-y", "uv"],
                app_settings=None,
                current_logger=logger_instance,
            )
            log_map_server(
                f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' installed successfully via apt.",
                "info",
                current_logger=logger_instance,
                app_settings=None,
            )
            return True
        except Exception as e:
            log_map_server(
                f"{SYMBOLS_OUTER.get('warning', '!!')} Failed to install 'uv' via apt on '{codename}': {e}. Falling back to pipx.",
                "warning",
                current_logger=logger_instance,
                app_settings=None,
            )
            return _install_uv_with_pipx_prereq(logger_instance)
    else:  # pragma: no cover
        log_map_server(
            f"{SYMBOLS_OUTER.get('package', '>>')} OS '{codename if codename else 'Unknown'}' detected. Using pipx to install 'uv'.",
            "info",
            current_logger=logger_instance,
            app_settings=None,
        )
        return _install_uv_with_pipx_prereq(logger_instance)


def ensure_pg_config_or_libpq_dev_installed_prereq(
    logger_instance: logging.Logger,
) -> bool:
    """
    Checks for the presence of the 'pg_config' command, which is required for psycopg
    compilation. If 'pg_config' is not found, attempts to install the 'libpq-dev'
    library using the APT package manager. This function aims to ensure that the
    prerequisites for psycopg installation are available on the system.

    The process involves logging the check results, attempting an installation if
    necessary, and reporting success or failure through the logger instance provided.

    Arguments:
        logger_instance (logging.Logger): The logger to use for recording messages
            during the execution of the function.

    Returns:
        bool: True if 'pg_config' is available or successfully installed; False otherwise.
    """
    log_map_server(
        f"{SYMBOLS_OUTER.get('step', '->')} Checking for 'pg_config' (for psycopg compilation)...",
        "info",
        current_logger=logger_instance,
        app_settings=None,
    )
    if command_exists("pg_config"):
        log_map_server(
            f"{SYMBOLS_OUTER.get('success', 'OK')} 'pg_config' is available.",
            "info",
            current_logger=logger_instance,
            app_settings=None,
        )
        return True
    log_map_server(
        f"{SYMBOLS_OUTER.get('warning', '!!')} 'pg_config' not found. Attempting to install 'libpq-dev'...",
        "warning",
        current_logger=logger_instance,
        app_settings=None,
    )
    if not command_exists("apt"):  # pragma: no cover
        log_map_server(
            f"{SYMBOLS_OUTER.get('error', '!!')} 'apt' not found. Cannot install 'libpq-dev'.",
            "error",
            current_logger=logger_instance,
            app_settings=None,
        )
        return False
    try:
        run_elevated_command(
            ["apt", "update"],
            app_settings=None,
            capture_output=True,
            current_logger=logger_instance,
        )
        run_elevated_command(
            ["apt", "install", "-y", "libpq-dev"],
            app_settings=None,
            capture_output=True,
            current_logger=logger_instance,
        )
        if command_exists("pg_config"):
            log_map_server(
                f"{SYMBOLS_OUTER.get('success', 'OK')} 'pg_config' now available after 'libpq-dev' install.",
                "info",
                current_logger=logger_instance,
                app_settings=None,
            )
            return True
        else:  # pragma: no cover
            log_map_server(
                f"{SYMBOLS_OUTER.get('error', '!!')} 'libpq-dev' installed, but 'pg_config' still not found.",
                "error",
                current_logger=logger_instance,
                app_settings=None,
            )
            return False
    except Exception as e:  # pragma: no cover
        log_map_server(
            f"{SYMBOLS_OUTER.get('error', '!!')} Failed to install 'libpq-dev' via apt: {e}",
            "error",
            current_logger=logger_instance,
            app_settings=None,
        )
        return False


def get_venv_python_executable(project_root: str, venv_dir_name: str) -> str:
    """
    Constructs the path to the Python executable within a virtual environment.

    This function generates the full path to the Python executable inside a
    specified virtual environment. It assumes the virtual environment uses
    the standard directory structure. The path is constructed by combining
    the given project root directory with the virtual environment directory
    name and the expected 'bin/python3' structure.

    Args:
        project_root (str): The root directory of the project where the virtual
            environment is located.
        venv_dir_name (str): The name of the directory containing the virtual
            environment.

    Returns:
        str: The full path to the Python executable within the specified virtual
        environment.
    """
    return os.path.join(project_root, venv_dir_name, "bin", "python3")


def generate_preseed_yaml_output(
    venv_python_exe: str,
    project_root_dir: str,
    logger_instance: logging.Logger,
) -> None:
    """
    Generates the default preseed data YAML to stdout using a specified Python executable within a virtual
    environment. The function composes and runs a Python script dynamically to handle the generation of YAML output
    from predefined configuration attributes in the project.

    The function ensures compatibility by managing imports dynamically based on project directory
    structure and modifies `sys.path` temporarily for module access. Logs relevant messages and handles
    failures gracefully.

    Arguments:
        venv_python_exe (str): The path to the Python executable in a virtual environment that will execute the script.
        project_root_dir (str): The root directory of the project, used to locate and import necessary modules for
            processing.
        logger_instance (logging.Logger): Logger instance used to log the progress, success, or errors during
            execution.
    """
    log_map_server(
        f"{SYMBOLS_OUTER.get('yaml', '📜')} Generating default preseed data YAML using venv Python: {venv_python_exe}",
        "info",
        current_logger=logger_instance,
        app_settings=None,
    )
    python_script_to_run = f"""
import yaml
import sys
import os

project_root_for_snippet = r'''{project_root_dir}''' 
if project_root_for_snippet not in sys.path:
    sys.path.insert(0, project_root_for_snippet)

DEFAULT_PACKAGE_PRESEEDING_VALUES = None
config_models_attributes = []

try:
    import setup.config_models
    config_models_attributes = dir(setup.config_models)
    DEFAULT_PACKAGE_PRESEEDING_VALUES = setup.config_models.DEFAULT_PACKAGE_PRESEEDING_VALUES
except ImportError as e:
    print(f"Error: Could not import setup.config_models module itself: {{e}}", file=sys.stderr)
    print(f"Attempted to add '{{project_root_for_snippet}}' to sys.path. Current sys.path: {{sys.path}}", file=sys.stderr)
    print("Ensure that 'setup' is a package (contains __init__.py).", file=sys.stderr)
    sys.exit(1)
except AttributeError as e:
    print(f"Error: Could not access DEFAULT_PACKAGE_PRESEEDING_VALUES from setup.config_models: {{e}}", file=sys.stderr)
    print(f"Attributes found in setup.config_models: {{config_models_attributes}}", file=sys.stderr)
    sys.exit(1)
except Exception as e_gen:
    print(f"An unexpected error occurred during import: {{e_gen}}", file=sys.stderr)
    print(f"Attributes found in setup.config_models (if module was imported): {{config_models_attributes}}", file=sys.stderr)
    sys.exit(1)

if DEFAULT_PACKAGE_PRESEEDING_VALUES is None:
    print("Error: DEFAULT_PACKAGE_PRESEEDING_VALUES is None after import attempts. This should not happen if imports were successful.", file=sys.stderr)
    print(f"Attributes found in setup.config_models at time of failure: {{config_models_attributes}}", file=sys.stderr)
    sys.exit(1)

output_data = {{'package_preseeding_values': DEFAULT_PACKAGE_PRESEEDING_VALUES}}
print("--- Start of Preseed YAML ---")
yaml.dump(output_data, sys.stdout, indent=2, sort_keys=False, default_flow_style=False)
print("--- End of Preseed YAML ---")
print("\\n# Instructions: Copy the section 'package_preseeding_values:' (including the key itself)", file=sys.stderr)
print("# and its content into your config.yaml file to customize preseed values.", file=sys.stderr)
"""
    try:
        run_command(
            [venv_python_exe, "-c", python_script_to_run],
            app_settings=None,
            cwd=project_root_dir,
            current_logger=logger_instance,
            capture_output=False,
            check=True,
        )
        log_map_server(
            f"{SYMBOLS_OUTER.get('success', 'OK')} Preseed YAML generated to stdout.",
            "info",
            current_logger=logger_instance,
            app_settings=None,
        )
    except Exception as e:  # pragma: no cover
        log_map_server(
            f"{SYMBOLS_OUTER.get('error', '!!')} Failed to generate preseed YAML: {e}",
            "error",
            current_logger=logger_instance,
            app_settings=None,
        )
        log_map_server(
            "   Ensure PyYAML is listed as a dependency in pyproject.toml and installed in the venv.",
            "error",
            current_logger=logger_instance,
            app_settings=None,
        )


def main() -> int:
    """
    Main entry point for the install script.

    This function:
    1. Sets up logging
    2. Ensures prerequisites are installed (uv, pg_config)
    3. Creates a virtual environment
    4. Installs project dependencies
    5. Launches the main map server installer

    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    common_setup_logging(
        log_level=logging.INFO,
        log_to_console=True,
        log_prefix="[PREREQ-INSTALL]",
    )
    prereq_script_logger = logging.getLogger("PrereqInstaller")

    script_name = os.path.basename(sys.argv[0])
    project_root = os.path.dirname(os.path.abspath(__file__))

    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    def get_install_py_help_text():
        """
        Main script for managing Python virtual environments, ensuring required system dependencies,
        and facilitating installation of project dependencies. This script also provides help text
        for understanding its usage and supported actions.

        Returns
        -------
        int
            Return code indicating the success or failure state of the script.
        """
        return f"""
Usage: {script_name} <action_flag_or_help> [arguments_for_main_map_server_entry]

This script performs the following actions:
1. Ensures 'uv' (Python packager and virtual environment manager) is installed.
2. Ensures 'libpq-dev' (for 'pg_config' needed by psycopg) is installed.
3. Creates a virtual environment in '{VENV_DIR}' using 'uv venv'.
4. Installs project dependencies from 'pyproject.toml' into the venv.
5. Based on the <action_flag>, performs the specified action.

Action Flags and Help (one is required if not -h/--help):
  -h, --help                  Show this help message, it will also attempt to display
                                help from '{MAP_SERVER_INSTALLER_NAME}'.

Arguments for {MAP_SERVER_INSTALLER_NAME}:
  (Displayed below if accessible when --help)
"""

    parser = argparse.ArgumentParser(
        description="Prerequisite installer for the Map Server Setup.",
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False,  # Disable default help
    )
    # Our custom help flag
    parser.add_argument(
        "-h",
        "--help",
        action="store_true",
        help="Show this help message and combined help for the main installer, then exit.",
    )

    args, unknown_args = parser.parse_known_args()

    if args.help:
        print(get_install_py_help_text())
        print("\n" + "=" * 80)
        print(
            f"Help information for the main setup module ({MAP_SERVER_INSTALLER_NAME}):"
        )
        print("=" * 80)
        venv_python_exe_for_help = get_venv_python_executable(
            project_root, VENV_DIR
        )
        main_installer_help_cmd = [
            venv_python_exe_for_help
            if os.path.exists(venv_python_exe_for_help)
            else sys.executable,
            "-m",
            MAP_SERVER_INSTALLER_NAME,
            "--help",
        ]
        try:
            subprocess.run(
                main_installer_help_cmd, check=False, cwd=project_root
            )
        except Exception as e_main_help:  # pragma: no cover
            log_map_server(
                f"{SYMBOLS_OUTER.get('error', '!!')} Error trying to display help from {MAP_SERVER_INSTALLER_NAME}: {e_main_help}",
                "error",
                current_logger=prereq_script_logger,
                app_settings=None,
            )
            print(
                f"Could not display help from {MAP_SERVER_INSTALLER_NAME}. Its venv might need to be set up first (e.g. run with --exit-on-complete)."
            )
        return 0

    if not install_uv_prereq(prereq_script_logger):  # pragma: no cover
        log_map_server(
            f"{SYMBOLS_OUTER.get('critical', '!!')} Failed to install 'uv'. Critical prerequisite. Aborting.",
            "critical",
            current_logger=prereq_script_logger,
            app_settings=None,
        )
        return 1
    if not command_exists("uv"):  # pragma: no cover
        log_map_server(
            f"{SYMBOLS_OUTER.get('critical', '!!')} 'uv' not found in PATH after install attempt. Aborting.",
            "critical",
            current_logger=prereq_script_logger,
            app_settings=None,
        )
        return 1
    log_map_server(
        f"{SYMBOLS_OUTER.get('success', 'OK')} 'uv' command is available.",
        "info",
        current_logger=prereq_script_logger,
        app_settings=None,
    )

    if not ensure_pg_config_or_libpq_dev_installed_prereq(
        prereq_script_logger
    ):  # pragma: no cover
        log_map_server(
            f"{SYMBOLS_OUTER.get('critical', '!!')} Failed to ensure 'pg_config' (via 'libpq-dev'). Python DB drivers may fail to build. Aborting.",
            "critical",
            current_logger=prereq_script_logger,
            app_settings=None,
        )
        return 1

    venv_path = os.path.join(project_root, VENV_DIR)
    venv_python_executable = get_venv_python_executable(
        project_root, VENV_DIR
    )

    log_map_server(
        f"{SYMBOLS_OUTER.get('step', '->')} Setting up virtual environment in '{venv_path}'...",
        "info",
        current_logger=prereq_script_logger,
        app_settings=None,
    )
    try:
        run_command(
            ["uv", "venv", VENV_DIR, "--python", sys.executable],
            app_settings=None,
            cwd=project_root,
            current_logger=prereq_script_logger,
        )
        log_map_server(
            f"{SYMBOLS_OUTER.get('success', 'OK')} Virtual environment created/updated at '{venv_path}'.",
            "info",
            current_logger=prereq_script_logger,
            app_settings=None,
        )

        log_map_server(
            f"{SYMBOLS_OUTER.get('package', '>>')} Installing/syncing project dependencies into '{VENV_DIR}' using 'uv pip install .'... ",
            "info",
            current_logger=prereq_script_logger,
            app_settings=None,
        )
        run_command(
            ["uv", "pip", "install", "."],
            app_settings=None,
            cwd=project_root,
            current_logger=prereq_script_logger,
        )
        log_map_server(
            f"{SYMBOLS_OUTER.get('success', 'OK')} Project dependencies installed/synced into '{VENV_DIR}'.",
            "info",
            current_logger=prereq_script_logger,
            app_settings=None,
        )
    except Exception as e:  # pragma: no cover
        log_map_server(
            f"{SYMBOLS_OUTER.get('critical', '!!')} Failed to set up virtual environment or install dependencies: {e}",
            "critical",
            current_logger=prereq_script_logger,
            app_settings=None,
        )
        return 1

    cmd_to_run_main_installer = [
        venv_python_executable,
        "-m",
        MAP_SERVER_INSTALLER_NAME,
    ] + unknown_args
    log_map_server(
        f"{SYMBOLS_OUTER.get('link', '>>')} Launching: {' '.join(cmd_to_run_main_installer)}",
        "debug",
        current_logger=prereq_script_logger,
        app_settings=None,
    )
    try:
        process_result = run_command(
            cmd_to_run_main_installer,
            app_settings=None,
            check=False,
            cwd=project_root,
            current_logger=prereq_script_logger,
        )
        result_code = process_result.returncode
        if result_code == 0:
            log_map_server(
                f"{SYMBOLS_OUTER.get('success', 'OK')} {SYMBOLS_OUTER.get('sparkles', '**')} Main map server setup ({MAP_SERVER_INSTALLER_NAME}) reported success!",
                "info",
                current_logger=prereq_script_logger,
                app_settings=None,
            )
        else:  # pragma: no cover
            log_map_server(
                f"{SYMBOLS_OUTER.get('error', '!!')} Main map server setup ({MAP_SERVER_INSTALLER_NAME}) reported failure or no action (exit code {result_code}).",
                "error",
                current_logger=prereq_script_logger,
                app_settings=None,
            )
        return result_code
    except Exception as e:  # pragma: no cover
        log_map_server(
            f"{SYMBOLS_OUTER.get('critical', '!!')} Unexpected error launching main map server setup: {e}",
            "critical",
            current_logger=prereq_script_logger,
            app_settings=None,
        )
        return 1


if __name__ == "__main__":  # pragma: no cover
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        temp_logger_ki = logging.getLogger("PrereqInstaller")
        if not temp_logger_ki.handlers:
            _handler_kb = logging.StreamHandler(sys.stderr)
            _formatter_kb = logging.Formatter(
                "[PREREQ-INSTALL] %(asctime)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            _handler_kb.setFormatter(_formatter_kb)
            temp_logger_ki.addHandler(_handler_kb)
            temp_logger_ki.setLevel(logging.INFO)
        temp_logger_ki.warning(
            f"\n{SYMBOLS_OUTER.get('warning', '!!')} Prerequisite installation interrupted by user. Exiting."
        )
        sys.exit(130)
    except SystemExit as e:
        sys.exit(e.code)
    except Exception as e_global:
        temp_logger_ex = logging.getLogger("PrereqInstaller")
        if not temp_logger_ex.handlers:
            _handler_ex = logging.StreamHandler(sys.stderr)
            _formatter_ex = logging.Formatter(
                "[PREREQ-INSTALL] %(asctime)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            _handler_ex.setFormatter(_formatter_ex)
            temp_logger_ex.addHandler(_handler_ex)
            temp_logger_ex.setLevel(logging.INFO)
        temp_logger_ex.critical(
            f"{SYMBOLS_OUTER.get('critical', '!!')} A critical unhandled error occurred in prerequisite installer: {e_global}"
        )
        import traceback

        temp_logger_ex.error(traceback.format_exc())
        sys.exit(1)
