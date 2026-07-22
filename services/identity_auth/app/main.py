"""
Identity & Auth — authenticates/validates the request and resolves the
logical ONOS endpoints onto KMS domains, then forwards to Topology Manager.
"""
from __future__ import annotations

from pathlib import Path

import httpx
import yaml
from fastapi import FastAPI

from shared.logging_client import audit
from shared.models import (AdapterContext, ResolvedEndpoints,
                           VirtualCircuitResponse)
from shared.settings import get_settings
from .resolver import ResolutionError, resolve_endpoint

app = FastAPI(title="QSDN · Identity & Auth", version="0.1.0")


def _node_labels() -> dict[str, str]:
    # A logical endpoint is resolvable if it maps to a known KMS DOMAIN.
    # Read from the domains directory (decoupled from KMS transport), so cities
    # added to the topology at runtime still resolve.
    data = yaml.safe_load(Path(get_settings().domains_config).read_text("utf-8")) or {}
    return dict(data.get("domains") or {})


def _reject(ctx: AdapterContext, message: str) -> AdapterContext:
    ctx.status = "REJECTED"
    ctx.error = message
    ctx.response = VirtualCircuitResponse(
        request_id=ctx.request.request_id,
        status="REJECTED",
        source=ctx.request.source,
        destination=ctx.request.destination,
        message=message,
    )
    return ctx


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "identity_auth"}


@app.post("/identity/v1/authorize", response_model=AdapterContext)
async def authorize(ctx: AdapterContext) -> AdapterContext:
    req = ctx.request

    # --- (simulated) authentication ---------------------------------------
    # In a real deployment this would validate a token / mTLS identity.
    # For the simulation we accept the request and record the decision.
    await audit(req.request_id, "auth_validated",
                detail={"priority": req.priority})

    # --- endpoint resolution ----------------------------------------------
    labels = _node_labels()
    try:
        src_node, src_label = resolve_endpoint(req.source, labels)
        dst_node, dst_label = resolve_endpoint(req.destination, labels)
    except ResolutionError as exc:
        await audit(req.request_id, "resolution_failed", error=str(exc))
        return _reject(ctx, str(exc))

    ctx.resolved = ResolvedEndpoints(
        source_node=src_node, source_domain=src_label,
        destination_node=dst_node, destination_domain=dst_label,
    )
    ctx.status = "AUTHORIZED"
    await audit(req.request_id, "endpoints_resolved",
                endpoints={"source": f"{req.source} -> {src_label}",
                           "destination": f"{req.destination} -> {dst_label}"})

    # --- forward to Topology Manager --------------------------------------
    settings = get_settings()
    url = f"{settings.topology_url}/topology/v1/resolve"
    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        resp = await client.post(url, json=ctx.model_dump())
        resp.raise_for_status()
        return AdapterContext.model_validate(resp.json())
