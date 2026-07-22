#!/usr/bin/env python3
"""
Run the WHOLE adapter chain in a single process, without Docker.

It mounts every FastAPI app (the 6 microservices + Audit Log + 8 KMS mocks)
in memory and routes the inter-service HTTP calls through an httpx transport
that dispatches by hostname. Useful for a quick local demo / CI smoke test
when a Docker daemon isn't available.

Usage:
    pip install -r requirements.txt
    python scripts/run_local_e2e.py
    python scripts/run_local_e2e.py --source Monza --destination Napoli --num-keys 2
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Point config at the in-repo files and use a throwaway audit DB BEFORE the
# services import shared.settings (settings are cached at first import).
os.environ.setdefault("TOPOLOGY_CONFIG", str(ROOT / "config" / "topology.yaml"))
os.environ.setdefault("KMS_REGISTRY", str(ROOT / "config" / "kms_registry.yaml"))
os.environ.setdefault("DOMAINS_CONFIG", str(ROOT / "config" / "domains.yaml"))
os.environ.setdefault("AUDIT_DB_PATH", tempfile.mktemp(suffix="-audit.db"))

import httpx  # noqa: E402

KMS_PORTS = {
    "milano": 9001, "torino": 9002, "genova": 9003, "venezia": 9004,
    "bologna": 9005, "firenze": 9006, "roma": 9007, "napoli": 9008,
    # Trusted relay nodes (see config/topology.yaml).
    "parma": 9009, "la_spezia": 9010, "padova": 9011,
    # Densification: Pavia/Ferrara relays + Verona main KMS.
    "pavia": 9012, "ferrara": 9013, "verona": 9014,
}


def _load_service_app(module_path: str):
    return importlib.import_module(module_path).app


def _load_kms_app(city: str):
    """kms_mock reads CITY at import time, so load it freshly per city."""
    os.environ["CITY"] = city
    os.environ["SAE_ID"] = f"{city}-sae"
    spec = importlib.util.spec_from_file_location(
        f"kms_{city}", ROOT / "services" / "kms_mock" / "app" / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def build_router() -> httpx.AsyncBaseTransport:
    apps = {
        "northbound-api-gateway":    _load_service_app("services.northbound_api_gateway.app.main"),
        "identity-auth":             _load_service_app("services.identity_auth.app.main"),
        "topology-manager":          _load_service_app("services.topology_manager.app.main"),
        "path-computation-engine":   _load_service_app("services.path_computation_engine.app.main"),
        "key-orchestration-manager": _load_service_app("services.key_orchestration_manager.app.main"),
        "service-provisioning":      _load_service_app("services.service_provisioning.app.main"),
        "audit-log":                 _load_service_app("services.audit_log.app.main"),
    }
    for city in KMS_PORTS:
        apps[f"kms-{city}"] = _load_kms_app(city)

    class Router(httpx.AsyncBaseTransport):
        def __init__(self) -> None:
            self._t = {host: httpx.ASGITransport(app=app) for host, app in apps.items()}

        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            transport = self._t.get(request.url.host)
            if transport is None:
                raise httpx.ConnectError(f"unknown host: {request.url.host}")
            return await transport.handle_async_request(request)

    return Router()


def patch_httpx(router: httpx.AsyncBaseTransport) -> None:
    """Make every AsyncClient created by the services use our in-memory router."""
    original = httpx.AsyncClient

    def patched(*args, **kwargs):
        kwargs.setdefault("transport", router)
        return original(*args, **kwargs)

    httpx.AsyncClient = patched  # type: ignore[assignment]


async def run(source: str, destination: str, num_keys: int, key_size: int) -> int:
    patch_httpx(build_router())
    request = {
        "request_id": "req-local-e2e",
        "source": source,
        "destination": destination,
        "service_type": "qkd_virtual_circuit",
        "key_size": key_size,
        "num_keys": num_keys,
        "priority": "normal",
    }
    async with httpx.AsyncClient() as client:
        print(f"==> POST /adapter/v1/virtual-circuits  ({source} -> {destination})")
        resp = await client.post(
            "http://northbound-api-gateway:8080/adapter/v1/virtual-circuits", json=request)
        body = resp.json()
        print(json.dumps(body, indent=2))

        audit = await client.get("http://audit-log:8086/audit/v1/events",
                                 params={"request_id": request["request_id"]})
        events = [e["event_type"] for e in audit.json()["events"]]
        print("\n==> Audit trail:", " -> ".join(events))

    ok = body.get("status") == "PROVISIONED" and body.get("keys")
    print("\n" + (">>> END-TO-END OK" if ok else ">>> FAILED"))
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="In-process QSDN end-to-end demo (no Docker).")
    parser.add_argument("--source", default="Monza")
    parser.add_argument("--destination", default="Venezia")
    parser.add_argument("--num-keys", type=int, default=1)
    parser.add_argument("--key-size", type=int, default=256)
    args = parser.parse_args()
    return asyncio.run(run(args.source, args.destination, args.num_keys, args.key_size))


if __name__ == "__main__":
    sys.exit(main())
