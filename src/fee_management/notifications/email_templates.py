"""Reminder email subject/body rendering (TDD §11.5)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from fee_management.domain.payment_status import compute_due_amount


def _money(value: Decimal | float | int | str) -> str:
    amount = Decimal(str(value))
    return f"{amount.quantize(Decimal('0.01'))}"


def _due_date_str(value: date | str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def render_reminder_email(student: dict[str, Any]) -> tuple[str, str]:
    """
    Return ``(subject, body)`` for an overdue fee reminder.

    Expected keys (camelCase from activity payload): name, course, email,
    totalFee, paidAmount, dueDate.
    """
    name = str(student["name"])
    course = str(student["course"])
    total_fee = Decimal(str(student["totalFee"]))
    paid_amount = Decimal(str(student["paidAmount"]))
    due_date = _due_date_str(student["dueDate"])
    due_amount = compute_due_amount(total_fee, paid_amount)

    subject = f"Fee Payment Reminder — {course} — Due {due_date}"
    body = (
        f"Dear {name},\n"
        f"\n"
        f"This is a reminder that your fee payment for {course} is overdue.\n"
        f"\n"
        f"  Total Fee:     ₹{_money(total_fee)}\n"
        f"  Paid Amount:   ₹{_money(paid_amount)}\n"
        f"  Amount Due:    ₹{_money(due_amount)}\n"
        f"  Original Due Date: {due_date}\n"
        f"\n"
        f"Please make the outstanding payment at your earliest convenience to avoid\n"
        f"any disruption to your enrollment. If you have already paid, please\n"
        f"disregard this message — payments can take up to 2 business days to reflect.\n"
        f"\n"
        f"Regards,\n"
        f"Accounts Office\n"
    )
    return subject, body
