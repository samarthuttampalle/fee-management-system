"""Health check HTTP endpoint — GET /api/health (TDD §8.5 / §9.5)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import azure.functions as func

from fee_management.api.errors import get_correlation_id, json_response
from fee_management.api.exception_mapping import map_exception_to_response
from fee_management.api.schemas import HealthResponse, dump_camel
from fee_management.data import db

bp = func.Blueprint()
logger = logging.getLogger(__name__)


@bp.function_name(name="HealthCheck")
@bp.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Unauthenticated liveness/readiness probe; pings the database."""
    correlation_id = get_correlation_id(req)
    try:
        logger.info("Health check", extra={"correlation_id": correlation_id})
        reachable = db.ping(timeout_seconds=2.0)
        body = HealthResponse(
            status="healthy" if reachable else "unhealthy",
            db_reachable=reachable,
            timestamp=datetime.now(UTC).replace(tzinfo=None),
        )
        status_code = 200 if reachable else 503
        return json_response(
            dump_camel(body), status_code=status_code, correlation_id=correlation_id
        )
    except Exception as exc:
        return map_exception_to_response(exc, correlation_id)
