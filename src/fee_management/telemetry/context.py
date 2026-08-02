"""Request-scoped correlation ID via contextvars (TDD §15.3)."""

from __future__ import annotations

from contextvars import ContextVar, Token

_correlation_id: ContextVar[str | None] = ContextVar("fee_mgmt_correlation_id", default=None)


def get_bound_correlation_id() -> str | None:
    """Return the correlation ID bound to the current execution context, if any."""
    return _correlation_id.get()


def bind_correlation_id(correlation_id: str) -> Token[str | None]:
    """
    Bind ``correlation_id`` for the current context (HTTP request or Durable activity).

    Also attaches OpenTelemetry baggage when the SDK is available so App Insights
    request telemetry can be filtered by the same id.
    """
    token = _correlation_id.set(correlation_id)
    _attach_otel_baggage(correlation_id)
    return token


def reset_correlation_id(token: Token[str | None]) -> None:
    """Restore the previous correlation ID binding."""
    _correlation_id.reset(token)


def _attach_otel_baggage(correlation_id: str) -> None:
    try:
        from opentelemetry import baggage, context

        ctx = baggage.set_baggage("correlation.id", correlation_id)
        context.attach(ctx)
    except Exception:
        # OTel may be absent locally or not yet configured — logging still works.
        return
