"""Unit tests for domain Pydantic schemas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from fee_management.domain.models import FeeDetail
from fee_management.domain.payment_status import PaymentStatus


def test_fee_detail_rejects_negative_amounts() -> None:
    with pytest.raises(ValidationError):
        FeeDetail(
            student_id=1,
            name="A",
            course="B",
            total_fee=Decimal("-1"),
            paid_amount=Decimal("0"),
            due_amount=Decimal("0"),
            due_date=date(2026, 1, 1),
            payment_status=PaymentStatus.PAID,
        )
