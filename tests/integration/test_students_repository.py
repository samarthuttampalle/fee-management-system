"""Integration tests for StudentsRepository against Azure SQL."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from fee_management.data.students_repository import (
    FeeUpdateFields,
    StudentsRepository,
)
from fee_management.domain.exceptions import ConcurrencyConflictError, StudentNotFoundError
from fee_management.domain.payment_status import PaymentStatus


@pytest.fixture
def repo(azure_sql_engine: Engine) -> StudentsRepository:
    return StudentsRepository(engine=azure_sql_engine)


def test_get_by_id_returns_seeded_student(repo: StudentsRepository) -> None:
    student = repo.get_by_id(1)
    assert student is not None
    assert student.name == "Aarav Sharma"
    assert student.email.endswith("@institution.edu")
    assert student.total_fee == Decimal("120000.00")
    assert isinstance(student.row_version, (bytes, bytearray))


def test_get_by_id_returns_none_for_missing(repo: StudentsRepository) -> None:
    assert repo.get_by_id(999999) is None


def test_get_status_columns_by_id_is_narrow(repo: StudentsRepository) -> None:
    cols = repo.get_status_columns_by_id(1)
    assert cols is not None
    assert cols.student_id == 1
    assert cols.total_fee == Decimal("120000.00")
    assert cols.paid_amount == Decimal("120000.00")


def test_list_paginated_total_and_page_size(repo: StudentsRepository) -> None:
    page = repo.list_paginated(page=1, page_size=5)
    assert page.total_count == 20
    assert len(page.items) == 5
    assert page.page == 1
    assert page.page_size == 5


def test_list_paginated_filter_by_course(repo: StudentsRepository) -> None:
    page = repo.list_paginated(course="B.Tech Computer Science", page=1, page_size=25)
    assert page.total_count == 2
    assert all(i.course == "B.Tech Computer Science" for i in page.items)


def test_list_paginated_filter_by_status_paid(repo: StudentsRepository) -> None:
    page = repo.list_paginated(status=PaymentStatus.PAID, page=1, page_size=100)
    assert page.total_count >= 1
    assert all(i.payment_status == PaymentStatus.PAID for i in page.items)
    # Aarav (id=1) is fully paid in seed data
    assert any(i.student_id == 1 for i in page.items)


def test_list_overdue_matches_predicate(repo: StudentsRepository) -> None:
    overdue = repo.list_overdue()
    assert overdue, "expected at least one overdue seed student"
    today = date.today()
    ids = {s.student_id for s in overdue}
    for s in overdue:
        assert s.paid_amount < s.total_fee
        assert s.due_date < today
        assert s.email
    # Fully paid Aarav must not appear
    assert 1 not in ids
    # Nisha (id=16) unpaid but due 2026-09-01 — not overdue while today < due
    nisha = repo.get_by_id(16)
    assert nisha is not None
    if nisha.due_date >= today:
        assert 16 not in ids


def test_update_fee_happy_path_and_restore(
    repo: StudentsRepository, azure_sql_engine: Engine
) -> None:
    original = repo.get_by_id(4)
    assert original is not None

    try:
        updated = repo.update_fee(
            4,
            FeeUpdateFields(paid_amount=Decimal("45000.00")),
            expected_row_version=original.row_version,
        )
        assert updated.paid_amount == Decimal("45000.00")
        assert updated.row_version != original.row_version
        assert updated.updated_at >= original.updated_at
    finally:
        # Restore seed value using current row version
        current = repo.get_by_id(4)
        assert current is not None
        repo.update_fee(
            4,
            FeeUpdateFields(
                total_fee=original.total_fee,
                paid_amount=original.paid_amount,
                due_date=original.due_date,
            ),
            expected_row_version=current.row_version,
        )


def test_update_fee_rowversion_conflict(repo: StudentsRepository) -> None:
    original = repo.get_by_id(5)
    assert original is not None
    stale = original.row_version

    # First writer succeeds
    after_first = repo.update_fee(
        5,
        FeeUpdateFields(paid_amount=Decimal("100.00")),
        expected_row_version=stale,
    )
    assert after_first.paid_amount == Decimal("100.00")

    try:
        with pytest.raises(ConcurrencyConflictError):
            repo.update_fee(
                5,
                FeeUpdateFields(paid_amount=Decimal("200.00")),
                expected_row_version=stale,  # stale token from before first write
            )
    finally:
        current = repo.get_by_id(5)
        assert current is not None
        repo.update_fee(
            5,
            FeeUpdateFields(
                total_fee=original.total_fee,
                paid_amount=original.paid_amount,
                due_date=original.due_date,
            ),
            expected_row_version=current.row_version,
        )


def test_update_fee_missing_student(repo: StudentsRepository) -> None:
    with pytest.raises(StudentNotFoundError):
        repo.update_fee(999999, FeeUpdateFields(paid_amount=Decimal("1")))


def test_db_check_constraint_rejects_excessive_overpayment(
    azure_sql_engine: Engine,
) -> None:
    """Bypass app validation; DB CHECK (PaidAmount <= TotalFee * 1.5) must reject."""
    with azure_sql_engine.connect() as conn:
        trans = conn.begin()
        try:
            # 200 > 100 * 1.5 → violates CK_Students_PaidAmount_Bound
            conn.execute(
                text(
                    """
                    UPDATE dbo.Students
                    SET PaidAmount = 200.00, TotalFee = 100.00
                    WHERE StudentID = 1
                    """
                )
            )
            trans.commit()
            pytest.fail("Expected CHECK constraint violation")
        except Exception as exc:
            trans.rollback()
            message = str(exc).upper()
            assert (
                "CHECK" in message
                or "CONFLICTED" in message
                or "545" in str(exc)
                or "547" in str(exc)
            ), f"Unexpected error: {exc}"

        row = conn.execute(
            text("SELECT PaidAmount, TotalFee FROM dbo.Students WHERE StudentID = 1")
        ).one()
        assert Decimal(str(row.PaidAmount)) == Decimal("120000.00")
        assert Decimal(str(row.TotalFee)) == Decimal("120000.00")
