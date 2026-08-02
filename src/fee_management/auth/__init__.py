"""JWT validation and RBAC helpers."""

from fee_management.auth.jwt_validator import TokenValidationError, validate_token
from fee_management.auth.rbac import (
    ROLE_ADMINISTRATOR,
    ROLE_STUDENT,
    authorize_student_record_access,
    get_claims,
    require_role,
)

__all__ = [
    "ROLE_ADMINISTRATOR",
    "ROLE_STUDENT",
    "TokenValidationError",
    "authorize_student_record_access",
    "get_claims",
    "require_role",
    "validate_token",
]
