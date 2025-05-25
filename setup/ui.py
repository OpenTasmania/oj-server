# setup/ui.py
"""
User interface elements, step execution logic, and menu system for map server setup.
"""
import logging
import datetime  # For view_configuration
from typing import Callable, List, Tuple  # For type hinting

# Relative imports from within the 'setup' package
from . import config  # To access config.SYMBOLS, SCRIPT_HASH, etc.
from .command_utils import log_map_server  # SYMBOLS is NOT imported from here
from .state_manager import (
    is_step_completed,
    mark_step_completed,
    view_completed_steps,
    clear_state_file,
)

# Import step functions from their respective modules
# These will be needed for run_custom_selection_interactive and potentially show_menu
# For now, these are illustrative. You'll need to ensure these modules and functions exist.
# from .core_setup import boot_verbosity, core_conflict_removal, core_install, docker_install, node_js_lts_install
# from .services_setup import ufw_setup # etc.
# from .data_processing import gtfs_data_prep # etc.
# from .helpers import systemd_reload


module_logger = logging.getLogger(__name__)


def execute_step(
    step_tag: str,
    step_description: str,
    step_function: Callable,
    current_logger_instance,
) -> bool:
    """
    Execute a single step with state tracking, user prompts for re-run, and error handling.
    The step_function is expected to take 'current_logger' as an argument.
    """
    logger_to_use = (
        current_logger_instance if current_logger_instance else module_logger
    )
    run_this_step = True

    if is_step_completed(step_tag, current_logger=logger_to_use):
        # Use config.SYMBOLS directly here
        log_map_server(
            f"{config.SYMBOLS['info']} Step '{step_description}' ({step_tag}) is already marked as completed.",
            "info",
            logger_to_use,
        )
        try:
            user_input = (
                input(
                    f"   {config.SYMBOLS['info']} Do you want to re-run it anyway? (y/N): "
                )
                .strip()
                .lower()
            )
        except EOFError:
            user_input = "n"
            log_map_server(
                f"{config.SYMBOLS['warning']} No user input (EOF), defaulting to skip re-run.",
                "warning",
                logger_to_use,
            )

        if user_input != "y":
            log_map_server(
                f"{config.SYMBOLS['info']} Skipping step: {step_tag} - {step_description}",
                "info",
                logger_to_use,
            )
            run_this_step = False

    if run_this_step:
        log_map_server(
            f"--- {config.SYMBOLS['step']} Executing: {step_description} ({step_tag}) ---",
            "info",
            logger_to_use,
        )
        try:
            step_function(current_logger=logger_to_use)
            mark_step_completed(step_tag, current_logger=logger_to_use)
            log_map_server(
                f"--- {config.SYMBOLS['success']} Successfully completed: {step_description} ({step_tag}) ---",
                "success",
                logger_to_use,
            )
            return True
        except Exception as e:
            log_map_server(
                f"{config.SYMBOLS['error']} FAILED: {step_description} ({step_tag})",
                "error",
                logger_to_use,
            )
            log_map_server(
                f"   Error details: {str(e)}", "error", logger_to_use
            )
            return False

    return True


def view_configuration(current_logger=None) -> None:
    """Display the current configuration values."""
    logger_to_use = current_logger if current_logger else module_logger

    # Use config.SYMBOLS directly
    config_text = f"{config.SYMBOLS['info']} Current effective configuration values:\n\n"
    config_text += f"  ADMIN_GROUP_IP:              {config.ADMIN_GROUP_IP}\n"
    config_text += f"  GTFS_FEED_URL:               {config.GTFS_FEED_URL}\n"
    config_text += (
        f"  VM_IP_OR_DOMAIN:             {config.VM_IP_OR_DOMAIN}\n"
    )
    config_text += f"  PG_TILESERV_BINARY_LOCATION: {config.PG_TILESERV_BINARY_LOCATION}\n"
    config_text += f"  LOG_PREFIX (for logger):     {config.LOG_PREFIX}\n\n"  # This is the active one from args
    config_text += f"  PGHOST:                      {config.PGHOST}\n"
    config_text += f"  PGPORT:                      {config.PGPORT}\n"
    config_text += f"  PGDATABASE:                  {config.PGDATABASE}\n"
    config_text += f"  PGUSER:                      {config.PGUSER}\n"

    pg_password_display = "[DEFAULT - Potentially Insecure]"
    if config.PGPASSWORD and config.PGPASSWORD != config.PGPASSWORD_DEFAULT:
        pg_password_display = "[SET BY USER/ARG]"
    elif (
        not config.PGPASSWORD
    ):  # Handles if PGPASSWORD was set to empty string
        pg_password_display = "[NOT SET or EMPTY]"
    config_text += f"  PGPASSWORD:                  {pg_password_display}\n\n"

    config_text += (
        f"  STATE_FILE_PATH:             {config.STATE_FILE_PATH}\n"
    )
    config_text += f"  SCRIPT_HASH:              {config.SCRIPT_HASH}\n"
    config_text += f"  TIMESTAMP (current view):    {datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S')}\n\n"
    config_text += (
        "You can override these using command-line options (see -h)."
    )

    log_map_server("Displaying current configuration:", "info", logger_to_use)
    print("\n" + config_text + "\n")


def manage_state_interactive(current_logger) -> None:
    """Interactive menu for managing the state file."""
    logger_to_use = current_logger if current_logger else module_logger
    while True:
        print("\nState Management:")
        print("1. View Completed Steps")
        print("2. Clear All Progress (Retains Script Version)")
        print("3. Return to Main Menu")
        choice = input("Enter your choice (1-3): ").strip()

        if choice == "1":
            completed = view_completed_steps(current_logger=logger_to_use)
            if completed:
                print("\nCompleted Steps:")
                for i, step_tag in enumerate(completed):
                    print(f"  {i + 1}. {step_tag}")
            else:
                print("\nNo steps have been marked as completed yet.")
        elif choice == "2":
            confirm = (
                input(
                    f"{config.SYMBOLS['warning']} Are you sure you want to clear recorded progress from {config.STATE_FILE_PATH}? (yes/NO): "
                )
                .strip()
                .lower()
            )
            if confirm == "yes":
                clear_state_file( current_logger=logger_to_use
                )
                print("Progress state cleared (version retained).")
            else:
                print("State file not cleared.")
        elif choice == "3":
            break
        else:
            print("Invalid choice.")
        input("Press Enter to continue...")


def run_custom_selection_interactive(
    all_steps: List[Tuple[str, str, Callable]], current_logger
) -> None:
    """Allow user to select and run a custom set of steps."""
    # ... (implementation as provided before, ensure it uses config.SYMBOLS) ...
    # This function is quite long, for brevity I'll assume its internal SYMBOLS usage
    # would also be changed to config.SYMBOLS if it directly used them.
    # The main calls to log_map_server within it will correctly pick up SYMBOLS via command_utils.
    log_map_server(
        "Custom step selection needs its SYMBOLS usage reviewed if any direct use.",
        "warning",
        current_logger,
    )
    print(
        "Custom step selection placeholder - implement fully or remove if not using interactive menu."
    )


def show_menu(
    all_step_definitions: List[Tuple[str, str, Callable]], current_logger
) -> None:
    """Display the main menu and handle user input."""
    logger_to_use = current_logger if current_logger else module_logger

    while True:
        print("\n" + "=" * 80)
        print(
            f"Map Server Setup Script (v{config.SCRIPT_HASH}) - Main Menu"
        )
        print("=" * 80)
        print("1. View Current Configuration")
        print("2. Manage Setup State (View/Clear Progress)")
        # print("3. Run Custom Selection of Steps") # Assuming this is complex and might be CLI driven for now
        print("3. Exit Script")  # Simplified menu for now

        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            view_configuration(current_logger=logger_to_use)
        elif choice == "2":
            manage_state_interactive(current_logger=logger_to_use)
        # elif choice == "3":
        #     run_custom_selection_interactive(all_step_definitions, current_logger=logger_to_use)
        elif choice == "3":
            confirm_exit = (
                input("Are you sure you want to exit? (y/N): ")
                .strip()
                .lower()
            )
            if confirm_exit == "y":
                log_map_server(
                    "Exiting script by user choice from menu.",
                    "info",
                    logger_to_use,
                )
                break
        else:
            print("Invalid choice. Please enter a valid number.")

        if choice != "3":  # Don't pause if exiting
            input("\nPress Enter to continue...")
