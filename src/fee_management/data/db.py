"""SQLAlchemy engine factory, connection helpers, and transient-error retry."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import TypeVar

import pyodbc
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError, OperationalError

from fee_management.config import Settings, get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

_RETRY_BACKOFF_SECONDS = (0.5, 1.0, 2.0)
_DEADLOCK_SQLSTATE = "40001"
_DEADLOCK_ERROR_NUMBER = 1205


@lru_cache
def get_engine(connection_string: str | None = None) -> Engine:
    """
    Create (or return cached) SQLAlchemy engine for Azure SQL / SQL Server.

    Pool settings follow TDD §17.1: pool_size=5, max_overflow=10,
    pool_pre_ping=True, pool_recycle=280.

    Uses a pyodbc creator so the ODBC connection string from App Settings /
    local.settings.json is passed through unchanged (avoids URL-encoding issues
    with Driver={...} braces).
    """
    settings = get_settings()
    odbc = connection_string or settings.sql_connection_string
    if not odbc:
        raise RuntimeError(
            "SQL_CONNECTION_STRING is not configured. "
            "Set it in local.settings.json or the process environment."
        )

    def _creator() -> pyodbc.Connection:
        return pyodbc.connect(odbc, timeout=30)

    return create_engine(
        "mssql+pyodbc://",
        creator=_creator,
        pool_size=settings.sql_pool_size,
        max_overflow=settings.sql_max_overflow,
        pool_pre_ping=True,
        pool_recycle=settings.sql_pool_recycle,
        future=True,
    )


def reset_engine_cache() -> None:
    """Clear the cached engine (used by tests)."""
    get_engine.cache_clear()


@contextmanager
def connection(*, engine: Engine | None = None) -> Iterator[Connection]:
    """Yield a SQLAlchemy connection; commits on success, rolls back on error."""
    eng = engine or get_engine()
    with eng.connect() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def ping(timeout_seconds: float = 2.0, *, engine: Engine | None = None) -> bool:
    """
    Liveness check used by GET /health.

    Returns True if ``SELECT 1`` succeeds within the timeout window.
    """
    eng = engine or get_engine()
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.warning("Database ping failed", exc_info=True)
        return False


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, OperationalError):
        return True
    if isinstance(exc, DBAPIError) and exc.connection_invalidated:
        return True

    # SQL Server deadlock victim (1205)
    orig = getattr(exc, "orig", None)
    args = getattr(orig, "args", ()) if orig is not None else ()
    if len(args) >= 1 and args[0] == _DEADLOCK_ERROR_NUMBER:
        return True
    text_blob = " ".join(str(a) for a in args).lower()
    return "deadlock" in text_blob or _DEADLOCK_SQLSTATE in text_blob


def with_db_retry(operation: Callable[[], T], *, attempts: int = 3) -> T:
    """
    Retry ``operation`` on transient SQL errors / deadlocks.

    Backoff: 0.5s, 1s, 2s (TDD §16.5). Permanent errors (e.g. IntegrityError)
    are not retried.
    """
    last_exc: BaseException | None = None
    for attempt in range(attempts):
        try:
            return operation()
        except Exception as exc:
            last_exc = exc
            if not _is_transient(exc) or attempt >= attempts - 1:
                raise
            delay = _RETRY_BACKOFF_SECONDS[min(attempt, len(_RETRY_BACKOFF_SECONDS) - 1)]
            logger.warning(
                "Transient DB error on attempt %s/%s; retrying in %ss",
                attempt + 1,
                attempts,
                delay,
                exc_info=True,
            )
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc


def build_settings_from_env() -> Settings:
    """Convenience for callers that need a fresh Settings instance."""
    get_settings.cache_clear()
    return get_settings()
