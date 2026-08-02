"""Unit tests for Phase 7 observability (correlation IDs + logging setup)."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import azure.functions as func
import pytest

from fee_management.api.errors import error_response, get_correlation_id
from fee_management.telemetry.context import (
    bind_correlation_id,
    get_bound_correlation_id,
)
from fee_management.telemetry.logging_setup import (
    CorrelationIdFilter,
    CorrelationLoggerAdapter,
    reset_observability_for_tests,
    setup_logging,
    setup_telemetry,
)


def test_bind_correlation_id_is_readable_from_context() -> None:
    bind_correlation_id("cid-abc")
    assert get_bound_correlation_id() == "cid-abc"


def test_get_correlation_id_uses_inbound_header() -> None:
    req = MagicMock(spec=func.HttpRequest)
    req.headers = {"x-correlation-id": "from-apim-123"}
    assert get_correlation_id(req) == "from-apim-123"
    assert get_bound_correlation_id() == "from-apim-123"


def test_get_correlation_id_generates_when_missing() -> None:
    req = MagicMock(spec=func.HttpRequest)
    req.headers = {}
    cid = get_correlation_id(req)
    assert cid
    assert get_bound_correlation_id() == cid


def test_correlation_filter_injects_bound_id() -> None:
    bind_correlation_id("filter-cid")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    assert CorrelationIdFilter().filter(record) is True
    assert record.correlation_id == "filter-cid"


def test_logger_adapter_adds_correlation_extra(caplog: pytest.LogCaptureFixture) -> None:
    bind_correlation_id("adapter-cid")
    adapter = CorrelationLoggerAdapter(logging.getLogger("fee_mgmt.test_adapter"), {})
    with caplog.at_level(logging.INFO, logger="fee_mgmt.test_adapter"):
        adapter.info("ping")
    assert any(getattr(r, "correlation_id", None) == "adapter-cid" for r in caplog.records)


def test_error_response_includes_correlation_id_for_4xx() -> None:
    resp = error_response(
        status_code=404,
        code="STUDENT_NOT_FOUND",
        message="missing",
        correlation_id="err-cid-1",
    )
    assert resp.status_code == 404
    assert resp.headers.get("x-correlation-id") == "err-cid-1"
    body = resp.get_body()
    assert b"correlationId" in body
    assert b"err-cid-1" in body


def test_setup_telemetry_skips_without_connection_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_observability_for_tests()
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    assert setup_telemetry() is False


def test_setup_logging_idempotent() -> None:
    reset_observability_for_tests()
    setup_logging(level="INFO")
    setup_logging(level="DEBUG")  # second call no-ops
