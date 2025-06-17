#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Entry point for the OSM-OSRM Server installer.

This script provides a command-line interface for installing and managing
the OSM-OSRM Server components using a modular architecture.
"""

# DO NOT MOVE OR REMOVE
# This MUST be the very first thing that runs to ensure the environment is correct.
from modular_bootstrap.mb_bootstrap import ensure_venv_and_dependencies

ensure_venv_and_dependencies()
# END DO NOT MOVE OR REMOVE

import argparse
import logging
import sys
from typing import List, Optional

from modular.orchestrator import InstallerOrchestrator
from setup.config_loader import load_app_settings


def setup_logging(verbose: bool = False) -> logging.Logger:
    """
    Set up logging for the installer.

    Args:
        verbose: Whether to enable verbose logging.

    Returns:
        A configured logger instance.
    """
    log_level = logging.DEBUG if verbose else logging.INFO

    logger = logging.getLogger("osm_osrm_installer")
    logger.setLevel(log_level)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(console_handler)

    return logger


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """
    Parse command-line arguments.

    Args:
        args: Command-line arguments. If None, sys.argv[1:] is used.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Installer for OSM-OSRM Server"
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )

    subparsers = parser.add_subparsers(
        dest="command", help="Command to execute"
    )

    list_parser = subparsers.add_parser(  # noqa: F841
        "list", help="List available installers"
    )

    install_parser = subparsers.add_parser(
        "install", help="Install components"
    )
    install_parser.add_argument(
        "components", nargs="+", help="Components to install"
    )

    uninstall_parser = subparsers.add_parser(
        "uninstall", help="Uninstall components"
    )
    uninstall_parser.add_argument(
        "components", nargs="+", help="Components to uninstall"
    )
    status_parser = subparsers.add_parser(
        "status", help="Check installation status of components"
    )
    status_parser.add_argument(
        "components", nargs="+", help="Components to check"
    )

    return parser.parse_args(args)


def main(args: Optional[List[str]] = None) -> int:
    """
    Main entry point for the OSM-OSRM Server installer.

    Args:
        args: Command-line arguments. If None, sys.argv[1:] is used.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    parsed_args = parse_args(args)

    logger = setup_logging(parsed_args.verbose)

    try:
        app_settings = load_app_settings()

        orchestrator = InstallerOrchestrator(app_settings, logger)

        if parsed_args.command == "list":
            installers = orchestrator.get_available_installers()

            logger.info("Available installers:")
            for name, installer_class in installers.items():
                description = getattr(installer_class, "metadata", {}).get(
                    "description", ""
                )
                logger.info(f"  {name}: {description}")

            return 0

        elif parsed_args.command == "install":
            success = orchestrator.install(parsed_args.components)

            if success:
                logger.info("Installation completed successfully")
                return 0
            else:
                logger.error("Installation failed")
                return 1

        elif parsed_args.command == "uninstall":
            success = orchestrator.uninstall(parsed_args.components)

            if success:
                logger.info("Uninstallation completed successfully")
                return 0
            else:
                logger.error("Uninstallation failed")
                return 1

        elif parsed_args.command == "status":
            status = orchestrator.check_installation_status(
                parsed_args.components
            )

            logger.info("Installation status:")
            for component, installed in status.items():
                status_str = "installed" if installed else "not installed"
                logger.info(f"  {component}: {status_str}")

            return 0 if all(status.values()) else 1

        else:
            logger.error(
                "No command specified. Use --help for usage information."
            )
            return 1

    except Exception as e:
        logger.exception(f"Error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
