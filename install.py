# filename: ot-osm-osrm-server/install.py
# !/usr/bin/env python3
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

from modular.orchestrator import ComponentOrchestrator
from modular.registry import ComponentRegistry
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
        "list", help="List available components"
    )

    apply_parser = subparsers.add_parser(
        "apply", help="Apply (install and configure) components"
    )
    apply_parser.add_argument(
        "components", nargs="*", help="Components to apply"
    )
    apply_parser.add_argument(
        "--force",
        action="store_true",
        help="Force reconfiguration even if already configured",
    )

    install_parser = subparsers.add_parser(
        "install", help="Install components (without configuring)"
    )
    install_parser.add_argument(
        "components", nargs="*", help="Components to install"
    )

    configure_parser = subparsers.add_parser(
        "configure", help="Configure components (without installing)"
    )
    configure_parser.add_argument(
        "components", nargs="*", help="Components to configure"
    )
    configure_parser.add_argument(
        "--force",
        action="store_true",
        help="Force reconfiguration even if already configured",
    )

    uninstall_parser = subparsers.add_parser(
        "uninstall", help="Uninstall components"
    )
    uninstall_parser.add_argument(
        "components", nargs="+", help="Components to uninstall"
    )

    unconfigure_parser = subparsers.add_parser(
        "unconfigure", help="Unconfigure components"
    )
    unconfigure_parser.add_argument(
        "components", nargs="+", help="Components to unconfigure"
    )

    status_parser = subparsers.add_parser(
        "status", help="Check status of components"
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

    # Legacy commands for backward compatibility
    setup_parser = subparsers.add_parser(
        "setup",
        help="Run the setup process for a component or group (legacy command)",
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

        orchestrator = ComponentOrchestrator(app_settings, logger)

        if parsed_args.command == "list":
            components_map = orchestrator.get_available_components()

            logger.info("Available components:")
            for name, component_class in components_map.items():
                description = getattr(component_class, "metadata", {}).get(
                    "description", ""
                )
                logger.info(f"  {name}: {description}")

            return 0

        elif parsed_args.command == "apply":
            if not parsed_args.components:
                logger.error("No components specified for application")
                return 1

            logger.info(
                f"Installing components: {', '.join(parsed_args.components)}"
            )
            install_success = orchestrator.install(parsed_args.components)

            if not install_success:
                logger.error("Installation failed")
                return 1

            logger.info("Installation completed successfully")

            # Then configure the components
            logger.info(
                f"Configuring components: {', '.join(parsed_args.components)}"
            )
            configure_success = orchestrator.configure(
                parsed_args.components, force=parsed_args.force
            )

            if configure_success:
                logger.info("Configuration completed successfully")
                return 0
            else:
                logger.error("Configuration failed")
                return 1

        elif parsed_args.command == "install":
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

        elif parsed_args.command == "configure":
            if not parsed_args.components:
                logger.error("No components specified for configuration")
                return 1

            success = orchestrator.configure(
                parsed_args.components, force=parsed_args.force
            )

            if success:
                logger.info("Configuration completed successfully")
                return 0
            else:
                logger.error("Configuration failed")
                return 1

        elif parsed_args.command == "uninstall":
            success = orchestrator.uninstall(parsed_args.components)

            if success:
                logger.info("Uninstallation completed successfully")
                return 0
            else:
                logger.error("Uninstallation failed")
                return 1

        elif parsed_args.command == "unconfigure":
            success = orchestrator.unconfigure(parsed_args.components)

            if success:
                logger.info("Unconfiguration completed successfully")
                return 0
            else:
                logger.error("Unconfiguration failed")
                return 1

        elif parsed_args.command == "status":
            requested_components: List[str] = parsed_args.components
            all_available_component_names = list(
                orchestrator.get_available_components().keys()
            )
            if not requested_components:
                requested_components = all_available_component_names

            status_dict = orchestrator.check_status(requested_components)

            if parsed_args.tree:
                logger.info("Component dependency tree:")

                tree = build_dependency_tree(
                    requested_components,
                    lambda c: ComponentRegistry.get_component_dependencies(c),
                    set(all_available_component_names),
                )

                all_dependencies = set()
                for deps in tree.values():
                    all_dependencies.update(deps)

                root_components = [
                    c
                    for c in requested_components
                    if c not in all_dependencies
                ]
                if not root_components:
                    root_components = requested_components

                display_tree(
                    tree,
                    root_components,
                    lambda c: status_dict.get(c, {}).get("installed", False),
                    lambda c: status_dict.get(c, {}).get("configured", False),
                    logger,
                )
            else:
                logger.info("Component status:")
                for component, status in status_dict.items():
                    installed = status.get("installed", False)
                    configured = status.get("configured", False)

                    status_str = "installed" if installed else "not installed"
                    status_str += ", " + (
                        "configured" if configured else "not configured"
                    )

                    logger.info(f"  {component}: {status_str}")

            return (
                0
                if all(
                    status.get("installed", False)
                    and status.get("configured", False)
                    for status in status_dict.values()
                )
                else 1
            )

        # Legacy commands for backward compatibility
        elif parsed_args.command == "setup":
            setup_components: List[str] = (
                list(orchestrator.get_available_components().keys())
                if parsed_args.component == "all"
                else [parsed_args.component]
            )

            if parsed_args.status:
                # Check if components are already configured
                logger.info(
                    f"Checking configuration status for: {parsed_args.component}"
                )

                status_dict = orchestrator.check_status(setup_components)

                logger.info("Configuration status:")
                for component, status in status_dict.items():
                    configured = status.get("configured", False)
                    status_str = (
                        "configured" if configured else "not configured"
                    )
                    logger.info(f"  {component}: {status_str}")

                return (
                    0
                    if all(
                        status.get("configured", False)
                        for status in status_dict.values()
                    )
                    else 1
                )

            elif parsed_args.dry_run:
                logger.info(
                    f"Dry run setup for component: {parsed_args.component}"
                )

                try:
                    ordered_components = (
                        ComponentRegistry.resolve_dependencies(
                            setup_components
                        )
                    )

                    logger.info(
                        "The following components would be configured (in order):"
                    )
                    for component_name in ordered_components:
                        component_class = ComponentRegistry.get_component(
                            component_name
                        )
                        description = getattr(
                            component_class, "metadata", {}
                        ).get("description", "")
                        logger.info(f"  {component_name}: {description}")

                    return 0
                except Exception as e:
                    logger.error(f"Error resolving dependencies: {str(e)}")
                    return 1

            else:
                logger.info(
                    f"Running setup for component: {parsed_args.component}"
                )

                success = orchestrator.configure(
                    setup_components, force=parsed_args.force
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
