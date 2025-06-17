#!/usr/bin/env python3
"""
Modular setup script for the OSM-OSRM Server.

This script is the central entry point for the modular installation and configuration
system. It imports and runs the InstallerOrchestrator from the modular directory
for installation tasks and the SetupOrchestrator from the modular_setup directory
for configuration tasks.

Before any installation or configuration tasks are performed, the script runs
a bootstrap process to ensure that all prerequisites are met.
"""

import argparse
import logging
import sys

from modular.orchestrator import InstallerOrchestrator
from modular_bootstrap import run_modular_bootstrap
from modular_setup.orchestrator import SetupOrchestrator


def setup_logging(verbose: bool = False) -> logging.Logger:
    """
    Set up logging for the script.

    Args:
        verbose: Whether to enable verbose logging.

    Returns:
        A configured logger instance.
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("setup_modular")


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        The parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Modular setup script for the OSM-OSRM Server."
    )

    # Configuration file
    parser.add_argument(
        "--config",
        "-c",
        default="config.yaml",
        help="Path to the configuration file (default: config.yaml)",
    )

    # Verbose output
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    # Action to perform
    action_group = parser.add_mutually_exclusive_group(required=True)

    # Installation actions
    action_group.add_argument(
        "--install",
        action="store_true",
        help="Install the system components",
    )
    action_group.add_argument(
        "--uninstall",
        action="store_true",
        help="Uninstall the system components",
    )
    action_group.add_argument(
        "--check-installation",
        action="store_true",
        help="Check the installation status of the system components",
    )

    # Configuration actions
    action_group.add_argument(
        "--configure",
        action="store_true",
        help="Configure the system",
    )
    action_group.add_argument(
        "--unconfigure",
        action="store_true",
        help="Unconfigure the system",
    )
    action_group.add_argument(
        "--status",
        action="store_true",
        help="Check the configuration status of the system",
    )

    # Components to install/uninstall/configure/unconfigure/check
    parser.add_argument(
        "--components",
        nargs="+",
        help="Components to install/uninstall/configure/unconfigure/check (default: all)",
    )

    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the script.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    args = parse_args()
    logger = setup_logging(args.verbose)

    try:
        # Run the modular bootstrap process to ensure prerequisites are met
        logger.info(
            "Running modular bootstrap process to ensure prerequisites are met..."
        )
        bootstrap_success, bootstrap_context = run_modular_bootstrap(
            None, logger
        )
        if not bootstrap_success:
            logger.error("Modular bootstrap process failed. Cannot continue.")
            return 1
        logger.info("Modular bootstrap process completed successfully.")

        # Load the configuration
        setup_orchestrator = SetupOrchestrator(
            config_file=args.config,
            logger=logger,
        )
        app_settings = setup_orchestrator.load_config()

        # Handle installation actions
        if args.install or args.uninstall or args.check_installation:
            # Create the installer orchestrator
            installer_orchestrator = InstallerOrchestrator(
                app_settings=app_settings,
                logger=logger,
            )

            # Get all available installers if no components are specified
            if args.components is None:
                available_installers = (
                    installer_orchestrator.get_available_installers()
                )
                components = list(available_installers.keys())
            else:
                components = args.components

            # Perform the requested installation action
            if args.install:
                logger.info("Installing system components...")
                success = installer_orchestrator.install(components)
                if success:
                    logger.info("System components installed successfully.")
                    return 0
                else:
                    logger.error("Failed to install system components.")
                    return 1

            elif args.uninstall:
                logger.info("Uninstalling system components...")
                success = installer_orchestrator.uninstall(components)
                if success:
                    logger.info("System components uninstalled successfully.")
                    return 0
                else:
                    logger.error("Failed to uninstall system components.")
                    return 1

            elif args.check_installation:
                logger.info("Checking system installation status...")
                status = installer_orchestrator.check_installation_status(
                    components
                )

                # Print the status of each component
                for component, installed in status.items():
                    status_str = "Installed" if installed else "Not installed"
                    logger.info(f"{component}: {status_str}")

                # Return 0 if all components are installed, 1 otherwise
                if all(status.values()):
                    logger.info("All components are installed.")
                    return 0
                else:
                    logger.warning("Some components are not installed.")
                    return 1

        # Handle configuration actions
        elif args.configure or args.unconfigure or args.status:
            # Create the setup orchestrator (already created above)
            orchestrator = setup_orchestrator

            # Perform the requested configuration action
            if args.configure:
                logger.info("Configuring the system...")
                success = orchestrator.configure(args.components)
                if success:
                    logger.info("System configured successfully.")
                    return 0
                else:
                    logger.error("Failed to configure the system.")
                    return 1

            elif args.unconfigure:
                logger.info("Unconfiguring the system...")
                success = orchestrator.unconfigure(args.components)
                if success:
                    logger.info("System unconfigured successfully.")
                    return 0
                else:
                    logger.error("Failed to unconfigure the system.")
                    return 1

            elif args.status:
                logger.info("Checking system configuration status...")
                status = orchestrator.check_status(args.components)

                # Print the status of each component
                for component, configured in status.items():
                    status_str = (
                        "Configured" if configured else "Not configured"
                    )
                    logger.info(f"{component}: {status_str}")

                # Return 0 if all components are configured, 1 otherwise
                if all(status.values()):
                    logger.info("All components are configured.")
                    return 0
                else:
                    logger.warning("Some components are not configured.")
                    return 1

        # Default return if no action was specified (should not happen due to required argument group)
        return 0

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=args.verbose)
        return 1


if __name__ == "__main__":
    sys.exit(main())
