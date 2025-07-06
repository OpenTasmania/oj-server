#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script provides utilities for deploying Kubernetes configurations,
and creating custom Debian installer images for both AMD64 and Raspberry Pi 64-bit architectures.
It supports both interactive menu-driven operation and command-line arguments.
"""

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

_VERBOSE: bool = False
_DEBUG: bool = False
_IMAGE_OUTPUT_DIR: str = "images"


def _pause_for_debug(message: str) -> None:
    """
    Pauses execution for debugging purposes by printing a debug message and waiting for user input.

    This function is only invoked if the _DEBUG flag is set to True. It allows developers
    to review specific debug messages and manually resume execution by pressing Enter.

    Parameters:
    message: str
        The debug message to be printed before pausing.

    Returns:
    None
    """
    if _DEBUG:
        print(f"DEBUG PAUSE: {message}")
        input("Press Enter to continue...")


def _get_project_version_from_pyproject_toml() -> str:
    """
    Reads the project version from pyproject.toml.

    Returns:
        str: The version string.

    Raises:
        SystemExit: If pyproject.toml is not found or version cannot be extracted.
    """
    pyproject_path = "pyproject.toml"
    if not os.path.exists(pyproject_path):
        print(
            f"Error: {pyproject_path} not found. Cannot determine package version.",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(pyproject_path, "r") as f:
        content = f.read()

    # Regex to find the version under [project]
    match = re.search(
        r'\[project\]\s*\n[^\[]*?version\s*=\s*"([^"]*)"',
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


def _create_stripped_installer_script() -> str:
    """
    Creates a temporary version of this script with Debian package creation
    functionality removed, for inclusion in installer images.
    """
    original_script_path = os.path.abspath(__file__)
    with open(original_script_path, "r") as f:
        content = f.read()

    # Remove the create_debian_package function block
    content = re.sub(
        r"\ndef create_debian_package\(.*\?\):.*\?\n(?=\ndef|if __name__ == "
        "__main__"
        ":|$)",
        "",
        content,
        flags=re.DOTALL | re.MULTILINE,
    )

    # Remove the create_debian_installer_amd64 function block
    content = re.sub(
        r"\ndef create_debian_installer_amd64\(.*\?\):.*\?\n(?=\ndef|if __name__ == "
        "__main__"
        ":|$)",
        "",
        content,
        flags=re.DOTALL | re.MULTILINE,
    )

    # Remove the create_debian_installer_rpi64 function block
    content = re.sub(
        r"\ndef create_debian_installer_rpi64\(.*\?\):.*\?\n(?=\ndef|if __name__ == "
        "__main__"
        ":|$)",
        "",
        content,
        flags=re.DOTALL | re.MULTILINE,
    )

    # Remove hashlib import
    content = re.sub(
        r"import hashlib\n",
        "",
        content,
        flags=re.DOTALL,
    )

    # Remove 'build-deb' from choices in argparse
    content = re.sub(
        r"choices=\[(.*?),\s*\"build-deb\"\s*\]",
        r"choices=[\1]",
        content,
        flags=re.DOTALL,
    )
    content = re.sub(
        r"choices=\[\"build-deb\"\s*,\s*(.*?)\]",
        r"choices=[\1]",
        content,
        flags=re.DOTALL,
    )
    content = re.sub(
        r"choices=\[\"build-deb\"\]",
        r"choices=[]",
        content,
        flags=re.DOTALL,
    )

    # Remove 'Create Debian Package' from menu
    content = re.sub(
        r"\s*print\('3\\. Create Debian Package'\)",
        "",
        content,
    )
    content = content.replace("4. Back to Main Menu", "3. Back to Main Menu")

    # Remove the menu option for create_debian_package
    content = re.sub(
        r"\s*elif create_choice == \"3\":\n\s*create_debian_package\(\)",
        "",
        content,
    )

    # Remove the CLI action for build-deb
    content = re.sub(
        r"\s*elif args.action == \"build-deb\":\n\s*create_debian_package\(\)\n\s*sys.exit\(0\)",
        "",
        content,
    )

    temp_script_path = os.path.join(
        os.path.dirname(original_script_path),
        _IMAGE_OUTPUT_DIR,
        "install_kubernetes_stripped.py",
    )
    with open(temp_script_path, "w") as f:
        f.write(content)

    return temp_script_path


def run_command(
    command: List[str],
    directory: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> None:
    """
    Runs a shell command and handles errors.

    If the global `_VERBOSE` flag is set, it prints the command being executed
    and attempts to add a verbose flag (`-v`) to certain known commands.
    If the command fails (returns a non-zero exit code), the script exits.

    Args:
        command (List[str]): A list of strings representing the command and its arguments.
        directory (Optional[str]): The directory in which to execute the command. Defaults to None (current working directory).
        env (Optional[Dict[str, str]]): A dictionary of environment variables to set for the command. Defaults to None.

    Raises:
        SystemExit: If the executed command returns a non-zero exit code.
    """
    if _VERBOSE:
        print(f"[VERBOSE] Executing: {' '.join(command)}")

    if _VERBOSE:
        if command[0] in [
            "wget",
            "vmdb2",
            "dpkg",
            "apt",
            "apt-get",
            "python3",
        ]:
            if "-v" not in command and "--verbose" not in command:
                command.insert(1, "-v")

    result: subprocess.CompletedProcess = subprocess.run(
        command, stdout=sys.stdout, stderr=sys.stderr, cwd=directory, env=env
    )
    if result.returncode != 0:
        print(
            f"Error: Command failed with exit code {result.returncode}",
            file=sys.stderr,
        )
        sys.exit(1)


def get_apt_http_proxy() -> Optional[str]:
    """
    Detects the APT HTTP proxy from system configuration files.

    This function searches common APT configuration paths for proxy settings.
    It looks for `Acquire::http::Proxy` directives in `/etc/apt/apt.conf`
    and files within `/etc/apt/apt.conf.d/`.

    Returns:
        Optional[str]: The detected APT HTTP proxy URL as a string, or None if no proxy is found.
    """
    proxy: Optional[str] = None
    apt_conf_dirs: List[str] = ["/etc/apt/apt.conf", "/etc/apt/apt.conf.d/"]

    for conf_path in apt_conf_dirs:
        if os.path.isfile(conf_path):
            with open(conf_path, "r") as f:
                content: str = f.read()
                match: Optional[re.Match] = re.search(
                    r'Acquire::http::Proxy\s+"([^"]+)";', content
                )
                if match:
                    proxy = match.group(1)
                    break
        elif os.path.isdir(conf_path):
            for root, _, files in os.walk(conf_path):
                for file in files:
                    if file.endswith(".conf"):
                        full_path: str = os.path.join(root, file)
                        with open(full_path, "r") as f:
                            content = f.read()
                            match = re.search(
                                r'Acquire::http::Proxy\s+"([^"]+)";', content
                            )
                            if match:
                                proxy = match.group(1)
                                break
                if proxy:
                    break
    return proxy


def check_and_install_tools(tools: List[Tuple[str, str, str]]) -> bool:
    """
    Checks if required tools are installed and attempts to install missing ones using APT.

    This function iterates through a list of tools, checking if their corresponding
    Debian packages are installed using `dpkg`. If a tool is missing, it adds it
    to a list of packages to be installed. It then attempts to install all missing
    packages at once using `sudo apt install -y`.

    Args:
        tools (List[Tuple[str, str, str]]): A list of tuples, where each tuple contains:
            - tool_name (str): The common name of the tool (e.g., "wget").
            - package_name (str): The Debian package name for the tool (e.g., "wget").
            - description (str): A brief description of the tool's purpose.

    Returns:
        bool: True if all required tools are installed (or successfully installed), False otherwise.
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
            ["sudo", apt_cmd, "install", "-y"] + package_names_to_install
        )
        return True
    except Exception as e:
        print(f"Error installing required tools: {e}", file=sys.stderr)
        print("Please install the listed packages manually.")
        return False


def get_kubectl_command() -> str:
    """
    Determines which Kubernetes command-line tool (kubectl or microk8s.kubectl) to use.

    If both `microk8s` and `kubectl` are available, it prompts the user to choose.
    If only one is available, it selects that one. If neither is found, it provides
    installation instructions and exits.

    Returns:
        str: The command string for the chosen Kubernetes tool (e.g., "kubectl" or "microk8s.kubectl").
    """
    has_microk8s: Optional[str] = shutil.which("microk8s")
    has_kubectl: Optional[str] = shutil.which("kubectl")

    if has_microk8s and has_kubectl:
        while True:
            print(
                "Both 'microk8s' and 'kubectl' are available. Which one would you like to use?"
            )
            print("1. microk8s")
            print("2. kubectl")
            choice: str = input("Please enter your choice (1/2): ")
            if choice == "1":
                return "microk8s.kubectl"
            elif choice == "2":
                return "kubectl"
            print("Invalid choice. Please enter '1' or '2'.")
    elif has_microk8s:
        return "microk8s.kubectl"
    elif has_kubectl:
        return "kubectl"
    else:
        while True:
            print(
                "Neither 'microk8s' nor 'kubectl' were found. Which would you like to install?"
            )
            print("1. microk8s")
            print("2. kubectl")
            choice = input("Please enter your choice (1/2): ")
            if choice == "1":
                print(
                    "MicroK8s is a lightweight, single-node Kubernetes distribution."
                )
                print(
                    "Installation instructions: https://microk8s.io/docs/getting-started"
                )
                sys.exit(1)
            elif choice == "2":
                print(
                    "kubectl is the command-line tool for interacting with a Kubernetes cluster."
                )
                print(
                    "Installation instructions: https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/"
                )
                sys.exit(1)
            print("Invalid choice. Please enter '1' or '2'.")


def deploy(env: str, kubectl: str) -> None:
    """
    Deploys the application using Kustomize.

    This function applies a Kustomize configuration located in
    `kubernetes/overlays/{env}` to the Kubernetes cluster.

    Args:
        env (str): The environment name (e.g., "local", "production") corresponding
                   to a Kustomize overlay directory.
        kubectl (str): The kubectl command to use (e.g., "kubectl" or "microk8s.kubectl").
    """
    print(f"Deploying '{env}' environment...")
    kustomize_path: str = f"/opt/openjourneymapper/kubernetes/overlays/{env}"
    command: List[str] = [kubectl, "apply", "-k", kustomize_path]
    run_command(command)


def destroy(env: str, kubectl: str) -> None:
    """
    Destroys the application deployment.

    This function deletes a Kustomize configuration located in
    `kubernetes/overlays/{env}` from the Kubernetes cluster.

    Args:
        env (str): The environment name (e.g., "local", "production") corresponding
                   to a Kustomize overlay directory.
        kubectl (str): The kubectl command to use (e.g., "kubectl" or "microk8s.kubectl").
    """
    print(f"Destroying '{env}' environment...")
    kustomize_path: str = f"/opt/openjourneymapper/kubernetes/overlays/{env}"
    command: List[str] = [kubectl, "delete", "-k", kustomize_path]
    run_command(command)


def create_debian_package(package_name: str = "openjourneymapper") -> None:
    """
    Creates a custom Debian package containing the Kubernetes configurations.

    Args:
        package_name (str): The name of the Debian package.
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
        "kubernetes",
        f"{build_dir}/opt/{package_name}/kubernetes",
        dirs_exist_ok=True,
    )
    shutil.copy2("install_kubernetes.py", f"{build_dir}/opt/{package_name}/")
    print("Step 3/5: Kubernetes installer directory copied.")
    control_file_content: str = f"""Package: {package_name}
Version: {version}
Section: base
Priority: optional
Architecture: all
Maintainer: Your Name <debian@opentasmania.net>
Description: Open Journey Mapper Kubernetes Configurations
 This package contains the Kubernetes configurations for Open Journey Mapper.
"""
    control_dir: str = f"{build_dir}/DEBIAN"
    os.makedirs(control_dir, exist_ok=True)
    control_file_path: str = os.path.join(control_dir, "control")
    print(f"Step 4/5: Creating DEBIAN/control file at {control_file_path}...")
    with open(control_file_path, "w") as f:
        f.write(control_file_content)
    print("Step 4/5: DEBIAN/control file created.")

    print(f"Step 5/5: Building Debian package {package_output_name}...")
    run_command([
        "dpkg-deb",
        "--root-owner-group",
        "--build",
        build_dir,
        package_output_name,
    ])
    print("Step 5/5: Debian package built.")

    print(f"Successfully created Debian package: {package_output_name}")
    print(f"Cleaning up temporary build directory {build_dir}...")
    shutil.rmtree(
        os.path.join(_IMAGE_OUTPUT_DIR, "build/debian_package_build")
    )
    print("Temporary build directory cleaned up.")


def create_debian_installer_amd64() -> None:
    """
    Creates a custom Debian installer ISO for AMD64 architecture.

    This function downloads a Debian netinst ISO, verifies its checksum,
    extracts its contents, injects a preseed file for unattended installation,
    modifies the bootloader configuration, and rebuilds the ISO.
    It requires `wget` and `xorriso` to be installed.
    """
    required_tools: List[Tuple[str, str, str]] = [
        ("wget", "wget", "download the Debian ISO"),
        ("xorriso", "xorriso", "extract and rebuild the ISO"),
        ("isolinux", "isolinux", "provide bootloader files for ISO creation"),
        (
            "grub-efi-amd64-bin",
            "grub-efi-amd64-bin",
            "provide EFI boot support",
        ),
        ("dpkg-deb", "dpkg-dev", "build Debian packages"),
    ]

    print("Step 1/9: Checking and installing required tools...")
    _pause_for_debug(
        "Before checking and installing required tools for AMD64 installer."
    )
    if not check_and_install_tools(required_tools):
        sys.exit(1)
    print("Step 1/9: Required tools checked/installed.")

    print("Creating Debian installer for amd64...")
    create_debian_package()
    stripped_script_path = _create_stripped_installer_script()
    base_url: str = (
        "https://cdimage.debian.org/cdimage/weekly-builds/amd64/iso-cd"
    )
    iso_filename: str = "debian-testing-amd64-netinst.iso"
    iso_path: str = os.path.join(_IMAGE_OUTPUT_DIR, iso_filename)
    iso_url: str = f"{base_url}/{iso_filename}"
    new_iso_filename: str = os.path.join(
        _IMAGE_OUTPUT_DIR, "debian-trixie-amd64-microk8s-unattended.iso"
    )
    build_dir: str = os.path.join(_IMAGE_OUTPUT_DIR, "build/debian_installer")

    print(f"Step 2/9: Downloading Debian ISO from {iso_url}...")
    if not os.path.exists(iso_path):
        run_command(
            ["wget", "-P", _IMAGE_OUTPUT_DIR, iso_url], env=os.environ.copy()
        )
    print("Step 2/9: Debian ISO downloaded.")

    print("Step 3/9: Downloading SHA512SUMS and verifying checksum...")
    sha512sums_url: str = f"{base_url}/SHA512SUMS"
    sha512sums_filename: str = "SHA512SUMS"
    sha512sums_path: str = os.path.join(
        _IMAGE_OUTPUT_DIR, sha512sums_filename
    )
    if not os.path.exists(sha512sums_path):
        run_command(
            ["wget", "-P", _IMAGE_OUTPUT_DIR, sha512sums_url],
            env=os.environ.copy(),
        )

    expected_checksum: str = ""
    with open(sha512sums_path, "r") as f:
        for line in f:
            if iso_filename in line:
                expected_checksum = line.split(" ")[0]
                break

    if not expected_checksum:
        print(
            f"Error: Could not find checksum for {iso_filename} in {sha512sums_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(iso_path, "rb") as f:
        calculated_checksum: str = hashlib.sha512(f.read()).hexdigest()

    if calculated_checksum != expected_checksum:
        print(f"Error: Checksum mismatch for {iso_filename}", file=sys.stderr)
        print(f"Expected: {expected_checksum}", file=sys.stderr)
        print(f"Calculated: {calculated_checksum}", file=sys.stderr)
        sys.exit(1)
    print("Step 3/9: Checksum verified successfully.")

    print(f"Step 4/9: Creating build directory {build_dir}...")
    os.makedirs(f"{build_dir}/EFI/BOOT", exist_ok=True)

    # Copy EFI boot files
    try:
        shutil.copy2(
            "/usr/lib/grub/x86_64-efi/monolithic/grubx64.efi",
            f"{build_dir}/EFI/BOOT/bootx64.efi",
        )
        print(
            "Copied grubx64.efi from monolithic path to EFI/BOOT/bootx64.efi"
        )
    except FileNotFoundError:
        print(
            "Warning: grubx64.efi not found in /usr/lib/grub/x86_64-efi/monolithic/. Attempting alternative location."
        )
        try:
            shutil.copy2(
                "/usr/lib/grub/x86_64-efi/grubx64.efi",
                f"{build_dir}/EFI/BOOT/bootx64.efi",
            )
            print(
                "Copied grubx64.efi from default path to EFI/BOOT/bootx64.efi"
            )
        except FileNotFoundError:
            print(
                "Warning: grubx64.efi not found in /usr/lib/grub/x86_64-efi/. Attempting another alternative location."
            )
            try:
                shutil.copy2(
                    "/usr/lib/grub-efi/x86_64-efi/grubx64.efi",
                    f"{build_dir}/EFI/BOOT/bootx64.efi",
                )
                print(
                    "Copied grubx64.efi from alternative location to EFI/BOOT/bootx64.efi"
                )
            except FileNotFoundError:
                print(
                    "Error: grubx64.efi not found in common locations. UEFI boot might fail.",
                    file=sys.stderr,
                )
                sys.exit(1)

    print("Step 4/9: Build directory created and EFI files copied.")

    print(f"Step 5/9: Extracting ISO to {build_dir}...")
    run_command([
        "sudo",
        "xorriso",
        "-osirrox",
        "on",
        "-indev",
        iso_path,
        "-extract",
        "/",
        build_dir,
    ])
    print("Step 5/9: ISO extracted.")

    # To generate a preseed.cfg file, you can extract the example file from
    # the downloaded ISO. After this script has run step 5, the ISO contents
    # will be available in the build directory. The example preseed file is
    # located within the initrd.gz archive. To extract it, you can use the
    # following commands from the project root directory:
    #
    # mkdir -p build/initrd_contents
    # cd build/initrd_contents
    # gzip -dc ../debian_installer/install.amd/initrd.gz | cpio -id
    # cp preseed.cfg ../../
    # cd ../..
    #
    # Once you have the preseed.cfg in your project root, you can customize it
    # and then re-run this script to create the unattended installer.
    preseed_file = "preseed.cfg"
    if os.path.exists(preseed_file):
        print(f"Step 6/9: Copying preseed file to {build_dir}/preseed.cfg...")
        shutil.copy(preseed_file, f"{build_dir}/preseed.cfg")
        with open(f"{build_dir}/preseed.cfg", "a") as f:
            f.write(
                "\nd-i preseed/late_command string cp /cdrom/openjourneymapper_"
                + _get_project_version_from_pyproject_toml()
                + "_all.deb /target/tmp/ && chroot /target /usr/bin/dpkg -i /tmp/openjourneymapper_"
                + _get_project_version_from_pyproject_toml()
                + "_all.deb && rm /target/tmp/openjourneymapper_"
                + _get_project_version_from_pyproject_toml()
                + "_all.deb\n"
            )
        print("Step 6/9: Added package installation command to preseed.cfg.")

        isolinux_cfg_path: str = f"{build_dir}/isolinux/isolinux.cfg"
        print(
            f"Step 7/9: Modifying bootloader configuration in {isolinux_cfg_path}..."
        )
        with open(isolinux_cfg_path, "r") as f:
            isolinux_cfg: str = f.read()

        isolinux_cfg = isolinux_cfg.replace(
            "append initrd=/install.amd/initrd.gz",
            "append initrd=/install.amd/initrd.gz preseed/file=/cdrom/preseed.cfg",
        )

        with open(isolinux_cfg_path, "w") as f:
            f.write(isolinux_cfg)
        print("Step 7/9: Bootloader configuration modified.")
    else:
        print(
            "Step 6/9: No preseed.cfg file found, skipping unattended installation."
        )
        print("Step 7/9: Bootloader configuration not modified.")

    print(
        "Step 8/9: Copying openjourneymapper.deb and stripped installer script to ISO build directory..."
    )
    shutil.copy(
        os.path.join(
            _IMAGE_OUTPUT_DIR,
            f"openjourneymapper_{_get_project_version_from_pyproject_toml()}_all.deb",
        ),
        os.path.join(
            build_dir,
            f"openjourneymapper_{_get_project_version_from_pyproject_toml()}_all.deb",
        ),
    )
    shutil.copy(stripped_script_path, f"{build_dir}/install_kubernetes.py")
    print("Step 8/9: Files copied.")

    print(f"Step 9/9: Rebuilding ISO as {new_iso_filename}...")
    # Rebuild the ISO
    run_command([
        "xorriso",
        "-as",
        "mkisofs",
        "-isohybrid-mbr",
        "/usr/lib/ISOLINUX/isohdpfx.bin",
        "-c",
        "isolinux/boot.cat",
        "-b",
        "isolinux/isolinux.bin",
        "-no-emul-boot",
        "-boot-load-size",
        "4",
        "-boot-info-table",
        "-eltorito-alt-boot",
        "--efi-boot",
        "EFI/boot/bootx64.efi",
        "-no-emul-boot",
        "-o",
        new_iso_filename,
        build_dir,
    ])
    print("Step 8/9: ISO rebuilt.")
    print(f"Step 9/9: Cleaning up temporary build directory {build_dir}...")
    run_command([
        "sudo",
        "rm",
        "-rf",
        os.path.join(_IMAGE_OUTPUT_DIR, "build/debian_installer"),
    ])
    os.remove(stripped_script_path)
    print("Step 9/9: Temporary build directory cleaned up.")
    print(f"Successfully created {new_iso_filename}.")


def create_debian_installer_rpi64(model: int = 4) -> None:
    """
    Creates a custom Debian installer image for Raspberry Pi 64-bit.

    This function clones the Raspberry Pi image-specs repository, injects
    commands to install MicroK8s into the image build process, and then
    uses `vmdb2` to build the custom Debian image. It requires several
    tools like `git`, `vmdb2`, `dosfstools`, `qemu-img`, etc., to be installed.

    Args:
        model (int): The Raspberry Pi model number (e.g., 3 or 4). Defaults to 4.
    """
    # DO NOT REMOVE THE NEXT LINE
    # Instructions on https://salsa.debian.org/raspi-team/image-specs
    required_tools: List[Tuple[str, str, str]] = [
        ("git", "git", "clone the RPi image-specs repository"),
        ("vmdb2", "vmdb2", "build the RPi image"),
        ("dosfstools", "dosfstools", "format filesystems"),
        ("qemu-img", "qemu-utils", "manage disk images"),
        (
            "qemu-aarch64-static",
            "qemu-user-static",
            "emulate ARM64 architecture",
        ),
        ("debootstrap", "debootstrap", "create a Debian base system"),
        ("update-binfmts", "binfmt-support", "register binary formats"),
        ("time", "time", "measure command execution time"),
        ("kpartx", "kpartx", "map disk partitions"),
        ("parted", "parted", "manipulate disk partitions"),
        ("bmaptool", "bmap-tools", "flash images efficiently"),
        ("python3", "python3", "run Python scripts"),
        ("zerofree", "zerofree", "zero out unused blocks"),
        ("fakemachine", "fakemachine", "create fake chroot environments"),
    ]

    print("Step 1/14: Checking and installing required tools...")
    _pause_for_debug(
        "Before checking and installing required tools for RPi64 installer."
    )
    if not check_and_install_tools(required_tools):
        sys.exit(1)
    print("Step 2/14: Required tools checked/installed.")

    print("Step 3/14: Checking for PyYAML package...")
    try:
        from importlib.util import find_spec

        if find_spec("yaml") is None:
            _pause_for_debug("PyYAML not found, before installing.")
            print("PyYAML not found, installing...")
            run_command([sys.executable, "-m", "pip", "install", "PyYAML"])
    except ImportError:
        _pause_for_debug(
            "importlib.util not found, before installing PyYAML."
        )
        print("importlib.util not found, installing PyYAML directly...")
        run_command([sys.executable, "-m", "pip", "install", "PyYAML"])
    print("Step 4/14: PyYAML is available.")

    _pause_for_debug("Before setting up RPi image directories.")
    print("Creating Debian installer for Raspberry Pi 64-bit...")
    create_debian_package()
    stripped_script_path = _create_stripped_installer_script()
    rpi_image_specs_dir: str = os.path.join(
        _IMAGE_OUTPUT_DIR, "build/rpi-image-specs"
    )
    output_image: str = "debian-trixie-rpi64-microk8s-unattended.img"

    _pause_for_debug(
        f"Before cloning Raspberry Pi image-specs repository to {rpi_image_specs_dir}."
    )
    print(
        f"Step 5/14: Cloning Raspberry Pi image-specs repository to {rpi_image_specs_dir}..."
    )
    if not os.path.exists(rpi_image_specs_dir):
        run_command([
            "git",
            "clone",
            "--recursive",
            "https://salsa.debian.org/raspi-team/image-specs.git",
            rpi_image_specs_dir,
        ])
    print("Step 6/14: Repository cloned.")

    _pause_for_debug(
        "Before copying openjourneymapper.deb and stripped installer script to RPi image build directory."
    )
    print(
        "Step 7/14: Copying openjourneymapper.deb and stripped installer script to RPi image build directory..."
    )
    shutil.copy(
        os.path.join(
            _IMAGE_OUTPUT_DIR,
            f"openjourneymapper_{_get_project_version_from_pyproject_toml()}_all.deb",
        ),
        f"{rpi_image_specs_dir}/openjourneymapper_{_get_project_version_from_pyproject_toml()}_all.deb",
    )
    shutil.copy(
        stripped_script_path, f"{rpi_image_specs_dir}/install_kubernetes.py"
    )
    print("Step 7/14: Files copied.")

    _pause_for_debug("Before preparing commands to inject into image build.")
    print("Step 8/14: Preparing commands to inject into image build...")
    inject_commands: List[str] = [
        "apt-get update",
        "apt-get install --yes snapd",
        "snap install microk8s --classic",
        "usermod --append --groups microk8s user",
        "microk8s status --wait-ready",
        f"cp /openjourneymapper_{_get_project_version_from_pyproject_toml()}_all.deb /tmp/",
        f"dpkg -i /tmp/openjourneymapper_{_get_project_version_from_pyproject_toml()}_all.deb",
        f"rm /tmp/openjourneymapper_{_get_project_version_from_pyproject_toml()}_all.deb",
    ]
    print(
        "Step 8/14: Modifying generate-recipe.py to include MicroK8s installation..."
    )
    generate_recipe_path: str = os.path.join(
        rpi_image_specs_dir, "generate-recipe.py"
    )
    with open(generate_recipe_path, "r") as f:
        generate_recipe_content: str = f.read()

    commands_as_string = ",\n    ".join([
        f'"{cmd}"' for cmd in inject_commands
    ])
    replacement_string = (
        f"extra_chroot_shell_cmds = [\n    {commands_as_string}\n]"
    )
    target_line = "extra_chroot_shell_cmds = []"
    modified_generate_recipe_content: str = generate_recipe_content.replace(
        target_line, replacement_string
    )

    temp_generate_recipe_path: str = os.path.join(
        rpi_image_specs_dir, "temp_generate-recipe.py"
    )
    with open(temp_generate_recipe_path, "w") as f:
        f.write(modified_generate_recipe_content)
    print("Step 9/14: Commands prepared.")

    _pause_for_debug("Before modifying generate-recipe.py.")
    print(
        f"Step 10/14: Executing modified generate-recipe.py for model {model}..."
    )
    # Execute the modified generate-recipe.py
    run_command(
        ["python3", "temp_generate-recipe.py", str(model), "trixie"],
        directory=rpi_image_specs_dir,
    )
    print("Step 11/14: Image recipe generated.")

    generated_yaml_filename: str = f"raspi_{model}_trixie.yaml"

    output_image_path: str = os.path.join(
        os.getcwd(), _IMAGE_OUTPUT_DIR, output_image
    )

    _pause_for_debug("Before building RPi image using corrected recipe.")
    print("Step 12/14: Building RPi image using corrected recipe...")
    vmdb2_command: List[str] = [
        "sudo",
        "vmdb2",
        f"--rootfs-tarball={output_image}.tar.gz",
        "--output",
        output_image_path,
        generated_yaml_filename,
        "--log",
        f"{os.getcwd()}/{_IMAGE_OUTPUT_DIR}/{output_image}.log",
    ]
    if _VERBOSE:
        vmdb2_command.insert(2, "--verbose")
    else:
        print(
            "vmdb2 execution can take a very long time with very little feedback. Please use other tools to monitor progress,"
        )
    run_command(vmdb2_command, directory=rpi_image_specs_dir)
    print("Step 13/14: RPi image built.")

    _pause_for_debug("Before cleaning up temporary files.")
    print("Step 14/14: Cleaning up temporary files...")
    os.remove(temp_generate_recipe_path)
    shutil.rmtree(rpi_image_specs_dir)
    os.remove(stripped_script_path)

    print(f"Successfully created {output_image}")


if __name__ == "__main__":
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Kubernetes deployment script for OJM."
    )
    parser.add_argument(
        "action",
        nargs="?",
        default="menu",
        choices=[
            "menu",
            "deploy",
            "destroy",
            "build-amd64",
            "build-rpi64",
            "build-deb",
        ],
        help="The action to perform.",
    )
    parser.add_argument(
        "--env",
        default="local",
        help="The environment to target (default: local).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output.",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable debug mode (implies --verbose and pauses before each step).",
    )
    args: argparse.Namespace = parser.parse_args()

    _VERBOSE = args.verbose
    _DEBUG = args.debug
    if _DEBUG:
        _VERBOSE = True

    # Create the images directory if it doesn't exist
    os.makedirs(_IMAGE_OUTPUT_DIR, exist_ok=True)

    if args.action == "menu":
        while True:
            print("--- Kubernetes Deployment Script Menu ---")
            print("1. Deploy (apply Kustomize configuration)")
            print("2. Destroy (delete Kustomize configuration)")
            print("3. Create (build custom Debian installer images)")
            print("4. Exit")
            choice: str = input("Please enter your choice (1-4): ")

            if choice == "1":
                env_choice: str = (
                    input(
                        "Enter environment (local/production, default: local): "
                    ).lower()
                    or "local"
                )
                kubectl_cmd: str = get_kubectl_command()
                print(f"Using '{kubectl_cmd}' for Kubernetes commands.")
                deploy(env_choice, kubectl_cmd)
            elif choice == "2":
                env_choice = (
                    input(
                        "Enter environment (local/production, default: local): "
                    ).lower()
                    or "local"
                )
                kubectl_cmd = get_kubectl_command()
                print(f"Using '{kubectl_cmd}' for Kubernetes commands.")
                destroy(env_choice, kubectl_cmd)
            elif choice == "3":
                while True:
                    print("\n--- Create Installer Image Menu ---")
                    print("1. Create AMD64 Debian Installer")
                    print("2. Create RPi64 Debian Installer")
                    print("3. Create Debian Package")
                    print("4. Back to Main Menu")
                    create_choice: str = input(
                        "Please enter your choice (1-4): "
                    )
                    if create_choice == "1":
                        create_debian_installer_amd64()
                        break
                    elif create_choice == "2":
                        while True:
                            rpi_model_input: str = input(
                                "Enter Raspberry Pi model (3 or 4, default: 4): "
                            )
                            rpi_model_to_pass: int = 4  # Default value

                            if rpi_model_input == "":
                                create_debian_installer_rpi64(
                                    rpi_model_to_pass
                                )
                                break
                            else:
                                try:
                                    rpi_model_to_pass = int(rpi_model_input)
                                    if rpi_model_to_pass in [3, 4]:
                                        create_debian_installer_rpi64(
                                            rpi_model_to_pass
                                        )
                                        break
                                    else:
                                        print(
                                            "Invalid Raspberry Pi model. Please enter 3 or 4."
                                        )
                                except ValueError:
                                    print(
                                        "Invalid input. Please enter a number (3 or 4)."
                                    )
                        break
                    elif create_choice == "3":
                        create_debian_package()
                        break
                    elif create_choice == "4":
                        break
                    else:
                        print("Invalid choice. Please enter 1, 2, 3, or 4.")
            elif choice == "4":
                print("Exiting.")
                sys.exit(0)
            else:
                print("Invalid choice. Please enter 1, 2, 3, or 4.")
    elif args.action == "deploy":
        kubectl_cmd = get_kubectl_command()
        print(f"Using '{kubectl_cmd}' for Kubernetes commands.")
        deploy(args.env, kubectl_cmd)
    elif args.action == "destroy":
        kubectl_cmd = get_kubectl_command()
        print(f"Using '{kubectl_cmd}' for Kubernetes commands.")
        destroy(args.env, kubectl_cmd)
    elif args.action == "build-amd64":
        create_debian_installer_amd64()
        sys.exit(0)
    elif args.action == "build-rpi64":
        create_debian_installer_rpi64()
        sys.exit(0)
    elif args.action == "build-deb":
        create_debian_package()
        sys.exit(0)
