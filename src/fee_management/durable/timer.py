"""Timer trigger that starts ReminderOrchestration (TDD §9.6)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import azure.durable_functions as df
import azure.functions as func

from fee_management.durable.bp import bp
from fee_management.durable.helpers import reminder_instance_id
from fee_management.telemetry.context import bind_correlation_id

logger = logging.getLogger(__name__)


@bp.function_name(name="ReminderTimerTrigger")
@bp.timer_trigger(
    schedule="%REMINDER_CRON_SCHEDULE%",
    arg_name="timer",
    run_on_startup=False,
)
@bp.durable_client_input(client_name="client")
async def reminder_timer_trigger(
    timer: func.TimerRequest,
    client: df.DurableOrchestrationClient,
) -> None:
    """Start a daily ReminderOrchestration instance; does not touch the DB."""
    today = datetime.now(UTC).date()
    instance_id = reminder_instance_id(today)
    # Durable instance_id is the correlation id across timer → orch → activities (§15.3).
    bind_correlation_id(instance_id)

    if timer.past_due:
        logger.warning("ReminderTimerTrigger is past due; starting orchestration anyway")

    try:
        started_id = await client.start_new(
            "ReminderOrchestration",
            instance_id=instance_id,
            client_input=None,
        )
        logger.info(
            "Started ReminderOrchestration",
            extra={
                "event": "ReminderOrchestrationStarted",
                "instanceId": started_id,
                "correlation_id": instance_id,
            },
        )
    except Exception:
        # Duplicate instance_id for an existing run/day → skip (idempotency §9.6).
        logger.exception(
            "Could not start ReminderOrchestration (may already exist for today)",
            extra={"instanceId": instance_id, "correlation_id": instance_id},
        )
