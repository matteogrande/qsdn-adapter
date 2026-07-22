"""
Async client for the ONOS REST API (read-only topology discovery).

Endpoints used (ONOS, default port 8181, basic auth onos/rocks):
  GET /onos/v1/devices
  GET /onos/v1/links

This is an OUTBOUND read from the adapter to the SDN controller — a separate
channel from the inbound ONOS->Northbound request path. It does not break the
"Northbound Gateway is the only entry point" invariant.
"""
from __future__ import annotations

import httpx

from shared.settings import get_settings


async def fetch_devices_and_links() -> tuple[list[dict], list[dict]]:
    settings = get_settings()
    auth = (settings.onos_user, settings.onos_password)
    base = settings.onos_base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=settings.http_timeout, auth=auth) as client:
        dev_resp = await client.get(f"{base}/onos/v1/devices")
        dev_resp.raise_for_status()
        link_resp = await client.get(f"{base}/onos/v1/links")
        link_resp.raise_for_status()
    devices = dev_resp.json().get("devices", [])
    links = link_resp.json().get("links", [])
    return devices, links
