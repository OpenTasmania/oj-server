# osm/setup/tui.py
# -*- coding: utf-8 -*-
"""
Urwid-based Text User Interface (TUI) for the Map Server Installer.

This module provides an interactive TUI for navigating setup options,
viewing configuration, managing state, and selecting steps to run.
"""

import logging
from sys import stderr
from typing import Callable, List, Optional, Tuple

import urwid

# Assuming these are correctly imported relative to the TUI's execution context
# when integrated into the main application.
from . import config  # For SYMBOLS, etc.
from .state_manager import view_completed_steps
from .step_executor import execute_step

# Placeholder for imports from your project.
# These will be needed to actually run steps and manage state.
# Example: from .core_setup import boot_verbosity, core_install, ...
# from .services.ufw import ufw_setup etc.

# For TUI development/testing, a placeholder list of tasks.
# This should be populated from main_installer.py's defined_tasks in a
# real integration.
ALL_DEFINED_TASKS_FOR_TUI: List[Tuple[str, str, Callable]] = [
    ("EXAMPLE_STEP_1", "Run Example Step 1",
     lambda cl: log_map_server_tui("Example Step 1 executed", "info", cl)),
    ("EXAMPLE_STEP_2", "Run Example Step 2",
     lambda cl: log_map_server_tui("Example Step 2 executed", "info", cl)),
]

module_logger = logging.getLogger(__name__)
# It's good practice for the main application (main_installer.py when launching
# TUI) to configure the root logger or pass a configured logger instance.


# --- Palette Definition ---
# Defines color schemes for different UI elements.
palette = [
    ('header', 'white', 'dark blue', 'standout'),
    ('footer', 'white', 'dark blue', 'standout'),
    ('body', 'black', 'light gray'),
    ('button', 'black', 'dark cyan'),
    ('button_focus', 'white', 'dark blue', 'standout'),
    ('dialog_bg', 'light gray', 'dark blue'),
    ('dialog_border', 'black', 'dark blue'),
    ('dialog_text', 'white', 'dark blue'),
    ('dialog_button', 'black', 'light gray'),
    ('dialog_button_focus', 'white', 'dark blue', 'standout'),
    ('log_debug', 'dark gray', 'light gray'),
    ('log_info', 'dark blue', 'light gray'),
    ('log_warning', 'brown', 'light gray'),
    ('log_error', 'dark red', 'light gray', 'bold'),
    ('log_critical', 'white', 'dark red', 'standout'),
    ('checklist_focus', 'black', 'dark cyan', 'standout'),
    ('edit_focus', 'black', 'dark cyan', 'standout'),
]


# --- Global TUI State / Helper ---
class GlobalTUIState:
    """A simple class to hold global state for TUI dialogs."""
    dialog_yes_no_result: Optional[bool] = None


tui_state = GlobalTUIState()


# --- UI Components ---

class LogDisplay(urwid.WidgetWrap):
    """A widget to display log messages in the TUI."""

    def __init__(self) -> None:
        """Initialize the log display area."""
        self.log_lines = urwid.SimpleFocusListWalker([])
        self.list_box = urwid.ListBox(self.log_lines)
        super().__init__(self.list_box)

    def add_message(self, message: str, level: str = "info") -> None:
        """
        Add a new message to the log display.

        Args:
            message: The log message string.
            level: The log level (e.g., 'info', 'error'), used for styling.
        """
        attr_map_key = f'log_{level.lower()}'
        attr = attr_map_key if attr_map_key in dict(palette) else 'body'
        self.log_lines.append(urwid.AttrMap(urwid.Text(message), attr))
        if self.log_lines:
            # Auto-scroll to the latest message.
            self.list_box.set_focus(len(self.log_lines) - 1)

    def clear_logs(self) -> None:
        """Clear all messages from the log display."""
        self.log_lines.clear()


class YesNoDialog(urwid.WidgetWrap):
    """A modal dialog widget for Yes/No questions."""
    signals = ['close']  # Signal emitted when the dialog closes.

    def __init__(
        self,
        title_text: str,
        message_text: str,
        callback_on_close: Optional[Callable[[bool], None]] = None
    ) -> None:
        """
        Initialize the Yes/No dialog.

        Args:
            title_text: The title of the dialog.
            message_text: The message/question to display.
            callback_on_close: Optional function to call when the dialog
                               is closed, passing True for "Yes" and
                               False for "No".
        """
        self.callback_on_close = callback_on_close
        title_widget = urwid.Text(('dialog_text', title_text), align='center')
        message_widget = urwid.Text(
            ('dialog_text', message_text), align='center'
        )

        yes_button = urwid.AttrMap(
            urwid.Button("Yes", self._on_yes),
            'dialog_button',
            focus_map='dialog_button_focus'
        )
        no_button = urwid.AttrMap(
            urwid.Button("No", self._on_no),
            'dialog_button',
            focus_map='dialog_button_focus'
        )

        buttons = urwid.GridFlow(
            [yes_button, no_button],
            cell_width=10, h_sep=1, v_sep=1, align='center'
        )

        content = urwid.Pile([
            message_widget,
            urwid.Divider(),
            buttons
        ])

        line_box = urwid.LineBox(
            urwid.Padding(content, left=2, right=2), title=title_widget
        )
        super().__init__(urwid.AttrMap(line_box, 'dialog_bg'))

    def _on_yes(self, button: urwid.Button) -> None:
        """Handle the 'Yes' button press."""
        tui_state.dialog_yes_no_result = True
        self._emit('close')
        if self.callback_on_close:
            self.callback_on_close(True)

    def _on_no(self, button: Optional[urwid.Button]) -> None:
        """Handle the 'No' button press or Escape key."""
        tui_state.dialog_yes_no_result = False
        self._emit('close')
        if self.callback_on_close:
            self.callback_on_close(False)

    def keypress(self, size: Tuple[int, int], key: str) -> Optional[str]:
        """
        Handle key presses for the dialog.

        Escape key is treated as "No".
        """
        if key == 'esc':
            self._on_no(None)  # Treat escape as "No".
            return None  # Key handled.
        return super().keypress(size, key)


class InstallerTUI:
    """Main class for the Installer Text User Interface."""

    def __init__(self) -> None:
        """Initialize the TUI components and main loop."""
        self.current_task_thread = None  # For future threaded task execution.
        self.pipe_for_log_reader = None  # For future log piping from threads.

        self.header = urwid.AttrMap(
            urwid.Text("OSM Server Installer TUI", align='center'), 'header'
        )
        self.footer = urwid.AttrMap(
            urwid.Text(
                "Ctrl-C to Exit | Keys: Up, Down, Enter, Esc", align='center'
            ),
            'footer'
        )
        self.log_display = LogDisplay()

        self.main_menu_items = self._build_main_menu()
        self.main_menu_listbox = urwid.ListBox(
            urwid.SimpleFocusListWalker(self.main_menu_items)
        )

        self.current_body = self.main_menu_listbox  # Start with the main menu.
        self.frame = urwid.Frame(
            body=self.current_body, header=self.header, footer=self.footer
        )

        self.main_loop = urwid.MainLoop(
            self.frame,
            palette=palette,
            unhandled_input=self._handle_global_keys,
            pop_ups=True  # Enable pop-ups for Overlays.
        )

    def _build_main_menu(self) -> List[urwid.Widget]:
        """Build the list of main menu buttons."""
        menu_options = [
            ("View Configuration", self.show_view_configuration),
            ("Manage State", self.show_manage_state),
            ("Run Full Installation", self.run_full_installation),
            ("Select Specific Steps to Run", self.show_step_selection),
            ("Exit", self.confirm_exit)
        ]
        buttons: List[urwid.Widget] = []
        for name, callback in menu_options:
            button = urwid.AttrMap(
                urwid.Button(name, on_press=callback),
                'button',
                focus_map='button_focus'
            )
            buttons.append(button)
        return buttons

    def _handle_global_keys(self, key: str) -> None:
        """Handle global key presses (e.g., Ctrl-C, 'q' to go back)."""
        if key == 'ctrl c':
            self.confirm_exit()
        elif key == 'q' and self.current_body is not self.main_menu_listbox:
            # Example: 'q' to go back to the main menu from other views.
            self.show_main_menu()

    def show_main_menu(self, button: Optional[urwid.Button] = None) -> None:
        """Display the main menu."""
        self.frame.body = self.main_menu_listbox
        self.footer.original_widget.set_text(
            "Ctrl-C to Exit | Keys: Up, Down, Enter, Esc"
        )

    def show_view_configuration(
        self, button: Optional[urwid.Button] = None
    ) -> None:
        """Display the current configuration in the log view."""
        # A proper TUI view would format this nicely.
        self.log_display.clear_logs()
        self.log_display.add_message("--- Current Configuration ---", "header")
        # Placeholder: In a real app, capture output of view_configuration()
        # or re-implement its display logic using Urwid widgets.
        self.log_display.add_message(
            f"Admin IP: {config.ADMIN_GROUP_IP}", "info"
        )
        self.log_display.add_message(
            f"GTFS URL: {config.GTFS_FEED_URL}", "info"
        )
        # ... and so on for other config items ...
        self.frame.body = self.log_display  # Temporarily show logs.
        self.footer.original_widget.set_text(
            "Press 'q' to return to main menu."
        )

    def show_manage_state(
        self, button: Optional[urwid.Button] = None
    ) -> None:
        """Display options for managing setup state (view/clear)."""
        self.log_display.clear_logs()
        self.log_display.add_message("Manage State - TUI Placeholder", "header")
        # Example: view completed steps
        completed = view_completed_steps(current_logger=module_logger)
        if completed:
            self.log_display.add_message("Completed steps:", "info")
            for step in completed:
                self.log_display.add_message(f" - {step}", "info")
        else:
            self.log_display.add_message("No steps completed.", "info")
        # TODO: Add buttons/options for 'Clear State' with confirmation.
        self.frame.body = self.log_display
        self.footer.original_widget.set_text(
            "Press 'q' to return to main menu."
        )

    def run_full_installation(
        self, button: Optional[urwid.Button] = None
    ) -> None:
        """Initiate the full installation process."""
        self.log_display.clear_logs()
        self.frame.body = self.log_display  # Switch to log view.
        self.log_display.add_message("Starting Full Installation...", "header")
        self.footer.original_widget.set_text(
            "Installation in progress... Press Ctrl-C to attempt abort "
            "(may be unsafe)."
        )
        # This needs to run in a separate thread to not block the UI.
        # For each step in the full installation (from main_installer.py logic)
        # you'd call self.execute_installer_step(...)
        self.log_display.add_message(
            "Full installation TUI execution not fully implemented.", "warning"
        )
        # Example:
        # self.execute_installer_step("UFW_SETUP", "Setup UFW Firewall",
        #                             ufw_setup)

    def show_step_selection(
        self, button: Optional[urwid.Button] = None
    ) -> None:
        """Display a checklist for selecting specific steps to run."""
        self.log_display.clear_logs()
        self.log_display.add_message(
            "Select Specific Steps - TUI Placeholder", "header"
        )
        self.frame.body = self.log_display  # Show logs during selection setup

        items_to_run: List[Tuple[str, str, Callable]] = []

        def on_checklist_change(
            checkbox: urwid.CheckBox, new_state: bool,
            step_data: Tuple[str, str, Callable]
        ) -> None:
            """Callback for when a checkbox state changes."""
            if new_state:
                items_to_run.append(step_data)
            else:
                if step_data in items_to_run:
                    items_to_run.remove(step_data)

        checklist_items: List[urwid.Widget] = []
        # Use your actual list of tasks from main_installer.py.
        for tag, desc, func_ref in ALL_DEFINED_TASKS_FOR_TUI:
            cb = urwid.CheckBox(
                f"{desc} ({tag})",
                on_state_change=on_checklist_change,
                user_data=(tag, desc, func_ref)
            )
            checklist_items.append(
                urwid.AttrMap(cb, None, focus_map='checklist_focus')
            )

        def do_run_selected(btn: urwid.Button) -> None:
            """Execute the steps selected by the user."""
            self.log_display.clear_logs()
            self.frame.body = self.log_display
            self.log_display.add_message("Running selected steps...", "header")
            for item_tag, item_desc, item_func in items_to_run:
                # This is where self.execute_installer_step would be called.
                self.log_display.add_message(
                    f"Executing (placeholder): {item_tag} {item_desc} {item_func}", "info"
                )
                # self.execute_installer_step(item_tag, item_desc, item_func)
            self.show_main_menu()  # Go back to main menu after.

        run_button = urwid.AttrMap(
            urwid.Button("Run Selected", on_press=do_run_selected),
            'button',
            focus_map='button_focus'
        )
        cancel_button = urwid.AttrMap(
            urwid.Button("Cancel", on_press=self.show_main_menu),
            'button',
            focus_map='button_focus'
        )

        list_walker_items = checklist_items + [
            urwid.Divider(), run_button, cancel_button
        ]
        list_walker = urwid.SimpleFocusListWalker(list_walker_items)
        checklist_lb = urwid.ListBox(list_walker)

        self.frame.body = checklist_lb
        self.footer.original_widget.set_text(
            "Space to toggle, Enter on buttons. 'q' for main menu."
        )

    def tui_prompt_for_rerun(self, prompt_message: str) -> bool:
        """
        Display a Yes/No dialog using Urwid for `execute_step`.

        This is a simplified blocking prompt for this example. A truly
        non-blocking app would use callbacks more extensively.

        Args:
            prompt_message: The message to display in the dialog.

        Returns:
            True if "Yes" is chosen, False otherwise.
        """
        original_widget = self.main_loop.widget
        dialog = YesNoDialog("Confirmation", prompt_message)

        # This is a simplified "blocking" emulation for the sake of example.
        # In a real Urwid app, `execute_step` might need to be async or
        # take a callback for its result.
        tui_state.dialog_yes_no_result = None  # Reset before showing dialog.

        # This nested loop makes the dialog appear blocking.
        # The YesNoDialog's buttons will eventually call _emit('close'),
        # which breaks this inner loop.
        temp_loop = urwid.MainLoop(
            widget=urwid.Overlay(
                dialog, original_widget,
                align='center', width=('relative', 80),
                valign='middle', height=('relative', 30),
                min_width=24, min_height=8
            ),
            palette=palette,
            unhandled_input=self._handle_global_keys,  # Reuse global keys
            pop_ups=True
        )

        # Connect the dialog's close signal to stop this temporary loop.
        urwid.connect_signal(dialog, 'close', lambda d: temp_loop.stop())
        temp_loop.run()

        # No need to manually pop_ups or restore widget if temp_loop handles
        # the overlay correctly. The main_loop's widget was not changed.

        return tui_state.dialog_yes_no_result \
            if tui_state.dialog_yes_no_result is not None else False

    def execute_installer_step(
        self,
        tag: str,
        desc: str,
        func: Callable[[Optional[logging.Logger]], None]
    ) -> None:
        """
        Wrap `execute_step` for use within the TUI.

        Handles running `func` (potentially in a non-blocking way in a
        full implementation) and updating TUI logs.

        Args:
            tag: The unique tag for the step.
            desc: A human-readable description of the step.
            func: The function to execute for the step.
        """
        self.log_display.add_message(
            f"--- Preparing to execute: {desc} ({tag}) ---", "info"
        )

        # This is a simple, blocking call for now.
        # In a real implementation, 'func' might run in a thread,
        # and its output piped to self.log_display.add_message
        # via main_loop.watch_pipe.
        try:
            success = execute_step(
                tag, desc, func,
                current_logger_instance=module_logger,
                prompt_user_for_rerun=self.tui_prompt_for_rerun
            )
            if success:
                self.log_display.add_message(
                    f"--- SUCCESS: {desc} ({tag}) ---", "log_info"
                )
            else:
                self.log_display.add_message(
                    f"--- FAILED: {desc} ({tag}) ---", "log_error"
                )
        except Exception as e:
            self.log_display.add_message(
                f"--- CRITICAL ERROR during {desc}: {e} ---", "log_critical"
            )
            module_logger.exception(
                f"Critical error during TUI execution of step {tag}"
            )

    def confirm_exit(self, button: Optional[urwid.Button] = None) -> None:
        """Display a confirmation dialog before exiting the TUI."""
        def do_exit(result: bool) -> None:
            if result:  # True means Yes.
                raise urwid.ExitMainLoop()

        dialog = YesNoDialog(
            "Confirm Exit",
            "Are you sure you want to quit the installer?",
            callback_on_close=do_exit
        )
        # Get the current top widget for the overlay.
        current_top_widget = self.main_loop.widget
        overlay = urwid.Overlay(
            dialog, current_top_widget,
            align='center', width=('relative', 60),
            valign='middle', height=7, min_width=20, min_height=5
        )
        # Show the overlay by making it the new top widget.
        self.main_loop.widget = overlay

    def run(self) -> None:
        """Start the TUI main event loop."""
        # TODO: Add a custom logging handler to route logs to the TUI's
        #       log_display. This is essential for good TUI logging.
        self.log_display.add_message(
            "Installer TUI Initialized. Welcome!", "info"
        )
        try:
            self.main_loop.run()
        except Exception:
            # Catch any unhandled exceptions from the UI loop for debugging.
            module_logger.exception("Unhandled exception in TUI main loop")
            raise


# --- Main Entry Point for TUI (Standalone Testing) ---
def run_tui_installer_standalone() -> None:
    """Run the TUI for standalone testing."""
    # Basic logger for standalone testing.
    if not module_logger.handlers:
        handler = logging.StreamHandler(stderr)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        module_logger.addHandler(handler)
        module_logger.setLevel(logging.INFO)  # Or DEBUG for more TUI logs.

    app = InstallerTUI()
    app.run()


# Dummy log_map_server for standalone tui.py testing
def log_map_server_tui(
    message: str, level: str = "info",
    logger_instance: Optional[logging.Logger] = None
) -> None:
    """Dummy log_map_server for TUI standalone testing."""
    _logger = logger_instance if logger_instance else module_logger
    if level == "info":
        _logger.info(message)
    elif level == "warning":
        _logger.warning(message)
    elif level == "error":
        _logger.error(message)
    else:  # debug, critical etc.
        _logger.debug(message)


if __name__ == '__main__':
    # This allows running tui.py directly for testing.
    # In actual use, main_installer.py would call a function like run_tui_installer().

    # Dummy config for standalone testing
    class DummyConfig:
        SYMBOLS = {
            "info": "ℹ>", "step": "->", "success": "✓ ", "error": "✗ "
        }
        ADMIN_GROUP_IP = "1.2.3.4/24"
        GTFS_FEED_URL = "http://example.com/gtfs.zip"

    config = DummyConfig()  # Overwrite imported config for standalone test.

    # Dummy step_executor for standalone testing
    def dummy_execute_step(
        tag: str, desc: str, func: Callable,
        current_logger_instance: logging.Logger,
        prompt_user_for_rerun: Callable[[str], bool]
    ) -> bool:
        log_map_server_tui(
            f"Executing (dummy): {desc}", "info", current_logger_instance
        )
        if prompt_user_for_rerun(
            f"'{desc}' completed (dummy). Rerun?"
        ):
            log_map_server_tui(
                f"Dummy Re-running: {desc}", "info", current_logger_instance
            )
        try:
            func(current_logger_instance)  # Pass logger to dummy func
            log_map_server_tui(
                f"Completed (dummy): {desc}", "info", current_logger_instance
            )
            return True
        except Exception as e:
            log_map_server_tui(
                f"Failed (dummy): {desc} - {e}", "error",
                current_logger_instance
            )
            return False
    # Replace the actual execute_step with the dummy for standalone testing.
    execute_step = dummy_execute_step

    # Dummy state_manager functions
    def dummy_view_completed_steps(current_logger) -> List[str]:
        return ["DUMMY_STEP_A", "DUMMY_STEP_B"]
    view_completed_steps = dummy_view_completed_steps

    run_tui_installer_standalone()