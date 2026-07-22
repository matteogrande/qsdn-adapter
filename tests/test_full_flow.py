"""End-to-end demo test. Requires the docker-compose stack to be running."""
import httpx
import pytest

GATEWAY = "http://localhost:8080"
AUDIT = "http://localhost:8086"

pytestmark = pytest.mark.integration


def _stack_up() -> bool:
    try:
        httpx.get(f"{GATEWAY}/health", timeout=2.0).raise_for_status()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _stack_up(), reason="docker-compose stack not running")
def test_monza_venezia_end_to_end():
    req = {"request_id": "req-test-e2e", "source": "Monza",
           "destination": "Venezia", "key_size": 256, "num_keys": 1}
    r = httpx.post(f"{GATEWAY}/adapter/v1/virtual-circuits", json=req, timeout=15.0)
    r.raise_for_status()
    body = r.json()

    assert body["status"] == "PROVISIONED"
    assert body["resolved_source_domain"] == "Milano KMS"
    assert body["resolved_destination_domain"] == "Venezia KMS"
    assert body["selected_path"][0] == "Milano KMS"
    assert body["selected_path"][-1] == "Venezia KMS"
    assert body["keys"], "expected at least one simulated key"

    audit = httpx.get(f"{AUDIT}/audit/v1/events",
                      params={"request_id": "req-test-e2e"}, timeout=5.0).json()
    types = {e["event_type"] for e in audit["events"]}
    assert "request_received" in types and "service_provisioned" in types
