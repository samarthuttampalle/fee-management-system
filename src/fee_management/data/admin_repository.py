"""All SQL access for the Administrators table (auth lookups)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine, Row

from fee_management.data.db import connection as db_connection
from fee_management.data.db import get_engine, with_db_retry


@dataclass(frozen=True, slots=True)
class AdministratorRecord:
    admin_id: int
    name: str
    role: str
    aad_object_id: UUID | None
    created_at: datetime


def _as_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _map_admin(row: Row[Any]) -> AdministratorRecord:
    return AdministratorRecord(
        admin_id=int(row.AdminID),
        name=str(row.Name),
        role=str(row.Role),
        aad_object_id=_as_uuid(row.AadObjectId),
        created_at=row.CreatedAt,
    )


class AdminRepository:
    """Repository for dbo.Administrators."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine

    def _engine_or_default(self) -> Engine:
        return self._engine or get_engine()

    def get_by_id(self, admin_id: int) -> AdministratorRecord | None:
        """Return an administrator by primary key."""

        def _run() -> AdministratorRecord | None:
            stmt = text("""
                SELECT AdminID, Name, Role, AadObjectId, CreatedAt
                FROM dbo.Administrators
                WHERE AdminID = :admin_id
                """)
            with db_connection(engine=self._engine_or_default()) as conn:
                row = conn.execute(stmt, {"admin_id": admin_id}).first()
                if row is None:
                    return None
                return _map_admin(row)

        return with_db_retry(_run)

    def get_by_aad_object_id(self, aad_object_id: UUID | str) -> AdministratorRecord | None:
        """Lookup used when mapping Entra oid → administrator row."""

        def _run() -> AdministratorRecord | None:
            stmt = text("""
                SELECT AdminID, Name, Role, AadObjectId, CreatedAt
                FROM dbo.Administrators
                WHERE AadObjectId = :aad_object_id
                """)
            with db_connection(engine=self._engine_or_default()) as conn:
                row = conn.execute(stmt, {"aad_object_id": str(aad_object_id)}).first()
                if row is None:
                    return None
                return _map_admin(row)

        return with_db_retry(_run)

    def list_all(self) -> list[AdministratorRecord]:
        """Return all administrators (small table; used in diagnostics/tests)."""

        def _run() -> list[AdministratorRecord]:
            stmt = text("""
                SELECT AdminID, Name, Role, AadObjectId, CreatedAt
                FROM dbo.Administrators
                ORDER BY AdminID
                """)
            with db_connection(engine=self._engine_or_default()) as conn:
                rows = conn.execute(stmt).all()
                return [_map_admin(r) for r in rows]

        return with_db_retry(_run)


_default_repo = AdminRepository()


def get_by_id(admin_id: int) -> AdministratorRecord | None:
    return _default_repo.get_by_id(admin_id)


def get_by_aad_object_id(aad_object_id: UUID | str) -> AdministratorRecord | None:
    return _default_repo.get_by_aad_object_id(aad_object_id)


def list_all() -> list[AdministratorRecord]:
    return _default_repo.list_all()
