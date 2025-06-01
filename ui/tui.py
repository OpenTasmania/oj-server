# osm/setup/tui.py
# -*- coding: utf-8 -*-
"""
Urwid-based Text User Interface (TUI) for the Map Server Installer.

This module provides an interactive TUI for navigating setup options,
viewing configuration, managing state, and selecting steps to run.
"""

import logging
import sys
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

import urwid

# Assuming these are correctly imported relative to the TUI's execution context
# For the __main__ block, we'll use a DummyConfig.
# For actual integration, AppSettings would come from the main installer.
from setup.config_models import AppSettings, SYMBOLS_DEFAULT
from setup.state_manager import view_completed_steps
from setup.step_executor import execute_step  # This is the real execute_step

module_logger = logging.getLogger(__name__)

# --- Palette Definition ---
palette = [
    ("header", "white", "dark blue", "standout"),
    ("footer", "white", "dark blue", "standout"),
    ("body", "black", "light gray"),
    ("button", "black", "dark cyan"),
    ("button_focus", "white", "dark blue", "standout"),
    ("dialog_bg", "light gray", "dark blue"),
    ("dialog_border", "black", "dark blue"),
    ("dialog_text", "white", "dark blue"),
    ("dialog_button", "black", "light gray"),
    ("dialog_button_focus", "white", "dark blue", "standout"),
    ("log_debug", "dark gray", "light gray"),
    ("log_info", "dark blue", "light gray"),
    ("log_warning", "brown", "light gray"),
    ("log_error", "dark red", "light gray", "bold"),
    ("log_critical", "white", "dark red", "standout"),
    ("checklist_focus", "black", "dark cyan", "standout"),
    ("edit_focus", "black", "dark cyan", "standout"),
    ("pane_border", "black", "light gray"),
]


# --- UI Components ---


class LogDisplay(urwid.WidgetWrap):
    """A widget to display log messages in the TUI."""

    def __init__(self) -> None:
        self.log_lines = urwid.SimpleFocusListWalker([])
        self.list_box = urwid.ListBox(self.log_lines)
        super().__init__(urwid.LineBox(self.list_box, title="Logs"))

    def add_message(self, message: str, level: str = "info") -> None:
        attr_map_key = f"log_{level.lower()}"
        attr = attr_map_key if any((p[0] == attr_map_key for p in palette)) else "body"
        styled_text_widget = urwid.AttrMap(urwid.Text(message), attr)
        self.log_lines.append(styled_text_widget)
        if self.log_lines:
            self.list_box.set_focus(len(self.log_lines) - 1)

    def clear_logs(self) -> None:
        self.log_lines.clear()


class TuiLogHandler(logging.Handler):
    """A logging handler that directs messages to the Urwid LogDisplay."""

    def __init__(self, log_display_widget: LogDisplay, main_loop: urwid.MainLoop):
        super().__init__()
        self.log_display_widget = log_display_widget
        self.main_loop: urwid.MainLoop = main_loop
        self.formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            level_name = record.levelname.lower()
            if threading.current_thread() is threading.main_thread():
                self.log_display_widget.add_message(msg, level=level_name)
            else:  # pragma: no cover
                def _update_log_display_from_thread():
                    self.log_display_widget.add_message(msg, level=level_name)

                self.main_loop.alarm(0, lambda _l, _u: _update_log_display_from_thread())  # type: ignore[attr-defined]
        except RecursionError:  # pragma: no cover
            raise
        except Exception:  # pragma: no cover
            self.handleError(record)


class YesNoDialog(urwid.WidgetWrap):
    """A modal dialog widget for Yes/No questions."""
    signals = ["close_yes", "close_no"]

    def __init__(self, title_text: str, message_text: str):
        title_widget = urwid.Text(("dialog_text", title_text), align="center")
        message_widget = urwid.Text(("dialog_text", message_text), align="center")
        yes_button = urwid.AttrMap(urwid.Button("Yes", self._on_yes), "dialog_button", focus_map="dialog_button_focus")
        no_button = urwid.AttrMap(urwid.Button("No", self._on_no), "dialog_button", focus_map="dialog_button_focus")
        buttons = urwid.GridFlow([yes_button, no_button], cell_width=10, h_sep=2, v_sep=1, align="center")
        content = urwid.Pile([urwid.Divider(), message_widget, urwid.Divider(), buttons, urwid.Divider()])
        line_box = urwid.LineBox(urwid.Padding(content, left=2, right=2), title=title_widget)
        super().__init__(urwid.AttrMap(line_box, "dialog_bg"))

    def _on_yes(self, button: urwid.Button) -> None:
        self._emit("close_yes")

    def _on_no(self, button: Optional[urwid.Button]) -> None:
        self._emit("close_no")

    def keypress(self, size: Tuple[int, int], key: str) -> Optional[str]:
        if key == "esc":  # pragma: no cover
            self._on_no(None)
            return None
        return super().keypress(size, key)


# Step function signature expected by execute_step and thus by _task_runner's 'func'
StepFunctionType = Callable[[AppSettings, Optional[logging.Logger]], Any]


class InstallerTUI:
    """Main class for the Installer Text User Interface."""

    def __init__(
            self,
            defined_tasks: List[Tuple[str, str, StepFunctionType]],  # Use StepFunctionType
            app_settings_instance: AppSettings,  # Added app_settings_instance
    ) -> None:
        self.defined_tasks = defined_tasks
        self.app_settings: AppSettings = app_settings_instance  # Store AppSettings
        self.tui_log_handler: Optional[TuiLogHandler] = None
        self.task_queue: List[Tuple[str, str, StepFunctionType]] = []
        self.is_task_running: bool = False
        self.current_task_info: Optional[Dict[str, Any]] = None
        self._active_worker_thread: Optional[threading.Thread] = None
        self._dialog_event: Optional[threading.Event] = None
        self._dialog_prompt_message: str = ""
        self._dialog_result: Optional[bool] = None
        self._original_root_logger_level: Optional[int] = None
        self._root_logger_level_modified_by_tui: bool = False
        self._original_root_handlers: List[logging.Handler] = []
        self._removed_handlers_by_tui: List[logging.Handler] = []

        self.header = urwid.AttrMap(urwid.Text("OSM Server Installer TUI", align="center"), "header")
        self.footer_text = urwid.Text("Ctrl-C to Exit | Keys: Up, Down, Enter, Esc | 'q' to Main Menu", align="center")
        self.footer = urwid.AttrMap(self.footer_text, "footer")
        self.log_display = LogDisplay()
        self.main_menu_listbox = urwid.ListBox(urwid.SimpleFocusListWalker(self._build_main_menu()))
        self.interactive_pane_placeholder = urwid.WidgetPlaceholder(
            urwid.LineBox(self.main_menu_listbox, title="Controls"))
        self.columns_view = urwid.Columns(
            [("weight", 1, self.interactive_pane_placeholder), ("weight", 2, self.log_display)], dividechars=1)
        self.frame = urwid.Frame(body=self.columns_view, header=self.header, footer=self.footer)
        self.main_loop: urwid.MainLoop = urwid.MainLoop(self.frame, palette=palette,
                                                        unhandled_input=self._handle_global_keys, pop_ups=True)

    def _build_main_menu(self) -> List[urwid.Widget]:
        menu_options = [
            ("View Configuration", self.show_view_configuration),
            ("Manage State", self.show_manage_state),
            ("Run Full Installation", self.run_full_installation),
            ("Select Specific Steps to Run", self.show_step_selection),
            ("Exit", self.confirm_exit_dialog),
        ]
        buttons: List[urwid.Widget] = []
        for name, callback in menu_options:
            buttons.append(urwid.AttrMap(urwid.Button(name, on_press=callback), "button", focus_map="button_focus"))
        return buttons

    def _handle_global_keys(self, key: str) -> None:  # pragma: no cover
        if key == "ctrl c":
            self.confirm_exit_dialog()
        elif key == "q":
            is_main_menu = isinstance(self.interactive_pane_placeholder.original_widget, urwid.LineBox) and \
                           self.interactive_pane_placeholder.original_widget.original_widget is self.main_menu_listbox
            if not is_main_menu and not self.is_task_running:
                self.show_main_menu()
            elif self.is_task_running:
                self.log_display.add_message("Cannot return to main menu while a task is running.", "warning")

    def _update_interactive_pane(self, widget: urwid.Widget, title: str = "Controls") -> None:
        self.interactive_pane_placeholder.original_widget = urwid.LineBox(widget, title=title)
        self.main_loop.draw_screen()

    def show_main_menu(self, button: Optional[urwid.Button] = None) -> None:
        if self.is_task_running:  # pragma: no cover
            self.log_display.add_message("Task in progress. Cannot show main menu now.", "warning");
            return
        self._update_interactive_pane(self.main_menu_listbox, title="Main Menu")
        self.footer_text.set_text("Ctrl-C to Exit | Keys: Up, Down, Enter, Esc | 'q' to Main Menu")

    def show_view_configuration(self, button: Optional[urwid.Button] = None) -> None:  # pragma: no cover
        if self.is_task_running: self.log_display.add_message("Task in progress. Cannot view configuration now.",
                                                              "warning"); return
        self.log_display.clear_logs()
        self.log_display.add_message("--- Current Configuration ---", "header")
        # In a real app, self.app_settings would be AppSettings. Here, using the dummy app_config for display.
        cfg_to_display = self.app_settings  # Use the stored app_settings
        try:
            self.log_display.add_message(f"Admin IP: {cfg_to_display.admin_group_ip}", "info")
            self.log_display.add_message(f"GTFS URL: {cfg_to_display.gtfs_feed_url}", "info")
            self.log_display.add_message(f"VM Domain: {cfg_to_display.vm_ip_or_domain}", "info")
            # Add more config details from cfg_to_display as needed
        except AttributeError as e:
            self.log_display.add_message(f"Config item not found: {e}", "error")
        except Exception as e:
            self.log_display.add_message(f"Error loading config: {e}", "error")
        self.footer_text.set_text("Configuration displayed in Logs. Press 'q' to return to main menu.")
        self.main_loop.draw_screen()

    def show_manage_state(self, button: Optional[urwid.Button] = None) -> None:  # pragma: no cover
        if self.is_task_running: self.log_display.add_message("Task in progress. Cannot manage state now.",
                                                              "warning"); return
        self.log_display.clear_logs()
        self.log_display.add_message("--- Manage State ---", "header")
        try:
            # view_completed_steps expects AppSettings
            completed = view_completed_steps(app_settings=self.app_settings, current_logger=module_logger)
            if completed:
                self.log_display.add_message("Completed steps:", "info")
                for step_tag in completed: self.log_display.add_message(f" - {step_tag}", "info")
            else:
                self.log_display.add_message("No steps recorded as completed.", "info")
        except Exception as e:
            self.log_display.add_message(f"Error viewing state: {e}", "error"); module_logger.exception(
                "Error in show_manage_state")
        self.footer_text.set_text("State information in Logs. Press 'q' to return to main menu.")
        self.main_loop.draw_screen()

    def _task_runner(self, tag: str, desc: str, func: StepFunctionType) -> None:  # pragma: no cover
        success = False
        try:
            # Corrected call to execute_step: added self.app_settings
            success = execute_step(
                tag,
                desc,
                func,  # func is the actual step function from defined_tasks
                self.app_settings,  # Pass the stored AppSettings instance
                current_logger_instance=module_logger,
                prompt_user_for_rerun=self._threaded_prompt_for_rerun,
            )
        except Exception as e:
            module_logger.critical(f"Unhandled exception in threaded task {tag} ({desc}): {e}", exc_info=True)
            success = False
        finally:
            self.main_loop.alarm(0, lambda _l, _d: self._handle_task_completion(tag, desc,
                                                                                success))  # type: ignore[attr-defined]

    def _handle_task_completion(self, tag: str, desc: str, success: bool) -> None:  # pragma: no cover
        self.is_task_running = False
        self._active_worker_thread = None
        log_level = "log_info" if success else "log_error"
        status_text = "SUCCESS" if success else "FAILED/SKIPPED"
        self.log_display.add_message(f"--- THREAD {status_text}: {desc} ({tag}) ---", log_level)
        self._process_next_task_in_queue()

    def _process_next_task_in_queue(self) -> None:  # pragma: no cover
        if self.is_task_running: return
        if not self.task_queue:
            self.is_task_running = False;
            self.current_task_info = None
            self.footer_text.set_text("All queued tasks finished. Press 'q' for main menu.")
            self.log_display.add_message("--- All queued tasks complete ---", "info")
            self._update_interactive_pane(self.main_menu_listbox, title="Main Menu");
            return

        tag, desc, func = self.task_queue.pop(0)
        self.is_task_running = True;
        self.current_task_info = {"tag": tag, "desc": desc}
        status_message = f"Running Task:\n\n{desc} ({tag})\n\nLogs appear on the right..."
        self._update_interactive_pane(urwid.Filler(urwid.Text(status_message, align="center"), valign="middle"),
                                      title="Task In Progress")
        self.footer_text.set_text(f"Running: {desc} ({tag})... Ctrl-C to attempt abort.")
        self.execute_installer_step(tag, desc, func)

    def run_full_installation(self, button: Optional[urwid.Button] = None) -> None:  # pragma: no cover
        if self.is_task_running: self.log_display.add_message("A task or sequence is already in progress.",
                                                              "warning"); return
        self.log_display.clear_logs();
        self.log_display.add_message("--- Queuing Full Installation ---", "header")
        if not self.defined_tasks:
            self.log_display.add_message("No installation tasks defined.", "warning")
            self._update_interactive_pane(urwid.Filler(urwid.Text("No tasks to run.", align="center")), title="Status");
            return
        self.task_queue = list(self.defined_tasks)
        self._process_next_task_in_queue()

    def show_step_selection(self, button: Optional[urwid.Button] = None) -> None:  # pragma: no cover
        if self.is_task_running: self.log_display.add_message("Task in progress. Cannot select new steps now.",
                                                              "warning"); return
        items_to_run_for_queue: List[Tuple[str, str, StepFunctionType]] = []

        def on_checklist_change(checkbox: urwid.CheckBox, new_state: bool,
                                step_data: Tuple[str, str, StepFunctionType]):
            if new_state:
                if step_data not in items_to_run_for_queue: items_to_run_for_queue.append(step_data)
            else:
                if step_data in items_to_run_for_queue: items_to_run_for_queue.remove(step_data)

        checklist_items: List[urwid.Widget] = [
            urwid.Text("No tasks available to select.")] if not self.defined_tasks else \
            [urwid.AttrMap(
                urwid.CheckBox(f"{desc} ({tag})", on_state_change=on_checklist_change, user_data=(tag, desc, func_ref)),
                None, focus_map="checklist_focus")
             for tag, desc, func_ref in self.defined_tasks]
        run_button = urwid.AttrMap(urwid.Button("Run Selected", on_press=lambda b: do_run_selected(b)), "button",
                                   focus_map="button_focus")
        cancel_button = urwid.AttrMap(urwid.Button("Cancel (Back to Main Menu)", on_press=self.show_main_menu),
                                      "button", focus_map="button_focus")
        checklist_lb = urwid.ListBox(
            urwid.SimpleFocusListWalker(checklist_items + [urwid.Divider(), run_button, cancel_button]))

        def do_run_selected(_btn: urwid.Button):
            if self.is_task_running: self.log_display.add_message("A task is already in progress.", "warning"); return
            self.log_display.clear_logs();
            self.log_display.add_message("--- Queuing Selected Steps ---", "header")
            if not items_to_run_for_queue:
                self.log_display.add_message("No steps were selected to run.", "warning")
                self._update_interactive_pane(urwid.Filler(urwid.Text("No steps selected.", align="center")),
                                              title="Status")
                self.footer_text.set_text("No steps selected. Press 'q' for main menu.")
            else:
                self.task_queue = list(items_to_run_for_queue)
                self._process_next_task_in_queue()

        self._update_interactive_pane(checklist_lb, title="Select Steps to Run")
        self.footer_text.set_text("Space to toggle, Enter on buttons. 'q' for main menu.")

    def _show_rerun_dialog_from_worker(self, _loop=None, _data=None) -> None:  # pragma: no cover
        if not self._dialog_prompt_message:
            module_logger.error("No prompt message for rerun dialog from worker.")
            if self._dialog_event: self._dialog_result = False; self._dialog_event.set()
            return
        dialog = YesNoDialog("Confirmation", self._dialog_prompt_message)
        original_top_widget = self.main_loop.widget

        def _handle_dialog_response(is_yes: bool):
            self.main_loop.widget = original_top_widget
            self._dialog_result = is_yes
            if self._dialog_event: self._dialog_event.set()
            self.main_loop.draw_screen()

        urwid.connect_signal(dialog, "close_yes", lambda d: _handle_dialog_response(True))
        urwid.connect_signal(dialog, "close_no", lambda d: _handle_dialog_response(False))
        self.main_loop.widget = urwid.Overlay(dialog, original_top_widget, align="center", width=("relative", 80),
                                              valign="middle", height=("pack", None), min_width=40, min_height=8)
        self.main_loop.draw_screen()

    def _threaded_prompt_for_rerun(self, prompt_message: str) -> bool:  # pragma: no cover
        if threading.current_thread() is threading.main_thread():
            module_logger.warning("_threaded_prompt_for_rerun called from main thread, using original.")
            # When called by execute_step, it needs app_settings.
            # The original tui_prompt_for_rerun doesn't take app_settings. This is a design inconsistency.
            # For now, assuming the TUI's self.app_settings is the one to use for its own prompts.
            return self.tui_prompt_for_rerun(prompt_message)  # This will use a new MainLoop for the prompt.
            # This needs careful review if TUI is deeply nested.
            # The execute_step's prompt_user_for_rerun callback expects:
            # (prompt: str, app_settings: AppSettings, logger: Optional[logging.Logger]) -> bool
            # Our self._threaded_prompt_for_rerun has sig (prompt_message: str) -> bool
            # This mismatch needs to be harmonized.
            # For now, _threaded_prompt_for_rerun directly calls tui_prompt_for_rerun.
        self._dialog_event = threading.Event()
        self._dialog_prompt_message = prompt_message
        self._dialog_result = None
        self.main_loop.alarm(0, self._show_rerun_dialog_from_worker)  # type: ignore[attr-defined]
        self._dialog_event.wait()
        self._dialog_event = None;
        self._dialog_prompt_message = ""
        return self._dialog_result if self._dialog_result is not None else False

    # This is the prompt function if called from the main TUI thread for its own purposes
    def tui_prompt_for_rerun(self, prompt_message: str) -> bool:  # pragma: no cover
        # This version is for prompts originating from the TUI itself, not from execute_step's callback.
        if threading.current_thread() is not threading.main_thread():
            module_logger.error("FATAL: tui_prompt_for_rerun (original) called from non-main thread!");
            return False
        original_main_loop_widget = self.main_loop.widget
        dialog = YesNoDialog("Confirmation", prompt_message)
        dialog_result_holder: Dict[str, Optional[bool]] = {"result": None}
        temp_loop: urwid.MainLoop = urwid.MainLoop(
            widget=urwid.Overlay(dialog, original_main_loop_widget, align="center", width=("relative", 80),
                                 valign="middle", height=("pack", None), min_width=40, min_height=8),
            palette=palette, pop_ups=True
        )

        def handle_dialog_close(is_yes: bool, current_temp_loop_ref: urwid.MainLoop):
            dialog_result_holder["result"] = is_yes
            if current_temp_loop_ref.is_running(): current_temp_loop_ref.stop()  # type: ignore[attr-defined]

        urwid.connect_signal(dialog, "close_yes", lambda d: handle_dialog_close(True, temp_loop))
        urwid.connect_signal(dialog, "close_no", lambda d: handle_dialog_close(False, temp_loop))
        temp_loop.run()
        return dialog_result_holder["result"] if dialog_result_holder["result"] is not None else False

    def execute_installer_step(self, tag: str, desc: str, func: StepFunctionType) -> None:  # pragma: no cover
        self._active_worker_thread = threading.Thread(target=self._task_runner, args=(tag, desc, func), daemon=True)
        self._active_worker_thread.start()

    def confirm_exit_dialog(self, button: Optional[urwid.Button] = None) -> None:  # pragma: no cover
        message = "Are you sure you want to quit?" + (" (A task is running!)" if self.is_task_running else "")
        dialog = YesNoDialog("Confirm Exit", message)
        original_top_widget = self.main_loop.widget

        def close_dialog_and_exit(_d: YesNoDialog, confirmed: bool):
            self.main_loop.widget = original_top_widget
            if confirmed: raise urwid.ExitMainLoop()
            self.main_loop.draw_screen()

        urwid.connect_signal(dialog, "close_yes", lambda d: close_dialog_and_exit(d, True))
        urwid.connect_signal(dialog, "close_no", lambda d: close_dialog_and_exit(d, False))
        self.main_loop.widget = urwid.Overlay(dialog, original_top_widget, align="center", width=("relative", 70),
                                              valign="middle", height=("pack", None), min_width=40, min_height=7)
        self.main_loop.draw_screen()

    def run(self) -> None:
        self.tui_log_handler = TuiLogHandler(self.log_display, self.main_loop)
        self.tui_log_handler.setLevel(logging.DEBUG)  # TUI handler catches all
        root_logger = logging.getLogger()
        self._original_root_logger_level = root_logger.level
        self._original_root_handlers = list(root_logger.handlers)
        self._removed_handlers_by_tui.clear();
        self._root_logger_level_modified_by_tui = False
        if root_logger.level == 0 or root_logger.level > logging.DEBUG:  # NOTSET or > DEBUG
            root_logger.setLevel(logging.DEBUG);
            self._root_logger_level_modified_by_tui = True
            module_logger.debug(
                f"TUI temporarily set root logger level to DEBUG (was {self._original_root_logger_level})")
        for handler in list(root_logger.handlers):
            if isinstance(handler, logging.StreamHandler) and handler.stream in (sys.stdout, sys.stderr):
                module_logger.debug(f"TUI temporarily removing console handler: {handler}");
                root_logger.removeHandler(handler);
                self._removed_handlers_by_tui.append(handler)
        if self.tui_log_handler not in root_logger.handlers:
            root_logger.addHandler(self.tui_log_handler);
            module_logger.debug(f"TUI added TuiLogHandler: {self.tui_log_handler}")
        self.log_display.add_message("Installer TUI Initialized. Welcome!", "info")
        try:
            self.main_loop.run()
        except urwid.ExitMainLoop:
            module_logger.info("Exiting TUI normally.")  # pragma: no cover
        except Exception:
            module_logger.exception("Unhandled exception in TUI main loop")  # pragma: no cover
        finally:
            module_logger.debug("TUI shutting down. Restoring original logging setup...")
            if self.tui_log_handler and self.tui_log_handler in root_logger.handlers:
                root_logger.removeHandler(self.tui_log_handler);
                module_logger.debug(f"TUI removed TuiLogHandler: {self.tui_log_handler}")
            for handler_to_restore in self._removed_handlers_by_tui:
                if handler_to_restore not in root_logger.handlers:
                    root_logger.addHandler(handler_to_restore);
                    module_logger.debug(f"TUI restored console handler: {handler_to_restore}")
            if self._root_logger_level_modified_by_tui and self._original_root_logger_level is not None:
                root_logger.setLevel(self._original_root_logger_level);
                module_logger.debug(f"TUI restored root logger level to: {self._original_root_logger_level}")
            print("Installer TUI has shut down.", file=sys.stderr)


def run_tui_installer(
        defined_tasks: List[Tuple[str, str, StepFunctionType]],  # Use StepFunctionType
        app_settings: AppSettings  # Expect AppSettings here
) -> None:  # pragma: no cover
    app = InstallerTUI(defined_tasks=defined_tasks, app_settings_instance=app_settings)
    app.run()


if __name__ == "__main__":  # pragma: no cover
    print("Running TUI in standalone test mode...", file=sys.stderr)
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr,
                            format="[TUI-STANDALONE-TEST] %(asctime)s %(levelname)s %(name)s: %(message)s")
        module_logger.info("TUI __main__: BasicConfig logging configured for standalone test.")


    # Create a dummy AppSettings for standalone TUI testing
    class DummyAppSettings(AppSettings):
        admin_group_ip: str = "192.168.1.0/24"
        gtfs_feed_url: str = "http://example.com/gtfs.zip"
        vm_ip_or_domain: str = "dummy.example.com"
        # Populate other fields with defaults or dummy values as needed by TUI views or step functions
        # For simplicity, many will use Pydantic defaults.
        symbols: Dict[str, str] = SYMBOLS_DEFAULT.copy()


    dummy_app_settings = DummyAppSettings()


    # Define dummy step functions that now accept AppSettings
    def example_step_alpha(settings: AppSettings, cl: Optional[logging.Logger]):
        (cl or module_logger).info(f"Executing Example Step Alpha with admin_ip: {settings.admin_group_ip}...")
        import time;
        time.sleep(2)
        (cl or module_logger).info("Example Step Alpha finished.")


    has_beta_failed_once = False


    def example_step_beta_fails_and_reruns(settings: AppSettings, cl: Optional[logging.Logger]):
        global has_beta_failed_once
        (cl or module_logger).info(
            f"Executing Example Step Beta (will fail first time) for domain: {settings.vm_ip_or_domain}...")
        import time;
        time.sleep(1)
        if not has_beta_failed_once:
            has_beta_failed_once = True
            (cl or module_logger).error("Something went wrong in Beta!");
            raise ValueError("Beta step simulated failure (1st time)")
        (cl or module_logger).info("Example Step Beta (rerun) finished successfully.")


    DUMMY_TASKS_FOR_STANDALONE: List[Tuple[str, str, StepFunctionType]] = [
        ("ALPHA_STEP", "Run Example Step Alpha (OK, 2s)", example_step_alpha),
        ("BETA_STEP", "Run Beta (FAILS 1st, then OK)", example_step_beta_fails_and_reruns),
        ("GAMMA_STEP", "Run Example Step Gamma (OK, 2s)", example_step_alpha),
    ]

    _original_real_execute_step = execute_step  # Keep a reference to the real one


    # Monkey patch execute_step for the TUI standalone test to simulate its behavior
    # This dummy version now matches the real signature
    def dummy_execute_step_for_tui_test(
            tag: str, desc: str,
            func: StepFunctionType,  # Callable[[AppSettings, Optional[logging.Logger]], Any]
            app_settings_param: AppSettings,  # Matches real execute_step
            current_logger_instance: Optional[logging.Logger],
            prompt_user_for_rerun_cb: Callable[[str, AppSettings, Optional[logging.Logger]], bool],
    ) -> bool:
        effective_logger = current_logger_instance or module_logger
        effective_logger.info(
            f"[DummyTUI Exec] Attempting: {desc} with app_settings.domain = {app_settings_param.vm_ip_or_domain}")
        try:
            func(app_settings_param, effective_logger)  # Call func with app_settings and logger
            effective_logger.info(f"[DummyTUI Exec] Completed: {desc}")
            return True
        except Exception as e:
            effective_logger.error(f"[DummyTUI Exec] FAILED: {desc} with {e}")
            # The prompt_user_for_rerun_cb is self._threaded_prompt_for_rerun
            # which now calls self.tui_prompt_for_rerun (which is a simple Yes/No without AppSettings)
            # This part of the dummy needs to align with how prompt is actually called by real execute_step.
            # For simplicity, let's make the dummy prompt always use the passed logger.
            if prompt_user_for_rerun_cb(f"'{desc}' failed. Rerun?", app_settings_param, effective_logger):
                effective_logger.info(f"[DummyTUI Exec] User chose to rerun: {desc}")
                try:
                    func(app_settings_param, effective_logger)
                    effective_logger.info(f"[DummyTUI Exec] Re-run OK: {desc}")
                    return True
                except Exception as e_rerun:
                    effective_logger.error(f"[DummyTUI Exec] Re-run FAILED: {desc} with {e_rerun}")
                    return False
            else:
                effective_logger.info(f"[DummyTUI Exec] User chose NOT to rerun: {desc}")
                return False


    execute_step = dummy_execute_step_for_tui_test  # Monkey patch

    _original_view_completed_steps = view_completed_steps


    def dummy_view_completed_steps_for_tui(app_settings_param: AppSettings,
                                           current_logger_param: Optional[logging.Logger]) -> List[str]:
        (current_logger_param or module_logger).info(
            f"[Dummy State] Viewing completed steps for domain {app_settings_param.vm_ip_or_domain}.")
        return ["PREVIOUS_DUMMY_STEP_1", "PREVIOUS_DUMMY_STEP_2"]


    view_completed_steps = dummy_view_completed_steps_for_tui  # Monkey patch

    try:
        run_tui_installer(defined_tasks=DUMMY_TASKS_FOR_STANDALONE, app_settings=dummy_app_settings)
    finally:
        execute_step = _original_real_execute_step  # Restore real execute_step
        view_completed_steps = _original_view_completed_steps  # Restore
        has_beta_failed_once = False  # Reset global for dummy step
        print("Standalone TUI test finished.", file=sys.stderr)
