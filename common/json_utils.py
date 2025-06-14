import json
from enum import Enum
from pathlib import Path


class JsonFileType(str, Enum):
    """Enumeration for the different states of a JSON file check."""

    VALID_JSON = "VALID_JSON"
    MALFORMED_JSON = "MALFORMED_JSON"
    NOT_JSON = "NOT_JSON"


def check_json_file(file_path: Path) -> JsonFileType:
    """
    Checks if a file is a valid JSON, malformed JSON, or not a JSON file.

    The distinction between MALFORMED_JSON and NOT_JSON is made based on the
    file extension. A file with a .json extension that fails to parse is
    considered malformed. Any other file that fails to parse is considered
    not JSON.

    Args:
        file_path: The path to the file to check.

    Returns:
        The type of the file as a JsonFileType enum member.
    """
    if not file_path.is_file():
        return JsonFileType.NOT_JSON

    try:
        content = file_path.read_text(encoding="utf-8")
    except (IOError, UnicodeDecodeError):
        return JsonFileType.NOT_JSON

    try:
        json.loads(content)
        return JsonFileType.VALID_JSON
    except json.JSONDecodeError:
        if file_path.suffix.lower() == ".json":
            return JsonFileType.MALFORMED_JSON
        else:
            return JsonFileType.NOT_JSON
