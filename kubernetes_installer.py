#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script provides utilities for deploying Kubernetes configurations,
and creating custom Debian installer images for both AMD64 and Raspberry Pi 64-bit architectures.
It supports both interactive menu-driven operation and command-line arguments.
"""

import argparse
import os
import sys

from install_kubernetes.builders.amd64 import create_debian_installer_amd64
from install_kubernetes.builders.rpi64 import create_debian_installer_rpi64
from install_kubernetes.common import create_debian_package
from install_kubernetes.kubernetes_tools import (
    deploy,
    destroy,
    get_kubectl_command,
    get_managed_images,
)

_VERBOSE: bool = False
_DEBUG: bool = False
_IMAGE_OUTPUT_DIR: str = "images"


if __name__ == "__main__":
    managed_images = get_managed_images()
    epilog_text = f"Managed images: {', '.join(managed_images)}"

    actions = ["deploy", "destroy", "build-amd64", "build-rpi64", "build-deb"]
    args_list = sys.argv[1:]
    action = "menu"

    for act in actions:
        if act in args_list:
            action = act
            args_list.remove(act)
            break

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Kubernetes deployment script for OJM.",
        epilog=epilog_text,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--env",
        default="local",
        help="The environment to target (e.g., 'local', 'staging'). Cannot be used with --production.",
    )
    parser.add_argument(
        "--images",
        nargs="*",
        default=None,
        help="A space-delimited list of images to deploy or destroy. If not provided, all images will be processed.",
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
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Force overwrite of existing Docker images in the local registry. Only valid with 'deploy' action.",
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="Target the production environment. Cannot be used with --env.",
    )
    args: argparse.Namespace = parser.parse_args(args_list)
    args.action = action

    if args.production and args.env != "local":
        parser.error(
            "Cannot use --env and --production flags simultaneously."
        )

    if args.overwrite and args.action != "deploy":
        parser.error(
            "--overwrite is only available with the 'deploy' action."
        )

    _VERBOSE = args.verbose
    _DEBUG = args.debug
    if _DEBUG:
        _VERBOSE = True

    os.makedirs(_IMAGE_OUTPUT_DIR, exist_ok=True)

    script_path = os.path.abspath(__file__)
    is_installed_run = script_path.startswith("/opt/oj-server")
    package_name = "oj-server"

    if args.action == "deploy":
        kubectl_cmd = get_kubectl_command()
        print(f"Using '{kubectl_cmd}' for Kubernetes commands.")
        deploy(
            args.env,
            kubectl_cmd,
            is_installed=is_installed_run,
            images=args.images,
            overwrite=args.overwrite,
            production=args.production,
        )
        sys.exit(0)

    elif args.action == "destroy":
        kubectl_cmd = get_kubectl_command()
        destroy(
            args.env,
            kubectl_cmd,
            images=args.images,
        )
        sys.exit(0)

    elif args.action in ["build-amd64", "build-rpi64", "build-deb"]:
        if is_installed_run:
            print(
                "Error: Build actions can only be run from the source repository.",
                file=sys.stderr,
            )
            sys.exit(1)
        if args.action == "build-amd64":
            create_debian_installer_amd64()
        elif args.action == "build-rpi64":
            create_debian_installer_rpi64()
        elif args.action == "build-deb":
            create_debian_package()
        sys.exit(0)

    elif args.action == "menu":
        if is_installed_run:
            print(
                "Menu is not available for the installed script. Please use command-line arguments (deploy, destroy)."
            )
            sys.exit(1)

        while True:
            print("\n--- Kubernetes Deployment Script Menu ---")
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
                kubectl_cmd = get_kubectl_command()
                print(f"Using '{kubectl_cmd}' for Kubernetes commands.")
                deploy(
                    env=env_choice,
                    kubectl=kubectl_cmd,
                    is_installed=is_installed_run,
                )

            elif choice == "2":
                env_choice = (
                    input(
                        "Enter environment (local/production, default: local): "
                    ).lower()
                    or "local"
                )
                kubectl_cmd = get_kubectl_command()
                print(f"Using '{kubectl_cmd}' for Kubernetes commands.")
                destroy(env=env_choice, kubectl=kubectl_cmd)
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
                            rpi_model_to_pass: int = 4

                            if rpi_model_input == "":
                                create_debian_installer_rpi64(
                                    rpi_model_to_pass, _VERBOSE
                                )
                                break
                            else:
                                try:
                                    rpi_model_to_pass = int(rpi_model_input)
                                    if rpi_model_to_pass in [3, 4]:
                                        create_debian_installer_rpi64(
                                            rpi_model_to_pass, _VERBOSE
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
