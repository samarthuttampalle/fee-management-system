"""Unit tests for JWT local bypass and RBAC (TDD §12 / §20.4 / §16.4)."""

from __future__ import annotations

import json
from uuid import UUID

import azure.functions as func
import pytest

from fee_management.auth.jwt_validator import TokenValidationError, validate_token
from fee_management.auth.rbac import (
    ROLE_ADMINISTRATOR,
    ROLE_STUDENT,
    authorize_student_record_access,
    require_role,
)
from fee_management.config import Settings, get_settings


def _settings(**overrides: object) -> Settings:
    base = {
        "environment": "local",
        "local_auth_bypass_token": "local-admin-token",
        "local_auth_bypass_student_token": "local-student-token",
        "local_auth_bypass_student_oid": "11111111-1111-1111-1111-111111111111",
        "aad_tenant_id": "tenant",
        "aad_audience": "api://fee-mgmt-dev",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_local_admin_bypass_returns_administrator_claims() -> None:
    claims = validate_token("local-admin-token", settings=_settings())
    assert claims["roles"] == ["Administrator"]
    assert claims["oid"] == "local-test-admin"


def test_local_student_bypass_returns_student_claims() -> None:
    claims = validate_token("local-student-token", settings=_settings())
    assert claims["roles"] == ["Student"]
    assert claims["oid"] == "11111111-1111-1111-1111-111111111111"


def test_local_bypass_disabled_outside_local_environment() -> None:
    with pytest.raises(TokenValidationError):
        validate_token(
            "local-admin-token",
            settings=_settings(environment="prod", aad_tenant_id="", aad_audience=""),
        )


def test_invalid_token_without_bypass_raises() -> None:
    with pytest.raises(TokenValidationError):
        validate_token("not-a-real-jwt", settings=_settings(local_auth_bypass_token=""))


def test_authorize_admin_always_allowed() -> None:
    resp = authorize_student_record_access(
        {"roles": [ROLE_ADMINISTRATOR], "oid": "x"},
        student_aad_object_id=None,
        student_found=False,
        correlation_id="c1",
    )
    assert resp is None


def test_authorize_student_own_record_allowed() -> None:
    oid = UUID("11111111-1111-1111-1111-111111111111")
    resp = authorize_student_record_access(
        {"roles": [ROLE_STUDENT], "oid": str(oid)},
        student_aad_object_id=oid,
        student_found=True,
        correlation_id="c1",
    )
    assert resp is None


def test_authorize_student_other_record_forbidden_even_if_missing() -> None:
    """Anti-enumeration: missing row still yields 403 for Student role."""
    resp = authorize_student_record_access(
        {"roles": [ROLE_STUDENT], "oid": "11111111-1111-1111-1111-111111111111"},
        student_aad_object_id=None,
        student_found=False,
        correlation_id="c1",
    )
    assert resp is not None
    assert resp.status_code == 403
    body = json.loads(resp.get_body().decode())
    assert body["error"] == "FORBIDDEN"
    assert "own fee record" in body["message"]


def test_authorize_student_oid_mismatch_forbidden() -> None:
    resp = authorize_student_record_access(
        {"roles": [ROLE_STUDENT], "oid": "11111111-1111-1111-1111-111111111111"},
        student_aad_object_id=UUID("22222222-2222-2222-2222-222222222222"),
        student_found=True,
        correlation_id="c1",
    )
    assert resp is not None
    assert resp.status_code == 403


def _make_request(auth: str | None) -> func.HttpRequest:
    headers = {"Authorization": auth} if auth else {}
    return func.HttpRequest(
        method="GET",
        url="http://localhost/api/students/1",
        headers=headers,
        params={},
        route_params={"studentId": "1"},
        body=b"",
    )


def test_require_role_missing_token_401() -> None:
    @require_role(ROLE_ADMINISTRATOR)
    def _handler(req: func.HttpRequest) -> func.HttpResponse:
        return func.HttpResponse("ok", status_code=200)

    get_settings.cache_clear()
    resp = _handler(_make_request(None))
    assert resp.status_code == 401


def test_require_role_admin_bypass_allows_administrator() -> None:
    @require_role(ROLE_ADMINISTRATOR)
    def _handler(req: func.HttpRequest) -> func.HttpResponse:
        assert req.claims["roles"] == ["Administrator"]
        return func.HttpResponse("ok", status_code=200)

    # Ensure settings pick up bypass from env-like defaults via explicit monkeypatch
    import os

    os.environ["ENVIRONMENT"] = "local"
    os.environ["LOCAL_AUTH_BYPASS_TOKEN"] = "local-admin-token"
    get_settings.cache_clear()

    resp = _handler(_make_request("Bearer local-admin-token"))
    assert resp.status_code == 200
    get_settings.cache_clear()


def test_require_role_student_token_forbidden_on_admin_endpoint() -> None:
    @require_role(ROLE_ADMINISTRATOR)
    def _handler(req: func.HttpRequest) -> func.HttpResponse:
        return func.HttpResponse("ok", status_code=200)

    import os

    os.environ["ENVIRONMENT"] = "local"
    os.environ["LOCAL_AUTH_BYPASS_TOKEN"] = "local-admin-token"
    os.environ["LOCAL_AUTH_BYPASS_STUDENT_TOKEN"] = "local-student-token"
    get_settings.cache_clear()

    resp = _handler(_make_request("Bearer local-student-token"))
    assert resp.status_code == 403
    get_settings.cache_clear()
