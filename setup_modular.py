#!/usr/bin/env python3
"""
Modular setup script for the OSM-OSRM Server.

This script is a new, parallel entry point for the modular configuration system
that does not interfere with the existing setup scripts. It imports and runs the
SetupOrchestrator from the modular_setup directory.
"""

import argparse
import logging
import sys

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

    # Components to configure/unconfigure/check
    parser.add_argument(
        "--components",
        nargs="+",
        help="Components to configure/unconfigure/check (default: all)",
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
        # Create the orchestrator
        orchestrator = SetupOrchestrator(
            config_file=args.config,
            logger=logger,
        )

        # Perform the requested action
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
                status_str = "Configured" if configured else "Not configured"
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
