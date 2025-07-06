import os
import shutil
import sys
from typing import List, Tuple

from install_kubernetes.common import (
    _IMAGE_OUTPUT_DIR,
    _create_stripped_installer_script,
    _get_project_version_from_pyproject_toml,
    _pause_for_debug,
    check_and_install_tools,
    create_debian_package,
    run_command,
)


def create_debian_installer_rpi64(
    model: int = 4, verbose: bool = False
) -> None:
    """
    Creates a custom Debian installer image for Raspberry Pi 64-bit.
    """
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
            run_command(
                [sys.executable, "-m", "pip", "install", "PyYAML"], check=True
            )
    except ImportError:
        _pause_for_debug(
            "importlib.util not found, before installing PyYAML."
        )
        print("importlib.util not found, installing PyYAML directly...")
        run_command(
            [sys.executable, "-m", "pip", "install", "PyYAML"], check=True
        )
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
        run_command(
            [
                "git",
                "clone",
                "--recursive",
                "https://salsa.debian.org/raspi-team/image-specs.git",
                rpi_image_specs_dir,
            ],
            check=True,
        )
    print("Step 6/14: Repository cloned.")

    _pause_for_debug(
        "Before copying ojp-server.deb and stripped installer script to RPi image build directory."
    )
    print(
        "Step 7/14: Copying ojp-server.deb and stripped installer script to RPi image build directory..."
    )
    shutil.copy(
        os.path.join(
            _IMAGE_OUTPUT_DIR,
            f"ojp-server_{_get_project_version_from_pyproject_toml()}_all.deb",
        ),
        f"{rpi_image_specs_dir}/ojp-server_{_get_project_version_from_pyproject_toml()}_all.deb",
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
        f"cp /ojp-server_{_get_project_version_from_pyproject_toml()}_all.deb /tmp/",
        f"dpkg -i /tmp/ojp-server_{_get_project_version_from_pyproject_toml()}_all.deb",
        f"rm /tmp/ojp-server_{_get_project_version_from_pyproject_toml()}_all.deb",
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
    run_command(
        ["python3", "temp_generate-recipe.py", str(model), "trixie"],
        directory=rpi_image_specs_dir,
        check=True,
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
    if verbose:
        vmdb2_command.insert(2, "--verbose")
    else:
        print(
            "vmdb2 execution can take a very long time with very little feedback. Please use other tools to monitor progress,"
        )
    run_command(vmdb2_command, directory=rpi_image_specs_dir, check=True)
    print("Step 13/14: RPi image built.")

    _pause_for_debug("Before cleaning up temporary files.")
    print("Step 14/14: Cleaning up temporary files...")
    os.remove(temp_generate_recipe_path)
    shutil.rmtree(rpi_image_specs_dir)
    os.remove(stripped_script_path)

    print(f"Successfully created {output_image}")
