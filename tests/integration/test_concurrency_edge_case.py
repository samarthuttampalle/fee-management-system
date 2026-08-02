"""§21.5 concurrent PUT edge case — second writer with stale RowVersion gets 409."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.engine import Engine

from fee_management.data.students_repository import FeeUpdateFields, StudentsRepository
from fee_management.domain.exceptions import ConcurrencyConflictError


@pytest.fixture
def students_repo(azure_sql_engine: Engine) -> StudentsRepository:
    return StudentsRepository(engine=azure_sql_engine)


def test_concurrent_put_second_writer_gets_conflict(students_repo: StudentsRepository) -> None:
    """
    Two admins update the same student: first wins, second with stale If-Match/RowVersion
    raises ConcurrencyConflictError (HTTP 409 at the API boundary).
    """
    student_id = 8
    original = students_repo.get_by_id(student_id)
    assert original is not None
    stale_version = original.row_version

    first = students_repo.update_fee(
        student_id,
        FeeUpdateFields(paid_amount=original.paid_amount + Decimal("1.00")),
        expected_row_version=stale_version,
    )
    assert first.row_version != stale_version

    try:
        with pytest.raises(ConcurrencyConflictError) as raised:
            students_repo.update_fee(
                student_id,
                FeeUpdateFields(paid_amount=original.paid_amount + Decimal("2.00")),
                expected_row_version=stale_version,
            )
        assert raised.value.student_id == student_id
    finally:
        current = students_repo.get_by_id(student_id)
        assert current is not None
        students_repo.update_fee(
            student_id,
            FeeUpdateFields(
                total_fee=original.total_fee,
                paid_amount=original.paid_amount,
                due_date=original.due_date,
            ),
            expected_row_version=current.row_version,
        )
