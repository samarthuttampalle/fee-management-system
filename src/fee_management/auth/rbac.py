"""RBAC helpers and role-check decorator (TDD §12.4 / §12.5 / §16.4)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar
from uuid import UUID

import azure.functions as func

from fee_management.api.errors import error_response, get_correlation_id
from fee_management.auth.jwt_validator import TokenValidationError, validate_token
from fee_management.config import get_settings

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., func.HttpResponse])

ROLE_STUDENT = "Student"
ROLE_ADMINISTRATOR = "Administrator"

# Generic message — must not disclose whether a student id exists (§16.4)
_FORBIDDEN_OWN_RECORD_MESSAGE = "You may only access your own fee record"
_FORBIDDEN_ROLE_MESSAGE = "Insufficient role"
_UNAUTHORIZED_MISSING = "Authentication required"
_UNAUTHORIZED_INVALID = "Invalid or expired token"


def get_claims(req: func.HttpRequest) -> dict[str, Any]:
    """Return claims attached by ``require_role`` (empty dict if missing)."""
    return getattr(req, "claims", {}) or {}


def caller_roles(claims: dict[str, Any]) -> list[str]:
    roles = claims.get("roles") or []
    if isinstance(roles, str):
        return [roles]
    return list(roles)


def is_administrator(claims: dict[str, Any]) -> bool:
    return ROLE_ADMINISTRATOR in caller_roles(claims)


def is_student(claims: dict[str, Any]) -> bool:
    return ROLE_STUDENT in caller_roles(claims)


def require_role(*allowed_roles: str) -> Callable[[F], F]:
    """
    Validate Bearer JWT and require at least one of ``allowed_roles``.

    On success, attaches ``req.claims`` for downstream ownership checks.
    """

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(req: func.HttpRequest, *args: Any, **kwargs: Any) -> func.HttpResponse:
            correlation_id = get_correlation_id(req)
            auth_header = req.headers.get("Authorization") or req.headers.get("authorization") or ""
            if not auth_header.startswith("Bearer "):
                return error_response(
                    status_code=401,
                    code="UNAUTHORIZED",
                    message=_UNAUTHORIZED_MISSING,
                    correlation_id=correlation_id,
                )

            token = auth_header.removeprefix("Bearer ").strip()
            if not token:
                return error_response(
                    status_code=401,
                    code="UNAUTHORIZED",
                    message=_UNAUTHORIZED_MISSING,
                    correlation_id=correlation_id,
                )

            settings = get_settings()
            try:
                claims = validate_token(token, settings=settings)
            except TokenValidationError:
                return error_response(
                    status_code=401,
                    code="UNAUTHORIZED",
                    message=_UNAUTHORIZED_INVALID,
                    correlation_id=correlation_id,
                )

            roles = caller_roles(claims)
            if not any(r in allowed_roles for r in roles):
                logger.warning(
                    "Forbidden: role mismatch",
                    extra={"correlation_id": correlation_id, "roles": roles},
                )
                return error_response(
                    status_code=403,
                    code="FORBIDDEN",
                    message=_FORBIDDEN_ROLE_MESSAGE,
                    correlation_id=correlation_id,
                )

            req.claims = claims
            return fn(req, *args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def authorize_student_record_access(
    claims: dict[str, Any],
    *,
    student_aad_object_id: UUID | str | None,
    student_found: bool,
    correlation_id: str,
) -> func.HttpResponse | None:
    """
    Enforce Student own-record access (TDD §12.5 / §16.4).

    - Administrator: always allowed (caller handles 404).
    - Student: if row missing OR oid mismatch → 403 with generic message
      (anti-enumeration — do not return 404 to students for other ids).
    """
    if is_administrator(claims):
        return None

    if not is_student(claims):
        return error_response(
            status_code=403,
            code="FORBIDDEN",
            message=_FORBIDDEN_ROLE_MESSAGE,
            correlation_id=correlation_id,
        )

    oid = str(claims.get("oid") or "").strip().lower()
    row_oid = (
        str(student_aad_object_id).strip().lower() if student_aad_object_id is not None else ""
    )

    if (not student_found) or (not oid) or (not row_oid) or oid != row_oid:
        logger.warning(
            "Forbidden: student ownership check failed",
            extra={"correlation_id": correlation_id},
        )
        return error_response(
            status_code=403,
            code="FORBIDDEN",
            message=_FORBIDDEN_OWN_RECORD_MESSAGE,
            correlation_id=correlation_id,
        )

    return None
