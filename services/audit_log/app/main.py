"""
Audit Log — horizontal component. Every microservice POSTs events here; the
GET endpoint lets you inspect the full trace of a request.
"""
from __future__ import annotations

from fastapi import FastAPI

from shared.models import AuditEvent
from shared.settings import get_settings
from .store import AuditStore

app = FastAPI(title="QSDN · Audit Log", version="0.1.0")
store = AuditStore(get_settings().audit_db_path)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "audit_log"}


@app.post("/audit/v1/events")
def write_event(event: AuditEvent) -> dict:
    store.add(event)
    return {"stored": True}


@app.get("/audit/v1/events")
def read_events(request_id: str | None = None, limit: int = 200) -> dict:
    return {"events": store.query(request_id=request_id, limit=limit)}
