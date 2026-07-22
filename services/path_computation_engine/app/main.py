"""
Path Computation Engine — computes the optimal path between resolved domains
using the topology snapshot, then forwards to the Key Orchestration Manager.
"""
from __future__ import annotations

import httpx
from fastapi import FastAPI

from shared.logging_client import audit
from shared.models import AdapterContext, VirtualCircuitResponse
from shared.settings import get_settings
from .path_engine import NoPathError, compute_path

app = FastAPI(title="QSDN · Path Computation Engine", version="0.1.0")


def _reject(ctx: AdapterContext, message: str) -> AdapterContext:
    ctx.status = "REJECTED"
    ctx.error = message
    ctx.response = VirtualCircuitResponse(
        request_id=ctx.request.request_id, status="REJECTED",
        source=ctx.request.source, destination=ctx.request.destination,
        resolved_source_domain=ctx.resolved.source_domain if ctx.resolved else None,
        resolved_destination_domain=ctx.resolved.destination_domain if ctx.resolved else None,
        message=message,
    )
    return ctx


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "path_computation_engine"}


@app.post("/pce/v1/compute", response_model=AdapterContext)
async def compute(ctx: AdapterContext) -> AdapterContext:
    if ctx.topology is None or ctx.resolved is None:
        return _reject(ctx, "Missing topology or resolved endpoints")

    try:
        path = compute_path(
            ctx.topology,
            ctx.resolved.source_node,
            ctx.resolved.destination_node,
        )
    except NoPathError as exc:
        await audit(ctx.request.request_id, "path_not_found", error=str(exc))
        return _reject(ctx, str(exc))

    ctx.path = path
    ctx.status = "ROUTED"
    await audit(ctx.request.request_id, "path_computed",
                selected_path=path.path_domains,
                detail={"hops": path.hops, "cost": path.total_cost})

    settings = get_settings()
    url = f"{settings.kom_url}/kom/v1/orchestrate"
    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        resp = await client.post(url, json=ctx.model_dump())
        resp.raise_for_status()
        return AdapterContext.model_validate(resp.json())
