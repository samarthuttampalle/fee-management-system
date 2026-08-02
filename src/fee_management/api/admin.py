"""Admin HTTP endpoints (TDD §8.3–§8.4 / §9.3–§9.4) with Administrator RBAC."""

from __future__ import annotations

import base64
import logging
from datetime import date
from decimal import Decimal

import azure.functions as func

from fee_management.api.errors import error_response, get_correlation_id, json_response
from fee_management.api.exception_mapping import map_exception_to_response
from fee_management.api.schemas import (
    AdminStudentListItem,
    AdminStudentListResponse,
    UpdateFeeRequest,
    UpdateFeeResponse,
    dump_camel,
)
from fee_management.auth.rbac import ROLE_ADMINISTRATOR, get_claims, require_role
from fee_management.data.students_repository import FeeUpdateFields, StudentsRepository
from fee_management.domain.exceptions import FeeConstraintError, StudentNotFoundError
from fee_management.domain.payment_status import PaymentStatus, compute_payment_status

bp = func.Blueprint()
logger = logging.getLogger(__name__)
_repo = StudentsRepository()


def _parse_student_id(raw: str | None) -> int | None:
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return value


def _parse_if_match(header_value: str | None) -> bytes | None:
    if header_value is None or not header_value.strip():
        return None
    token = header_value.strip()
    if token.startswith('"') and token.endswith('"'):
        token = token[1:-1]
    try:
        return base64.b64decode(token, validate=True)
    except Exception as exc:
        raise ValueError("If-Match must be a base64-encoded RowVersion") from exc


@bp.function_name(name="ListStudentsForAdmin")
@bp.route(route="mgmt/students", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@require_role(ROLE_ADMINISTRATOR)
def list_students_for_admin(req: func.HttpRequest) -> func.HttpResponse:
    correlation_id = get_correlation_id(req)
    try:
        claims = get_claims(req)
        course = req.params.get("course") or None
        status_raw = req.params.get("status") or None
        page_raw = req.params.get("page") or "1"
        page_size_raw = req.params.get("pageSize") or "25"

        try:
            page = int(page_raw)
            page_size = int(page_size_raw)
        except ValueError as exc:
            raise ValueError("page and pageSize must be integers") from exc

        status: PaymentStatus | None = None
        if status_raw:
            try:
                status = PaymentStatus(status_raw)
            except ValueError as exc:
                raise ValueError("status must be one of Paid, PartiallyPaid, Overdue") from exc

        logger.info(
            "ListStudentsForAdmin",
            extra={
                "correlation_id": correlation_id,
                "course": course,
                "status": status_raw,
                "page": page,
                "page_size": page_size,
                "roles": claims.get("roles"),
            },
        )

        result = _repo.list_paginated(course=course, status=status, page=page, page_size=page_size)

        body = AdminStudentListResponse(
            page=result.page,
            page_size=result.page_size,
            total_count=result.total_count,
            items=[
                AdminStudentListItem(
                    student_id=i.student_id,
                    name=i.name,
                    course=i.course,
                    total_fee=i.total_fee,
                    paid_amount=i.paid_amount,
                    due_date=i.due_date,
                    payment_status=i.payment_status,
                )
                for i in result.items
            ],
        )
        return json_response(dump_camel(body), correlation_id=correlation_id)
    except Exception as exc:
        return map_exception_to_response(exc, correlation_id)


@bp.function_name(name="UpdateStudentFee")
@bp.route(
    route="mgmt/students/{studentId:int}/fee",
    methods=["PUT"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
@require_role(ROLE_ADMINISTRATOR)
def update_student_fee(req: func.HttpRequest) -> func.HttpResponse:
    correlation_id = get_correlation_id(req)
    try:
        claims = get_claims(req)
        student_id = _parse_student_id(req.route_params.get("studentId"))
        if student_id is None:
            return error_response(
                status_code=400,
                code="INVALID_STUDENT_ID",
                message="studentId must be a positive integer",
                correlation_id=correlation_id,
            )

        try:
            payload = req.get_json()
        except ValueError as exc:
            raise ValueError("Request body must be valid JSON") from exc

        update = UpdateFeeRequest.model_validate(payload or {})
        expected_rv = _parse_if_match(req.headers.get("If-Match"))

        current = _repo.get_by_id(student_id)
        if current is None:
            raise StudentNotFoundError(student_id)

        new_total = update.total_fee if update.total_fee is not None else current.total_fee
        new_paid = update.paid_amount if update.paid_amount is not None else current.paid_amount
        if new_paid > new_total * Decimal("1.5"):
            raise FeeConstraintError("paidAmount must be <= totalFee * 1.5")

        logger.info(
            "UpdateStudentFee",
            extra={
                "correlation_id": correlation_id,
                "student_id": student_id,
                "roles": claims.get("roles"),
                "has_if_match": expected_rv is not None,
            },
        )

        updated = _repo.update_fee(
            student_id,
            FeeUpdateFields(
                total_fee=update.total_fee,
                paid_amount=update.paid_amount,
                due_date=update.due_date,
            ),
            expected_row_version=expected_rv,
        )

        status = compute_payment_status(
            updated.total_fee, updated.paid_amount, updated.due_date, today=date.today()
        )
        body = UpdateFeeResponse(
            student_id=updated.student_id,
            name=updated.name,
            total_fee=updated.total_fee,
            paid_amount=updated.paid_amount,
            due_date=updated.due_date,
            payment_status=status,
            updated_at=updated.updated_at,
            row_version=updated.row_version_base64,
        )
        return json_response(
            dump_camel(body),
            correlation_id=correlation_id,
            extra_headers={"ETag": f'"{updated.row_version_base64}"'},
        )
    except Exception as exc:
        return map_exception_to_response(exc, correlation_id)
