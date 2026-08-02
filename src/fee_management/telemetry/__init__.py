"""Application Insights / OpenTelemetry configuration."""

from fee_management.telemetry.logging_setup import (
    get_logger,
    setup_logging,
    setup_observability,
    setup_telemetry,
)

__all__ = [
    "get_logger",
    "setup_logging",
    "setup_observability",
    "setup_telemetry",
]
