"""Azure Functions host entrypoint (adjacent to host.json).

The canonical FunctionApp definition lives at src/fee_management/function_app.py
per TDD §5. This thin re-export lets Azure Functions Core Tools discover `app`
when the project root is the repository root.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fee_management.function_app import app

__all__ = ["app"]
