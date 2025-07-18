# -*- coding: utf-8 -*-
"""
ProcessorInterface - Abstract base class for all static data processors

This module defines the formal interface that all static data processors must implement.
This enables a pluggable architecture where different data sourcescan be processed uniformly.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from .logging_config import (
    get_logger,
    setup_service_logging,
)


class ProcessorInterface(ABC):
    """
    Interface for ETL processors defining standard methods for data extraction, transformation,
    and loading.

    This class provides an abstract blueprint for implementing ETL (Extract, Transform, Load)
    processors. Subclasses are required to implement specific methods for extracting data from
    various sources, transforming raw data into a structured format, and loading it into a database
    or another destination. It also includes a processing pipeline that orchestrates the ETL process
    and additional utility functions such as validation and cleanup.
    """

    def __init__(self, db_config: Dict[str, Any]):
        """
        Initialize the processor with database configuration.

        Args:
            db_config: Database connection configuration dictionary
        """
        self.db_config = db_config
        # Set up centralized logging for this processor
        setup_service_logging(self.__class__.__name__)
        self.logger = get_logger(self.__class__.__name__)

    @property
    @abstractmethod
    def processor_name(self) -> str:
        """
        This abstract property represents the name of the processor. It is intended to be
        implemented by subclasses to specify the name of the processor being used or
        defined.

        Returns:
            str: The name of the processor.
        """
        pass

    @property
    @abstractmethod
    def supported_formats(self) -> List[str]:
        """
        Property to retrieve the list of supported formats.

        This property is an abstract method that must be implemented by any subclass.
        It specifies the supported formats in the form of a list of strings.

        Returns:
            List[str]: A list of supported formats as strings.
        """
        pass

    @abstractmethod
    def extract(self, source_path: Path, **kwargs) -> Dict[str, Any]:
        """
        Extract data from the source file/directory.

        Args:
            source_path: Path to the source data file or directory
            **kwargs: Additional extraction parameters

        Returns:
            Dictionary containing extracted raw data

        Raises:
            ProcessorError: If extraction fails
        """
        pass

    @abstractmethod
    def transform(
        self, raw_data: Dict[str, Any], source_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform raw data into canonical format.

        Args:
            raw_data: Raw data from extract phase
            source_info: Information about the data source (agency, URL, etc.)

        Returns:
            Dictionary containing transformed data ready for loading

        Raises:
            ProcessorError: If transformation fails
        """
        pass

    @abstractmethod
    def load(self, transformed_data: Dict[str, Any]) -> bool:
        """
        Load transformed data into the canonical database schema.

        Args:
            transformed_data: Data from transform phase

        Returns:
            True if load was successful, False otherwise

        Raises:
            ProcessorError: If loading fails
        """
        pass

    def process(
        self, source_path: Path, source_info: Dict[str, Any], **kwargs
    ) -> bool:
        """
        Execute the complete ETL pipeline.

        Args:
            source_path: Path to the source data
            source_info: Information about the data source
            **kwargs: Additional processing parameters

        Returns:
            True if processing was successful, False otherwise
        """
        try:
            self.logger.info(
                f"Starting {self.processor_name} processing for {source_path}"
            )

            # Extract
            self.logger.info("Extracting data...")
            raw_data = self.extract(source_path, **kwargs)

            # Transform
            self.logger.info("Transforming data...")
            transformed_data = self.transform(raw_data, source_info)

            # Load
            self.logger.info("Loading data...")
            success = self.load(transformed_data)

            if success:
                self.logger.info(
                    f"{self.processor_name} processing completed successfully"
                )
            else:
                self.logger.error(
                    f"{self.processor_name} processing failed during load phase"
                )

            return success

        except Exception as e:
            self.logger.error(
                f"{self.processor_name} processing failed: {str(e)}"
            )
            return False

    @abstractmethod
    def validate_source(self, source_path: Path) -> bool:
        """
        Validate that the source data is compatible with this processor.

        Args:
            source_path: Path to the source data

        Returns:
            True if source is valid for this processor, False otherwise
        """
        pass

    def get_source_info(self, source_path: Path) -> Dict[str, Any]:
        """
        Extract basic information about the data source.

        Args:
            source_path: Path to the source data

        Returns:
            Dictionary with source information (can be overridden by subclasses)
        """
        return {
            "source_path": str(source_path),
            "processor": self.processor_name,
            "file_size": source_path.stat().st_size
            if source_path.exists()
            else 0,
        }

    def cleanup(self, temp_files: List[Path]) -> None:
        """
        Clean up temporary files created during processing.

        Args:
            temp_files: List of temporary file paths to clean up
        """
        for temp_file in temp_files:
            try:
                if temp_file.exists():
                    if temp_file.is_dir():
                        import shutil

                        shutil.rmtree(temp_file)
                    else:
                        temp_file.unlink()
                    self.logger.debug(
                        f"Cleaned up temporary file: {temp_file}"
                    )
            except Exception as e:
                self.logger.warning(
                    f"Failed to clean up {temp_file}: {str(e)}"
                )


class ProcessorError(Exception):
    """
    Custom exception class to handle processor-specific errors.

    ProcessorError is used to encapsulate information about errors that occur
    during the execution of a specific processor. It includes the error message,
    the name of the processor where the error occurred (if applicable), and the
    original exception that may have triggered this error (if applicable).
    """

    def __init__(
        self,
        message: str,
        processor_name: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        self.processor_name = processor_name
        self.original_error = original_error
        super().__init__(message)


class ProcessorRegistry:
    """
    Registry for managing available processors.

    This class maintains a registry of all available processors and provides
    methods to find the appropriate processor for a given data source.
    """

    def __init__(self):
        self._processors: Dict[str, ProcessorInterface] = {}
        # Set up centralized logging for the registry
        setup_service_logging("ProcessorRegistry")
        self.logger = get_logger("ProcessorRegistry")

    def register(self, processor: ProcessorInterface) -> None:
        """
        Register a processor.

        Args:
            processor: Processor instance to register
        """
        name = processor.processor_name.lower()
        self._processors[name] = processor
        self.logger.info(f"Registered processor: {processor.processor_name}")

    def get_processor(self, name: str) -> Optional[ProcessorInterface]:
        """
        Get a processor by name.

        Args:
            name: Processor name (case-insensitive)

        Returns:
            Processor instance or None if not found
        """
        return self._processors.get(name.lower())

    def find_processor_for_source(
        self, source_path: Path
    ) -> Optional[ProcessorInterface]:
        """
        Find the appropriate processor for a given source file.

        Args:
            source_path: Path to the source data

        Returns:
            Processor instance that can handle the source, or None
        """
        for processor in self._processors.values():
            if processor.validate_source(source_path):
                return processor
        return None

    def list_processors(self) -> List[str]:
        """
        Get list of registered processor names.

        Returns:
            List of processor names
        """
        return list(self._processors.keys())

    def get_supported_formats(self) -> Dict[str, List[str]]:
        """
        Get supported formats for all processors.

        Returns:
            Dictionary mapping processor names to supported formats
        """
        return {
            name: processor.supported_formats
            for name, processor in self._processors.items()
        }


# Global processor registry instance
processor_registry = ProcessorRegistry()
