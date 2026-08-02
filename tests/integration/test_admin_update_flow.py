"""Integration tests for AdminRepository and admin fee-update flow."""

from __future__ import annotations

import pytest
from sqlalchemy.engine import Engine

from fee_management.data.admin_repository import AdminRepository
from fee_management.data.students_repository import FeeUpdateFields, StudentsRepository
from fee_management.domain.payment_status import (
    PaymentStatus,
    compute_payment_status,
)


@pytest.fixture
def admin_repo(azure_sql_engine: Engine) -> AdminRepository:
    return AdminRepository(engine=azure_sql_engine)


@pytest.fixture
def students_repo(azure_sql_engine: Engine) -> StudentsRepository:
    return StudentsRepository(engine=azure_sql_engine)


def test_list_administrators_seeded(admin_repo: AdminRepository) -> None:
    admins = admin_repo.list_all()
    assert len(admins) == 3
    roles = {a.role for a in admins}
    assert roles == {"Administrator"}


def test_get_admin_by_id(admin_repo: AdminRepository) -> None:
    admin = admin_repo.get_by_id(1)
    assert admin is not None
    assert admin.name == "Dr. Sunita Rao"
    assert admin.role == "Administrator"


def test_admin_update_fee_recomputes_status(students_repo: StudentsRepository) -> None:
    """Admin update flow: mutate fee → recompute payment status → restore."""
    original = students_repo.get_by_id(7)
    assert original is not None

    try:
        updated = students_repo.update_fee(
            7,
            FeeUpdateFields(paid_amount=original.total_fee),
            expected_row_version=original.row_version,
        )
        status = compute_payment_status(updated.total_fee, updated.paid_amount, updated.due_date)
        assert status == PaymentStatus.PAID
    finally:
        current = students_repo.get_by_id(7)
        assert current is not None
        students_repo.update_fee(
            7,
            FeeUpdateFields(
                total_fee=original.total_fee,
                paid_amount=original.paid_amount,
                due_date=original.due_date,
            ),
            expected_row_version=current.row_version,
        )
