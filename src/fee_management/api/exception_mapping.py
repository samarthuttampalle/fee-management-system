"""Map domain/platform exceptions to HTTP responses (TDD §16.1)."""

from __future__ import annotations

import logging
from typing import Any

import azure.functions as func
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, OperationalError

from fee_management.api.errors import error_response
from fee_management.auth.jwt_validator import TokenValidationError
from fee_management.domain.exceptions import (
    AuthorizationError,
    ConcurrencyConflictError,
    FeeConstraintError,
    StudentNotFoundError,
)

logger = logging.getLogger(__name__)


def map_exception_to_response(
    exc: BaseException,
    correlation_id: str,
) -> func.HttpResponse:
    """
    Single taxonomy boundary for HTTP handlers (§16.1 / §27).

    Known exceptions become sanitized 4xx/503 responses; everything else is 500
    with a generic message (stack trace logged, never returned).
    """
    if isinstance(exc, ValidationError):
        return error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message="Request body failed validation",
            correlation_id=correlation_id,
            details=_validation_details(exc),
        )

    if isinstance(exc, TokenValidationError):
        return error_response(
            status_code=401,
            code="UNAUTHORIZED",
            message="Missing or invalid bearer token",
            correlation_id=correlation_id,
        )

    if isinstance(exc, AuthorizationError):
        return error_response(
            status_code=403,
            code="FORBIDDEN",
            message="Insufficient permissions",
            correlation_id=correlation_id,
        )

    if isinstance(exc, StudentNotFoundError):
        return error_response(
            status_code=404,
            code="STUDENT_NOT_FOUND",
            message=str(exc),
            correlation_id=correlation_id,
        )

    if isinstance(exc, ConcurrencyConflictError):
        return error_response(
            status_code=409,
            code="CONCURRENCY_CONFLICT",
            message="The fee record was modified by another request; re-fetch and retry",
            correlation_id=correlation_id,
        )

    if isinstance(exc, FeeConstraintError | IntegrityError):
        return error_response(
            status_code=400,
            code="INVALID_FEE_AMOUNTS",
            message=(
                str(exc)
                if isinstance(exc, FeeConstraintError)
                else "Fee update violates database constraints "
                "(non-negative amounts and paidAmount <= totalFee * 1.5)"
            ),
            correlation_id=correlation_id,
        )

    if isinstance(exc, OperationalError):
        return error_response(
            status_code=503,
            code="SERVICE_UNAVAILABLE",
            message="Database temporarily unavailable; please retry",
            correlation_id=correlation_id,
        )

    if isinstance(exc, ValueError):
        return error_response(
            status_code=400,
            code="INVALID_REQUEST",
            message=str(exc) or "Invalid request",
            correlation_id=correlation_id,
        )

    logger.error(
        "Unhandled exception mapped to INTERNAL_ERROR",
        extra={"correlation_id": correlation_id, "exc_type": type(exc).__name__},
        exc_info=exc,
    )
    return error_response(
        status_code=500,
        code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        correlation_id=correlation_id,
    )


def _validation_details(exc: ValidationError) -> list[Any]:
    try:
        return list(exc.errors())
    except Exception:
        return []
