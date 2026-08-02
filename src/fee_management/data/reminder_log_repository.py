"""All SQL access for dbo.ReminderLog (reminder workflow audit)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from fee_management.data.db import connection as db_connection
from fee_management.data.db import get_engine, with_db_retry


@dataclass(frozen=True, slots=True)
class ReminderLogEntry:
    student_id: int
    status: str  # Sent | Failed
    error_detail: str | None = None


@dataclass(frozen=True, slots=True)
class ReminderLogRecord:
    reminder_log_id: int
    student_id: int
    sent_at: datetime
    status: str
    error_detail: str | None


class ReminderLogRepository:
    """Repository for dbo.ReminderLog."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine

    def _engine_or_default(self) -> Engine:
        return self._engine or get_engine()

    def insert_many(self, entries: list[ReminderLogEntry]) -> int:
        """Bulk-insert reminder outcomes; returns number of rows inserted."""
        if not entries:
            return 0

        def _run() -> int:
            stmt = text("""
                INSERT INTO dbo.ReminderLog (StudentID, Status, ErrorDetail)
                VALUES (:student_id, :status, :error_detail)
                """)
            with db_connection(engine=self._engine_or_default()) as conn:
                for entry in entries:
                    if entry.status not in ("Sent", "Failed"):
                        raise ValueError(f"Invalid ReminderLog status: {entry.status}")
                    conn.execute(
                        stmt,
                        {
                            "student_id": entry.student_id,
                            "status": entry.status,
                            "error_detail": entry.error_detail,
                        },
                    )
                return len(entries)

        return with_db_retry(_run)

    def list_recent(self, *, limit: int = 50) -> list[ReminderLogRecord]:
        """Newest ReminderLog rows (for smoke/integration checks)."""

        def _run() -> list[ReminderLogRecord]:
            stmt = text("""
                SELECT ReminderLogID, StudentID, SentAt, Status, ErrorDetail
                FROM dbo.ReminderLog
                ORDER BY ReminderLogID DESC
                OFFSET 0 ROWS FETCH NEXT :limit ROWS ONLY
                """)
            with db_connection(engine=self._engine_or_default()) as conn:
                rows = conn.execute(stmt, {"limit": limit}).mappings().all()
                return [_map_row(r) for r in rows]

        return with_db_retry(_run)


def _map_row(row: Any) -> ReminderLogRecord:
    return ReminderLogRecord(
        reminder_log_id=int(row["ReminderLogID"]),
        student_id=int(row["StudentID"]),
        sent_at=row["SentAt"],
        status=str(row["Status"]),
        error_detail=None if row["ErrorDetail"] is None else str(row["ErrorDetail"]),
    )


_default_repo = ReminderLogRepository()


def insert_many(entries: list[ReminderLogEntry]) -> int:
    return _default_repo.insert_many(entries)
