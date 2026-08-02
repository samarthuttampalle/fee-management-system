"""Apply local-dev AadObjectId link for student self-access testing."""

from __future__ import annotations

import json
from pathlib import Path

import pyodbc

ROOT = Path(__file__).resolve().parents[1]
OID = "11111111-1111-1111-1111-111111111111"


def main() -> None:
    values = json.loads((ROOT / "local.settings.json").read_text(encoding="utf-8"))["Values"]
    conn_str = values["SQL_CONNECTION_STRING"]
    with pyodbc.connect(conn_str, autocommit=True) as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE dbo.Students SET AadObjectId = ? WHERE StudentID = ?",
            OID,
            4,
        )
        print(f"updated_rows={cur.rowcount}")
        cur.execute("SELECT StudentID, CAST(AadObjectId AS varchar(36)) FROM dbo.Students WHERE StudentID = 4")
        row = cur.fetchone()
        print(f"student_id={row[0]} aad_object_id={row[1]}")


if __name__ == "__main__":
    main()
