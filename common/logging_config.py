# -*- coding: utf-8 -*-
"""
Centralized logging configuration for Open Journey Server.

This module provides structured, centralized logging capabilities for all services
in the Open Journey Server ecosystem. It implements JSON-structured logging with
consistent formatting and metadata across all components.

Features:
- JSON-structured logging for easy parsing by Loki
- Consistent log formatting across all services
- Service identification and metadata
- Environment-aware configuration
- Performance-optimized logging
"""

import json
import logging
import logging.config
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.

    Formats log records as JSON with consistent structure including:
    - timestamp (ISO format)
    - level
    - service name
    - message
    - additional metadata
    """

    def __init__(self, service_name: str = "openjourney-server"):
        super().__init__()
        self.service_name = service_name
        self.hostname = os.environ.get("HOSTNAME", "unknown")
        self.pod_name = os.environ.get("POD_NAME", "unknown")
        self.namespace = os.environ.get("POD_NAMESPACE", "default")

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat()
            + "Z",
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "process": record.process,
            "hostname": self.hostname,
            "pod_name": self.pod_name,
            "namespace": self.namespace,
        }

        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields from the log record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
                "exc_info",
                "exc_text",
                "stack_info",
            ]:
                extra_fields[key] = value

        if extra_fields:
            log_entry["extra"] = extra_fields

        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(
    service_name: str,
    log_level: Optional[str] = None,
    enable_console: bool = True,
    enable_file: bool = False,
    log_file_path: Optional[str] = None,
) -> logging.Logger:
    """
    Set up centralized logging for a service.

    Args:
        service_name: Name of the service (e.g., "gtfs-processor", "nginx")
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_console: Whether to enable console logging
        enable_file: Whether to enable file logging
        log_file_path: Path to log file (if file logging enabled)

    Returns:
        Configured logger instance
    """
    # Determine log level from environment or parameter
    if log_level is None:
        log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    # Validate log level
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
        log_level = "INFO"

    # Create formatters
    json_formatter = JSONFormatter(service_name)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler if enabled
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)

        # Use JSON format in Kubernetes, human-readable format locally
        if os.environ.get("KUBERNETES_SERVICE_HOST"):
            console_handler.setFormatter(json_formatter)
        else:
            console_handler.setFormatter(console_formatter)

        root_logger.addHandler(console_handler)

    # Add file handler if enabled
    if enable_file and log_file_path:
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(json_formatter)
        root_logger.addHandler(file_handler)

    # Create service-specific logger
    logger = logging.getLogger(service_name)

    # Log startup information
    logger.info(
        "Logging initialized",
        extra={
            "log_level": log_level,
            "service": service_name,
            "console_enabled": enable_console,
            "file_enabled": enable_file,
            "kubernetes": bool(os.environ.get("KUBERNETES_SERVICE_HOST")),
        },
    )

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.

    This should be used after setup_logging() has been called.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def log_performance(func):
    """
    Decorator to log function performance metrics.

    Usage:
        @log_performance
        def my_function():
            pass
    """

    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(
                f"Function {func.__name__} completed successfully",
                extra={
                    "function": func.__name__,
                    "duration_seconds": round(duration, 3),
                    "status": "success",
                },
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Function {func.__name__} failed",
                extra={
                    "function": func.__name__,
                    "duration_seconds": round(duration, 3),
                    "status": "error",
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    return wrapper


def log_database_operation(
    operation: str, table: Optional[str] = None, count: Optional[int] = None
):
    """
    Log database operations with consistent metadata.

    Args:
        operation: Type of operation (SELECT, INSERT, UPDATE, DELETE)
        table: Database table name
        count: Number of records affected
    """
    logger = logging.getLogger("database")
    logger.info(
        f"Database operation: {operation}",
        extra={
            "operation": operation,
            "table": table,
            "record_count": count,
            "component": "database",
        },
    )


def log_api_request(
    method: str, path: str, status_code: int, duration: float
):
    """
    Log API requests with consistent metadata.

    Args:
        method: HTTP method
        path: Request path
        status_code: HTTP status code
        duration: Request duration in seconds
    """
    logger = logging.getLogger("api")
    logger.info(
        f"API request: {method} {path}",
        extra={
            "http_method": method,
            "http_path": path,
            "http_status": status_code,
            "duration_seconds": round(duration, 3),
            "component": "api",
        },
    )


# Configuration for different environments
LOGGING_CONFIGS: Dict[str, Dict[str, Any]] = {
    "development": {
        "log_level": "DEBUG",
        "enable_console": True,
        "enable_file": True,
    },
    "production": {
        "log_level": "INFO",
        "enable_console": True,
        "enable_file": False,
    },
    "testing": {
        "log_level": "WARNING",
        "enable_console": False,
        "enable_file": False,
    },
}


def setup_service_logging(
    service_name: str, environment: Optional[str] = None
) -> logging.Logger:
    """
    Convenience function to set up logging for a service with environment-specific defaults.

    Args:
        service_name: Name of the service
        environment: Environment name (development, production, testing)

    Returns:
        Configured logger instance
    """
    if environment is None:
        environment = os.environ.get("ENVIRONMENT", "development")

    config = LOGGING_CONFIGS.get(environment, LOGGING_CONFIGS["development"])

    return setup_logging(
        service_name=service_name,
        log_level=config["log_level"],
        enable_console=config["enable_console"],
        enable_file=config["enable_file"],
    )
