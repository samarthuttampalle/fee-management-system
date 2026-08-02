"""Apply sql/006_drop_superadmin_role.sql against Azure SQL (local.settings.json)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pyodbc

ROOT = Path(__file__).resolve().parents[1]
SQL_FILE = Path(__file__).resolve().parent / "006_drop_superadmin_role.sql"


def main() -> None:
    values = json.loads((ROOT / "local.settings.json").read_text(encoding="utf-8"))["Values"]
    sql_text = SQL_FILE.read_text(encoding="utf-8")
    batches = [b.strip() for b in re.split(r"(?im)^\s*GO\s*$", sql_text) if b.strip()]
    with pyodbc.connect(values["SQL_CONNECTION_STRING"], autocommit=True, timeout=60) as conn:
        cur = conn.cursor()
        for batch in batches:
            cur.execute(batch)
            while cur.nextset():
                pass
    print("Applied 006_drop_superadmin_role.sql")


if __name__ == "__main__":
    main()
