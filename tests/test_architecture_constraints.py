"""
Static guards for the two hard architectural invariants from the diagram:
  1. The Northbound API Gateway may call ONLY Identity & Auth.
  2. The Key Orchestration Manager is the ONLY adapter service that calls KMS.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"

ADAPTER_SERVICES = [
    "northbound_api_gateway", "identity_auth", "topology_manager",
    "path_computation_engine", "key_orchestration_manager",
    "service_provisioning", "audit_log",
]


def _source(service: str) -> str:
    return "\n".join(p.read_text() for p in (SERVICES / service / "app").glob("*.py"))


def test_gateway_only_talks_to_identity():
    src = _source("northbound_api_gateway")
    assert "identity_url" in src
    for forbidden in ("topology_url", "pce_url", "kom_url", "provisioning_url"):
        assert forbidden not in src, f"gateway must not reference {forbidden}"


def test_only_kom_calls_the_kms():
    callers = []
    for svc in ADAPTER_SERVICES:
        src = _source(svc)
        if "enc_keys" in src or "kms_registry" in src or "load_registry" in src:
            callers.append(svc)
    assert callers == ["key_orchestration_manager"], (
        f"only KOM may call the KMS, but these do: {callers}")
