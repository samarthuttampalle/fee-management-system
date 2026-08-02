"""Integration test fixtures — Azure SQL (not Docker / testcontainers).

Loads connection settings from local.settings.json into the environment so
repositories use the same Azure SQL database as local development.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from fee_management.config import get_settings
from fee_management.data.db import get_engine, reset_engine_cache

ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = ROOT / "local.settings.json"


def _load_local_settings_into_env() -> None:
    if not SETTINGS_PATH.exists():
        pytest.skip(f"Missing {SETTINGS_PATH}; cannot run Azure SQL integration tests")

    data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    values = data.get("Values") or {}
    conn = (values.get("SQL_CONNECTION_STRING") or "").strip()
    if not conn or "YOUR_SERVER" in conn or "YOUR_SQL_" in conn:
        pytest.skip("SQL_CONNECTION_STRING is not configured for Azure SQL")

    for key, value in values.items():
        if value is not None and str(value) != "":
            os.environ[key] = str(value)

    get_settings.cache_clear()
    reset_engine_cache()


@pytest.fixture(scope="session")
def azure_sql_engine() -> Iterator[Engine]:
    """Session-scoped SQLAlchemy engine bound to Azure SQL."""
    _load_local_settings_into_env()
    engine = get_engine()
    # Smoke-check connectivity once per session
    with engine.connect() as conn:
        conn.exec_driver_sql("SELECT 1")
    yield engine
    reset_engine_cache()
    get_settings.cache_clear()
