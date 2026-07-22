"""
Outbound client for the gateway.

ARCHITECTURAL INVARIANT: the Northbound API Gateway may ONLY talk to the
Identity & Auth service. This module deliberately references *only*
settings.identity_url. Do not add calls to any other microservice here.
"""
from __future__ import annotations

import httpx

from shared.models import AdapterContext
from shared.settings import get_settings


async def forward_to_identity(ctx: AdapterContext) -> AdapterContext:
    settings = get_settings()
    url = f"{settings.identity_url}/identity/v1/authorize"
    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        resp = await client.post(url, json=ctx.model_dump())
        resp.raise_for_status()
        return AdapterContext.model_validate(resp.json())
