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
from installer.config_models import (
    SYMBOLS_DEFAULT,
    AppSettings,
)
from installer.state_manager import view_completed_steps
from installer.step_executor import execute_step

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
        """
        Initializes an instance of the class and sets up the main components of the TUI
        (Task-based User Interface). Configures initial attributes, task handling, and
        UI elements.

        Attributes:
            defined_tasks: List of predefined task tuples, each containing a name,
                description, and a callable step function representing the task.
            app_settings: Instance of AppSettings that manages application-specific
                configurations.
            tui_log_handler: An optional TuiLogHandler instance for logging within the
                TUI.
            task_queue: List that manages the queue of tasks awaiting execution,
                initialized as empty.
            is_task_running: A boolean indicating whether a task is currently being
                executed, initialized to False.
            current_task_info: Optional dictionary containing metadata about the
                currently running task; initialized to None.
            _active_worker_thread: Optional threading.Thread used for running tasks in
                a background thread; initialized to None.
            _dialog_event: Optional threading.Event used for synchronizing dialog-related
                UI interactions; initialized to None.
            _dialog_prompt_message: String that stores the current prompt message
                displayed in dialog boxes, initialized as empty.
            _dialog_result: Optional boolean representing the result of a dialog action,
                if applicable; initialized to None.
            _original_root_logger_level: Optional integer capturing the original logging
                level for the root logger; initialized to None.
            _root_logger_level_modified_by_tui: Boolean indicating whether the root
                logger's level has been modified by the TUI; initialized to False.
            _original_root_handlers: List of original logging.Handler instances
                associated with the root logger before TUI modifications.
            _removed_handlers_by_tui: List of logging.Handler instances removed or
                replaced by the TUI.

            header: An instance of urwid.AttrMap representing the header of the UI,
                containing a title text widget.
            footer_text: An instance of urwid.Text containing footer instructions for
                user interaction.
            footer: An instance of urwid.AttrMap wrapping the footer text for display
                styling.
            log_display: An instance of LogDisplay, managing the visual display of log
                messages in the TUI.
            main_menu_listbox: An instance of urwid.ListBox, built from a
                SimpleFocusListWalker populated by the main menu items.
            interactive_pane_placeholder: An instance of urwid.WidgetPlaceholder serving
                as a placeholder for the interactive pane within the interface.
            columns_view: An instance of urwid.Columns, laying out the interactive
                pane and log display side-by-side.
            frame: An instance of urwid.Frame, combining the body, header, and footer
                to construct the full UI frame.
            main_loop: An instance of urwid.MainLoop, serving as the application's
                main event loop, configured with a specific palette and an unhandled
                input handler.
        """
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
        """
        Builds and returns the main menu as a list of configured urwid Widgets.

        This private method constructs the main menu for the application interface. It
        creates menu options, assigns corresponding callback functions, and applies
        styling for the buttons that represent each menu option. The generated widgets
        are returned as a list to be further utilized in rendering the menu.

        Returns:
            List[urwid.Widget]: A list of urwid.Widget objects representing the main
            menu options with applied styles and their respective callbacks.

        """
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
        """
        Handle global key events for the application.

        This method processes key inputs that are intended to perform global actions,
        such as exiting the application or returning to the main menu. It handles these
        keys based on the current state of the application, ensuring certain operations
        are restricted when a task is actively running.

        Args:
            key: str
                The input key received from the user.

        Returns:
            None
        """
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
        """
        Updates the interactive pane with a new widget and title. The placeholder widget in
        the interactive pane is replaced with a new LineBox widget that wraps the provided
        widget. This method also redraws the screen to reflect the changes.

        Parameters
        ----------
        widget : urwid.Widget
            The widget to be displayed in the interactive pane.
        title : str, optional
            The title to be displayed on the LineBox containing the widget. Defaults to
            "Controls".

        Returns
        -------
        None
        """
        self.interactive_pane_placeholder.original_widget = urwid.LineBox(
            widget, title=title
        )
        self.main_loop.draw_screen()

    def _task_runner(
        self, tag: str, desc: str, func: StepFunctionType
    ) -> None:  # pragma: no cover
        """
        Executes a task within a threaded environment and handles its completion.

        This method is responsible for running a task provided as a function in a
        threaded setup, ensuring proper execution and logging of any exceptions
        encountered during execution. Upon task completion, it triggers an alarm
        to handle post-task processing asynchronously.

        Arguments:
            tag: str
                A unique identifier or name for the task, used for logging and
                tracking purposes.
            desc: str
                A descriptive string about the task, used for logging and
                better understanding of the task's intent or context.
            func: StepFunctionType
                The function representing the task to be executed. This function
                encapsulates the actual behavior or logic of the task.

        Raises:
            Exception
                If an unhandled exception occurs during the execution of the
                task, it is logged critically, providing information and context
                of the failure.
        """
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
        """
        Handles the completion of a task by updating the state, logging the result,
        and processing the next task in the queue.

        Parameters:
        tag : str
            The identifier for the completed task.
        desc : str
            A description of the completed task.
        success : bool
            Indicates whether the task was completed successfully.

        """
        self.is_task_running = False
        self._active_worker_thread = None
        log_level = "log_info" if success else "log_error"
        status_text = "SUCCESS" if success else "FAILED/SKIPPED"
        self.log_display.add_message(
            f"--- THREAD {status_text}: {desc} ({tag}) ---", log_level
        )
        self._process_next_task_in_queue()

    def _process_next_task_in_queue(self) -> None:  # pragma: no cover
        """
        Processes the next task in the task queue and manages task execution state.

        This method checks the current state of task execution and decides whether
        to process the next task, update the UI, or finish task execution. If there
        are no tasks in the queue, it resets the state and updates the user
        interface to indicate that all tasks are complete. If a task is available,
        it updates the state, initializes the interactive pane, and begins the task
        execution process using the provided function.

        Attributes
        ----------
        is_task_running : bool
            Indicates whether a task is currently running.
        task_queue : list of tuple
            A queue of tasks to be executed. Each task is a tuple containing
            the tag (str), description (str), and the function to execute.
        current_task_info : dict or None
            Stores information about the currently running task. Contains 'tag'
            (str) and 'desc' (str) keys.
        footer_text : urwid.Text
            UI component representing the footer text area.
        log_display : object
            UI component used to display log messages.
        main_menu_listbox : urwid.ListBox
            Listbox widget representing the main menu items.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
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

    def _show_rerun_dialog_from_worker(
        self, _loop=None, _data=None
    ) -> None:  # pragma: no cover
        """
        Handles the presentation and interaction of a confirmation dialog from a background
        worker process. This function is responsible for bringing up a Yes/No dialog
        to the interface, managing user response, and updating the state based on
        the user's decision. It ensures that the dialog is shown only if a valid
        prompt message exists, otherwise logs an error and handles fallback states.

        Parameters:
            _loop: optional
                An event loop instance used for any asynchronous operations, if applicable.
            _data: optional
                Arbitrary data payload that may be processed during the function call.

        Raises:
            None

        Returns:
            None
        """
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
        """
        Handles the logic for prompting the user about a rerun operation in a threaded
        context. If this method is called from the main thread, it directly triggers
        a textual user interface (TUI) prompt for a rerun decision. However, when called
        from a worker thread, it schedules a dialog event in the main thread for user
        interaction and waits for the result.

        Parameters:
            prompt_message: str
                The message to display as the prompt for the rerun decision.
            settings: AppSettings
                The application settings used to determine operational settings or
                configurations.
            logger_instance: Optional[logging.Logger]
                A specific logger instance to record warnings or events. If no logger is
                provided, a module-level logger will be used.

        Returns:
            bool
                A boolean indicating whether the user has opted for a rerun operation
                (True) or not (False).
        """
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

    def show_main_menu(self, button: Optional[urwid.Button] = None) -> None:
        """
        Displays the main menu of the application.

        This method is responsible for rendering the main menu in the interactive
        pane of the user interface. It checks if any task is running before attempting
        to display the menu to avoid interruptions. If a task is in progress, a warning
        message is added to the log display. When the menu is successfully displayed,
        navigation instructions are provided in the footer.

        Parameters
        ----------
        button : Optional[urwid.Button], optional
            The button triggering this action, default is None.
        """
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
        """
        Displays the application's current configuration in the log display.

        This method allows the user to view the current configuration settings of the
        application. If there is a task in progress, the configuration settings will not
        be displayed, and a warning will be logged instead. Configuration details such as
        the admin group IP, GTFS feed URL, and VM domain are displayed. In case of errors
        or missing configuration attributes, appropriate error messages are logged.

        Parameters:
            button: urwid.Button, optional
                A button object that triggers this method. Defaults to None.

        Returns:
            None
        """
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
        """
        Displays and manages the current state information and logs. This function handles
        displaying both completed steps along with associated messages or warnings. If a task
        is in progress, it logs a corresponding warning and prevents further state management
        to ensure data consistency. Additionally, errors during state inspection are caught,
        logged, and displayed.

        Parameters:
            button (Optional[urwid.Button]): The button triggering the state management
            display. This is optional and defaults to None.

        Raises:
            Exception: Logs an error message and exception details if there is an issue
            while viewing the state information.

        Returns:
            None
        """
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

    def run_full_installation(
        self, button: Optional[urwid.Button] = None
    ) -> None:  # pragma: no cover
        """
        Queues and executes a full installation sequence. The process is executed
        through a sequence of tasks. If tasks are already in progress, a warning
        is displayed, and no further actions are initiated. Before starting the
        execution, this function clears any previously displayed logs and adds
        a header indicating the initiation of the full installation. Also, if no
        tasks are defined, it updates the interactive pane and logs a warning.

        Parameters:
            button (Optional[urwid.Button]): A button that may trigger the
                installation process. Defaults to None.

        Returns:
            None
        """
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
        """
        Handles the display and interaction for step selection in a user interface, allowing
        users to select tasks or steps to be executed. If tasks are already in progress or
        no tasks are defined, appropriate messages are displayed and options are limited.
        Enables selection via a checklist UI and processes selected steps for execution.

        Parameters
        ----------
        button : Optional[urwid.Button], optional
            A button triggering the function, by default None

        Returns
        -------
        None

        Raises
        ------
        Does not explicitly raise any exceptions, but depends on error handling in
        UI or callback functions.
        """
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

    def tui_prompt_for_rerun(
        self, prompt_message: str
    ) -> bool:  # pragma: no cover
        """
        Prompts the user with a confirmation dialog for rerunning an operation using a
        text-based user interface (TUI).

        This method creates a temporary main loop to display a confirmation dialog
        and waits for the user's response. It ensures that the prompt operation is
        performed on the main thread and logs an error if called from a non-main
        thread.

        Attributes
        ----------
        main_loop : urwid.MainLoop
            The main event loop of the TUI application. The method temporarily replaces
            the main widget for UI interaction.

        Methods
        -------
        tui_prompt_for_rerun(self, prompt_message: str) -> bool
            Displays a confirmation dialog with the provided prompt message and returns
            the user's response as a boolean value.

        Parameters
        ----------
        prompt_message : str
            The prompt message shown within the confirmation dialog.

        Returns
        -------
        bool
            Returns True if the user confirms with "Yes"; False otherwise. If an error
            occurs or the result is unavailable, it defaults to False.
        """
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
        """
        Executes a step in the installer process within a separate thread.

        This method is used to initiate and execute a specific installer step by
        creating a new thread. The step is identified by a tag and description,
        and its execution logic is encapsulated within a function.

        Parameters:
            tag (str): A string representing the unique identifier of the installer step.
            desc (str): A descriptive string providing information about the step's purpose.
            func (StepFunctionType): The function containing the logic of the installer
                step being executed.

        Raises:
            This method does not explicitly raise exceptions, but exceptions raised
            within the specified step function should be handled appropriately.

        Returns:
            None
        """
        self._active_worker_thread = threading.Thread(
            target=self._task_runner, args=(tag, desc, func), daemon=True
        )
        self._active_worker_thread.start()

    def confirm_exit_dialog(
        self, button: Optional[urwid.Button] = None
    ) -> None:  # pragma: no cover
        """
        Displays a confirmation dialog to the user, asking if they are sure they want
        to quit the application. If a task is currently running, the dialog's message
        will warn the user about the active task. Handles the user's response to the
        dialog and either terminates the application or resumes it based on the input.

        Parameters:
            button (Optional[urwid.Button]): Optional button parameter that triggers
                the dialog. Defaults to None.

        Raises:
            urwid.ExitMainLoop: Raised if the user confirms the exit action by
                interacting with the dialog.
        """
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
        """
        Runs the Text User Interface (TUI) main loop, initializing logging mechanisms
        and ensuring proper setup and cleanup of the logging configuration to integrate
        with the TUI interface. This method manages logging handlers and levels to properly
        route log messages to the TUI display while preserving the original logging configuration.

        Attributes:
            tui_log_handler: An instance of TuiLogHandler to handle and display logs within the TUI.
            _original_root_logger_level: The original logging level of the root logger prior to TUI setup.
            _original_root_handlers: A list of the original handlers attached to the root logger.
            _removed_handlers_by_tui: A list to store temporarily removed handlers during TUI execution.
            _root_logger_level_modified_by_tui: A boolean indicating if the root logger's level was
                modified during TUI execution.

        Raises:
            urwid.ExitMainLoop: Raised to indicate a normal exit of the TUI.
            Exception: Any unhandled exceptions in the TUI main loop are logged and handled here.
        """
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
    """
    Run the Text User Interface (TUI) installer to execute a series of defined tasks for application installation or
    configuration. This function creates and runs an instance of a TUI installer, which orchestrates the process of
    executing a sequence of tasks defined by the user.

    Parameters:
        defined_tasks: List of tuples where each tuple contains a task label (str), a task description (str),
                       and a callable of type StepFunctionType to execute the task.
        app_settings: An instance of the AppSettings class containing configuration settings for the installer.

    Returns:
        None
    """
    app = InstallerTUI(
        defined_tasks=defined_tasks, app_settings_instance=app_settings
    )
    app.run()


if __name__ == "__main__":  # pragma: no cover
    print("Running TUI in standalone test mode...", file=sys.stderr)
    if not logging.getLogger().handlers:
        # Import and use the central logging setup function
        from common.core_utils import setup_logging

        setup_logging(
            log_level=logging.DEBUG,
            log_to_console=True,
            log_format_str="[TUI-STANDALONE-TEST] %(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        module_logger.info(
            "TUI __main__: Logging configured for standalone test using central setup_logging function."
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
