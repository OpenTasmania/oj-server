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
    Determines the type of a JSON file by attempting to parse it.

    This function reads a file and checks if it contains valid JSON. It distinguishes
    between valid JSON, malformed JSON, and files that are not JSON at all, such as
    binary files or files that cannot be read due to permissions or other errors.

    Parameters:
    file_path: Path
        The path to the file to be checked.

    Returns:
    JsonFileType
        Returns JsonFileType.VALID_JSON if the file contains valid JSON,
        JsonFileType.MALFORMED_JSON if the file contains invalid JSON,
        or JsonFileType.NOT_JSON if the file is not readable, is binary,
        or is not JSON.

    Raises:
    None
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            json.load(f)
        return JsonFileType.VALID_JSON
    except json.JSONDecodeError:
        return JsonFileType.MALFORMED_JSON
    except (IOError, OSError, UnicodeDecodeError):
        return JsonFileType.NOT_JSON
