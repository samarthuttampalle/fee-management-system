"""Durable activities: QueryOverdueStudents, SendReminderEmail, LogReminderSummary."""

from __future__ import annotations

import logging
from typing import Any

from fee_management.data.reminder_log_repository import ReminderLogEntry, ReminderLogRepository
from fee_management.data.students_repository import StudentsRepository
from fee_management.durable.bp import bp
from fee_management.durable.helpers import overdue_to_payload
from fee_management.notifications.sendgrid_client import SendGridError, send_reminder
from fee_management.telemetry.context import bind_correlation_id

logger = logging.getLogger(__name__)

_students_repo = StudentsRepository()
_reminder_repo = ReminderLogRepository()


def _bind_from_payload(payload: Any) -> None:
    if isinstance(payload, dict):
        cid = payload.get("correlationId") or payload.get("correlation_id")
        if cid:
            bind_correlation_id(str(cid))


@bp.function_name(name="QueryOverdueStudents")
@bp.activity_trigger(input_name="payload")
def query_overdue_students(payload: Any) -> Any:
    """Execute overdue-selection SQL (§10.5) and return serializable student dicts."""
    _bind_from_payload(payload)
    overdue = _students_repo.list_overdue()
    result = [overdue_to_payload(s) for s in overdue]
    logger.info(
        "QueryOverdueStudents completed",
        extra={"event": "QueryOverdueStudents", "totalOverdue": len(result)},
    )
    return result


@bp.function_name(name="SendReminderEmail")
@bp.activity_trigger(input_name="student")
def send_reminder_email(student: Any) -> Any:
    """
    Send one reminder email; always returns Sent/Failed so fan-out isolation holds.

    Transient SendGrid failures are retried inside the client (3× / exponential backoff,
    matching §16.5). Unexpected exceptions are re-raised so Durable RetryOptions can retry.
    """
    _bind_from_payload(student)
    student_id = int(student["studentId"])
    try:
        send_reminder(student)
        logger.info(
            "Reminder email sent",
            extra={"event": "ReminderEmailSent", "studentId": student_id},
        )
        return {"studentId": student_id, "status": "Sent", "error": None}
    except SendGridError as exc:
        logger.error(
            "Reminder email failed",
            extra={
                "event": "ReminderEmailFailed",
                "studentId": student_id,
                "error": str(exc),
            },
        )
        return {"studentId": student_id, "status": "Failed", "error": str(exc)}


@bp.function_name(name="LogReminderSummary")
@bp.activity_trigger(input_name="summary")
def log_reminder_summary(summary: Any) -> Any:
    """Structured log + ReminderLog bulk insert (TDD §9.10)."""
    _bind_from_payload(summary)
    results = list(summary.get("results") or [])
    entries = [
        ReminderLogEntry(
            student_id=int(r["studentId"]),
            status=str(r["status"]),
            error_detail=None if r.get("error") in (None, "") else str(r.get("error")),
        )
        for r in results
        if r.get("status") in ("Sent", "Failed")
    ]
    inserted = _reminder_repo.insert_many(entries)

    logger.info(
        "Reminder run completed",
        extra={
            "event": "ReminderRunCompleted",
            "totalOverdue": summary.get("totalOverdue"),
            "sent": summary.get("sent"),
            "failed": summary.get("failed"),
            "durationMs": summary.get("durationMs"),
            "reminderLogInserted": inserted,
        },
    )
    return {
        "totalOverdue": summary.get("totalOverdue", 0),
        "sent": summary.get("sent", 0),
        "failed": summary.get("failed", 0),
        "durationMs": summary.get("durationMs", 0),
        "reminderLogInserted": inserted,
        "correlationId": summary.get("correlationId"),
    }
