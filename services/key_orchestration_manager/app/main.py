"""
Key Orchestration Manager — selects which KMS to query along the computed
path and retrieves (simulated) key material via the ETSI 014 client, then
forwards to Service Provisioning.

Orchestration model (simulated, ETSI-014-flavoured):
  * master  = first KMS on the path (source domain) -> enc_keys
  * slave   = last  KMS on the path (destination)   -> dec_keys(key_IDs)
  * intermediates are queried for status (relay nodes)
"""
from __future__ import annotations

import httpx
from fastapi import FastAPI

from shared.logging_client import audit
from shared.models import (AdapterContext, KeyInfo, KeyOrchestrationResult,
                           VirtualCircuitResponse)
from shared.settings import get_settings
from . import etsi014_client as etsi

app = FastAPI(title="QSDN · Key Orchestration Manager", version="0.1.0")


def _reject(ctx: AdapterContext, message: str) -> AdapterContext:
    ctx.status = "REJECTED"
    ctx.error = message
    ctx.response = VirtualCircuitResponse(
        request_id=ctx.request.request_id, status="REJECTED",
        source=ctx.request.source, destination=ctx.request.destination,
        resolved_source_domain=ctx.resolved.source_domain if ctx.resolved else None,
        resolved_destination_domain=ctx.resolved.destination_domain if ctx.resolved else None,
        selected_path=ctx.path.path_domains if ctx.path else [],
        message=message,
    )
    return ctx


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "key_orchestration_manager"}


@app.post("/kom/v1/orchestrate", response_model=AdapterContext)
async def orchestrate(ctx: AdapterContext) -> AdapterContext:
    if ctx.path is None or not ctx.path.path_nodes:
        return _reject(ctx, "Missing computed path")

    nodes = ctx.path.path_nodes
    source_kms = etsi.kms_for_node(nodes[0])
    dest_kms = etsi.kms_for_node(nodes[-1])
    if source_kms is None or dest_kms is None:
        return _reject(ctx, "No KMS registered for path endpoints")

    # KMS chain (trusted-node relay) for the response — labels of every hop.
    kms_chain: list[str] = []
    for node_id in nodes:
        kms = etsi.kms_for_node(node_id)
        if kms is None:
            return _reject(ctx, f"No KMS registered for node '{node_id}'")
        kms_chain.append(kms["label"])

    keys: list[KeyInfo] = []
    verified = False
    try:
        # master (source) KMS -> fresh keys toward the slave (destination) SAE
        enc = await etsi.get_enc_keys(
            source_kms, slave_sae_id=dest_kms["sae_id"],
            number=ctx.request.num_keys, size=ctx.request.key_size)
        key_ids = [k["key_ID"] for k in enc]
        keys = [KeyInfo(key_id=k["key_ID"], size=ctx.request.key_size,
                        status="available") for k in enc]

        # slave (destination) KMS -> retrieve the SAME keys by id.
        # Real proof of sharing for ndks<->ndks; best-effort otherwise.
        if key_ids:
            try:
                got = await etsi.get_dec_keys(
                    dest_kms, master_sae_id=source_kms["sae_id"], key_ids=key_ids)
                verified = len(got) == len(key_ids)
            except httpx.HTTPError as exc:
                await audit(ctx.request.request_id, "key_verify_skipped", error=str(exc))
    except httpx.HTTPError as exc:
        await audit(ctx.request.request_id, "kms_error", error=str(exc),
                    kms_called=kms_chain)
        return _reject(ctx, f"KMS query failed: {exc}")

    ctx.keys = KeyOrchestrationResult(kms_chain=kms_chain, keys=keys)
    ctx.status = "KEYED"
    await audit(ctx.request.request_id, "keys_retrieved",
                kms_called=kms_chain, keys=[k.key_id for k in keys],
                backend={"source": source_kms.get("backend", "mock"),
                         "destination": dest_kms.get("backend", "mock")},
                key_shared_verified=verified)

    settings = get_settings()
    url = f"{settings.provisioning_url}/provisioning/v1/provision"
    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        resp = await client.post(url, json=ctx.model_dump())
        resp.raise_for_status()
        return AdapterContext.model_validate(resp.json())
