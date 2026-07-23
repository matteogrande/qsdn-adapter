"""
Shared helpers for the KPI measurement harness.

Everything the individual KPI scripts need: endpoints, a timed request to the
gateway, retrieval + per-stage decomposition of the audit trail, a CSV writer,
and a matplotlib style built on the (CVD-validated) data-viz palette so every
chart in the thesis reads as one system.

Nothing here talks to the KMS directly — measurements are taken exactly where a
real operator would take them: the northbound API and the audit log.
"""
from __future__ import annotations

import csv
import os
import time
from pathlib import Path

import httpx

# --------------------------------------------------------------------------- #
# Endpoints (override via env for the ndks profile or a remote host)
# --------------------------------------------------------------------------- #
GATEWAY_URL = os.getenv("QSDN_GATEWAY_URL", "http://localhost:8080")
AUDIT_URL = os.getenv("QSDN_AUDIT_URL", "http://localhost:8086")
TOPOLOGY_URL = os.getenv("QSDN_TOPOLOGY_URL", "http://localhost:8082")

RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# --------------------------------------------------------------------------- #
# The six microservice stages, derived from the eight ordered audit events.
# Each service emits its completion event; the interval between two consecutive
# completion events is the work done by the downstream service (+ one network
# hop). The two Identity events are merged so the decomposition is exactly one
# bucket per microservice. Sum of the six == end-to-end audit latency.
#   request_received --Identity&Auth--> endpoints_resolved
#   endpoints_resolved --Topology--> topology_attached
#   topology_attached --PCE--> path_computed
#   path_computed --KOM--> keys_retrieved
#   keys_retrieved --Provisioning--> service_provisioned
#   service_provisioned --Gateway(egress)--> response_returned
# --------------------------------------------------------------------------- #
STAGES: list[tuple[str, str, str]] = [
    ("Identity & Auth",       "request_received",    "endpoints_resolved"),
    ("Topology Manager",      "endpoints_resolved",  "topology_attached"),
    ("Path Computation",      "topology_attached",   "path_computed"),
    ("Key Orchestration",     "path_computed",       "keys_retrieved"),
    ("Service Provisioning",  "keys_retrieved",      "service_provisioned"),
    ("Northbound Gateway",    "service_provisioned", "response_returned"),
]
STAGE_LABELS = [s[0] for s in STAGES]


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #
def make_request(source: str, destination: str, request_id: str,
                 num_keys: int = 1, key_size: int = 256,
                 priority: str = "normal") -> dict:
    return {
        "request_id": request_id, "source": source, "destination": destination,
        "service_type": "qkd_virtual_circuit", "key_size": key_size,
        "num_keys": num_keys, "priority": priority,
    }


def post_circuit(client: httpx.Client, body: dict) -> tuple[int, dict, float]:
    """POST a virtual-circuit request; return (http_status, json, latency_ms)."""
    t0 = time.perf_counter()
    r = client.post(f"{GATEWAY_URL}/adapter/v1/virtual-circuits", json=body)
    latency_ms = (time.perf_counter() - t0) * 1000.0
    try:
        payload = r.json()
    except Exception:  # noqa: BLE001
        payload = {}
    return r.status_code, payload, latency_ms


# --------------------------------------------------------------------------- #
# Audit trail -> per-stage latency
# --------------------------------------------------------------------------- #
def fetch_events(client: httpx.Client, request_id: str) -> list[dict]:
    r = client.get(f"{AUDIT_URL}/audit/v1/events",
                   params={"request_id": request_id})
    r.raise_for_status()
    return r.json().get("events", [])


def _ts(event: dict) -> float:
    """ISO-8601 -> epoch seconds."""
    from datetime import datetime
    return datetime.fromisoformat(event["timestamp"]).timestamp()


def stage_latencies_ms(events: list[dict]) -> dict[str, float] | None:
    """Return {stage_name: ms} from an audit trail, or None if incomplete."""
    by_type: dict[str, float] = {}
    for ev in events:
        # keep the *last* occurrence of each type (append-only store, new run wins)
        by_type[ev["event_type"]] = _ts(ev)
    out: dict[str, float] = {}
    for name, start, end in STAGES:
        if start not in by_type or end not in by_type:
            return None
        out[name] = max(0.0, (by_type[end] - by_type[start]) * 1000.0)
    return out


def path_info(events: list[dict]) -> dict:
    """Pull hops/cost/path/status out of the audit trail of one request."""
    info: dict = {"hops": None, "cost": None, "path": None, "status": None}
    for ev in events:
        if ev["event_type"] == "path_computed":
            d = ev.get("detail") or {}
            info["hops"] = d.get("hops")
            info["cost"] = d.get("cost")
            info["path"] = ev.get("selected_path")
        if ev["event_type"] == "response_returned":
            info["status"] = (ev.get("detail") or {}).get("status")
    return info


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def write_csv(name: str, rows: list[dict], fieldnames: list[str]) -> Path:
    path = RESULTS_DIR / name
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {path.relative_to(RESULTS_DIR.parent)}")
    return path


def new_client(timeout: float = 30.0) -> httpx.Client:
    return httpx.Client(timeout=timeout)


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)
