# ui/tui_application.py
# -*- coding: utf-8 -*-
"""
Main application class and runner for the Urwid-based TUI.
"""

import logging
import sys
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

import urwid  # type: ignore[import-untyped]

# Imports from the setup package
from setup.config_models import (
    SYMBOLS_DEFAULT,
    AppSettings,
)
from setup.state_manager import view_completed_steps
from setup.step_executor import execute_step

# Imports from other TUI modules in the ui package
from .tui_constants import (
    StepFunctionType,
    palette,
)  # StepFunctionType is Callable[..., None]
from .tui_logging import TuiLogHandler
from .tui_widgets import LogDisplay, YesNoDialog

module_logger = logging.getLogger(__name__)


class InstallerTUI:
    """
    A text-based user interface (TUI) for managing server installation tasks.

    This class provides a TUI for organizing and executing a sequence of tasks
    related to server installation. It integrates task management, log display,
    configuration viewing, and management state utilities within an interactive
    UI, allowing users to view progress and manage workflows in real time. It
    leverages the `urwid` library for rendering console-based user interfaces and
    also interacts with application settings through the `AppSettings` instance
    passed to it. The class also facilitates multi-threaded task execution and
    handles log integration for improved error tracking and debugging.

    Attributes:
        defined_tasks: A list of tasks, where each task is a tuple containing
            a tag, description, and a callable step function.
        app_settings: The application settings instance, providing configuration
            and shared parameters.
        tui_log_handler: Optional `TuiLogHandler` instance for logging integration
            in the TUI.
        task_queue: A queue of tasks to be executed by the TUI.
        is_task_running: Flag indicating whether a task is currently being
            executed.
        current_task_info: Contains details of the currently executing task, if
            available.
        _active_worker_thread: Internal reference to the current worker thread for
            task execution.
        _dialog_event: Internal thread synchronization event for managing dialog
            prompts.
        _dialog_prompt_message: Stores the message to display in dialog prompts.
        _dialog_result: Stores the result of dialog interactions (e.g., `bool`).
        _original_root_logger_level: Original logging level of the root logger,
            used for restoring logger state.
        _root_logger_level_modified_by_tui: Indicates whether the logger's state
            was modified by the TUI.
        _original_root_handlers: List of original root logger handlers prior to
            modification by the TUI.
        _removed_handlers_by_tui: List of handlers removed by the TUI for log
            redirection purposes.
        header: UI header displaying the title of the TUI.
        footer_text: Text widget for the footer, containing help and navigation
            information.
        footer: UI footer providing navigation instructions and context.
        log_display: Log display area within the TUI, where messages are shown.
        main_menu_listbox: List box widget rendering the main menu options.
        interactive_pane_placeholder: Placeholder widget for dynamically updating
            interactive panes.
        columns_view: Layout defining two-column UI layout (controls and logs).
        frame: Main frame layout of the TUI, combining header, controls, and logs.
        main_loop: Main loop managing user input and UI rendering.
    """

    def __init__(
        self,
        defined_tasks: List[Tuple[str, str, StepFunctionType]],
        app_settings_instance: AppSettings,
    ) -> None:
        self.defined_tasks = defined_tasks
        self.app_settings: AppSettings = app_settings_instance
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

        self.header = urwid.AttrMap(
            urwid.Text("OSM Server Installer TUI", align="center"), "header"
        )
        self.footer_text = urwid.Text(
            "Ctrl-C to Exit | Keys: Up, Down, Enter, Esc | 'q' to Main Menu",
            align="center",
        )
        self.footer = urwid.AttrMap(self.footer_text, "footer")
        self.log_display = LogDisplay()
        self.main_menu_listbox = urwid.ListBox(
            urwid.SimpleFocusListWalker(self._build_main_menu())
        )
        self.interactive_pane_placeholder = urwid.WidgetPlaceholder(
            urwid.LineBox(self.main_menu_listbox, title="Controls")
        )
        self.columns_view = urwid.Columns(
            [
                ("weight", 1, self.interactive_pane_placeholder),
                ("weight", 2, self.log_display),
            ],
            dividechars=1,
        )
        self.frame = urwid.Frame(
            body=self.columns_view, header=self.header, footer=self.footer
        )
        self.main_loop: urwid.MainLoop = urwid.MainLoop(
            self.frame,
            palette=palette,
            unhandled_input=self._handle_global_keys,
            pop_ups=True,
        )

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
            buttons.append(
                urwid.AttrMap(
                    urwid.Button(name, on_press=callback),
                    "button",
                    focus_map="button_focus",
                )
            )
        return buttons

    def _handle_global_keys(self, key: str) -> None:  # pragma: no cover
        if key == "ctrl c":
            self.confirm_exit_dialog()
        elif key == "q":
            is_main_menu_linebox_widget = (
                self.interactive_pane_placeholder.original_widget
            )
            is_main_menu = (
                isinstance(is_main_menu_linebox_widget, urwid.LineBox)
                and is_main_menu_linebox_widget.original_widget
                is self.main_menu_listbox
            )
            if not is_main_menu and not self.is_task_running:
                self.show_main_menu()
            elif self.is_task_running:
                self.log_display.add_message(
                    "Cannot return to main menu while a task is running.",
                    "warning",
                )

    def _update_interactive_pane(
        self, widget: urwid.Widget, title: str = "Controls"
    ) -> None:
        self.interactive_pane_placeholder.original_widget = urwid.LineBox(
            widget, title=title
        )
        self.main_loop.draw_screen()

    def show_main_menu(self, button: Optional[urwid.Button] = None) -> None:
        if self.is_task_running:  # pragma: no cover
            self.log_display.add_message(
                "Task in progress. Cannot show main menu now.", "warning"
            )
            return
        self._update_interactive_pane(
            self.main_menu_listbox, title="Main Menu"
        )
        self.footer_text.set_text(
            "Ctrl-C to Exit | Keys: Up, Down, Enter, Esc | 'q' to Main Menu"
        )

    def show_view_configuration(
        self, button: Optional[urwid.Button] = None
    ) -> None:  # pragma: no cover
        if self.is_task_running:
            self.log_display.add_message(
                "Task in progress. Cannot view configuration now.", "warning"
            )
            return
        self.log_display.clear_logs()
        self.log_display.add_message(
            "--- Current Configuration ---", "header"
        )
        cfg_to_display = self.app_settings
        try:
            self.log_display.add_message(
                f"Admin IP: {cfg_to_display.admin_group_ip}", "info"
            )
            self.log_display.add_message(
                f"GTFS URL: {str(cfg_to_display.gtfs_feed_url)}", "info"
            )
            self.log_display.add_message(
                f"VM Domain: {cfg_to_display.vm_ip_or_domain}", "info"
            )
        except AttributeError as e:
            self.log_display.add_message(
                f"Config item not found: {e}", "error"
            )
        except Exception as e:
            self.log_display.add_message(
                f"Error loading config: {e}", "error"
            )
        self.footer_text.set_text(
            "Configuration displayed in Logs. Press 'q' to return to main menu."
        )
        self.main_loop.draw_screen()

    def show_manage_state(
        self, button: Optional[urwid.Button] = None
    ) -> None:  # pragma: no cover
        if self.is_task_running:
            self.log_display.add_message(
                "Task in progress. Cannot manage state now.", "warning"
            )
            return
        self.log_display.clear_logs()
        self.log_display.add_message("--- Manage State ---", "header")
        try:
            completed = view_completed_steps(
                app_settings=self.app_settings, current_logger=module_logger
            )
            if completed:
                self.log_display.add_message("Completed steps:", "info")
                for step_tag in completed:
                    self.log_display.add_message(f" - {step_tag}", "info")
            else:
                self.log_display.add_message(
                    "No steps recorded as completed.", "info"
                )
        except Exception as e:
            self.log_display.add_message(f"Error viewing state: {e}", "error")
            module_logger.exception("Error in show_manage_state")
        self.footer_text.set_text(
            "State information in Logs. Press 'q' to return to main menu."
        )
        self.main_loop.draw_screen()

    def _task_runner(
        self, tag: str, desc: str, func: StepFunctionType
    ) -> None:  # pragma: no cover
        success = False
        try:
            success = execute_step(
                tag,
                desc,
                func,
                self.app_settings,
                current_logger_instance=module_logger,
                prompt_user_for_rerun=self._threaded_prompt_for_rerun,
            )
        except Exception as e:
            module_logger.critical(
                f"Unhandled exception in threaded task {tag} ({desc}): {e}",
                exc_info=True,
            )
            success = False
        finally:
            self.main_loop.alarm(
                0,
                lambda _l, _d: self._handle_task_completion(
                    tag, desc, success
                ),
            )  # type: ignore[attr-defined]

    def _handle_task_completion(
        self, tag: str, desc: str, success: bool
    ) -> None:  # pragma: no cover
        self.is_task_running = False
        self._active_worker_thread = None
        log_level = "log_info" if success else "log_error"
        status_text = "SUCCESS" if success else "FAILED/SKIPPED"
        self.log_display.add_message(
            f"--- THREAD {status_text}: {desc} ({tag}) ---", log_level
        )
        self._process_next_task_in_queue()

    def _process_next_task_in_queue(self) -> None:  # pragma: no cover
        if self.is_task_running:
            return
        if not self.task_queue:
            self.is_task_running = False
            self.current_task_info = None
            self.footer_text.set_text(
                "All queued tasks finished. Press 'q' for main menu."
            )
            self.log_display.add_message(
                "--- All queued tasks complete ---", "info"
            )
            self._update_interactive_pane(
                self.main_menu_listbox, title="Main Menu"
            )
            return

        tag, desc, func = self.task_queue.pop(0)
        self.is_task_running = True
        self.current_task_info = {"tag": tag, "desc": desc}
        status_message = (
            f"Running Task:\n\n{desc} ({tag})\n\nLogs appear on the right..."
        )
        self._update_interactive_pane(
            urwid.Filler(
                urwid.Text(status_message, align="center"), valign="middle"
            ),
            title="Task In Progress",
        )
        self.footer_text.set_text(
            f"Running: {desc} ({tag})... Ctrl-C to attempt abort."
        )
        self.execute_installer_step(tag, desc, func)

    def run_full_installation(
        self, button: Optional[urwid.Button] = None
    ) -> None:  # pragma: no cover
        if self.is_task_running:
            self.log_display.add_message(
                "A task or sequence is already in progress.", "warning"
            )
            return
        self.log_display.clear_logs()
        self.log_display.add_message(
            "--- Queuing Full Installation ---", "header"
        )
        if not self.defined_tasks:
            self.log_display.add_message(
                "No installation tasks defined.", "warning"
            )
            self._update_interactive_pane(
                urwid.Filler(urwid.Text("No tasks to run.", align="center")),
                title="Status",
            )
            return
        self.task_queue = list(self.defined_tasks)
        self._process_next_task_in_queue()

    def show_step_selection(
        self, button: Optional[urwid.Button] = None
    ) -> None:  # pragma: no cover
        if self.is_task_running:
            self.log_display.add_message(
                "Task in progress. Cannot select new steps now.", "warning"
            )
            return

        items_to_run_for_queue: List[Tuple[str, str, StepFunctionType]] = []

        def on_checklist_change(
            checkbox: urwid.CheckBox,
            new_state: bool,
            step_data: Tuple[str, str, StepFunctionType],
        ):
            if new_state:
                if step_data not in items_to_run_for_queue:
                    items_to_run_for_queue.append(step_data)
            else:
                if step_data in items_to_run_for_queue:
                    items_to_run_for_queue.remove(step_data)

        checklist_items: List[urwid.Widget] = []
        if not self.defined_tasks:
            checklist_items.append(
                urwid.Text("No tasks available to select.")
            )
        else:
            for tag, desc, func_ref in self.defined_tasks:
                cb = urwid.CheckBox(
                    f"{desc} ({tag})",
                    on_state_change=on_checklist_change,
                    user_data=(tag, desc, func_ref),
                )
                checklist_items.append(
                    urwid.AttrMap(cb, None, focus_map="checklist_focus")
                )

        def do_run_selected(_btn: urwid.Button):
            if self.is_task_running:
                self.log_display.add_message(
                    "A task is already in progress.", "warning"
                )
                return
            self.log_display.clear_logs()
            self.log_display.add_message(
                "--- Queuing Selected Steps ---", "header"
            )
            if not items_to_run_for_queue:
                self.log_display.add_message(
                    "No steps were selected to run.", "warning"
                )
                self._update_interactive_pane(
                    urwid.Filler(
                        urwid.Text("No steps selected.", align="center")
                    ),
                    title="Status",
                )
                self.footer_text.set_text(
                    "No steps selected. Press 'q' for main menu."
                )
            else:
                self.task_queue = list(items_to_run_for_queue)
                self._process_next_task_in_queue()

        run_button = urwid.AttrMap(
            urwid.Button("Run Selected", on_press=do_run_selected),
            "button",
            focus_map="button_focus",
        )
        cancel_button = urwid.AttrMap(
            urwid.Button(
                "Cancel (Back to Main Menu)", on_press=self.show_main_menu
            ),
            "button",
            focus_map="button_focus",
        )
        list_walker_items = checklist_items + [
            urwid.Divider(),
            run_button,
            cancel_button,
        ]
        checklist_lb = urwid.ListBox(
            urwid.SimpleFocusListWalker(list_walker_items)
        )
        self._update_interactive_pane(
            checklist_lb, title="Select Steps to Run"
        )
        self.footer_text.set_text(
            "Space to toggle, Enter on buttons. 'q' for main menu."
        )

    def _show_rerun_dialog_from_worker(
        self, _loop=None, _data=None
    ) -> None:  # pragma: no cover
        if not self._dialog_prompt_message:
            module_logger.error(
                "No prompt message for rerun dialog from worker."
            )
            if self._dialog_event:
                self._dialog_result = False
                self._dialog_event.set()
                return
        dialog = YesNoDialog("Confirmation", self._dialog_prompt_message)
        original_top_widget = self.main_loop.widget

        def _handle_dialog_response(is_yes: bool):
            self.main_loop.widget = original_top_widget
            self._dialog_result = is_yes
            if self._dialog_event:
                self._dialog_event.set()
            self.main_loop.draw_screen()

        urwid.connect_signal(
            dialog, "close_yes", lambda d: _handle_dialog_response(True)
        )
        urwid.connect_signal(
            dialog, "close_no", lambda d: _handle_dialog_response(False)
        )
        self.main_loop.widget = urwid.Overlay(
            dialog,
            original_top_widget,
            align="center",
            width=("relative", 80),
            valign="middle",
            height=("pack", None),
            min_width=40,
            min_height=8,
        )
        self.main_loop.draw_screen()

    def _threaded_prompt_for_rerun(
        self,
        prompt_message: str,
        settings: AppSettings,
        logger_instance: Optional[
            logging.Logger
        ],  # Renamed from 'logger' to avoid conflict with module_logger
    ) -> bool:  # pragma: no cover
        if threading.current_thread() is threading.main_thread():
            (logger_instance or module_logger).warning(
                "_threaded_prompt_for_rerun called from main thread unexpectedly, using direct TUI prompt."
            )
            return self.tui_prompt_for_rerun(prompt_message)

        self._dialog_event = threading.Event()
        self._dialog_prompt_message = prompt_message
        self._dialog_result = None
        self.main_loop.alarm(0, self._show_rerun_dialog_from_worker)  # type: ignore[attr-defined]
        self._dialog_event.wait()
        self._dialog_event = None
        self._dialog_prompt_message = ""
        return (
            self._dialog_result if self._dialog_result is not None else False
        )

    def tui_prompt_for_rerun(
        self, prompt_message: str
    ) -> bool:  # pragma: no cover
        if threading.current_thread() is not threading.main_thread():
            module_logger.error(
                "FATAL: tui_prompt_for_rerun (direct) called from non-main thread!"
            )
            return False
        original_main_loop_widget = self.main_loop.widget
        dialog = YesNoDialog("Confirmation", prompt_message)
        dialog_result_holder: Dict[str, Optional[bool]] = {"result": None}
        temp_loop: urwid.MainLoop = urwid.MainLoop(
            widget=urwid.Overlay(
                dialog,
                original_main_loop_widget,
                align="center",
                width=("relative", 80),
                valign="middle",
                height=("pack", None),
                min_width=40,
                min_height=8,
            ),
            palette=palette,
            pop_ups=True,
        )

        def handle_dialog_close(
            is_yes: bool, current_temp_loop_ref: urwid.MainLoop
        ):
            dialog_result_holder["result"] = is_yes
            if current_temp_loop_ref.is_running():
                current_temp_loop_ref.stop()  # type: ignore[attr-defined]

        urwid.connect_signal(
            dialog,
            "close_yes",
            lambda d: handle_dialog_close(True, temp_loop),
        )
        urwid.connect_signal(
            dialog,
            "close_no",
            lambda d: handle_dialog_close(False, temp_loop),
        )
        temp_loop.run()
        return (
            dialog_result_holder["result"]
            if dialog_result_holder["result"] is not None
            else False
        )

    def execute_installer_step(
        self, tag: str, desc: str, func: StepFunctionType
    ) -> None:  # pragma: no cover
        self._active_worker_thread = threading.Thread(
            target=self._task_runner, args=(tag, desc, func), daemon=True
        )
        self._active_worker_thread.start()

    def confirm_exit_dialog(
        self, button: Optional[urwid.Button] = None
    ) -> None:  # pragma: no cover
        message = "Are you sure you want to quit?" + (
            " (A task is running!)" if self.is_task_running else ""
        )
        dialog = YesNoDialog("Confirm Exit", message)
        original_top_widget = self.main_loop.widget

        def close_dialog_and_exit(_d: YesNoDialog, confirmed: bool):
            self.main_loop.widget = original_top_widget
            if confirmed:
                raise urwid.ExitMainLoop()
            self.main_loop.draw_screen()

        urwid.connect_signal(
            dialog, "close_yes", lambda d: close_dialog_and_exit(d, True)
        )
        urwid.connect_signal(
            dialog, "close_no", lambda d: close_dialog_and_exit(d, False)
        )
        self.main_loop.widget = urwid.Overlay(
            dialog,
            original_top_widget,
            align="center",
            width=("relative", 70),
            valign="middle",
            height=("pack", None),
            min_width=40,
            min_height=7,
        )
        self.main_loop.draw_screen()

    def run(self) -> None:
        self.tui_log_handler = TuiLogHandler(self.log_display, self.main_loop)
        self.tui_log_handler.setLevel(logging.DEBUG)
        root_logger = logging.getLogger()
        self._original_root_logger_level = root_logger.level
        self._original_root_handlers = list(root_logger.handlers)
        self._removed_handlers_by_tui.clear()
        self._root_logger_level_modified_by_tui = False

        if (
            root_logger.level == 0 or root_logger.level > logging.DEBUG
        ):  # Ensure DEBUG to capture all levels
            root_logger.setLevel(logging.DEBUG)
            self._root_logger_level_modified_by_tui = True
            module_logger.debug(
                f"TUI temporarily set root logger level to DEBUG (was {self._original_root_logger_level})"
            )
        # Remove existing console handlers to avoid duplicate console output
        for handler in list(root_logger.handlers):  # Iterate over a copy
            if isinstance(
                handler, logging.StreamHandler
            ) and handler.stream in (sys.stdout, sys.stderr):
                module_logger.debug(
                    f"TUI temporarily removing console handler: {handler}"
                )
                root_logger.removeHandler(handler)
                self._removed_handlers_by_tui.append(handler)

        if self.tui_log_handler not in root_logger.handlers:
            root_logger.addHandler(self.tui_log_handler)
            module_logger.debug(
                f"TUI added TuiLogHandler: {self.tui_log_handler}"
            )
        self.log_display.add_message(
            "Installer TUI Initialized. Welcome!", "info"
        )
        try:
            self.main_loop.run()
        except urwid.ExitMainLoop:
            module_logger.info("Exiting TUI normally.")
        except Exception:  # pragma: no cover
            module_logger.exception("Unhandled exception in TUI main loop")
        finally:
            module_logger.debug(
                "TUI shutting down. Restoring original logging setup..."
            )
            if (
                self.tui_log_handler
                and self.tui_log_handler in root_logger.handlers
            ):
                root_logger.removeHandler(self.tui_log_handler)
                module_logger.debug(
                    f"TUI removed TuiLogHandler: {self.tui_log_handler}"
                )
            for handler_to_restore in self._removed_handlers_by_tui:
                if (
                    handler_to_restore not in root_logger.handlers
                ):  # Check to avoid adding if already re-added elsewhere
                    root_logger.addHandler(handler_to_restore)
                    module_logger.debug(
                        f"TUI restored console handler: {handler_to_restore}"
                    )
            if (
                self._root_logger_level_modified_by_tui
                and self._original_root_logger_level is not None
            ):
                root_logger.setLevel(self._original_root_logger_level)
                module_logger.debug(
                    f"TUI restored root logger level to: {self._original_root_logger_level}"
                )
            print("Installer TUI has shut down.", file=sys.stderr)


def run_tui_installer(
    defined_tasks: List[Tuple[str, str, StepFunctionType]],
    app_settings: AppSettings,
) -> None:  # pragma: no cover
    app = InstallerTUI(
        defined_tasks=defined_tasks, app_settings_instance=app_settings
    )
    app.run()


if __name__ == "__main__":  # pragma: no cover
    print("Running TUI in standalone test mode...", file=sys.stderr)
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.DEBUG,
            stream=sys.stderr,
            format="[TUI-STANDALONE-TEST] %(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        module_logger.info(
            "TUI __main__: BasicConfig logging configured for standalone test."
        )

    class DummyAppSettings(AppSettings):
        admin_group_ip: str = "192.168.1.0/24 (dummy)"
        gtfs_feed_url: str = "http://example.com/gtfs.zip (dummy)"
        vm_ip_or_domain: str = "dummy.example.com (dummy)"
        symbols: Dict[str, str] = SYMBOLS_DEFAULT.copy()

    dummy_app_settings = DummyAppSettings()

    def example_step_alpha(
        settings: AppSettings, cl: Optional[logging.Logger]
    ) -> None:
        (cl or module_logger).info(
            f"Executing Example Step Alpha with admin_ip: {settings.admin_group_ip}..."
        )
        import time

        time.sleep(2)
        (cl or module_logger).info("Example Step Alpha finished.")

    has_beta_failed_once_tui_test = False

    def example_step_beta_fails_and_reruns(
        settings: AppSettings, cl: Optional[logging.Logger]
    ) -> None:
        global has_beta_failed_once_tui_test
        (cl or module_logger).info(
            f"Executing Example Step Beta (will fail first time) for domain: {settings.vm_ip_or_domain}..."
        )
        import time

        time.sleep(1)
        if not has_beta_failed_once_tui_test:
            has_beta_failed_once_tui_test = True
            (cl or module_logger).error("Something went wrong in Beta!")
            raise ValueError("Beta step simulated failure (1st time)")
        (cl or module_logger).info(
            "Example Step Beta (rerun) finished successfully."
        )

    DUMMY_TASKS_FOR_STANDALONE: List[Tuple[str, str, StepFunctionType]] = [
        ("ALPHA_STEP", "Run Example Step Alpha (OK, 2s)", example_step_alpha),
        (
            "BETA_STEP",
            "Run Beta (FAILS 1st, then OK)",
            example_step_beta_fails_and_reruns,
        ),
        ("GAMMA_STEP", "Run Example Step Gamma (OK, 2s)", example_step_alpha),
    ]

    _original_real_execute_step_tui = execute_step  # Store original

    def dummy_execute_step_for_tui_test(
        step_tag: str,
        step_description: str,
        step_function: StepFunctionType,
        app_settings: AppSettings,
        current_logger_instance: Optional[logging.Logger],
        prompt_user_for_rerun: Callable[  # Was prompt_user_for_rerun_cb
            [str, AppSettings, Optional[logging.Logger]], bool
        ],
        cli_flag: Optional[str] = None,
        group_cli_flag: Optional[str] = None,
    ) -> bool:
        effective_logger = current_logger_instance or module_logger
        effective_logger.info(
            f"[DummyTUI Exec] Attempting: {step_description} with app_settings.domain = {app_settings.vm_ip_or_domain}"
        )
        try:
            step_function(app_settings, effective_logger)
            effective_logger.info(
                f"[DummyTUI Exec] Completed: {step_description}"
            )
            return True
        except Exception as e:
            effective_logger.error(
                f"[DummyTUI Exec] FAILED: {step_description} with {e}"
            )
            if prompt_user_for_rerun(
                f"'{step_description}' failed. Rerun?",
                app_settings,
                effective_logger,
            ):
                effective_logger.info(
                    f"[DummyTUI Exec] User chose to rerun: {step_description}"
                )
                try:
                    step_function(app_settings, effective_logger)
                    effective_logger.info(
                        f"[DummyTUI Exec] Re-run OK: {step_description}"
                    )
                    return True
                except Exception as e_rerun:
                    effective_logger.error(
                        f"[DummyTUI Exec] Re-run FAILED: {step_description} with {e_rerun}"
                    )
                    return False
            else:
                effective_logger.info(
                    f"[DummyTUI Exec] User chose NOT to rerun: {step_description}"
                )
                return False

    execute_step = dummy_execute_step_for_tui_test

    _original_view_completed_steps_tui = view_completed_steps

    def dummy_view_completed_steps_for_tui(
        app_settings: AppSettings,
        current_logger: Optional[logging.Logger] = None,
    ) -> List[str]:
        (current_logger or module_logger).info(
            f"[Dummy State] Viewing completed steps for config with domain '{app_settings.vm_ip_or_domain}'."
        )
        return ["PREVIOUS_DUMMY_STEP_1", "PREVIOUS_DUMMY_STEP_2"]

    view_completed_steps = dummy_view_completed_steps_for_tui

    try:
        run_tui_installer(
            defined_tasks=DUMMY_TASKS_FOR_STANDALONE,
            app_settings=dummy_app_settings,
        )
    finally:
        execute_step = _original_real_execute_step_tui
        view_completed_steps = _original_view_completed_steps_tui
        has_beta_failed_once_tui_test = False
        print("Standalone TUI test finished.", file=sys.stderr)
