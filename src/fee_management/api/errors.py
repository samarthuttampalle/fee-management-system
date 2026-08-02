"""Shared HTTP error helpers and correlation-id handling (TDD §8 / §15.3)."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import azure.functions as func

from fee_management.telemetry.context import bind_correlation_id

logger = logging.getLogger(__name__)


def get_correlation_id(req: func.HttpRequest) -> str:
    """Use inbound x-correlation-id or generate a new UUID4; bind for this request."""
    incoming = req.headers.get("x-correlation-id") or req.headers.get("X-Correlation-Id")
    correlation_id = incoming.strip() if incoming and incoming.strip() else str(uuid.uuid4())
    bind_correlation_id(correlation_id)
    return correlation_id


def json_response(
    body: dict[str, Any],
    *,
    status_code: int = 200,
    correlation_id: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> func.HttpResponse:
    headers = {"Content-Type": "application/json"}
    if correlation_id:
        headers["x-correlation-id"] = correlation_id
    if extra_headers:
        headers.update(extra_headers)
    return func.HttpResponse(
        body=json.dumps(body, default=str),
        status_code=status_code,
        headers=headers,
        mimetype="application/json",
    )


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    correlation_id: str,
    details: list[Any] | None = None,
) -> func.HttpResponse:
    payload: dict[str, Any] = {
        "error": code,
        "message": message,
        "correlationId": correlation_id,
    }
    if details is not None:
        payload["details"] = details
    if status_code >= 500:
        logger.error(
            "Request failed with %s: %s",
            code,
            message,
            extra={"correlation_id": correlation_id, "error_code": code},
            exc_info=True,
        )
    else:
        logger.warning(
            "Client error %s: %s",
            code,
            message,
            extra={"correlation_id": correlation_id, "error_code": code},
        )
    return json_response(payload, status_code=status_code, correlation_id=correlation_id)
