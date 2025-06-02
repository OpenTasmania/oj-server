# ui/tui_logging.py
# -*- coding: utf-8 -*-
"""
Logging handler for the TUI.
"""

import logging
import threading

import urwid  # type: ignore[import-untyped]

# Assuming tui_widgets.py is in the same directory (ui/)
from .tui_widgets import LogDisplay


class TuiLogHandler(logging.Handler):
    """A logging handler that directs messages to the Urwid LogDisplay."""

    def __init__(
        self, log_display_widget: LogDisplay, main_loop: urwid.MainLoop
    ):
        super().__init__()
        self.log_display_widget = log_display_widget
        self.main_loop: urwid.MainLoop = main_loop
        self.formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            level_name = record.levelname.lower()
            if threading.current_thread() is threading.main_thread():
                self.log_display_widget.add_message(msg, level=level_name)
            else:  # pragma: no cover
                # Ensure updates to Urwid widgets from other threads are scheduled via the main loop
                def _update_log_display_from_thread():
                    self.log_display_widget.add_message(msg, level=level_name)

                # Schedule the widget update on the main Urwid event loop
                self.main_loop.alarm(
                    0,
                    lambda _loop_unused,
                    _data_unused: _update_log_display_from_thread(),
                )  # type: ignore[attr-defined]
        except RecursionError:  # pragma: no cover
            # This can happen if logging is triggered from within logging itself under certain conditions
            raise
        except Exception:  # pragma: no cover
            # Fallback for any other unexpected errors during log emission
            self.handleError(record)
