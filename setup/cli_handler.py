# osm/setup/cli_handler.py
# -*- coding: utf-8 -*-
"""
Handles Command Line Interface (CLI) interactions for the map server setup.

This module includes functions for prompting the user, displaying
configuration, and managing setup state through a simple CLI menu.
"""

import datetime
import logging

from . import config  # For SYMBOLS, config values
from .command_utils import log_map_server

# Assuming direct use for CLI menu:
from .state_manager import clear_state_file, view_completed_steps

module_logger = logging.getLogger(__name__)


def cli_prompt_for_rerun(prompt_message: str) -> bool:
    """
    Handle yes/no prompts for the CLI.

    Args:
        prompt_message: The message to display to the user.

    Returns:
        True if the user inputs 'y', False otherwise.
    """
    try:
        user_input = (
            input(f"   {config.SYMBOLS['info']} {prompt_message} (y/N): ")
            .strip()
            .lower()
        )
        return user_input == "y"
    except EOFError:  # Handle non-interactive environments or Ctrl+D
        log_map_server(
            f"{config.SYMBOLS['warning']} No user input (EOF), defaulting to "
            f"'N' for prompt: '{prompt_message}'",
            "warning",
            module_logger,
        )
        return False


def view_configuration(current_logger: logging.Logger = None) -> None:
    """
    Display the current effective configuration values.

    Args:
        current_logger: The logger instance to use. Defaults to module_logger.
    """
    logger_to_use = current_logger if current_logger else module_logger
    config_text = f"{config.SYMBOLS['info']} Current effective configuration values:\n\n"
    config_text += f"  ADMIN_GROUP_IP:              {config.ADMIN_GROUP_IP}\n"
    config_text += f"  GTFS_FEED_URL:               {config.GTFS_FEED_URL}\n"
    config_text += (
        f"  VM_IP_OR_DOMAIN:             {config.VM_IP_OR_DOMAIN}\n"
    )
    config_text += (
        f"  PG_TILESERV_BINARY_LOCATION: "
        f"{config.PG_TILESERV_BINARY_LOCATION}\n"
    )
    config_text += f"  LOG_PREFIX (for logger):     {config.LOG_PREFIX}\n\n"
    config_text += f"  PGHOST:                      {config.PGHOST}\n"
    config_text += f"  PGPORT:                      {config.PGPORT}\n"
    config_text += f"  PGDATABASE:                  {config.PGDATABASE}\n"
    config_text += f"  PGUSER:                      {config.PGUSER}\n"

    pg_password_display = "[DEFAULT - Potentially Insecure]"
    if config.PGPASSWORD and config.PGPASSWORD != config.PGPASSWORD_DEFAULT:
        pg_password_display = "[SET BY USER/ARG]"
    elif not config.PGPASSWORD:
        pg_password_display = "[NOT SET or EMPTY]"
    config_text += f"  PGPASSWORD:                  {pg_password_display}\n\n"

    config_text += (
        f"  STATE_FILE_PATH:             {config.STATE_FILE_PATH}\n"
    )
    # SCRIPT_HASH would be more relevant than SCRIPT_VERSION here if shown.
    # from setup.state_manager import get_current_script_hash
    # current_hash = get_current_script_hash(
    #    logger_instance=logger_to_use
    # ) or "N/A"
    # config_text += f"  SCRIPT_HASH:                 {current_hash}\n"
    config_text += f"  SCRIPT_VERSION (comments):   {config.SCRIPT_VERSION}\n"
    config_text += (
        f"  TIMESTAMP (current view):    "
        f"{datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S')}\n\n"
    )
    config_text += (
        "You can override these using command-line options (see -h)."
    )

    log_map_server("Displaying current configuration:", "info", logger_to_use)
    print(f"\n{config_text}\n")


def manage_state_interactive(current_logger: logging.Logger = None) -> None:
    """
    Provide an interactive CLI menu for managing the setup state.

    Allows viewing completed steps and clearing progress.

    Args:
        current_logger: The logger instance to use. Defaults to module_logger.
    """
    logger_to_use = current_logger if current_logger else module_logger
    while True:
        print("\nState Management:")
        print("1. View Completed Steps")
        print("2. Clear All Progress (Retains Script Hash & Version)")
        print("3. Return to Main Menu")
        choice = input("Enter your choice (1-3): ").strip()

        if choice == "1":
            completed = view_completed_steps(current_logger=logger_to_use)
            if completed:
                print("\nCompleted Steps:")
                for i, step_tag_item in enumerate(completed):
                    print(f"  {i + 1}. {step_tag_item}")
            else:
                print("\nNo steps have been marked as completed yet.")
        elif choice == "2":
            confirm = (
                input(
                    f"{config.SYMBOLS['warning']} Are you sure you want to clear "
                    f"recorded progress from {config.STATE_FILE_PATH}? (yes/NO): "
                )
                .strip()
                .lower()
            )
            if confirm == "yes":
                # clear_state_file in state_manager handles writing the
                # current hash.
                clear_state_file(current_logger=logger_to_use)
                print(
                    "Progress state cleared (script hash and version line "
                    "retained)."
                )
            else:
                print("State file not cleared.")
        elif choice == "3":
            break
        else:
            print("Invalid choice.")
        input("Press Enter to continue...")


def show_menu(
    all_step_definitions, current_logger: logging.Logger = None
) -> None:
    """
    Display a basic interactive CLI menu for the setup script.

    Note:
        If Urwid becomes the main UI, this menu might be deprecated.
        The `all_step_definitions` argument might be unused if custom
        step selection is removed from this basic CLI.

    Args:
        all_step_definitions: List of step definitions (may be unused).
        current_logger: The logger instance to use. Defaults to module_logger.
    """
    logger_to_use = current_logger if current_logger else module_logger
    while True:
        print("\n" + "=" * 80)
        print(
            f"Map Server Setup Script (v{config.SCRIPT_VERSION}) - CLI Menu"
        )
        print("=" * 80)
        print("1. View Current Configuration")
        print("2. Manage Setup State (View/Clear Progress)")
        print("3. Exit Script")
        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            view_configuration(current_logger=logger_to_use)
        elif choice == "2":
            manage_state_interactive(current_logger=logger_to_use)
        elif choice == "3":
            confirm_exit = (
                input("Are you sure you want to exit? (y/N): ")
                .strip()
                .lower()
            )
            if confirm_exit == "y":
                log_map_server(
                    "Exiting script by user choice from CLI menu.",
                    "info",
                    logger_to_use,
                )
                break
        else:
            print("Invalid choice. Please enter a valid number.")

        if choice != "3":
            input("\nPress Enter to continue...")
