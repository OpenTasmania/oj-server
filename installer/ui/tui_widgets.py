# ui/tui_widgets.py
# -*- coding: utf-8 -*-
"""
Custom Urwid widget components for the TUI.
"""

from typing import Optional, Tuple

import urwid  # type: ignore[import-untyped]


class LogDisplay(urwid.WidgetWrap):
    """
    LogDisplay is a GUI widget for displaying and managing log messages in a dynamic
    list format.

    This class wraps urwid widget functionality to provide a custom list-based display
    for log entries. Each log entry is styled based on its severity level and appended
    to the list. The widget also supports clearing all logged messages at once.

    Attributes:
        log_lines (urwid.SimpleFocusListWalker): The data container for storing the
            list of log message widgets.
        list_box (urwid.ListBox): The UI component that displays the log lines.
    """

    def __init__(self) -> None:
        """
        A class inheriting from a UI container that displays logs in a scrollable box.

        Attributes:
            log_lines (urwid.SimpleFocusListWalker): A focusable list walker to store
                and navigate through log entries.
            list_box (urwid.ListBox): A ListBox widget that contains and displays
                log entries on the UI.

        """
        self.log_lines = urwid.SimpleFocusListWalker([])
        self.list_box = urwid.ListBox(self.log_lines)
        super().__init__(urwid.LineBox(self.list_box, title="Logs"))

    def add_message(self, message: str, level: str = "info") -> None:
        """
        Adds a formatted message to the log lines and updates the focus
        of the list box to the latest message.

        Parameters
        ----------
        message : str
            The log message to be added to the log lines.
        level : str, optional
            The logging level for the message, default is "info".

        Raises
        ------
        None

        Returns
        -------
        None
        """
        attr_map_key = f"log_{level.lower()}"
        styled_text_widget = urwid.AttrMap(
            urwid.Text(message), attr_map_key, focus_map="body"
        )
        self.log_lines.append(styled_text_widget)
        if self.log_lines:  # pragma: no branch
            self.list_box.set_focus(len(self.log_lines) - 1)

    def clear_logs(self) -> None:
        """
        Clears all the log lines maintained by the instance.

        This method resets the internal storage for log lines, removing
        all previously logged entries from the collection.

        Returns:
            None
        """
        self.log_lines.clear()


class YesNoDialog(urwid.WidgetWrap):
    """
    Represents a Yes/No dialog widget in a UI.

    This class is a customizable dialog comprising title text, a message text, and
    two buttons labeled "Yes" and "No". It is designed for use with the urwid
    library and emits signals when either button is pressed or the escape key is
    used. The dialog is typically used in UI workflows to capture yes/no decisions
    from the user or to confirm specific actions.

    Attributes:
        signals (List[str]): A list of strings representing event signals emitted by
            the dialog. Includes "close_yes" for the Yes button and "close_no" for
            the No button.
    """

    signals = ["close_yes", "close_no"]

    def __init__(self, title_text: str, message_text: str):
        """
        Handles the creation and initialization of a dialog box interface with a message,
        title, and Yes/No buttons.

        This class inherits from another component and configures the layout to display
        text-based dialog boxes for user interaction. It includes title and message
        widgets aligned and styled accordingly, as well as button controls for user input.

        Attributes:
            title_text (str): Text to be displayed in the dialog's title.
            message_text (str): Text to be displayed in the body of the dialog.

        Parameters:
            title_text: str
                The text to display as the dialog's title.
            message_text: str
                The text to display as the dialog's main content.

        Raises:
            None
        """
        title_widget = urwid.Text(("dialog_text", title_text), align="center")
        message_widget = urwid.Text(
            ("dialog_text", message_text), align="center"
        )
        yes_button = urwid.AttrMap(
            urwid.Button("Yes", self._on_yes),
            "dialog_button",
            focus_map="dialog_button_focus",
        )
        no_button = urwid.AttrMap(
            urwid.Button("No", self._on_no),
            "dialog_button",
            focus_map="dialog_button_focus",
        )
        buttons = urwid.GridFlow(
            [yes_button, no_button],
            cell_width=10,
            h_sep=2,
            v_sep=1,
            align="center",
        )
        content = urwid.Pile([
            urwid.Divider(),
            message_widget,
            urwid.Divider(),
            buttons,
            urwid.Divider(),
        ])
        line_box = urwid.LineBox(
            urwid.Padding(content, left=2, right=2), title=title_widget
        )
        super().__init__(urwid.AttrMap(line_box, "dialog_bg"))

    def _on_yes(self, button: urwid.Button) -> None:
        """
        Handles the event triggered when the "yes" button is pressed.

        This method is invoked when the "yes" button is clicked. It emits a signal
        indicating the user's confirmation action.

        Args:
            button (urwid.Button): The "yes" button that was pressed.

        Returns:
            None
        """
        self._emit("close_yes")

    def _on_no(self, button: Optional[urwid.Button]) -> None:
        """
        Handles the user's selection of "No" in a dialog or menu.

        This private method is triggered when the "No" button is pressed by the
        user. It emits the "close_no" event, which can be used to handle the
        specific behavior for this selection in the application.

        Parameters:
            button (Optional[urwid.Button]): The button instance that triggered
            the event, if any.

        Returns:
            None
        """
        self._emit("close_no")

    def keypress(self, size: Tuple[int, int], key: str) -> Optional[str]:
        """
        Handles keypress events for the widget and invokes appropriate actions based on
        the key pressed. This includes handling specific keys like "esc" and delegating
        other key events to the superclass for further processing.

        Args:
            size (Tuple[int, int]): The size of the widget, represented as a tuple
                specifying width and height.
            key (str): The key that was pressed, represented as a string.

        Returns:
            Optional[str]: Returns the result of the superclass keypress method if the
                key is not "esc", otherwise returns None.
        """
        if key == "esc":  # pragma: no cover
            self._on_no(None)
            return None
        return super().keypress(size, key)  # type: ignore[no-any-return]
