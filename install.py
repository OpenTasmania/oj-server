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
from typing import Callable, Dict, List, Optional, Set

from modular.orchestrator import InstallerOrchestrator
from modular.registry import InstallerRegistry
from modular_setup.orchestrator import SetupOrchestrator
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

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    return logger


def build_dependency_tree(
    component_names: List[str],
    get_dependencies_func: Callable,
    all_components: Set[str],
) -> Dict[str, List[str]]:
    """
    Build a dependency tree for the specified components.

    Args:
        component_names: A list of component names to build the tree for.
        get_dependencies_func: A function that returns the dependencies of a component.
        all_components: A set of all available component names.

    Returns:
        A dictionary mapping component names to their direct dependencies.
    """
    if not component_names:
        component_names = list(all_components)

    tree = {}
    visited = set()

    def visit(component: str):
        if component in visited:
            return
        visited.add(component)

        dependencies = get_dependencies_func(component)
        tree[component] = list(dependencies)

        for dependency in dependencies:
            visit(dependency)

    for component in component_names:
        visit(component)

    return tree


def display_tree(
    tree: Dict[str, List[str]],
    root_components: List[str],
    status_func: Callable,
    setup_status_func: Optional[Callable] = None,
    logger: Optional[logging.Logger] = None,
    prefix: str = "",
    is_last: bool = True,
) -> None:
    """
    Display a dependency tree.

    Args:
        tree: A dictionary mapping component names to their direct dependencies.
        root_components: A list of component names to display as roots of the tree.
        status_func: A function that returns the installation status of a component.
        setup_status_func: Optional function that returns the setup status of a component.
        logger: Optional logger instance. If not provided, print to stdout.
        prefix: Prefix for the current line (used for recursion).
        is_last: Whether the current component is the last in its branch (used for recursion).
    """
    for i, component in enumerate(root_components):
        is_last_component = i == len(root_components) - 1

        installed = status_func(component)
        status_str = "installed" if installed else "not installed"

        if setup_status_func:
            configured = setup_status_func(component)
            setup_status_str = (
                "configured" if configured else "not configured"
            )
            status_str = f"{status_str}, {setup_status_str}"

        if prefix == "":
            # Root level
            branch = "└── " if is_last_component else "├── "
            new_prefix = "    " if is_last_component else "│   "
        else:
            branch = prefix + ("└── " if is_last_component else "├── ")
            new_prefix = prefix + ("    " if is_last_component else "│   ")

        message = f"{branch}{component}: {status_str}"
        if logger:
            logger.info(message)
        else:
            print(message)

        if component in tree and tree[component]:
            display_tree(
                tree,
                tree[component],
                status_func,
                setup_status_func,
                logger,
                new_prefix,
                is_last_component,
            )


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
        "components", nargs="*", help="Components to install"
    )

    install_subparsers = install_parser.add_subparsers(
        dest="install_subcommand", help="Install subcommands"
    )

    install_setup_parser = install_subparsers.add_parser(
        "setup", help="Install and then setup a component or group"
    )
    install_setup_parser.add_argument(
        "component_name", help="Component or group to install and setup"
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
        "components",
        nargs="*",
        help="Components to check (if none specified, all components will be checked)",
    )
    status_parser.add_argument(
        "--tree",
        action="store_true",
        help="Display status as a dependency tree",
    )

    setup_parser = subparsers.add_parser(
        "setup", help="Run the setup process for a component or group"
    )
    setup_parser.add_argument(
        "component",
        nargs="?",
        default="all",
        help="The component or group to set up (default: all)",
    )
    setup_parser.add_argument(
        "--status",
        action="store_true",
        help="Check if components are already configured",
    )
    setup_parser.add_argument(
        "--force",
        action="store_true",
        help="Force reconfiguration even if already configured",
    )
    setup_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be configured without actually doing it",
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
            if (
                not hasattr(parsed_args, "install_subcommand")
                or parsed_args.install_subcommand is None
            ):
                if not parsed_args.components:
                    logger.error("No components specified for installation")
                    return 1

                success = orchestrator.install(parsed_args.components)

                if success:
                    logger.info("Installation completed successfully")
                    return 0
                else:
                    logger.error("Installation failed")
                    return 1

            elif parsed_args.install_subcommand == "setup":
                component = parsed_args.component_name

                logger.info(f"Installing component: {component}")
                success = orchestrator.install([component])

                if success:
                    logger.info(
                        f"Installation of {component} completed successfully"
                    )

                    logger.info(f"Running setup for component: {component}")
                    setup_orchestrator = SetupOrchestrator(logger=logger)
                    setup_success = setup_orchestrator.configure([component])

                    if setup_success:
                        logger.info(
                            f"Setup of {component} completed successfully"
                        )
                        return 0
                    else:
                        logger.error(f"Setup of {component} failed")
                        return 1
                else:
                    logger.error(f"Installation of {component} failed")
                    return 1

            else:
                logger.error("Invalid install subcommand")
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
            orchestrator._import_installer_modules()

            all_installers = InstallerRegistry.get_all_installers()

            components = parsed_args.components
            if not components:
                components = list(all_installers.keys())

            status = orchestrator.check_installation_status(components)

            setup_orchestrator = SetupOrchestrator(logger=logger)
            setup_orchestrator._import_configurators()

            setup_status = {}
            try:
                from modular_setup.registry import ConfiguratorRegistry

                all_configurators = (
                    ConfiguratorRegistry.get_all_configurators()
                )

                for component in components:
                    if component in all_configurators:
                        setup_status[component] = (
                            setup_orchestrator.check_status([component]).get(
                                component, False
                            )
                        )
            except Exception as e:
                logger.warning(f"Error checking setup status: {str(e)}")

            if parsed_args.tree:
                # Display status as a dependency tree
                logger.info("Component dependency tree:")

                tree = build_dependency_tree(
                    components,
                    lambda c: InstallerRegistry.get_installer_dependencies(c),
                    set(all_installers.keys()),
                )

                all_dependencies = set()
                for deps in tree.values():
                    all_dependencies.update(deps)

                root_components = [
                    c for c in components if c not in all_dependencies
                ]
                if not root_components:
                    root_components = components

                display_tree(
                    tree,
                    root_components,
                    lambda c: status.get(c, False),
                    lambda c: setup_status.get(c, False)
                    if c in setup_status
                    else None,
                    logger,
                )
            else:
                logger.info("Installation status:")
                for component, installed in status.items():
                    status_str = "installed" if installed else "not installed"

                    if component in setup_status:
                        configured = setup_status[component]
                        setup_status_str = (
                            "configured" if configured else "not configured"
                        )
                        status_str = f"{status_str}, {setup_status_str}"

                    logger.info(f"  {component}: {status_str}")

            return 0 if all(status.values()) else 1

        elif parsed_args.command == "setup":
            setup_orchestrator = SetupOrchestrator(logger=logger)

            components = (
                None
                if parsed_args.component == "all"
                else [parsed_args.component]
            )

            if parsed_args.status:
                # Check if components are already configured
                logger.info(
                    f"Checking configuration status for: {parsed_args.component}"
                )
                status = setup_orchestrator.check_status(components)

                logger.info("Configuration status:")
                for component, configured in status.items():
                    status_str = (
                        "configured" if configured else "not configured"
                    )
                    logger.info(f"  {component}: {status_str}")

                return 0 if all(status.values()) else 1

            elif parsed_args.dry_run:
                logger.info(
                    f"Dry run setup for component: {parsed_args.component}"
                )

                setup_orchestrator._import_configurators()

                if components is None:
                    from modular_setup.registry import ConfiguratorRegistry

                    components = list(
                        ConfiguratorRegistry.get_all_configurators().keys()
                    )

                try:
                    from modular_setup.registry import ConfiguratorRegistry

                    ordered_configurators = (
                        ConfiguratorRegistry.resolve_dependencies(components)
                    )

                    logger.info(
                        "The following components would be configured (in order):"
                    )
                    for configurator_name in ordered_configurators:
                        configurator_class = (
                            ConfiguratorRegistry.get_configurator(
                                configurator_name
                            )
                        )
                        description = getattr(
                            configurator_class, "metadata", {}
                        ).get("description", "")
                        logger.info(f"  {configurator_name}: {description}")

                    return 0
                except Exception as e:
                    logger.error(f"Error resolving dependencies: {str(e)}")
                    return 1

            else:
                logger.info(
                    f"Running setup for component: {parsed_args.component}"
                )

                success = setup_orchestrator.configure(
                    components, force=parsed_args.force
                )

                if success:
                    logger.info("Setup completed successfully")
                    return 0
                else:
                    logger.error("Setup failed")
                    return 1

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
