import os
import tempfile
from pathlib import Path

import pytest

from common.json_utils import JsonFileType, check_json_file


def test_check_json_file_valid_json():
    """Test 'check_json_file' with a valid JSON file."""
    with tempfile.NamedTemporaryFile(
        delete=False, mode="w", suffix=".json"
    ) as temp_file:
        temp_file.write('{"key": "value"}')
    try:
        result = check_json_file(Path(temp_file.name))
        assert result == JsonFileType.VALID_JSON, (
            f"Expected VALID_JSON, got {result}"
        )
    finally:
        os.unlink(temp_file.name)


def test_check_json_file_malformed_json():
    """Test 'check_json_file' with a malformed JSON file."""
    with tempfile.NamedTemporaryFile(
        delete=False, mode="w", suffix=".json"
    ) as temp_file:
        temp_file.write('{"key": "value"')
    try:
        result = check_json_file(Path(temp_file.name))
        assert result == JsonFileType.MALFORMED_JSON, (
            f"Expected MALFORMED_JSON, got {result}"
        )
    finally:
        os.unlink(temp_file.name)


def test_check_json_file_not_json():
    """Test 'check_json_file' with a non-JSON file."""
    with tempfile.NamedTemporaryFile(
        delete=False, mode="w", suffix=".txt"
    ) as temp_file:
        temp_file.write("This is not JSON content.")
    try:
        result = check_json_file(Path(temp_file.name))
        assert result == JsonFileType.NOT_JSON, (
            f"Expected NOT_JSON, got {result}"
        )
    finally:
        os.unlink(temp_file.name)


def test_check_json_file_non_existent_path():
    """Test 'check_json_file' with a non-existent file path."""
    non_existent_path = Path("non_existent_file.json")
    result = check_json_file(non_existent_path)
    assert result == JsonFileType.NOT_JSON, (
        f"Expected NOT_JSON for non-existent file, got {result}"
    )


def test_json_file_type_valid_json():
    """Test if the VALID_JSON enum value is correct."""
    assert JsonFileType.VALID_JSON.value == "VALID_JSON", (
        f"Expected VALID_JSON value to be 'VALID_JSON', "
        f"but got '{JsonFileType.VALID_JSON.value}'"
    )


def test_json_file_type_malformed_json():
    """Test if the MALFORMED_JSON enum value is correct."""
    assert JsonFileType.MALFORMED_JSON.value == "MALFORMED_JSON", (
        f"Expected MALFORMED_JSON value to be 'MALFORMED_JSON', "
        f"but got '{JsonFileType.MALFORMED_JSON.value}'"
    )


def test_json_file_type_not_json():
    """Test if the NOT_JSON enum value is correct."""
    assert JsonFileType.NOT_JSON.value == "NOT_JSON", (
        f"Expected NOT_JSON value to be 'NOT_JSON', "
        f"but got '{JsonFileType.NOT_JSON.value}'"
    )


@pytest.mark.parametrize(
    "input_value, expected",
    [
        (JsonFileType.VALID_JSON, "VALID_JSON"),
        (JsonFileType.MALFORMED_JSON, "MALFORMED_JSON"),
        (JsonFileType.NOT_JSON, "NOT_JSON"),
    ],
)
def test_enum_values(input_value, expected):
    """Test all enum values in JsonFileType."""
    assert input_value.value == expected, (
        f"Expected enum value to be '{expected}', but got '{input_value.value}'"
    )
