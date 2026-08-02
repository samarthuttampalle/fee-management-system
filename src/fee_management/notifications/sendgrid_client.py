"""SendGrid wrapper with retry and local mock mode (TDD §9.9 / §20.5)."""

from __future__ import annotations

import logging
import time
from typing import Any

from fee_management.config import Settings, get_settings
from fee_management.notifications.email_templates import render_reminder_email

logger = logging.getLogger(__name__)

# Aligns with Durable RetryOptions (§16.5): 5s, 3 attempts, backoff ×2
_RETRY_BACKOFF_SECONDS = (5.0, 10.0)


class SendGridError(RuntimeError):
    """Raised when a real SendGrid send fails after retries."""


def send_reminder(
    student: dict[str, Any],
    *,
    settings: Settings | None = None,
) -> None:
    """
    Send (or mock-send) a fee reminder for one overdue student.

    ``SENDGRID_MODE=mock`` logs the rendered email and returns success.
    ``SENDGRID_MODE=real`` calls the SendGrid API with up to 3 attempts.
    """
    cfg = settings or get_settings()
    subject, body = render_reminder_email(student)
    to_email = str(student["email"])

    if cfg.sendgrid_mode.lower() == "mock":
        logger.info(
            "Mock SendGrid reminder email",
            extra={
                "event": "ReminderEmailMocked",
                "studentId": student.get("studentId"),
                "to": to_email,
                "subject": subject,
                "body": body,
            },
        )
        return

    _send_real_with_retry(
        to_email=to_email,
        subject=subject,
        body=body,
        api_key=cfg.sendgrid_api_key,
        from_email=cfg.sendgrid_from_email,
        student_id=student.get("studentId"),
    )


def _send_real_with_retry(
    *,
    to_email: str,
    subject: str,
    body: str,
    api_key: str,
    from_email: str,
    student_id: Any,
) -> None:
    if not api_key or not from_email:
        raise SendGridError("SENDGRID_API_KEY and SENDGRID_FROM_EMAIL are required in real mode")

    last_error: BaseException | None = None
    for attempt in range(3):
        try:
            _send_via_sendgrid(
                to_email=to_email,
                subject=subject,
                body=body,
                api_key=api_key,
                from_email=from_email,
            )
            return
        except Exception as exc:
            last_error = exc
            if attempt >= 2:
                break
            delay = _RETRY_BACKOFF_SECONDS[min(attempt, len(_RETRY_BACKOFF_SECONDS) - 1)]
            logger.warning(
                "SendGrid send failed (attempt %s/3); retrying in %ss",
                attempt + 1,
                delay,
                extra={"studentId": student_id},
                exc_info=True,
            )
            time.sleep(delay)

    assert last_error is not None
    raise SendGridError(str(last_error)) from last_error


def _send_via_sendgrid(
    *,
    to_email: str,
    subject: str,
    body: str,
    api_key: str,
    from_email: str,
) -> None:
    # Imported lazily so mock-mode local runs do not require a working SendGrid install path.
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject=subject,
        plain_text_content=body,
    )
    client = SendGridAPIClient(api_key)
    response = client.send(message)
    status = getattr(response, "status_code", None)
    if status is None or int(status) >= 400:
        raise SendGridError(f"SendGrid returned status {status}")
