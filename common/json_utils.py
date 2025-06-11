# common/json_utils.py
# -*- coding: utf-8 -*-
"""
Utility functions for handling JSON files.
"""

import json
import logging
from enum import Enum
from pathlib import Path

module_logger = logging.getLogger(__name__)


class JsonFileType(Enum):
    """Enumeration for JSON file validation status."""

    VALID_JSON = "VALID_JSON"
    MALFORMED_JSON = "MALFORMED_JSON"
    NOT_JSON = "NOT_JSON"


def check_json_file(file_path: Path) -> JsonFileType:
    """
    Checks if a file is a valid, malformed, or not a JSON file by attempting to parse it.

    This function does not rely on the file extension.

    Args:
        file_path: The path to the file to check.

    Returns:
        A JsonFileType enum value indicating the status of the file.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            json.load(f)
        return JsonFileType.VALID_JSON
    except json.JSONDecodeError:
        return JsonFileType.MALFORMED_JSON
    except (IOError, OSError, UnicodeDecodeError):
        # Catches file read errors, permission errors, or if it's a binary file
        return JsonFileType.NOT_JSON
