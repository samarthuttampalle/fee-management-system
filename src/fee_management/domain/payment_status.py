"""Payment status computation — pure domain logic (TDD §10).

Status is computed at read time and never persisted.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum


class PaymentStatus(str, Enum):  # noqa: UP042 — TDD §10.4 specifies str, Enum (not StrEnum)
    """API-facing payment status values (camelCase string values per §8 / §10)."""

    PAID = "Paid"
    PARTIALLY_PAID = "PartiallyPaid"
    OVERDUE = "Overdue"


def compute_payment_status(
    total_fee: Decimal,
    paid_amount: Decimal,
    due_date: date,
    today: date | None = None,
) -> PaymentStatus:
    """
    Compute Paid / PartiallyPaid / Overdue from fee amounts and due date.

    Preconditions:
    - ``total_fee`` and ``paid_amount`` are non-negative Decimals.
    - ``due_date`` is a calendar date (no time component).
    - ``today`` should be a UTC calendar date when provided; callers are
      responsible for passing a consistent clock per request. If omitted,
      ``date.today()`` is used (local date of the process).

    Rules (TDD §10.1 / §10.3):
    - Paid: ``paid_amount >= total_fee``
    - Overdue: underpaid and ``due_date < today``
    - PartiallyPaid: underpaid and not yet past due (includes unpaid, not due)
    """
    today = today or date.today()

    if paid_amount >= total_fee:
        return PaymentStatus.PAID
    if due_date < today:
        return PaymentStatus.OVERDUE
    return PaymentStatus.PARTIALLY_PAID


def compute_due_amount(total_fee: Decimal, paid_amount: Decimal) -> Decimal:
    """
    Outstanding balance, floored at zero (overpayment does not yield negative due).

    Assumes ``total_fee`` and ``paid_amount`` are Decimals suitable for money.
    """
    outstanding = total_fee - paid_amount
    return outstanding if outstanding > 0 else Decimal("0.00")


def compute_days_overdue(
    due_date: date,
    *,
    payment_status: PaymentStatus,
    today: date | None = None,
) -> int | None:
    """
    Number of calendar days past due when status is Overdue; otherwise None.

    ``today`` is injectable for testability (same clock contract as
    ``compute_payment_status``).
    """
    if payment_status is not PaymentStatus.OVERDUE:
        return None
    today = today or date.today()
    return (today - due_date).days
