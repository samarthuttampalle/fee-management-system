"""Unit tests for payment status computation (TDD §21.1)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from fee_management.domain.models import FeeDetail, Student
from fee_management.domain.payment_status import (
    PaymentStatus,
    compute_days_overdue,
    compute_due_amount,
    compute_payment_status,
)


def test_paid_when_paid_amount_equals_total() -> None:
    assert (
        compute_payment_status(
            Decimal("1000"),
            Decimal("1000"),
            date(2026, 1, 1),
            today=date(2026, 2, 1),
        )
        == PaymentStatus.PAID
    )


def test_paid_when_paid_amount_exceeds_total() -> None:
    """Small legitimate overpayment still counts as Paid (§21.5)."""
    assert (
        compute_payment_status(
            Decimal("1000"),
            Decimal("1000.01"),
            date(2026, 1, 1),
            today=date(2026, 2, 1),
        )
        == PaymentStatus.PAID
    )


def test_overdue_when_underpaid_and_past_due() -> None:
    assert (
        compute_payment_status(
            Decimal("1000"),
            Decimal("500"),
            date(2026, 1, 1),
            today=date(2026, 2, 1),
        )
        == PaymentStatus.OVERDUE
    )


def test_overdue_when_unpaid_and_past_due() -> None:
    assert (
        compute_payment_status(
            Decimal("1000"),
            Decimal("0"),
            date(2026, 1, 1),
            today=date(2026, 2, 1),
        )
        == PaymentStatus.OVERDUE
    )


def test_partially_paid_when_underpaid_but_not_yet_due() -> None:
    assert (
        compute_payment_status(
            Decimal("1000"),
            Decimal("500"),
            date(2026, 3, 1),
            today=date(2026, 2, 1),
        )
        == PaymentStatus.PARTIALLY_PAID
    )


def test_unpaid_and_not_due_is_partially_paid_not_overdue() -> None:
    assert (
        compute_payment_status(
            Decimal("1000"),
            Decimal("0"),
            date(2026, 3, 1),
            today=date(2026, 2, 1),
        )
        == PaymentStatus.PARTIALLY_PAID
    )


def test_boundary_due_date_equals_today_is_not_overdue() -> None:
    assert (
        compute_payment_status(
            Decimal("1000"),
            Decimal("500"),
            date(2026, 2, 1),
            today=date(2026, 2, 1),
        )
        == PaymentStatus.PARTIALLY_PAID
    )


def test_paid_takes_precedence_even_when_past_due() -> None:
    """Fully paid past the due date remains Paid, not Overdue."""
    assert (
        compute_payment_status(
            Decimal("1000"),
            Decimal("1000"),
            date(2026, 1, 1),
            today=date(2026, 2, 1),
        )
        == PaymentStatus.PAID
    )


def test_compute_due_amount_positive_and_zero_floor() -> None:
    assert compute_due_amount(Decimal("1000.00"), Decimal("400.00")) == Decimal("600.00")
    assert compute_due_amount(Decimal("1000.00"), Decimal("1000.00")) == Decimal("0.00")
    assert compute_due_amount(Decimal("1000.00"), Decimal("1100.00")) == Decimal("0.00")


def test_compute_days_overdue_only_when_overdue() -> None:
    today = date(2026, 2, 13)
    assert (
        compute_days_overdue(
            date(2026, 2, 1),
            payment_status=PaymentStatus.OVERDUE,
            today=today,
        )
        == 12
    )
    assert (
        compute_days_overdue(
            date(2026, 2, 1),
            payment_status=PaymentStatus.PARTIALLY_PAID,
            today=today,
        )
        is None
    )
    assert (
        compute_days_overdue(
            date(2026, 2, 1),
            payment_status=PaymentStatus.PAID,
            today=today,
        )
        is None
    )


def test_payment_status_enum_values_match_api_contract() -> None:
    assert PaymentStatus.PAID.value == "Paid"
    assert PaymentStatus.PARTIALLY_PAID.value == "PartiallyPaid"
    assert PaymentStatus.OVERDUE.value == "Overdue"


def test_student_model_accepts_valid_row() -> None:
    student = Student(
        student_id=1,
        name="Ananya Iyer",
        course="B.Sc Physics",
        email="ananya.iyer@institution.edu",
        total_fee=Decimal("80000.00"),
        paid_amount=Decimal("40000.00"),
        due_date=date(2026, 2, 1),
    )
    assert student.student_id == 1
    assert student.total_fee == Decimal("80000.00")


def test_student_model_rejects_non_positive_id() -> None:
    with pytest.raises(ValidationError):
        Student(
            student_id=0,
            name="X",
            course="Y",
            email="x@institution.edu",
            total_fee=Decimal("1"),
            paid_amount=Decimal("0"),
            due_date=date(2026, 1, 1),
        )


def test_fee_detail_model_with_computed_fields() -> None:
    detail = FeeDetail(
        student_id=4,
        name="Ananya Iyer",
        course="B.Sc Physics",
        total_fee=Decimal("80000.00"),
        paid_amount=Decimal("40000.00"),
        due_amount=Decimal("40000.00"),
        due_date=date(2026, 2, 1),
        payment_status=PaymentStatus.OVERDUE,
        days_overdue=12,
    )
    assert detail.payment_status == PaymentStatus.OVERDUE
    assert detail.days_overdue == 12
