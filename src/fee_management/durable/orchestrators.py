"""ReminderOrchestration — fan-out overdue reminder emails (TDD §9.7)."""

from __future__ import annotations

from typing import Any

import azure.durable_functions as df

from fee_management.durable.bp import bp
from fee_management.durable.helpers import aggregate_send_results, build_summary


@bp.function_name(name="ReminderOrchestration")
@bp.orchestration_trigger(context_name="context")
def reminder_orchestration(context: df.DurableOrchestrationContext) -> Any:
    """
    1) Query overdue students
    2) Fan-out SendReminderEmail (with RetryOptions for unexpected failures)
    3) Aggregate sent/failed
    4) LogReminderSummary
    """
    started = context.current_utc_datetime
    correlation_id = context.instance_id

    overdue: list[dict[str, Any]] = yield context.call_activity(
        "QueryOverdueStudents",
        {"correlationId": correlation_id},
    )

    if not overdue:
        summary = build_summary(
            total_overdue=0,
            sent=0,
            failed=0,
            duration_ms=_elapsed_ms(context, started),
            results=[],
        )
        summary["correlationId"] = correlation_id
        yield context.call_activity("LogReminderSummary", summary)
        return {
            "totalOverdue": 0,
            "sent": 0,
            "failed": 0,
            "durationMs": summary["durationMs"],
            "correlationId": correlation_id,
        }

    # RetryOptions for unexpected activity crashes (§16.5). Send failures return Failed
    # from the activity so one bad address cannot fail task_all / the whole fan-in.
    retry = df.RetryOptions(
        first_retry_interval_in_milliseconds=5000,
        max_number_of_attempts=3,
    )
    retry.backoff_coefficient = 2.0

    tasks = [
        context.call_activity_with_retry(
            "SendReminderEmail",
            retry,
            {**student, "correlationId": correlation_id},
        )
        for student in overdue
    ]
    results: list[dict[str, Any]] = yield context.task_all(tasks)

    counts = aggregate_send_results(results)
    summary = build_summary(
        total_overdue=counts["totalOverdue"],
        sent=counts["sent"],
        failed=counts["failed"],
        duration_ms=_elapsed_ms(context, started),
        results=results,
    )
    summary["correlationId"] = correlation_id
    yield context.call_activity("LogReminderSummary", summary)
    return {
        "totalOverdue": summary["totalOverdue"],
        "sent": summary["sent"],
        "failed": summary["failed"],
        "durationMs": summary["durationMs"],
        "correlationId": correlation_id,
    }


def _elapsed_ms(context: df.DurableOrchestrationContext, started: Any) -> int:
    ended = context.current_utc_datetime
    return int((ended - started).total_seconds() * 1000)
