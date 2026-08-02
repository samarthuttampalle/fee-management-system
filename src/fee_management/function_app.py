"""Azure Functions v2 entry point — HTTP APIs + Durable reminder workflow."""

from __future__ import annotations

import azure.durable_functions as df
import azure.functions as func

from fee_management.api import admin, health, students

# Import modules so Durable decorators register on the shared blueprint.
from fee_management.durable import (  # noqa: F401
    activities,
    http_start,
    orchestrators,
    timer,
)
from fee_management.durable.bp import bp as durable_bp
from fee_management.telemetry.logging_setup import setup_observability

# Structured logging + optional Application Insights (§15) — before the host serves traffic.
setup_observability()

app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)
app.register_functions(health.bp)
app.register_functions(students.bp)
app.register_functions(admin.bp)
app.register_functions(durable_bp)
