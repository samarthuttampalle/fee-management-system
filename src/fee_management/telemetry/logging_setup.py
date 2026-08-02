"""Application Insights / OpenTelemetry + structured logging setup (TDD §15)."""

from __future__ import annotations

import logging
import os
from typing import Any

from fee_management.telemetry.context import get_bound_correlation_id

_CONFIGURED = False
_TELEMETRY_CONFIGURED = False


class CorrelationIdFilter(logging.Filter):
    """Ensure every log record has ``correlation_id`` (for formatters / App Insights)."""

    def filter(self, record: logging.LogRecord) -> bool:
        existing = getattr(record, "correlation_id", None)
        if not existing:
            record.correlation_id = get_bound_correlation_id() or "-"
        return True


class CorrelationLoggerAdapter(logging.LoggerAdapter):
    """LoggerAdapter that injects the bound correlation_id into ``extra`` (§15.3)."""

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        extra = dict(kwargs.get("extra") or {})
        if "correlation_id" not in extra:
            bound = get_bound_correlation_id()
            if bound:
                extra["correlation_id"] = bound
            elif "correlation_id" in self.extra:
                extra["correlation_id"] = self.extra["correlation_id"]
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger(name: str) -> logging.LoggerAdapter:
    """Return a LoggerAdapter that always carries the request correlation id."""
    return CorrelationLoggerAdapter(logging.getLogger(name), {})


def setup_logging(*, level: str | None = None) -> None:
    """
    Configure root logging once: correlation filter + readable local format.

    Safe to call multiple times (idempotent). Does not wipe handlers already
    installed by the Azure Functions host.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    resolved = (level or os.environ.get("LOG_LEVEL") or "INFO").upper()
    root = logging.getLogger()
    root.setLevel(resolved)

    correlation_filter = CorrelationIdFilter()
    if not any(isinstance(f, CorrelationIdFilter) for f in root.filters):
        root.addFilter(correlation_filter)

    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s %(levelname)s [correlation_id=%(correlation_id)s] "
            "%(name)s - %(message)s"
        ),
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(resolved)
        handler.setFormatter(formatter)
        handler.addFilter(CorrelationIdFilter())
        root.addHandler(handler)
    else:
        for handler in root.handlers:
            if not any(isinstance(f, CorrelationIdFilter) for f in handler.filters):
                handler.addFilter(CorrelationIdFilter())
            # Prefer our format when the handler has no formatter yet.
            if handler.formatter is None:
                handler.setFormatter(formatter)

    _CONFIGURED = True


def setup_telemetry(*, connection_string: str | None = None) -> bool:
    """
    Configure Azure Monitor OpenTelemetry when a connection string is present (§15.1).

    Returns True if App Insights was configured, False if skipped (local default).
    """
    global _TELEMETRY_CONFIGURED
    if _TELEMETRY_CONFIGURED:
        return True

    conn = connection_string or os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING") or ""
    conn = conn.strip()
    if not conn:
        logging.getLogger(__name__).info(
            "APPLICATIONINSIGHTS_CONNECTION_STRING not set; skipping Azure Monitor setup"
        )
        return False

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=conn)
    except Exception:
        logging.getLogger(__name__).exception("Failed to configure Azure Monitor OpenTelemetry")
        return False

    _TELEMETRY_CONFIGURED = True
    logging.getLogger(__name__).info("Azure Monitor OpenTelemetry configured")
    return True


def setup_observability(*, log_level: str | None = None) -> None:
    """Configure structured logging and optional Application Insights (call once at startup)."""
    setup_logging(level=log_level)
    setup_telemetry()


def reset_observability_for_tests() -> None:
    """Reset module flags so unit tests can re-run setup (test-only)."""
    global _CONFIGURED, _TELEMETRY_CONFIGURED
    _CONFIGURED = False
    _TELEMETRY_CONFIGURED = False
