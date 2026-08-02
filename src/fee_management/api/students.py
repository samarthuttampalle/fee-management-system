"""Student HTTP endpoints (TDD §8.1–§8.2 / §9.1–§9.2) with JWT + ownership (Phase 5)."""

from __future__ import annotations

import logging
from datetime import date

import azure.functions as func

from fee_management.api.errors import error_response, get_correlation_id, json_response
from fee_management.api.exception_mapping import map_exception_to_response
from fee_management.api.schemas import (
    PaymentStatusResponse,
    StudentFeeDetailsResponse,
    dump_camel,
)
from fee_management.auth.rbac import (
    ROLE_ADMINISTRATOR,
    ROLE_STUDENT,
    authorize_student_record_access,
    get_claims,
    require_role,
)
from fee_management.data.students_repository import StudentsRepository
from fee_management.domain.payment_status import (
    compute_days_overdue,
    compute_due_amount,
    compute_payment_status,
)

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


@bp.function_name(name="GetStudentFeeDetails")
@bp.route(route="students/{studentId:int}", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
@require_role(ROLE_STUDENT, ROLE_ADMINISTRATOR)
def get_student_fee_details(req: func.HttpRequest) -> func.HttpResponse:
    correlation_id = get_correlation_id(req)
    try:
        student_id = _parse_student_id(req.route_params.get("studentId"))
        if student_id is None:
            return error_response(
                status_code=400,
                code="INVALID_STUDENT_ID",
                message="studentId must be a positive integer",
                correlation_id=correlation_id,
            )

        claims = get_claims(req)
        logger.info(
            "GetStudentFeeDetails",
            extra={
                "correlation_id": correlation_id,
                "student_id": student_id,
                "roles": claims.get("roles"),
            },
        )

        row = _repo.get_by_id(student_id)
        forbidden = authorize_student_record_access(
            claims,
            student_aad_object_id=row.aad_object_id if row else None,
            student_found=row is not None,
            correlation_id=correlation_id,
        )
        if forbidden is not None:
            return forbidden

        if row is None:
            # Reachable only for Administrator (students already got 403)
            return error_response(
                status_code=404,
                code="STUDENT_NOT_FOUND",
                message=f"No student found with id {student_id}",
                correlation_id=correlation_id,
            )

        today = date.today()
        status = compute_payment_status(row.total_fee, row.paid_amount, row.due_date, today=today)
        body = StudentFeeDetailsResponse(
            student_id=row.student_id,
            name=row.name,
            course=row.course,
            total_fee=row.total_fee,
            paid_amount=row.paid_amount,
            due_amount=compute_due_amount(row.total_fee, row.paid_amount),
            due_date=row.due_date,
            payment_status=status,
            days_overdue=compute_days_overdue(row.due_date, payment_status=status, today=today),
            row_version=row.row_version_base64,
        )
        return json_response(
            dump_camel(body),
            correlation_id=correlation_id,
            extra_headers={"ETag": f'"{row.row_version_base64}"'},
        )
    except Exception as exc:
        return map_exception_to_response(exc, correlation_id)


@bp.function_name(name="GetStudentPaymentStatus")
@bp.route(
    route="students/{studentId:int}/payment-status",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
@require_role(ROLE_STUDENT, ROLE_ADMINISTRATOR)
def get_student_payment_status(req: func.HttpRequest) -> func.HttpResponse:
    correlation_id = get_correlation_id(req)
    try:
        student_id = _parse_student_id(req.route_params.get("studentId"))
        if student_id is None:
            return error_response(
                status_code=400,
                code="INVALID_STUDENT_ID",
                message="studentId must be a positive integer",
                correlation_id=correlation_id,
            )

        claims = get_claims(req)
        logger.info(
            "GetStudentPaymentStatus",
            extra={
                "correlation_id": correlation_id,
                "student_id": student_id,
                "roles": claims.get("roles"),
            },
        )

        cols = _repo.get_status_columns_by_id(student_id)
        forbidden = authorize_student_record_access(
            claims,
            student_aad_object_id=cols.aad_object_id if cols else None,
            student_found=cols is not None,
            correlation_id=correlation_id,
        )
        if forbidden is not None:
            return forbidden

        if cols is None:
            return error_response(
                status_code=404,
                code="STUDENT_NOT_FOUND",
                message=f"No student found with id {student_id}",
                correlation_id=correlation_id,
            )

        status = compute_payment_status(
            cols.total_fee, cols.paid_amount, cols.due_date, today=date.today()
        )
        body = PaymentStatusResponse(student_id=cols.student_id, payment_status=status)
        return json_response(dump_camel(body), correlation_id=correlation_id)
    except Exception as exc:
        return map_exception_to_response(exc, correlation_id)
