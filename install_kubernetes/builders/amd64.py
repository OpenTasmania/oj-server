import hashlib
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


def create_debian_installer_amd64() -> None:
    """
    Creates a custom Debian installer ISO for AMD64 architecture.
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
            ["wget", "-P", _IMAGE_OUTPUT_DIR, iso_url],
            env=os.environ.copy(),
            check=True,
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
            check=True,
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
    run_command(
        [
            "sudo",
            "xorriso",
            "-osirrox",
            "on",
            "-indev",
            iso_path,
            "-extract",
            "/",
            build_dir,
        ],
        check=True,
    )
    print("Step 5/9: ISO extracted.")

    preseed_file = "preseed.cfg"
    if os.path.exists(preseed_file):
        print(f"Step 6/9: Copying preseed file to {build_dir}/preseed.cfg...")
        shutil.copy(preseed_file, f"{build_dir}/preseed.cfg")
        with open(f"{build_dir}/preseed.cfg", "a") as f:
            f.write(
                "\nd-i preseed/late_command string cp /cdrom/ojp-server_"
                + _get_project_version_from_pyproject_toml()
                + "_all.deb /target/tmp/ && chroot /target /usr/bin/dpkg -i /tmp/ojp-server_"
                + _get_project_version_from_pyproject_toml()
                + "_all.deb && rm /target/tmp/ojp-server_"
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
        "Step 8/9: Copying ojp-server.deb and stripped installer script to ISO build directory..."
    )
    shutil.copy(
        os.path.join(
            _IMAGE_OUTPUT_DIR,
            f"ojp-server_{_get_project_version_from_pyproject_toml()}_all.deb",
        ),
        os.path.join(
            build_dir,
            f"ojp-server_{_get_project_version_from_pyproject_toml()}_all.deb",
        ),
    )
    shutil.copy(stripped_script_path, f"{build_dir}/install_kubernetes.py")
    print("Step 8/9: Files copied.")

    print(f"Step 9/9: Rebuilding ISO as {new_iso_filename}...")
    run_command(
        [
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
        ],
        check=True,
    )
    print("Step 8/9: ISO rebuilt.")
    print(f"Step 9/9: Cleaning up temporary build directory {build_dir}...")
    run_command(
        [
            "sudo",
            "rm",
            "-rf",
            os.path.join(_IMAGE_OUTPUT_DIR, "build/debian_installer"),
        ],
        check=True,
    )
    os.remove(stripped_script_path)
    print("Step 9/9: Temporary build directory cleaned up.")
    print(f"Successfully created {new_iso_filename}.")
