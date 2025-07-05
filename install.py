# !/usr/bin/env python3
# filename: ot-osm-osrm-server/install.py
# -*- coding: utf-8 -*-
"""
Entry point for the OSM-OSRM Server installer.
"""

# DO NOT MOVE OR REMOVE
from bootstrap.mb_bootstrap import ensure_venv_and_dependencies

ensure_venv_and_dependencies()
# END DO NOT MOVE OR REMOVE

import argparse
import importlib
import logging
import sys
from typing import List, Optional

from installer.config_loader import load_app_settings
from installer.orchestrator import ComponentOrchestrator


def load_all_components(logger: logging.Logger):
    """Dynamically discover and import all component modules to register them."""
    try:
        import os

        import installer.components

        package = installer.components

        # Get all component directories using os.listdir
        component_dirs = []
        components_dir = package.__path__[0]

        for item in os.listdir(components_dir):
            item_path = os.path.join(components_dir, item)
            if os.path.isdir(item_path) and not item.startswith("__"):
                component_dirs.append(item)

        # Import installer and configurator modules for each component
        for component_name in component_dirs:
            # Handle the renamed component
            if component_name == "gtfs":
                logger.debug(
                    "Skipping 'gtfs' component, it has been renamed to 'py3gtfskit'"
                )
                continue
            if component_name == "py3gtfskit":
                configurator_module_name = (
                    "installer.components.py3gtfskit.py3gtfskit_configurator"
                )
                try:
                    importlib.import_module(configurator_module_name)
                except ImportError:
                    logger.debug(
                        f"No configurator module found for {component_name}"
                    )
                except Exception as e:
                    logger.error(
                        f"Error importing configurator module {configurator_module_name}: {str(e)}"
                    )
                continue

            # Try to import installer module
            installer_module_name = f"installer.components.{component_name}.{component_name}_installer"
            try:
                importlib.import_module(installer_module_name)
            except ImportError:
                logger.debug(
                    f"No installer module found for {component_name}"
                )
            except Exception as e:
                logger.error(
                    f"Error importing installer module {installer_module_name}: {str(e)}"
                )

            # Try to import configurator module
            configurator_module_name = f"installer.components.{component_name}.{component_name}_configurator"
            try:
                importlib.import_module(configurator_module_name)
            except ImportError:
                logger.debug(
                    f"No configurator module found for {component_name}"
                )
            except Exception as e:
                logger.error(
                    f"Error importing configurator module {configurator_module_name}: {str(e)}"
                )
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during component loading: {e}"
        )


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Set up logging for the installer."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logger = logging.getLogger("osm_osrm_installer")
    logger.setLevel(log_level)
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    return logger


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Installer for OSM-OSRM Server"
    )

    # First, extract any global flags like -v that might appear anywhere in the command
    all_args = args if args is not None else sys.argv[1:]
    global_parser = argparse.ArgumentParser(add_help=False)
    global_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )
    global_args, remaining_args = global_parser.parse_known_args(all_args)

    # Now set up the main parser with subcommands
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )
    subparsers = parser.add_subparsers(
        dest="command", help="Command to execute", required=True
    )

    list_parser = subparsers.add_parser(
        "list", help="List available components"
    )
    list_parser.add_argument(
        "components",
        nargs="*",
        help="Components to list (if none specified, all components will be listed)",
    )
    subparsers.add_parser(
        "generate-preseed",
        help="Generate package preseeding data as YAML and exit.",
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

    full_parser = subparsers.add_parser(
        "full",
        help="Install and configure all components in the recommended order",
    )
    full_parser.add_argument(
        "--force",
        action="store_true",
        help="Force reconfiguration of all components",
    )

    # Parse the remaining arguments with the main parser
    parsed_args = parser.parse_args(remaining_args)

    # Combine the global arguments with the subcommand arguments
    if global_args.verbose:
        parsed_args.verbose = True

    return parsed_args


def main(args: Optional[List[str]] = None) -> int:
    """Main entry point for the OSM-OSRM Server installer."""
    # Handle 'help' command as a synonym for '--help'
    if args is None:
        if len(sys.argv) > 1 and sys.argv[1] == "help":
            sys.argv[1] = "--help"
    elif args and args[0] == "help":
        args[0] = "--help"

    parsed_args = parse_args(args)
    logger = setup_logging(parsed_args.verbose)

    # Define component groups and their installation orders
    component_groups = {
        "full": [
            "ufw",
            "prerequisites",
            "docker",
            "nodejs",
            "postgres",
            "carto",
            "apache",
            "renderd",
            "pg_tileserv",
            "data_processing",
            "osrm",
            "nginx",
            "certbot",
        ]
    }

    logger.debug("Loading all available components...")
    load_all_components(logger)

    try:
        app_settings = load_app_settings()
        orchestrator = ComponentOrchestrator(app_settings, logger)

        if parsed_args.command == "list":
            # Check if specific components/groups were requested
            if parsed_args.components:
                for component_name in parsed_args.components:
                    # Check if the component is a group
                    if component_name in component_groups:
                        group_components = component_groups[component_name]
                        logger.info(
                            f"Components in group '{component_name}' (in installation order):"
                        )
                        for i, comp in enumerate(group_components, 1):
                            logger.info(f"  {i}. {comp}")
                    else:
                        logger.info(
                            f"'{component_name}' is not a recognized component group."
                        )
            else:
                # No specific components requested, list all available components
                components_dict = orchestrator.get_available_components()

                # Get the list of component directories to include non-registered components
                import os

                import installer.components

                component_dirs = []
                components_dir = installer.components.__path__[0]

                for item in os.listdir(components_dir):
                    item_path = os.path.join(components_dir, item)
                    if os.path.isdir(item_path) and not item.startswith("__"):
                        component_dirs.append(item)

                # Add "full" as a special case since it's a command, not a component
                # Filter out "apache-installer" as it's a duplicate of "apache"
                registered_components = set(components_dict.keys())
                if "apache-installer" in registered_components:
                    registered_components.remove("apache-installer")
                all_components = (
                    registered_components
                    | set(component_dirs)
                    | set(component_groups.keys())
                )

                if all_components:
                    logger.info("Available components:")
                    for name in sorted(all_components):
                        if name in component_groups:
                            logger.info(
                                f"  - {name} (group with {len(component_groups[name])} components)"
                            )
                        else:
                            logger.info(f"  - {name}")
                else:
                    logger.info("No components available.")
            return 0

        # Logic for 'full' command
        elif parsed_args.command == "full":
            logger.info("Starting full system installation...")

            # Use the component_groups dictionary to get the full installation order
            full_install_order = component_groups["full"]

            # Get all registered components
            registered_components = set(
                orchestrator.get_available_components().keys()
            )
            logger.debug(
                f"Registered components: {', '.join(sorted(registered_components))}"
            )

            # Filter out unregistered components
            filtered_components = []
            for comp in full_install_order:
                if comp in registered_components:
                    filtered_components.append(comp)
                    logger.debug(
                        f"Component '{comp}' is registered and will be installed."
                    )
                else:
                    logger.warning(
                        f"Component '{comp}' is not registered and will be skipped."
                    )

            if not filtered_components:
                logger.error("No registered components to install.")
                return 1

            logger.info(
                f"Installing registered components: {', '.join(filtered_components)}"
            )
            install_success = orchestrator.install(filtered_components)
            if not install_success:
                logger.error(
                    "Full installation failed during the installation phase."
                )
                return 1

            logger.info("Installation phase completed successfully.")

            logger.info(
                f"Configuring registered components: {', '.join(filtered_components)}"
            )
            configure_success = orchestrator.configure(
                filtered_components, force=parsed_args.force
            )
            if not configure_success:
                logger.error(
                    "Full installation failed during the configuration phase."
                )
                return 1

            logger.info(
                "🚀 Full installation and configuration completed successfully."
            )
            return 0

        # Logic for 'generate-preseed' command
        elif parsed_args.command == "generate-preseed":
            logger.info("Generating package preseeding data...")
            preseed_data = app_settings.package_preseeding_values
            if preseed_data:
                print("\n--- Start of Suggested Preseed YAML ---")
                # Manually construct YAML to ensure comments are included
                print("package_preseeding_values:")
                for package, values in preseed_data.items():
                    print(f"  {package}:")
                    for key, value in values.items():
                        # Properly quote the value in YAML
                        print(f'    {key}: "{value}"')
                print("--- End of Suggested Preseed YAML ---")
                print(
                    "\n# Instructions: Copy the 'package_preseeding_values' section into your config.yaml"
                )
                print("# to apply these preseed values during installation.")
            else:
                logger.info("No preseed data found in the configuration.")
            return 0

        # Logic for 'status' command
        elif parsed_args.command == "status":
            logger.info("Checking component status...")

            # If no components specified, check all available components
            if not parsed_args.components:
                all_components_dict = orchestrator.get_available_components()
                registered_components = set(all_components_dict.keys())
                if "apache-installer" in registered_components:
                    registered_components.remove("apache-installer")
                components_to_check = sorted(list(registered_components))
                logger.info(
                    f"No components specified, checking all {len(components_to_check)} available components"
                )
            else:
                components_to_check = parsed_args.components
                logger.info(
                    f"Checking status of specified components: {', '.join(components_to_check)}"
                )

            # Check status of components
            status_results = orchestrator.check_status(components_to_check)

            # Display results in a table
            logger.info("Component Status:")
            if status_results:
                # Determine column widths
                max_name_len = (
                    max(len(name) for name in status_results.keys())
                    if status_results
                    else 0
                )
                col_width = (
                    max(max_name_len, len("Component")) + 2
                )  # Add padding

                # Header
                header = f"{'Component':<{col_width}}{'Installed':<12}{'Configured':<12}"
                logger.info(header)
                logger.info("-" * len(header))

                # Rows
                for name, status in sorted(status_results.items()):
                    installed = "✅ Yes" if status["installed"] else "❌ No"
                    configured = "✅ Yes" if status["configured"] else "❌ No"
                    row = (
                        f"{name:<{col_width}}{installed:<12}{configured:<12}"
                    )
                    logger.info(row)
            else:
                logger.info("No components to display status for.")

            # If tree view is requested, display dependency tree
            if parsed_args.tree:
                logger.info("Dependency tree view not implemented yet")

            return 0

        # Logic for 'install' command
        elif parsed_args.command == "install":
            logger.info("Installing components...")

            # Check if components were specified
            if not parsed_args.components:
                logger.error("No components specified for installation")
                return 1

            components_to_install = []

            # Process each specified component or group
            for component_name in parsed_args.components:
                # Check if the component is a group
                if component_name in component_groups:
                    # Add all components from the group
                    group_components = component_groups[component_name]
                    logger.info(
                        f"Installing components from group '{component_name}': {', '.join(group_components)}"
                    )
                    components_to_install.extend(group_components)
                else:
                    # Add individual component
                    components_to_install.append(component_name)

            # Remove duplicates while preserving order
            unique_components = []
            for comp in components_to_install:
                if comp not in unique_components:
                    unique_components.append(comp)

            # Get all registered components
            registered_components = set(
                orchestrator.get_available_components().keys()
            )
            logger.debug(
                f"Registered components: {', '.join(sorted(registered_components))}"
            )

            # Filter out unregistered components
            filtered_components = []
            for comp in unique_components:
                if comp in registered_components:
                    filtered_components.append(comp)
                    logger.debug(
                        f"Component '{comp}' is registered and will be installed."
                    )
                else:
                    logger.warning(
                        f"Component '{comp}' is not registered and will be skipped."
                    )

            if not filtered_components:
                logger.error("No registered components to install.")
                return 1

            # Install the components
            logger.info(
                f"Installing registered components: {', '.join(filtered_components)}"
            )
            install_success = orchestrator.install(filtered_components)

            if not install_success:
                logger.error("Installation failed.")
                return 1

            logger.info("Installation completed successfully.")
            return 0

        # Logic for other commands (apply, configure, uninstall, etc.)
        # ... (rest of the command handling logic remains the same) ...

    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
