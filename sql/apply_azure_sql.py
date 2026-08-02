"""Apply sql/001–003 scripts to Azure SQL using SQL_CONNECTION_STRING.

Usage (from repo root, venv activated):
    python sql/apply_azure_sql.py

Reads connection string from:
  1) SQL_CONNECTION_STRING environment variable, or
  2) local.settings.json Values.SQL_CONNECTION_STRING
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pyodbc

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = Path(__file__).resolve().parent
SCRIPT_FILES = [
    "001_create_schema.sql",
    "002_seed_sample_data.sql",
    "003_indexes_constraints.sql",
]


def load_connection_string() -> str:
    env_value = __import__("os").environ.get("SQL_CONNECTION_STRING", "").strip()
    if env_value and "YOUR_SERVER" not in env_value and "YOUR_SQL_" not in env_value:
        return env_value

    settings_path = ROOT / "local.settings.json"
    if not settings_path.exists():
        raise SystemExit(
            "No SQL_CONNECTION_STRING found. Set it in the environment or in local.settings.json."
        )

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    conn = (data.get("Values") or {}).get("SQL_CONNECTION_STRING", "").strip()
    if not conn or "YOUR_SERVER" in conn or "YOUR_SQL_" in conn:
        raise SystemExit(
            "Update local.settings.json with your Azure SQL connection string "
            "(replace YOUR_SERVER / YOUR_SQL_USER / YOUR_SQL_PASSWORD), then re-run."
        )
    return conn


def split_batches(sql_text: str) -> list[str]:
    """Split on GO batch separators (sqlcmd-style), ignoring GO inside comments loosely."""
    parts = re.split(r"(?im)^\s*GO\s*$", sql_text)
    return [p.strip() for p in parts if p.strip()]


def apply_script(cursor: pyodbc.Cursor, path: Path) -> None:
    print(f"Applying {path.name} ...")
    batches = split_batches(path.read_text(encoding="utf-8"))
    for i, batch in enumerate(batches, start=1):
        try:
            cursor.execute(batch)
            while cursor.nextset():
                pass
        except pyodbc.Error as exc:
            raise RuntimeError(f"{path.name} batch {i} failed:\n{batch[:200]}...\n{exc}") from exc
    print(f"  OK ({len(batches)} batch(es))")


def verify(cursor: pyodbc.Cursor) -> None:
    cursor.execute("SELECT COUNT(*) FROM dbo.Students")
    student_count = int(cursor.fetchone()[0])
    cursor.execute("SELECT COUNT(*) FROM dbo.Administrators")
    admin_count = int(cursor.fetchone()[0])
    cursor.execute("""
        SELECT COUNT(*) FROM sys.indexes
        WHERE name IN (
            'UX_Students_AadObjectId',
            'IX_Students_DueDate',
            'IX_Students_Course',
            'UX_Administrators_AadObjectId',
            'IX_ReminderLog_StudentID_SentAt'
        )
        """)
    index_count = int(cursor.fetchone()[0])
    cursor.execute("""
        SELECT COUNT(*) FROM sys.triggers
        WHERE name = 'trg_Students_UpdatedAt' AND is_disabled = 0
        """)
    trigger_count = int(cursor.fetchone()[0])
    cursor.execute("""
        SELECT COUNT(*) FROM sys.columns
        WHERE object_id = OBJECT_ID('dbo.Students') AND name = 'Email'
        """)
    email_col = int(cursor.fetchone()[0])

    print()
    print("Verification:")
    print(f"  Students rows        : {student_count} (expected 20)")
    print(f"  Administrators rows  : {admin_count} (expected 3)")
    print(f"  Expected indexes     : {index_count} (expected 5)")
    print(f"  UpdatedAt trigger    : {trigger_count} (expected 1)")
    print(f"  Students.Email column: {email_col} (expected 1)")

    errors: list[str] = []
    if student_count != 20:
        errors.append(f"Students count is {student_count}, expected 20")
    if admin_count != 3:
        errors.append(f"Administrators count is {admin_count}, expected 3")
    if index_count != 5:
        errors.append(f"Index count is {index_count}, expected 5")
    if trigger_count != 1:
        errors.append("trg_Students_UpdatedAt missing or disabled")
    if email_col != 1:
        errors.append("Students.Email column missing")

    if errors:
        raise SystemExit("Verification FAILED:\n  - " + "\n  - ".join(errors))
    print("\nPhase 1 verification PASSED.")


def main() -> int:
    conn_str = load_connection_string()
    print("Connecting to Azure SQL ...")
    with pyodbc.connect(conn_str, autocommit=True) as conn:
        cursor = conn.cursor()
        for name in SCRIPT_FILES:
            apply_script(cursor, SQL_DIR / name)
        verify(cursor)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except pyodbc.Error as exc:
        print(f"Azure SQL error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
