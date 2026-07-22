#!/usr/bin/env python3
"""Python ONOS-client simulation for the Monza -> Venezia demo."""
import json
import os
import sys

import httpx

GATEWAY = os.getenv("GATEWAY", "http://localhost:8080")
AUDIT = os.getenv("AUDIT", "http://localhost:8086")

REQUEST = {
    "request_id": "req-demo-py-001",
    "source": "Monza",
    "destination": "Venezia",
    "service_type": "qkd_virtual_circuit",
    "key_size": 256,
    "num_keys": 1,
    "priority": "normal",
}


def main() -> int:
    with httpx.Client(timeout=15.0) as client:
        print(f"==> POST {GATEWAY}/adapter/v1/virtual-circuits")
        resp = client.post(f"{GATEWAY}/adapter/v1/virtual-circuits", json=REQUEST)
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))

        print(f"\n==> Audit trail for {REQUEST['request_id']}")
        audit = client.get(f"{AUDIT}/audit/v1/events",
                           params={"request_id": REQUEST["request_id"]})
        print(json.dumps(audit.json(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
