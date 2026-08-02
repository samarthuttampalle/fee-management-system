"""Domain / application exceptions mapped to HTTP (TDD §16)."""

from __future__ import annotations


class StudentNotFoundError(Exception):
    """Raised when a student id does not exist."""

    def __init__(self, student_id: int) -> None:
        self.student_id = student_id
        super().__init__(f"No student found with id {student_id}")


class ConcurrencyConflictError(Exception):
    """Raised when If-Match / RowVersion does not match the current row."""

    def __init__(self, student_id: int) -> None:
        self.student_id = student_id
        super().__init__(f"Concurrent modification detected for student {student_id}")


class AuthorizationError(Exception):
    """Raised on role or ownership failures."""

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message)


class FeeConstraintError(Exception):
    """Raised when fee amounts violate CHECK constraints / business bounds."""

    def __init__(
        self,
        message: str = "paidAmount must be <= totalFee * 1.5",
    ) -> None:
        super().__init__(message)
