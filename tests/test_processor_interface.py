# -*- coding: utf-8 -*-
from pathlib import Path
from unittest.mock import MagicMock

from common.processor_interface import ProcessorInterface


class MockProcessor(ProcessorInterface):
    """
    Mock class implementing ProcessorInterface for testing purposes.
    """

    @property
    def processor_name(self) -> str:
        return "MockProcessor"

    @property
    def supported_formats(self) -> list:
        return [".mock"]

    def extract(self, source_path: Path, **kwargs) -> dict:
        return {"mock_data": "data"}

    def transform(self, raw_data: dict, source_info: dict) -> dict:
        return {"transformed_data": "data"}

    def load(self, transformed_data: dict) -> bool:
        return True

    def validate_source(self, source_path: Path) -> bool:
        return source_path.suffix in self.supported_formats


def test_processor_name_property():
    """Test that processor_name property returns the correct name."""
    mock_processor = MockProcessor({})
    expected_name = "MockProcessor"
    assert mock_processor.processor_name == expected_name


def test_supported_formats_property():
    """Test that supported_formats property returns the correct formats."""
    mock_processor = MockProcessor({})
    expected_formats = [".mock"]
    assert mock_processor.supported_formats == expected_formats


def test_extract_method():
    """Test the extract method."""
    mock_processor = MockProcessor({})
    source_path = Path("test.mock")
    extracted_data = mock_processor.extract(source_path)
    expected_data = {"mock_data": "data"}
    assert extracted_data == expected_data


def test_transform_method():
    """Test the transform method."""
    mock_processor = MockProcessor({})
    raw_data = {"mock_data": "data"}
    source_info = {"info": "test"}
    transformed_data = mock_processor.transform(raw_data, source_info)
    expected_data = {"transformed_data": "data"}
    assert transformed_data == expected_data


def test_load_method():
    """Test the load method."""
    mock_processor = MockProcessor({})
    transformed_data = {"transformed_data": "data"}
    assert mock_processor.load(transformed_data) is True


def test_validate_source():
    """Test the validate_source method."""
    mock_processor = MockProcessor({})
    valid_source_path = Path("file.mock")
    invalid_source_path = Path("file.txt")
    assert mock_processor.validate_source(valid_source_path) is True
    assert mock_processor.validate_source(invalid_source_path) is False


def test_process_method():
    """Test the complete process method."""
    mock_processor = MockProcessor({})
    source_path = Path("source.mock")
    source_info = {"info": "test"}
    mock_processor.extract = MagicMock(return_value={"mock_data": "data"})
    mock_processor.transform = MagicMock(
        return_value={"transformed_data": "data"}
    )
    mock_processor.load = MagicMock(return_value=True)

    result = mock_processor.process(source_path, source_info)
    assert result is True
    mock_processor.extract.assert_called_once_with(source_path)
    mock_processor.transform.assert_called_once_with(
        {"mock_data": "data"}, source_info
    )
    mock_processor.load.assert_called_once_with({"transformed_data": "data"})


def test_get_source_info():
    """Test the get_source_info method."""
    mock_processor = MockProcessor({})
    source_path = Path("test.mock")
    source_path.stat = MagicMock(return_value=MagicMock(st_size=1024))
    expected_info = {
        "source_path": str(source_path),
        "processor": "MockProcessor",
        "file_size": 1024,
    }
    assert mock_processor.get_source_info(source_path) == expected_info


def test_cleanup():
    """Test the cleanup method."""
    mock_processor = MockProcessor({})
    temp_files = [Path("temp_file_1"), Path("temp_file_2")]
    for temp_file in temp_files:
        temp_file.exists = MagicMock(return_value=True)
        temp_file.is_dir = MagicMock(return_value=False)
        temp_file.unlink = MagicMock()

    mock_processor.cleanup(temp_files)

    for temp_file in temp_files:
        temp_file.exists.assert_called_once()
        temp_file.unlink.assert_called_once()
