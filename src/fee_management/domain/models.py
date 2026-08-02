"""Pydantic domain models for fee records (framework-free aside from Pydantic)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from fee_management.domain.payment_status import PaymentStatus


class Student(BaseModel):
    """Student fee record as represented in the domain layer."""

    model_config = ConfigDict(from_attributes=True)

    student_id: int = Field(..., ge=1)
    name: str
    course: str
    email: str
    total_fee: Decimal = Field(..., ge=0)
    paid_amount: Decimal = Field(..., ge=0)
    due_date: date
    aad_object_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FeeDetail(BaseModel):
    """Fee details plus computed payment status for API/service responses."""

    model_config = ConfigDict(from_attributes=True)

    student_id: int = Field(..., ge=1)
    name: str
    course: str
    total_fee: Decimal = Field(..., ge=0)
    paid_amount: Decimal = Field(..., ge=0)
    due_amount: Decimal = Field(..., ge=0)
    due_date: date
    payment_status: PaymentStatus
    days_overdue: int | None = None
