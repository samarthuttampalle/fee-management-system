"""All SQL access for the Students table (parameterized via SQLAlchemy Core)."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine, Row
from sqlalchemy.exc import IntegrityError

from fee_management.data.db import connection as db_connection
from fee_management.data.db import get_engine, with_db_retry
from fee_management.domain.exceptions import (
    ConcurrencyConflictError,
    FeeConstraintError,
    StudentNotFoundError,
)
from fee_management.domain.payment_status import PaymentStatus

logger = logging.getLogger(__name__)

_PAYMENT_STATUS_SQL = """
CASE
    WHEN s.PaidAmount >= s.TotalFee THEN 'Paid'
    WHEN s.DueDate < CAST(SYSUTCDATETIME() AS DATE) THEN 'Overdue'
    ELSE 'PartiallyPaid'
END
"""


@dataclass(frozen=True, slots=True)
class StudentRecord:
    """Row mapped from dbo.Students including concurrency token."""

    student_id: int
    name: str
    course: str
    email: str
    total_fee: Decimal
    paid_amount: Decimal
    due_date: date
    aad_object_id: UUID | None
    created_at: datetime
    updated_at: datetime
    row_version: bytes

    @property
    def row_version_base64(self) -> str:
        """Base64 form used in If-Match / ETag headers."""
        return base64.b64encode(self.row_version).decode("ascii")


@dataclass(frozen=True, slots=True)
class StudentStatusColumns:
    """Narrow projection for GET .../payment-status."""

    student_id: int
    total_fee: Decimal
    paid_amount: Decimal
    due_date: date
    aad_object_id: UUID | None


@dataclass(frozen=True, slots=True)
class StudentListItem:
    """Admin list row with SQL-computed payment status."""

    student_id: int
    name: str
    course: str
    total_fee: Decimal
    paid_amount: Decimal
    due_date: date
    payment_status: PaymentStatus


@dataclass(frozen=True, slots=True)
class PaginatedStudents:
    page: int
    page_size: int
    total_count: int
    items: list[StudentListItem]


@dataclass(frozen=True, slots=True)
class OverdueStudent:
    student_id: int
    name: str
    email: str
    course: str
    total_fee: Decimal
    paid_amount: Decimal
    due_date: date


@dataclass(frozen=True, slots=True)
class FeeUpdateFields:
    """Partial fee update; at least one field must be set by the caller."""

    total_fee: Decimal | None = None
    paid_amount: Decimal | None = None
    due_date: date | None = None


def _as_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _map_student(row: Row[Any]) -> StudentRecord:
    return StudentRecord(
        student_id=int(row.StudentID),
        name=str(row.Name),
        course=str(row.Course),
        email=str(row.Email),
        total_fee=Decimal(str(row.TotalFee)),
        paid_amount=Decimal(str(row.PaidAmount)),
        due_date=row.DueDate,
        aad_object_id=_as_uuid(row.AadObjectId),
        created_at=row.CreatedAt,
        updated_at=row.UpdatedAt,
        row_version=bytes(row.RowVersion),
    )


class StudentsRepository:
    """Repository for dbo.Students — the only module that owns Students SQL."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine

    def _engine_or_default(self) -> Engine:
        return self._engine or get_engine()

    def get_by_id(self, student_id: int) -> StudentRecord | None:
        """Return the full student row, or None if not found."""

        def _run() -> StudentRecord | None:
            with db_connection(engine=self._engine_or_default()) as conn:
                return self._get_by_id(conn, student_id)

        return with_db_retry(_run)

    def get_status_columns_by_id(self, student_id: int) -> StudentStatusColumns | None:
        """
        Narrow SELECT for payment-status endpoint (TDD §9.2).

        Fetches only TotalFee, PaidAmount, DueDate (+ identity / AadObjectId
        for authorization), not the full row.
        """

        def _run() -> StudentStatusColumns | None:
            stmt = text("""
                SELECT StudentID, TotalFee, PaidAmount, DueDate, AadObjectId
                FROM dbo.Students
                WHERE StudentID = :student_id
                """)
            with db_connection(engine=self._engine_or_default()) as conn:
                row = conn.execute(stmt, {"student_id": student_id}).mappings().first()
                if row is None:
                    return None
                return StudentStatusColumns(
                    student_id=int(row["StudentID"]),
                    total_fee=Decimal(str(row["TotalFee"])),
                    paid_amount=Decimal(str(row["PaidAmount"])),
                    due_date=row["DueDate"],
                    aad_object_id=_as_uuid(row["AadObjectId"]),
                )

        return with_db_retry(_run)

    def list_paginated(
        self,
        *,
        course: str | None = None,
        status: PaymentStatus | str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> PaginatedStudents:
        """
        Admin listing with optional course / payment-status filters.

        Status filtering uses the §10.5 CASE expression (never a stored column).
        """
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1 or page_size > 100:
            raise ValueError("pageSize must be between 1 and 100")

        status_value: str | None = None
        if status is not None:
            status_value = status.value if isinstance(status, PaymentStatus) else str(status)
            allowed = {s.value for s in PaymentStatus}
            if status_value not in allowed:
                raise ValueError(f"status must be one of {sorted(allowed)}")

        def _run() -> PaginatedStudents:
            filters = ["1 = 1"]
            params: dict[str, Any] = {
                "offset": (page - 1) * page_size,
                "page_size": page_size,
            }
            if course:
                filters.append("s.Course = :course")
                params["course"] = course
            if status_value:
                filters.append(f"({_PAYMENT_STATUS_SQL}) = :payment_status")
                params["payment_status"] = status_value

            where_sql = " AND ".join(filters)
            count_stmt = text(f"""
                SELECT COUNT(1) AS TotalCount
                FROM dbo.Students s
                WHERE {where_sql}
                """)
            list_stmt = text(f"""
                SELECT
                    s.StudentID,
                    s.Name,
                    s.Course,
                    s.TotalFee,
                    s.PaidAmount,
                    s.DueDate,
                    {_PAYMENT_STATUS_SQL} AS PaymentStatus
                FROM dbo.Students s
                WHERE {where_sql}
                ORDER BY s.StudentID
                OFFSET :offset ROWS FETCH NEXT :page_size ROWS ONLY
                """)

            with db_connection(engine=self._engine_or_default()) as conn:
                total_count = int(conn.execute(count_stmt, params).scalar_one())
                rows = conn.execute(list_stmt, params).mappings().all()
                items = [
                    StudentListItem(
                        student_id=int(r["StudentID"]),
                        name=str(r["Name"]),
                        course=str(r["Course"]),
                        total_fee=Decimal(str(r["TotalFee"])),
                        paid_amount=Decimal(str(r["PaidAmount"])),
                        due_date=r["DueDate"],
                        payment_status=PaymentStatus(str(r["PaymentStatus"])),
                    )
                    for r in rows
                ]
                return PaginatedStudents(
                    page=page,
                    page_size=page_size,
                    total_count=total_count,
                    items=items,
                )

        return with_db_retry(_run)

    def list_overdue(self) -> list[OverdueStudent]:
        """Students matching the §10.5 overdue-selection query (reminder job)."""

        def _run() -> list[OverdueStudent]:
            stmt = text("""
                SELECT StudentID, Name, Email, Course, TotalFee, PaidAmount, DueDate
                FROM dbo.Students
                WHERE PaidAmount < TotalFee
                  AND DueDate < CAST(SYSUTCDATETIME() AS DATE)
                ORDER BY StudentID
                """)
            with db_connection(engine=self._engine_or_default()) as conn:
                rows = conn.execute(stmt).mappings().all()
                return [
                    OverdueStudent(
                        student_id=int(r["StudentID"]),
                        name=str(r["Name"]),
                        email=str(r["Email"]),
                        course=str(r["Course"]),
                        total_fee=Decimal(str(r["TotalFee"])),
                        paid_amount=Decimal(str(r["PaidAmount"])),
                        due_date=r["DueDate"],
                    )
                    for r in rows
                ]

        return with_db_retry(_run)

    def update_fee(
        self,
        student_id: int,
        fields: FeeUpdateFields,
        *,
        expected_row_version: bytes | None = None,
    ) -> StudentRecord:
        """
        Partially update fee fields inside a transaction.

        If ``expected_row_version`` is provided and does not match, raises
        ``ConcurrencyConflictError`` (HTTP 409 path in Phase 8).
        """
        if fields.total_fee is None and fields.paid_amount is None and fields.due_date is None:
            raise ValueError("At least one of total_fee, paid_amount, due_date must be provided")

        def _run() -> StudentRecord:
            with db_connection(engine=self._engine_or_default()) as conn:
                current = self._get_by_id(conn, student_id)
                if current is None:
                    raise StudentNotFoundError(student_id)

                if expected_row_version is not None and expected_row_version != current.row_version:
                    raise ConcurrencyConflictError(student_id)

                new_total = fields.total_fee if fields.total_fee is not None else current.total_fee
                new_paid = (
                    fields.paid_amount if fields.paid_amount is not None else current.paid_amount
                )
                new_due = fields.due_date if fields.due_date is not None else current.due_date

                # Mirror CK_Students_PaidAmount_Bound for a friendly failure path
                if new_paid > new_total * Decimal("1.5"):
                    raise FeeConstraintError("paidAmount must be <= totalFee * 1.5")

                stmt = text("""
                    UPDATE dbo.Students
                    SET
                        TotalFee = :total_fee,
                        PaidAmount = :paid_amount,
                        DueDate = :due_date
                    WHERE StudentID = :student_id
                      AND RowVersion = :row_version
                    """)
                try:
                    result = conn.execute(
                        stmt,
                        {
                            "total_fee": new_total,
                            "paid_amount": new_paid,
                            "due_date": new_due,
                            "student_id": student_id,
                            "row_version": current.row_version,
                        },
                    )
                except IntegrityError as exc:
                    raise FeeConstraintError(
                        "Fee update violates database constraints "
                        "(non-negative amounts and paidAmount <= totalFee * 1.5)"
                    ) from exc

                if result.rowcount != 1:
                    # Lost the race after our read — treat as concurrency conflict
                    raise ConcurrencyConflictError(student_id)

                updated = self._get_by_id(conn, student_id)
                if updated is None:
                    raise StudentNotFoundError(student_id)
                return updated

        return with_db_retry(_run)

    def get_by_aad_object_id(self, aad_object_id: UUID | str) -> StudentRecord | None:
        """Lookup used for Student ownership checks (oid claim → row)."""

        def _run() -> StudentRecord | None:
            stmt = text("""
                SELECT
                    StudentID, Name, Course, Email, TotalFee, PaidAmount, DueDate,
                    AadObjectId, CreatedAt, UpdatedAt, RowVersion
                FROM dbo.Students
                WHERE AadObjectId = :aad_object_id
                """)
            with db_connection(engine=self._engine_or_default()) as conn:
                row = conn.execute(stmt, {"aad_object_id": str(aad_object_id)}).first()
                if row is None:
                    return None
                return _map_student(row)

        return with_db_retry(_run)

    @staticmethod
    def _get_by_id(conn: Connection, student_id: int) -> StudentRecord | None:
        stmt = text("""
            SELECT
                StudentID, Name, Course, Email, TotalFee, PaidAmount, DueDate,
                AadObjectId, CreatedAt, UpdatedAt, RowVersion
            FROM dbo.Students
            WHERE StudentID = :student_id
            """)
        row = conn.execute(stmt, {"student_id": student_id}).first()
        if row is None:
            return None
        return _map_student(row)


# Module-level convenience API matching TDD call sites (students_repository.get_by_id)
_default_repo = StudentsRepository()


def get_by_id(student_id: int) -> StudentRecord | None:
    return _default_repo.get_by_id(student_id)


def get_status_columns_by_id(student_id: int) -> StudentStatusColumns | None:
    return _default_repo.get_status_columns_by_id(student_id)


def list_paginated(
    *,
    course: str | None = None,
    status: PaymentStatus | str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> PaginatedStudents:
    return _default_repo.list_paginated(
        course=course, status=status, page=page, page_size=page_size
    )


def list_overdue() -> list[OverdueStudent]:
    return _default_repo.list_overdue()


def update_fee(
    student_id: int,
    fields: FeeUpdateFields,
    *,
    expected_row_version: bytes | None = None,
) -> StudentRecord:
    return _default_repo.update_fee(student_id, fields, expected_row_version=expected_row_version)
