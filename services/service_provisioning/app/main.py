"""
Service Provisioning — assembles the final JSON response for ONOS from the
fully-populated AdapterContext. It does NOT call ONOS directly: it returns
the context, which bubbles back up the chain to the Northbound API Gateway.
"""
from __future__ import annotations

from fastapi import FastAPI

from shared.logging_client import audit
from shared.models import AdapterContext, VirtualCircuitResponse

app = FastAPI(title="QSDN · Service Provisioning", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "service_provisioning"}


@app.post("/provisioning/v1/provision", response_model=AdapterContext)
async def provision(ctx: AdapterContext) -> AdapterContext:
    req = ctx.request
    response = VirtualCircuitResponse(
        request_id=req.request_id,
        status="PROVISIONED",
        source=req.source,
        destination=req.destination,
        resolved_source_domain=ctx.resolved.source_domain if ctx.resolved else None,
        resolved_destination_domain=ctx.resolved.destination_domain if ctx.resolved else None,
        selected_path=ctx.path.path_domains if ctx.path else [],
        kms_chain=ctx.keys.kms_chain if ctx.keys else [],
        keys=ctx.keys.keys if ctx.keys else [],
        message="Virtual QKD service provisioned successfully",
    )
    ctx.response = response
    ctx.status = "PROVISIONED"

    await audit(req.request_id, "service_provisioned",
                selected_path=response.selected_path,
                kms_called=response.kms_chain,
                keys=[k.key_id for k in response.keys])
    return ctx
