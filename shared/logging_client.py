"""
Thin async client used by every microservice to push events to the
horizontal Audit Log. Auditing must never break the main flow, so all
errors are swallowed (and logged locally).
"""
from __future__ import annotations

import logging

import httpx

from shared.models import AuditEvent
from shared.settings import get_settings

logger = logging.getLogger("audit")

# Reuse one keep-alive client per process instead of opening a fresh TCP
# connection for every audit event (~8 per request). Created lazily so it binds
# to the running event loop.
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=get_settings().audit_timeout,
            limits=httpx.Limits(max_connections=64, max_keepalive_connections=32),
        )
    return _client


def build_event(request_id: str, event_type: str, **fields) -> AuditEvent:
    settings = get_settings()
    return AuditEvent(
        request_id=request_id,
        service=settings.service_name,
        event_type=event_type,
        **fields,
    )


async def log_event(event: AuditEvent) -> None:
    """Fire an audit event. Failures are logged but never raised."""
    settings = get_settings()
    url = f"{settings.audit_url}/audit/v1/events"
    try:
        await _get_client().post(url, json=event.model_dump())
    except Exception as exc:  # noqa: BLE001 - audit must not break the flow
        logger.warning("audit write failed for %s/%s: %s",
                       event.request_id, event.event_type, exc)


async def audit(request_id: str, event_type: str, **fields) -> None:
    """Convenience helper: build + send in one call."""
    await log_event(build_event(request_id, event_type, **fields))
