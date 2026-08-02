"""Unit tests for API Pydantic schemas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from fee_management.api.schemas import StudentFeeDetailsResponse, UpdateFeeRequest, dump_camel
from fee_management.domain.payment_status import PaymentStatus


def test_update_fee_requires_at_least_one_field() -> None:
    with pytest.raises(ValidationError):
        UpdateFeeRequest.model_validate({})


def test_update_fee_accepts_partial_body() -> None:
    req = UpdateFeeRequest.model_validate({"paidAmount": 1000})
    assert req.paid_amount == Decimal("1000")
    assert req.total_fee is None


def test_update_fee_rejects_negative_amount() -> None:
    with pytest.raises(ValidationError):
        UpdateFeeRequest.model_validate({"totalFee": -1})


def test_fee_details_response_camel_case() -> None:
    body = dump_camel(
        StudentFeeDetailsResponse(
            student_id=4,
            name="Ananya Iyer",
            course="B.Sc Physics",
            total_fee=Decimal("80000.00"),
            paid_amount=Decimal("40000.00"),
            due_amount=Decimal("40000.00"),
            due_date=date(2026, 2, 1),
            payment_status=PaymentStatus.OVERDUE,
            days_overdue=12,
            row_version="AQIDBAUGBwg=",
        )
    )
    assert body["studentId"] == 4
    assert body["paymentStatus"] == "Overdue"
    assert body["totalFee"] == 80000.0
    assert body["rowVersion"] == "AQIDBAUGBwg="
    assert "student_id" not in body
