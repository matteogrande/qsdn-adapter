"""
QSDN Control Panel — a thin presentation layer over the adapter.

It serves the single-page UI and proxies the browser's calls to the adapter's
REST APIs (so the page talks to ONE origin: no CORS). It adds no business
logic: it consumes the same APIs ONOS or an operator would.
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx
import yaml
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://northbound-api-gateway:8080")
TOPOLOGY_URL = os.getenv("TOPOLOGY_URL", "http://topology-manager:8082")
AUDIT_URL = os.getenv("AUDIT_URL", "http://audit-log:8086")
KMS_REGISTRY = os.getenv("KMS_REGISTRY", "/app/config/kms_registry.yaml")
TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "15"))

HERE = Path(__file__).resolve().parent
app = FastAPI(title="QSDN · Control Panel", version="1.0.0")


@app.middleware("http")
async def _no_cache(request: Request, call_next):
    """Serve the UI assets with revalidation so the browser never shows a
    stale index.html / dashboard.js / dashboard.css after an update."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")


async def _get(url: str):
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.get(url)
        return r.json(), r.status_code


async def _post(url: str, payload: dict):
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.post(url, json=payload)
        return r.json(), r.status_code


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(HERE / "index.html")


@app.get("/api/cities")
async def cities() -> JSONResponse:
    data = yaml.safe_load(Path(KMS_REGISTRY).read_text("utf-8")) or {}
    out = [{"id": cid, "label": e.get("label", cid)}
           for cid, e in (data.get("kms") or {}).items()]
    return JSONResponse(out)


@app.get("/api/topology")
async def topology() -> JSONResponse:
    body, code = await _get(f"{TOPOLOGY_URL}/topology/v1/graph")
    return JSONResponse(body, status_code=code)


@app.post("/api/provision")
async def provision(request: Request) -> JSONResponse:
    payload = await request.json()
    body, code = await _post(f"{GATEWAY_URL}/adapter/v1/virtual-circuits", payload)
    return JSONResponse(body, status_code=code)


@app.get("/api/audit/{request_id}")
async def audit(request_id: str) -> JSONResponse:
    body, code = await _get(f"{AUDIT_URL}/audit/v1/events?request_id={request_id}")
    return JSONResponse(body, status_code=code)


@app.post("/api/topology/node")
async def edit_node(request: Request) -> JSONResponse:
    body, code = await _post(f"{TOPOLOGY_URL}/topology/v1/node", await request.json())
    return JSONResponse(body, status_code=code)


@app.post("/api/topology/link")
async def edit_link(request: Request) -> JSONResponse:
    body, code = await _post(f"{TOPOLOGY_URL}/topology/v1/link", await request.json())
    return JSONResponse(body, status_code=code)


@app.post("/api/topology/reset")
async def reset() -> JSONResponse:
    body, code = await _post(f"{TOPOLOGY_URL}/topology/v1/refresh", {})
    return JSONResponse(body, status_code=code)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "dashboard"}
