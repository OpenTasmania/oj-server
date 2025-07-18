# -*- coding: utf-8 -*-
import os
import re
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

_VERBOSE: bool = False
_DEBUG: bool = False
_IMAGE_OUTPUT_DIR: str = "images"

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def _get_project_version_from_pyproject_toml() -> str:
    """
    Determines the project version from the given pyproject.toml file.

    This function attempts to locate the `pyproject.toml` file in a predefined path relative
    to the project root. If the file is present, it reads the file content and extracts the
    project version from the `[project]` section. If the file is not found or the version
    cannot be located within the file, the function terminates the program with an error.

    Raises
    ------
    SystemExit
        If the pyproject.toml file is not found or the version cannot be extracted.
    Returns
    -------
    str
        The extracted version string from the pyproject.toml file.
    """
    pyproject_path = os.path.join(PROJECT_ROOT, "..", "..", "pyproject.toml")
    if not os.path.exists(pyproject_path):
        print(
            f"Error: {pyproject_path} not found. Cannot determine package version.",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(pyproject_path, "r") as f:
        content = f.read()

    match = re.search(
        r'\[project\]\\s*\\n[^\\[]*?version\\s*=\\s*"([^"]*)"',
        content,
        re.MULTILINE,
    )
    if match:
        return match.group(1)
    else:
        print(
            f"Error: Version not found in {pyproject_path} under [project].",
            file=sys.stderr,
        )
        sys.exit(1)


def _pause_for_debug(message: str) -> None:
    """
    Pauses the program execution for debugging purposes when debugging mode is active.

    This function prints a debug message and waits for user input to proceed if the
    debugging mode is enabled. The input message serves as an optional message to
    inform the user about the reason for the pause.

    Parameters:
        message (str): The message to display before pausing.

    Returns:
        None
    """
    if _DEBUG:
        print(f"DEBUG PAUSE: {message}")
        input("Press Enter to continue...")


def run_command(
    command: List[str],
    directory: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    check: bool = True,
    capture_output: bool = False,
    verbose: bool = False,
) -> subprocess.CompletedProcess:
    """
    Executes a shell command as a subprocess and optionally captures its output.

    This function runs a given command within an optional directory and environment,
    enabling additional verbosity and error handling. It allows for capturing stdout
    and stderr, and will fail gracefully if the command execution does not meet the
    expected conditions. The function supports verbose mode for improving debugging
    and adding verbosity to common command-line tools automatically.

    Parameters:
    command: List[str]
        The shell command to be executed as a list where each element is a part
        of the command.
    directory: Optional[str]
        The directory path to execute the command from. Default is None, which uses
        the current working directory.
    env: Optional[Dict[str, str]]
        An optional dictionary of environment variables to use when executing the
        command. Default is None, which inherits the environment from the current
        process.
    check: bool
        If True, the function validates the command's exit code and raises an error
        if it's non-zero. Default is True.
    capture_output: bool
        Whether to capture the command's stdout and stderr. If False, the output is
        printed directly to the console. Default is False.
    verbose: bool
        A flag to enable verbose logging of the command's execution. It also attempts
        to add verbosity flags to common command-line tools automatically. Default
        is False.

    Returns:
    subprocess.CompletedProcess
        The result of the executed command, containing information about the
        execution, such as exit code, stdout, and stderr.

    Raises:
    SystemExit
        Exits the current Python process with a status code of 1 if the command
        execution fails and `check` is True.

    Notes:
    This function modifies the command arguments to include additional verbosity
    for specific commands, such as docker, wget, apt, etc., when the verbose flag is
    enabled.
    """
    if verbose:
        print(f"[VERBOSE] Executing: {' '.join(command)}")

    if verbose and command[0] in [
        "wget",
        "vmdb2",
        "dpkg",
        "apt",
        "apt-get",
        "python3",
        "docker",
        "kubectl",
        "microk8s.kubectl",
    ]:
        if "-v" not in command and "--verbose" not in command:
            insert_pos = 1
            if command[0] == "docker" and command[1] in ["build", "pull"]:
                insert_pos = 2
            command.insert(
                insert_pos, "--verbose" if command[0] == "docker" else "-v"
            )

    result = subprocess.run(
        command,
        cwd=directory,
        env=env,
        capture_output=capture_output,
        text=True,
    )
    if check and result.returncode != 0:
        print(
            f"Error: Command failed with exit code {result.returncode}",
            file=sys.stderr,
        )
        if capture_output:
            print(f"STDOUT: {result.stdout}", file=sys.stderr)
            print(f"STDERR: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result


def check_and_install_tools(tools: List[Tuple[str, str, str]]) -> bool:
    """
    Checks if the specified tools are installed and installs missing ones.

    This function verifies the installation status of a list of tools by checking their
    corresponding package names. If a tool is missing or not installed correctly, it initiates
    an installation process using `sudo apt` or `sudo apt-get`. The function also includes
    specific verifications for the "vmdb2" tool to ensure it is configured for passwordless
    sudo execution. In case critical dependencies like `dpkg` are missing or required package
    managers (`apt`, `apt-get`) are not available, it provides appropriate error messages.

    Arguments:
        tools: List of tuples where each tuple contains three elements:
            - tool_name (str): The name of the tool.
            - package_name (str): The corresponding package name for the tool.
            - description (str): A short description of the tool's use case or purpose.

    Returns:
        bool: True if all tools are already installed or successfully installed.
              False if installation failed or critical dependencies are not available.

    Raises:
        SystemExit: If `dpkg` is not found on the system, the program exits with an error.
    """
    missing_packages: List[Tuple[str, str, str]] = []
    for tool_name, package_name, description in tools:
        try:
            result: subprocess.CompletedProcess = subprocess.run(
                ["dpkg", "-s", package_name],
                capture_output=True,
                text=True,
                check=False,
            )
            if (
                result.returncode == 0
                and "Status: install ok installed" in result.stdout
            ):
                if tool_name == "vmdb2":
                    try:
                        subprocess.run(
                            ["sudo", "-n", "vmdb2", "--version"],
                            check=True,
                            capture_output=True,
                            text=True,
                        )
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        print(
                            "Error: 'sudo vmdb2' requires a password or is not configured correctly for passwordless sudo.",
                            file=sys.stderr,
                        )
                        print(
                            "Please configure sudoers for vmdb2 or run this script with sudo.",
                            file=sys.stderr,
                        )
                        return False
                continue
        except FileNotFoundError:
            print(
                "Error: 'dpkg' command not found. Cannot verify package installation status.",
                file=sys.stderr,
            )
            print(
                "Please ensure dpkg is installed and in your PATH.",
                file=sys.stderr,
            )
            sys.exit(1)

        missing_packages.append((tool_name, package_name, description))

    if not missing_packages:
        return True

    print("The following tools are required and will be installed:")
    for tool_name, package_name, description in missing_packages:
        print(f"- {tool_name} (package: {package_name}) to {description}")

    if not shutil.which("sudo"):
        print(
            "Error: 'sudo' command not found. Cannot automatically install packages."
        )
        print("Please install the listed packages manually.")
        return False

    apt_cmd: Optional[str] = None
    if shutil.which("apt"):
        apt_cmd = "apt"
    elif shutil.which("apt-get"):
        apt_cmd = "apt-get"

    if not apt_cmd:
        print(
            "Error: Neither 'apt' nor 'apt-get' commands found. Cannot automatically install packages."
        )
        print("Please install the listed packages manually.")
        return False

    try:
        subprocess.run(
            ["sudo", "-n", apt_cmd, "update"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        print(
            f"Error: 'sudo {apt_cmd}' requires a password or is not configured correctly."
        )
        print("Please install the listed packages manually.")
        return False

    package_names_to_install: List[str] = [
        pkg for _, pkg, _ in missing_packages
    ]
    try:
        run_command(
            ["sudo", apt_cmd, "install", "-y"] + package_names_to_install,
            check=True,
        )
        return True
    except Exception as e:
        print(f"Error installing required tools: {e}", file=sys.stderr)
        print("Please install the listed packages manually.")
        return False


def create_debian_package(package_name: str = "oj-server") -> None:
    """
    Creates a Debian package for the specified package name.

    This function handles the entire process of creating a Debian package including
    checking and installing required tools, creating the build directory, copying
    necessary files, creating the DEBIAN control file, and finally building the
    Debian package. The function also performs cleanup of the temporary build
    directory after the package is successfully created.

    Parameters:
        package_name (str): The name of the package for which a Debian package
                            should be created. Defaults to "oj-server".

    Raises:
        SystemExit: If any required tool is missing and cannot be installed, the
                    system exits with a non-zero status.
    """
    version = _get_project_version_from_pyproject_toml()
    required_tools: List[Tuple[str, str, str]] = [
        ("dpkg-deb", "dpkg-dev", "build Debian packages"),
    ]

    print("Step 1/5: Checking and installing required tools...")
    _pause_for_debug(
        "Before checking and installing required tools for Debian package creation."
    )
    if not check_and_install_tools(required_tools):
        sys.exit(1)
    print("Step 1/5: Required tools checked/installed.")

    build_dir: str = os.path.join(
        _IMAGE_OUTPUT_DIR, f"build/debian_package_build/{package_name}"
    )
    package_output_name: str = os.path.join(
        _IMAGE_OUTPUT_DIR, f"{package_name}_{version}_all.deb"
    )

    print(f"Step 2/5: Creating build directory {build_dir}...")
    os.makedirs(f"{build_dir}/opt/{package_name}/kubernetes", exist_ok=True)
    print("Step 2/5: Build directory created.")

    print(
        f"Step 3/5: Copying kubernetes installer and directory to {build_dir}/opt/{package_name}"
    )
    shutil.copytree(
        os.path.join(PROJECT_ROOT, "..", "..", "kubernetes"),
        f"{build_dir}/opt/{package_name}/kubernetes",
        dirs_exist_ok=True,
    )
    shutil.copy2(
        os.path.join(PROJECT_ROOT, "..", "..", "kubernetes_installer.py"),
        f"{build_dir}/opt/{package_name}/",
    )
    print("Step 3/5: Kubernetes installer directory copied.")
    control_file_content: str = f"""Package: {package_name}
Version: {version}
Section: base
Priority: optional
Architecture: all
Maintainer: Your Name <debian@opentasmania.net>
Description: Open Journey Server Kubernetes Configurations
 This package contains the Kubernetes configurations for Open Journey Server.
"""
    control_dir: str = f"{build_dir}/DEBIAN"
    os.makedirs(control_dir, exist_ok=True)
    control_file_path: str = os.path.join(control_dir, "control")
    print(f"Step 4/5: Creating DEBIAN/control file at {control_file_path}...")
    with open(control_file_path, "w") as f:
        f.write(control_file_content)
    print("Step 4/5: DEBIAN/control file created.")

    print(f"Step 5/5: Building Debian package {package_output_name}...")
    run_command(
        [
            "dpkg-deb",
            "--root-owner-group",
            "--build",
            build_dir,
            package_output_name,
        ],
        check=True,
    )
    print("Step 5/5: Debian package built.")

    print(f"Successfully created Debian package: {package_output_name}")
    print(f"Cleaning up temporary build directory {build_dir}...")
    shutil.rmtree(
        os.path.join(_IMAGE_OUTPUT_DIR, "build/debian_package_build")
    )
    print("Temporary build directory cleaned up.")


def _create_stripped_installer_script() -> str:
    """
    Removes unnecessary components and creates a stripped version of the Kubernetes
    installer script.

    This function reads the original Kubernetes installer script, removes specific
    functions and statements that are not required for a stripped-down version, and
    writes the modified content to a new file. The stripped version excludes certain
    install options, unnecessary print statements, and options for creating Debian
    packages. The resultant stripped script is saved and its path is returned.

    Raises
    ------
    FileNotFoundError
        If the original script file cannot be found.
    IOError
        If there are issues in reading or writing to files.

    Returns
    -------
    str
        The file system path to the newly created stripped-down installer script.
    """
    original_script_path = os.path.join(
        PROJECT_ROOT, "..", "..", "kubernetes_installer.py"
    )
    with open(original_script_path, "r") as f:
        content = f.read()

    content = re.sub(
        r"\\ndef create_debian_package\\(.*\\?\\):.*\\?\\n(?=\\ndef|if __name__ == \"__main__\":|$)",
        "",
        content,
        flags=re.DOTALL | re.MULTILINE,
    )

    content = re.sub(
        r"\\ndef create_debian_installer_amd64\\(.*\\?\\):.*\\?\\n(?=\\ndef|if __name__ == \"__main__\":|$)",
        "",
        content,
        flags=re.DOTALL | re.MULTILINE,
    )

    content = re.sub(
        r"\\ndef create_debian_installer_rpi64\\(.*\\?\\):.*\\?\\n(?=\\ndef|if __name__ == \"__main__\":|$)",
        "",
        content,
        flags=re.DOTALL | re.MULTILINE,
    )

    content = re.sub(
        r"import hashlib\\n",
        "",
        content,
        flags=re.DOTALL,
    )

    content = re.sub(
        r"choices=\\[(.*?),\\s*\\\"build-deb\\\"\\s*\\]",
        r"choices=[\\1]",
        content,
        flags=re.DOTALL,
    )
    content = re.sub(
        r"choices=\\[\\\"build-deb\\\"\\s*,\\s*(.*?)\\]",
        r"choices=[\\1]",
        content,
        flags=re.DOTALL,
    )
    content = re.sub(
        r"choices=\\[\\\"build-deb\\\"\\]",
        r"choices=[]",
        content,
        flags=re.DOTALL,
    )

    content = re.sub(
        r"\\s*print\\('3\\\\. Create Debian Package'\\)",
        "",
        content,
    )
    content = content.replace("4. Back to Main Menu", "3. Back to Main Menu")

    content = re.sub(
        r"\\s*elif create_choice == \\\"3\\\":\\n\\s*create_debian_package\\(\\)",
        "",
        content,
    )

    content = re.sub(
        r"\\s*elif args.action == \\\"build-deb\\\":\\n\\s*create_debian_package\\(\\)\\n\\s*sys.exit\\(0\\)",
        "",
        content,
    )

    temp_script_path = os.path.join(
        PROJECT_ROOT,
        "..",
        "..",
        _IMAGE_OUTPUT_DIR,
        "install_kubernetes_stripped.py",
    )
    with open(temp_script_path, "w") as f:
        f.write(content)

    return temp_script_path
