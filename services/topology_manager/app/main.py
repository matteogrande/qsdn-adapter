"""
Topology Manager — owns the QKD/KMS topology and provides the up-to-date view
to the Path Computation Engine. The topology comes from a pluggable source
(static YAML or live ONOS discovery; see topology.py).
"""
from __future__ import annotations

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from shared.logging_client import audit
from shared.models import AdapterContext, TopologySnapshot, VirtualCircuitResponse
from shared.settings import get_settings
from .topology import (get_snapshot, refresh, remove_link, remove_node,
                       set_link_status, upsert_link, upsert_node)

app = FastAPI(title="QSDN · Topology Manager", version="0.2.0")


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
    return {"status": "ok", "service": "topology_manager",
            "source": get_settings().topology_source}


@app.get("/topology/v1/graph", response_model=TopologySnapshot)
async def graph() -> TopologySnapshot:
    """Inspection endpoint: returns the current topology snapshot."""
    return await get_snapshot()


@app.post("/topology/v1/refresh", response_model=TopologySnapshot)
async def refresh_topology() -> TopologySnapshot:
    return await refresh()


# --- live topology edits (dashboard) --------------------------------------
class NodeEdit(BaseModel):
    id: str
    label: str | None = None
    action: str = "upsert"        # upsert | remove


class LinkEdit(BaseModel):
    source: str
    target: str
    cost: float = 1.0
    type: str = "physical"
    status: str = "up"
    action: str = "upsert"        # upsert | remove | set_status


@app.post("/topology/v1/node", response_model=TopologySnapshot)
async def edit_node(edit: NodeEdit) -> TopologySnapshot:
    if edit.action == "remove":
        snap = await remove_node(edit.id)
    else:
        snap = await upsert_node(edit.id, edit.label)
    await audit("topology-edit", "node_" + edit.action, detail={"id": edit.id})
    return snap


@app.post("/topology/v1/link", response_model=TopologySnapshot)
async def edit_link(edit: LinkEdit) -> TopologySnapshot:
    if edit.action == "remove":
        snap = await remove_link(edit.source, edit.target)
    elif edit.action == "set_status":
        snap = await set_link_status(edit.source, edit.target, edit.status)
    else:
        snap = await upsert_link(edit.source, edit.target, edit.cost,
                                 edit.type, edit.status)
    await audit("topology-edit", "link_" + edit.action,
                detail={"source": edit.source, "target": edit.target,
                        "status": edit.status})
    return snap


@app.post("/topology/v1/resolve", response_model=AdapterContext)
async def attach_topology(ctx: AdapterContext) -> AdapterContext:
    try:
        snapshot = await get_snapshot()
    except httpx.HTTPError as exc:
        await audit(ctx.request.request_id, "topology_source_error", error=str(exc))
        return _reject(ctx, f"Topology source (ONOS) unavailable: {exc}")

    if not snapshot.nodes:
        await audit(ctx.request.request_id, "topology_empty")
        return _reject(ctx, "Topology is empty (no devices discovered yet)")

    ctx.topology = snapshot
    ctx.status = "RESOLVED"
    await audit(
        ctx.request.request_id, "topology_attached",
        topology={"nodes": len(snapshot.nodes), "links": len(snapshot.links),
                  "source": get_settings().topology_source},
    )

    settings = get_settings()
    url = f"{settings.pce_url}/pce/v1/compute"
    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        resp = await client.post(url, json=ctx.model_dump())
        resp.raise_for_status()
        return AdapterContext.model_validate(resp.json())
