"""Unit tests for reminder email template and SendGrid mock mode."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import pytest

from fee_management.config import Settings
from fee_management.data.students_repository import OverdueStudent
from fee_management.durable.helpers import (
    aggregate_send_results,
    overdue_to_payload,
    reminder_instance_id,
)
from fee_management.notifications.email_templates import render_reminder_email
from fee_management.notifications.sendgrid_client import send_reminder


def test_render_reminder_email_matches_template() -> None:
    subject, body = render_reminder_email(
        {
            "name": "Ananya Iyer",
            "course": "B.Sc Physics",
            "totalFee": 80000,
            "paidAmount": 40000,
            "dueDate": "2026-02-01",
        }
    )
    assert subject == "Fee Payment Reminder — B.Sc Physics — Due 2026-02-01"
    assert "Dear Ananya Iyer," in body
    assert "₹80000.00" in body
    assert "₹40000.00" in body
    assert "Amount Due:    ₹40000.00" in body


def test_send_reminder_mock_logs_email(caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(
        sendgrid_mode="mock",
        sendgrid_from_email="noreply@institution.edu",
    )
    student = {
        "studentId": 4,
        "name": "Ananya Iyer",
        "email": "ananya.iyer@institution.edu",
        "course": "B.Sc Physics",
        "totalFee": 80000,
        "paidAmount": 40000,
        "dueDate": "2026-02-01",
    }
    with caplog.at_level(logging.INFO):
        send_reminder(student, settings=settings)
    assert any("Mock SendGrid reminder email" in r.message for r in caplog.records)


def test_aggregate_send_results() -> None:
    counts = aggregate_send_results(
        [
            {"studentId": 1, "status": "Sent"},
            {"studentId": 2, "status": "Failed"},
            {"studentId": 3, "status": "Sent"},
        ]
    )
    assert counts["totalOverdue"] == 3
    assert counts["sent"] == 2
    assert counts["failed"] == 1


def test_overdue_to_payload_is_json_safe() -> None:
    payload = overdue_to_payload(
        OverdueStudent(
            student_id=4,
            name="Ananya Iyer",
            email="ananya.iyer@institution.edu",
            course="B.Sc Physics",
            total_fee=Decimal("80000.00"),
            paid_amount=Decimal("40000.00"),
            due_date=date(2026, 2, 1),
        )
    )
    assert payload["studentId"] == 4
    assert payload["dueDate"] == "2026-02-01"
    assert isinstance(payload["totalFee"], float)


def test_reminder_instance_id() -> None:
    assert reminder_instance_id(date(2026, 8, 1)) == "reminder-2026-08-01"
