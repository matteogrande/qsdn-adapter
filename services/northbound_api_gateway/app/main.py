"""
Northbound API Gateway — single entry point for ONOS.

ONOS REST client -> POST /adapter/v1/virtual-circuits -> Identity & Auth
                                                       -> ... internal chain ...
                                                       -> response back here -> ONOS
"""
from __future__ import annotations

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from shared.logging_client import audit
from shared.models import AdapterContext, VirtualCircuitRequest, VirtualCircuitResponse
from .client import forward_to_identity

app = FastAPI(title="QSDN · Northbound API Gateway", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "northbound_api_gateway"}


@app.post("/adapter/v1/virtual-circuits", response_model=VirtualCircuitResponse)
async def create_virtual_circuit(req: VirtualCircuitRequest) -> VirtualCircuitResponse:
    await audit(
        req.request_id, "request_received",
        endpoints={"source": req.source, "destination": req.destination},
        detail={"service_type": req.service_type, "key_size": req.key_size},
    )

    ctx = AdapterContext(request=req)
    try:
        # The gateway hands off to Identity & Auth and waits for the fully
        # populated context to bubble back up the chain.
        result = await forward_to_identity(ctx)
    except httpx.HTTPStatusError as exc:
        await audit(req.request_id, "downstream_error", error=str(exc))
        # Try to surface a structured error returned by Identity & Auth.
        try:
            ctx_err = AdapterContext.model_validate(exc.response.json())
            if ctx_err.response:
                return ctx_err.response
        except Exception:  # noqa: BLE001
            pass
        raise HTTPException(status_code=502, detail=f"Adapter chain error: {exc}")
    except httpx.HTTPError as exc:
        await audit(req.request_id, "downstream_error", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Adapter chain unreachable: {exc}")

    if result.response is None:
        raise HTTPException(status_code=500, detail="Empty response from adapter chain")

    await audit(
        req.request_id, "response_returned",
        selected_path=result.response.selected_path,
        detail={"status": result.response.status},
    )

    # A rejected circuit (no admissible path / insufficient key material) is not
    # a server success: surface it to ONOS as HTTP 503 while still returning the
    # structured body. PROVISIONED stays 200. This makes the 200-vs-503 success
    # rate an HTTP-level signal, not just a body field.
    if result.response.status == "REJECTED":
        return JSONResponse(status_code=503, content=result.response.model_dump())
    return result.response
