"""
Prometheus metrics collection for Open Journey Server.

This module provides centralized metrics collection for all Open Journey Server
components including the static ETL pipeline and GTFS daemon.
"""

import logging
from typing import Optional

from prometheus_client import (
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    start_http_server,
)

logger = logging.getLogger(__name__)


class OpenJourneyMetrics:
    """Centralized metrics collection for Open Journey Server."""

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """Initialize metrics collectors.

        Args:
            registry: Optional custom registry. Uses default if None.
        """
        self.registry = registry or REGISTRY

        # Static ETL Pipeline Metrics
        self.etl_feeds_processed = Counter(
            "openjourney_etl_feeds_processed_total",
            "Total number of feeds processed by the ETL pipeline",
            ["status", "feed_type"],
            registry=self.registry,
        )

        self.etl_processing_duration = Histogram(
            "openjourney_etl_processing_duration_seconds",
            "Time spent processing feeds in the ETL pipeline",
            ["feed_name", "feed_type"],
            registry=self.registry,
        )

        self.etl_records_processed = Counter(
            "openjourney_etl_records_processed_total",
            "Total number of records processed by the ETL pipeline",
            ["feed_name", "record_type"],
            registry=self.registry,
        )

        self.etl_processor_load_duration = Histogram(
            "openjourney_etl_processor_load_duration_seconds",
            "Time spent loading processors in the ETL pipeline",
            ["processor_type"],
            registry=self.registry,
        )

        self.etl_errors = Counter(
            "openjourney_etl_errors_total",
            "Total number of errors in the ETL pipeline",
            ["error_type", "feed_name"],
            registry=self.registry,
        )

        # GTFS Daemon Metrics
        self.gtfs_feeds_processed = Counter(
            "openjourney_gtfs_feeds_processed_total",
            "Total number of GTFS feeds processed by the daemon",
            ["status", "feed_name"],
            registry=self.registry,
        )

        self.gtfs_download_duration = Histogram(
            "openjourney_gtfs_download_duration_seconds",
            "Time spent downloading GTFS feeds",
            ["feed_name"],
            registry=self.registry,
        )

        self.gtfs_conversion_duration = Histogram(
            "openjourney_gtfs_conversion_duration_seconds",
            "Time spent converting GTFS data to OpenJourney format",
            ["feed_name"],
            registry=self.registry,
        )

        self.gtfs_database_operations = Counter(
            "openjourney_gtfs_database_operations_total",
            "Total number of database operations performed by GTFS daemon",
            ["operation_type", "status"],
            registry=self.registry,
        )

        self.gtfs_retry_attempts = Counter(
            "openjourney_gtfs_retry_attempts_total",
            "Total number of retry attempts for GTFS feed processing",
            ["feed_name", "retry_reason"],
            registry=self.registry,
        )

        self.gtfs_active_feeds = Gauge(
            "openjourney_gtfs_active_feeds",
            "Number of currently active GTFS feeds being processed",
            registry=self.registry,
        )

        # System-wide metrics
        self.system_info = Info(
            "openjourney_system_info",
            "System information for Open Journey Server",
            registry=self.registry,
        )

        # Set system info
        self.system_info.info({
            "version": "0.9.0",
            "component": "openjourney_server",
        })

        logger.info("OpenJourney metrics initialized")

    def record_etl_feed_processed(self, status: str, feed_type: str):
        """Record a processed feed in the ETL pipeline."""
        self.etl_feeds_processed.labels(
            status=status, feed_type=feed_type
        ).inc()

    def record_etl_processing_time(
        self, feed_name: str, feed_type: str, duration: float
    ):
        """Record processing time for an ETL feed."""
        self.etl_processing_duration.labels(
            feed_name=feed_name, feed_type=feed_type
        ).observe(duration)

    def record_etl_records_processed(
        self, feed_name: str, record_type: str, count: int
    ):
        """Record number of records processed."""
        self.etl_records_processed.labels(
            feed_name=feed_name, record_type=record_type
        ).inc(count)

    def record_etl_processor_load_time(
        self, processor_type: str, duration: float
    ):
        """Record processor loading time."""
        self.etl_processor_load_duration.labels(
            processor_type=processor_type
        ).observe(duration)

    def record_etl_error(self, error_type: str, feed_name: str):
        """Record an error in the ETL pipeline."""
        self.etl_errors.labels(
            error_type=error_type, feed_name=feed_name
        ).inc()

    def record_gtfs_feed_processed(self, status: str, feed_name: str):
        """Record a processed GTFS feed."""
        self.gtfs_feeds_processed.labels(
            status=status, feed_name=feed_name
        ).inc()

    def record_gtfs_download_time(self, feed_name: str, duration: float):
        """Record GTFS feed download time."""
        self.gtfs_download_duration.labels(feed_name=feed_name).observe(
            duration
        )

    def record_gtfs_conversion_time(self, feed_name: str, duration: float):
        """Record GTFS conversion time."""
        self.gtfs_conversion_duration.labels(feed_name=feed_name).observe(
            duration
        )

    def record_gtfs_database_operation(
        self, operation_type: str, status: str
    ):
        """Record a database operation."""
        self.gtfs_database_operations.labels(
            operation_type=operation_type, status=status
        ).inc()

    def record_gtfs_retry_attempt(self, feed_name: str, retry_reason: str):
        """Record a retry attempt."""
        self.gtfs_retry_attempts.labels(
            feed_name=feed_name, retry_reason=retry_reason
        ).inc()

    def set_gtfs_active_feeds(self, count: int):
        """Set the number of active GTFS feeds."""
        self.gtfs_active_feeds.set(count)


# Global metrics instance
_metrics_instance: Optional[OpenJourneyMetrics] = None


def get_metrics() -> OpenJourneyMetrics:
    """Get the global metrics instance."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = OpenJourneyMetrics()
    return _metrics_instance


def start_metrics_server(port: int = 8000, addr: str = "0.0.0.0"):
    """Start the Prometheus metrics HTTP server.

    Args:
        port: Port to serve metrics on
        addr: Address to bind to
    """
    try:
        start_http_server(port, addr)
        logger.info(f"Prometheus metrics server started on {addr}:{port}")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")
        raise


def initialize_metrics() -> OpenJourneyMetrics:
    """Initialize and return the global metrics instance."""
    return get_metrics()
