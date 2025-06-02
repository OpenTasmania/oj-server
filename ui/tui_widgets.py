# ui/tui_widgets.py
# -*- coding: utf-8 -*-
"""
Custom Urwid widget components for the TUI.
"""

from typing import Optional, Tuple

import urwid  # type: ignore[import-untyped]

# --- UI Components ---


class LogDisplay(urwid.WidgetWrap):
    """A widget to display log messages in the TUI."""

    def __init__(self) -> None:
        self.log_lines = urwid.SimpleFocusListWalker([])
        self.list_box = urwid.ListBox(self.log_lines)
        # The palette reference here is indirect: AttrMap keys are resolved by the MainLoop's palette
        super().__init__(urwid.LineBox(self.list_box, title="Logs"))

    def add_message(self, message: str, level: str = "info") -> None:
        attr_map_key = f"log_{level.lower()}"
        # Check against a passed-in palette or assume keys exist in MainLoop's palette
        # For simplicity, assuming keys exist. The palette is set in InstallerTUI.
        styled_text_widget = urwid.AttrMap(
            urwid.Text(message), attr_map_key, focus_map="body"
        )  # Fallback to 'body' if key not in palette
        self.log_lines.append(styled_text_widget)
        if self.log_lines:  # pragma: no branch
            self.list_box.set_focus(len(self.log_lines) - 1)

    def clear_logs(self) -> None:
        self.log_lines.clear()


class YesNoDialog(urwid.WidgetWrap):
    """A modal dialog widget for Yes/No questions."""

    signals = ["close_yes", "close_no"]

    def __init__(self, title_text: str, message_text: str):
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
        self._emit("close_yes")

    def _on_no(self, button: Optional[urwid.Button]) -> None:
        self._emit("close_no")

    def keypress(self, size: Tuple[int, int], key: str) -> Optional[str]:
        if key == "esc":  # pragma: no cover
            self._on_no(None)
            return None
        # super().keypress is from urwid.WidgetWrap, which is untyped by MyPy
        return super().keypress(size, key)  # type: ignore[no-any-return]
