"""HTTP starter for manually triggering ReminderOrchestration (local demo / Phase 6 exit)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import azure.durable_functions as df
import azure.functions as func

from fee_management.api.errors import get_correlation_id, json_response
from fee_management.durable.bp import bp
from fee_management.durable.helpers import reminder_instance_id
from fee_management.telemetry.context import bind_correlation_id

logger = logging.getLogger(__name__)


@bp.function_name(name="StartReminderOrchestration")
@bp.route(route="reminders/run", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
@bp.durable_client_input(client_name="client")
async def start_reminder_orchestration(
    req: func.HttpRequest,
    client: df.DurableOrchestrationClient,
) -> func.HttpResponse:
    """
    Manually start (or re-check) today's reminder orchestration.

    Query ``force=true`` uses a unique instance id so a completed daily run can be
    re-executed during local demos without waiting for the next UTC day.
    """
    request_cid = get_correlation_id(req)
    force = (req.params.get("force") or "").lower() in {"1", "true", "yes"}
    today = datetime.now(UTC).date()
    instance_id = None if force else reminder_instance_id(today)

    try:
        started_id = await client.start_new(
            "ReminderOrchestration",
            instance_id=instance_id,
            client_input=None,
        )
    except Exception as exc:
        logger.exception(
            "Failed to start ReminderOrchestration",
            extra={"correlation_id": request_cid},
        )
        return json_response(
            {
                "error": "ORCHESTRATION_START_FAILED",
                "message": "Could not start reminder orchestration",
                "correlationId": request_cid,
                "detail": str(exc),
            },
            status_code=409,
            correlation_id=request_cid,
        )

    # Prefer Durable instance id as the chain correlation id (§15.3).
    bind_correlation_id(started_id)
    logger.info(
        "Manually started ReminderOrchestration",
        extra={
            "instanceId": started_id,
            "force": force,
            "correlation_id": started_id,
            "requestCorrelationId": request_cid,
        },
    )
    response = client.create_check_status_response(req, started_id)
    response.headers["x-correlation-id"] = started_id
    return response
