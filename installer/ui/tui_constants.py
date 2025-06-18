# ui/tui_constants.py
# -*- coding: utf-8 -*-
"""
Constants and type aliases for the TUI.
"""

import logging
from typing import Callable, Optional

from installer.config_models import AppSettings

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

# Type alias for step functions expected by execute_step and TUI
StepFunctionType = Callable[[AppSettings, Optional[logging.Logger]], None]
