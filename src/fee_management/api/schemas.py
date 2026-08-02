"""Pydantic request/response schemas for HTTP APIs (camelCase JSON per §27.9)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from fee_management.domain.payment_status import PaymentStatus


class CamelModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        ser_json_by_alias=True,
    )


class StudentFeeDetailsResponse(CamelModel):
    student_id: int = Field(alias="studentId")
    name: str
    course: str
    total_fee: Decimal = Field(alias="totalFee")
    paid_amount: Decimal = Field(alias="paidAmount")
    due_amount: Decimal = Field(alias="dueAmount")
    due_date: date = Field(alias="dueDate")
    payment_status: PaymentStatus = Field(alias="paymentStatus")
    days_overdue: int | None = Field(default=None, alias="daysOverdue")
    row_version: str = Field(
        ...,
        alias="rowVersion",
        description="Base64-encoded RowVersion for If-Match on subsequent PUT",
    )

    @field_serializer("total_fee", "paid_amount", "due_amount")
    def _ser_money(self, value: Decimal) -> float:
        return float(value)


class PaymentStatusResponse(CamelModel):
    student_id: int = Field(alias="studentId")
    payment_status: PaymentStatus = Field(alias="paymentStatus")


class AdminStudentListItem(CamelModel):
    student_id: int = Field(alias="studentId")
    name: str
    course: str
    total_fee: Decimal = Field(alias="totalFee")
    paid_amount: Decimal = Field(alias="paidAmount")
    due_date: date = Field(alias="dueDate")
    payment_status: PaymentStatus = Field(alias="paymentStatus")

    @field_serializer("total_fee", "paid_amount")
    def _ser_money(self, value: Decimal) -> float:
        return float(value)


class AdminStudentListResponse(CamelModel):
    page: int
    page_size: int = Field(alias="pageSize")
    total_count: int = Field(alias="totalCount")
    items: list[AdminStudentListItem]


class UpdateFeeRequest(CamelModel):
    total_fee: Decimal | None = Field(default=None, alias="totalFee", ge=0)
    paid_amount: Decimal | None = Field(default=None, alias="paidAmount", ge=0)
    due_date: date | None = Field(default=None, alias="dueDate")

    @model_validator(mode="after")
    def at_least_one_field(self) -> UpdateFeeRequest:
        if self.total_fee is None and self.paid_amount is None and self.due_date is None:
            raise ValueError("At least one of totalFee, paidAmount, dueDate must be provided")
        return self


class UpdateFeeResponse(CamelModel):
    student_id: int = Field(alias="studentId")
    name: str
    total_fee: Decimal = Field(alias="totalFee")
    paid_amount: Decimal = Field(alias="paidAmount")
    due_date: date = Field(alias="dueDate")
    payment_status: PaymentStatus = Field(alias="paymentStatus")
    updated_at: datetime = Field(alias="updatedAt")
    row_version: str = Field(
        ...,
        alias="rowVersion",
        description="Base64-encoded RowVersion for If-Match on subsequent PUT",
    )

    @field_serializer("total_fee", "paid_amount")
    def _ser_money(self, value: Decimal) -> float:
        return float(value)

    @field_serializer("updated_at")
    def _ser_updated_at(self, value: datetime) -> str:
        # Ensure Zulu-style UTC suffix in responses
        if value.tzinfo is None:
            return value.isoformat(timespec="milliseconds") + "Z"
        return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


class HealthResponse(CamelModel):
    status: str
    db_reachable: bool = Field(alias="dbReachable")
    timestamp: datetime

    @field_serializer("timestamp")
    def _ser_ts(self, value: datetime) -> str:
        if value.tzinfo is None:
            return value.isoformat(timespec="milliseconds") + "Z"
        return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def dump_camel(model: BaseModel) -> dict[str, Any]:
    """Serialize a response model to a camelCase JSON-compatible dict."""
    return model.model_dump(by_alias=True, mode="json")
