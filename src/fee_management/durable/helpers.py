"""Pure helpers for the reminder Durable workflow (easy to unit-test)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from fee_management.data.students_repository import OverdueStudent


def overdue_to_payload(student: OverdueStudent) -> dict[str, Any]:
    """Serialize an overdue student for Durable activity I/O (JSON-safe)."""
    return {
        "studentId": student.student_id,
        "name": student.name,
        "email": student.email,
        "course": student.course,
        "totalFee": float(student.total_fee),
        "paidAmount": float(student.paid_amount),
        "dueDate": student.due_date.isoformat(),
    }


def aggregate_send_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Fan-in counts from SendReminderEmail activity outputs."""
    sent = sum(1 for r in results if r.get("status") == "Sent")
    failed = sum(1 for r in results if r.get("status") == "Failed")
    return {
        "totalOverdue": len(results),
        "sent": sent,
        "failed": failed,
        "results": results,
    }


def build_summary(
    *,
    total_overdue: int,
    sent: int,
    failed: int,
    duration_ms: int,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Payload for LogReminderSummary."""
    return {
        "totalOverdue": total_overdue,
        "sent": sent,
        "failed": failed,
        "durationMs": duration_ms,
        "results": results,
    }


def reminder_instance_id(today: date) -> str:
    """Deterministic daily orchestration id (TDD §9.6)."""
    return f"reminder-{today.isoformat()}"


def parse_money(value: Any) -> Decimal:
    return Decimal(str(value))
