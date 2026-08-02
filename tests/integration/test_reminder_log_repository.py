"""Integration tests for ReminderLog repository against Azure SQL."""

from __future__ import annotations

import pytest
from sqlalchemy.engine import Engine

from fee_management.data.reminder_log_repository import ReminderLogEntry, ReminderLogRepository
from fee_management.data.students_repository import StudentsRepository


@pytest.fixture
def reminder_repo(azure_sql_engine: Engine) -> ReminderLogRepository:
    return ReminderLogRepository(engine=azure_sql_engine)


@pytest.fixture
def students_repo(azure_sql_engine: Engine) -> StudentsRepository:
    return StudentsRepository(engine=azure_sql_engine)


def test_list_overdue_non_empty_against_seed(students_repo: StudentsRepository) -> None:
    overdue = students_repo.list_overdue()
    assert len(overdue) >= 1
    assert all(s.email for s in overdue)


def test_reminder_log_insert_and_list(reminder_repo: ReminderLogRepository) -> None:
    inserted = reminder_repo.insert_many(
        [
            ReminderLogEntry(student_id=4, status="Sent", error_detail=None),
            ReminderLogEntry(student_id=5, status="Failed", error_detail="mock failure"),
        ]
    )
    assert inserted == 2
    recent = reminder_repo.list_recent(limit=10)
    assert any(r.student_id == 4 and r.status == "Sent" for r in recent)
    assert any(r.student_id == 5 and r.status == "Failed" for r in recent)
