"""Unit tests for §16.1 exception → HTTP mapping (Phase 8)."""

from __future__ import annotations

import json

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, OperationalError

from fee_management.api.exception_mapping import map_exception_to_response
from fee_management.api.schemas import UpdateFeeRequest
from fee_management.auth.jwt_validator import TokenValidationError
from fee_management.domain.exceptions import (
    AuthorizationError,
    ConcurrencyConflictError,
    FeeConstraintError,
    StudentNotFoundError,
)


def _body(resp) -> dict:
    return json.loads(resp.get_body().decode("utf-8"))


def test_map_validation_error_to_400() -> None:
    try:
        UpdateFeeRequest.model_validate({})
    except ValidationError as exc:
        resp = map_exception_to_response(exc, "cid-1")
    assert resp.status_code == 400
    body = _body(resp)
    assert body["error"] == "VALIDATION_ERROR"
    assert body["correlationId"] == "cid-1"
    assert "details" in body


def test_map_token_validation_to_401() -> None:
    resp = map_exception_to_response(TokenValidationError("bad"), "cid-2")
    assert resp.status_code == 401
    assert _body(resp)["error"] == "UNAUTHORIZED"


def test_map_authorization_to_403() -> None:
    resp = map_exception_to_response(AuthorizationError(), "cid-3")
    assert resp.status_code == 403
    assert _body(resp)["error"] == "FORBIDDEN"


def test_map_student_not_found_to_404() -> None:
    resp = map_exception_to_response(StudentNotFoundError(99), "cid-4")
    assert resp.status_code == 404
    assert _body(resp)["error"] == "STUDENT_NOT_FOUND"


def test_map_concurrency_conflict_to_409() -> None:
    resp = map_exception_to_response(ConcurrencyConflictError(4), "cid-5")
    assert resp.status_code == 409
    body = _body(resp)
    assert body["error"] == "CONCURRENCY_CONFLICT"
    assert "re-fetch" in body["message"]


def test_map_fee_constraint_to_400() -> None:
    resp = map_exception_to_response(FeeConstraintError(), "cid-6")
    assert resp.status_code == 400
    assert _body(resp)["error"] == "INVALID_FEE_AMOUNTS"


def test_map_integrity_error_to_400() -> None:
    resp = map_exception_to_response(IntegrityError("stmt", {}, Exception("check")), "cid-7")
    assert resp.status_code == 400
    assert _body(resp)["error"] == "INVALID_FEE_AMOUNTS"


def test_map_operational_error_to_503() -> None:
    resp = map_exception_to_response(OperationalError("stmt", {}, Exception("timeout")), "cid-8")
    assert resp.status_code == 503
    assert _body(resp)["error"] == "SERVICE_UNAVAILABLE"


def test_map_unknown_to_500_without_leaking_message() -> None:
    resp = map_exception_to_response(RuntimeError("secret internals"), "cid-9")
    assert resp.status_code == 500
    body = _body(resp)
    assert body["error"] == "INTERNAL_ERROR"
    assert "secret" not in body["message"]
