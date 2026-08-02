"""Entra ID JWT validation with a local-only bypass (TDD §12.3 / §20.4)."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

from fee_management.config import Settings, get_settings

logger = logging.getLogger(__name__)

_JWKS_URL = "https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"

# Fixed local bypass identities (TDD §20.4 + student testing helper)
_LOCAL_ADMIN_OID = "local-test-admin"
_LOCAL_STUDENT_OID_DEFAULT = "11111111-1111-1111-1111-111111111111"


class TokenValidationError(Exception):
    """Raised when a bearer token cannot be validated."""


@lru_cache(maxsize=8)
def _jwk_client(tenant_id: str) -> PyJWKClient:
    return PyJWKClient(_JWKS_URL.format(tenant_id=tenant_id))


def _normalize_roles(roles: Any) -> list[str]:
    if roles is None:
        return []
    if isinstance(roles, str):
        return [roles]
    return [str(r) for r in roles]


def _try_local_bypass(token: str, settings: Settings) -> dict[str, Any] | None:
    """
    Honor LOCAL_AUTH_BYPASS_* only when ENVIRONMENT == \"local\".

    Physically impossible to enable in Azure if ENVIRONMENT is never \"local\" there.
    """
    if settings.environment.lower() != "local":
        return None

    admin_token = (settings.local_auth_bypass_token or "").strip()
    if admin_token and token == admin_token:
        return {"oid": _LOCAL_ADMIN_OID, "roles": ["Administrator"]}

    student_token = (settings.local_auth_bypass_student_token or "").strip()
    if student_token and token == student_token:
        oid = (settings.local_auth_bypass_student_oid or _LOCAL_STUDENT_OID_DEFAULT).strip()
        return {"oid": oid, "roles": ["Student"]}

    return None


def validate_token(
    token: str,
    tenant_id: str | None = None,
    audience: str | None = None,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """
    Validate an Entra ID access token (or local bypass token).

    Returns the decoded claims dict. Raises TokenValidationError on failure.
    """
    cfg = settings or get_settings()
    bypass = _try_local_bypass(token, cfg)
    if bypass is not None:
        logger.info("Authenticated via local auth bypass", extra={"roles": bypass.get("roles")})
        return bypass

    tid = tenant_id or cfg.aad_tenant_id
    aud_raw = audience or cfg.aad_audience
    if not tid or not aud_raw:
        raise TokenValidationError("AAD_TENANT_ID and AAD_AUDIENCE must be configured")

    # Entra may emit aud as api://<appId> or bare <appId>; accept either (comma-separated).
    audiences = [a.strip() for a in aud_raw.split(",") if a.strip()]
    aud: str | list[str] = audiences[0] if len(audiences) == 1 else audiences

    try:
        jwk_client = _jwk_client(tid)
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=aud,
            issuer=f"https://login.microsoftonline.com/{tid}/v2.0",
            options={"require": ["exp", "iss", "aud"]},
        )
        claims = dict(claims)
        claims["roles"] = _normalize_roles(claims.get("roles"))
        return claims
    except jwt.PyJWTError as exc:
        raise TokenValidationError(str(exc)) from exc


def reset_jwk_cache() -> None:
    """Clear cached JWKS clients (tests)."""
    _jwk_client.cache_clear()
