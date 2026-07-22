"""
ETSI GS QKD 014 client. ARCHITECTURAL INVARIANT: this is the ONLY place in
the whole adapter that talks to the KMS.

The adapter is BACKEND-AGNOSTIC. Each city in the KMS registry declares a
`backend`:

  backend: mock   -> our kms_mock; plain HTTP GET, no auth (simulated keys)
  backend: ndks   -> a REAL Next Door KME (ETSI 014); HTTPS + mutual-TLS + POST
                     (keys are genuinely shared between the two KMEs)

Same ETSI 014 contract (enc_keys / dec_keys / status, key_ID, master/slave SAE)
regardless of backend — that abstraction is what realises interoperability.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import httpx
import yaml

from shared.settings import get_settings


@lru_cache
def load_registry() -> dict[str, dict]:
    data = yaml.safe_load(Path(get_settings().kms_registry).read_text("utf-8")) or {}
    return data.get("kms", {})


def kms_for_node(node_id: str) -> dict | None:
    return load_registry().get(node_id)


def _is_ndks(kms: dict) -> bool:
    return kms.get("backend") == "ndks"


def _ndks_kwargs(kms: dict) -> dict:
    # present the city's SAE client certificate (mutual TLS); skip server-cert
    # verification (KME certs are self-signed, CN = UUID), exactly like Next Door
    # does between its own KMEs.
    return {"cert": (kms["sae_cert"], kms["sae_key"]), "verify": False}


# --- Get Status ------------------------------------------------------------
async def get_status(kms: dict, peer_sae_id: str | None = None) -> dict:
    settings = get_settings()
    if _is_ndks(kms):
        url = f"{kms['base_url']}/api/v1/keys/{peer_sae_id}/status"
        async with httpx.AsyncClient(timeout=settings.http_timeout, **_ndks_kwargs(kms)) as c:
            r = await c.get(url); r.raise_for_status(); return r.json()
    url = f"{kms['base_url']}/api/v1/keys/{kms['sae_id']}/status"
    async with httpx.AsyncClient(timeout=settings.http_timeout) as c:
        r = await c.get(url); r.raise_for_status(); return r.json()


# --- Get Key (master SAE) --------------------------------------------------
async def get_enc_keys(source_kms: dict, slave_sae_id: str,
                       number: int, size: int) -> list[dict]:
    settings = get_settings()
    if _is_ndks(source_kms):
        # real ETSI 014: path = SLAVE sae, authenticate as the MASTER (source) SAE
        url = f"{source_kms['base_url']}/api/v1/keys/{slave_sae_id}/enc_keys"
        async with httpx.AsyncClient(timeout=settings.http_timeout, **_ndks_kwargs(source_kms)) as c:
            r = await c.post(url, json={"number": number, "size": size})
            r.raise_for_status(); return r.json().get("keys", [])
    # mock: GET on the source KMS' own sae_id
    url = f"{source_kms['base_url']}/api/v1/keys/{source_kms['sae_id']}/enc_keys"
    async with httpx.AsyncClient(timeout=settings.http_timeout) as c:
        r = await c.get(url, params={"number": number, "size": size})
        r.raise_for_status(); return r.json().get("keys", [])


# --- Get Key with Key IDs (slave SAE) --------------------------------------
async def get_dec_keys(dest_kms: dict, master_sae_id: str,
                       key_ids: list[str]) -> list[dict]:
    settings = get_settings()
    if _is_ndks(dest_kms):
        # real ETSI 014: path = MASTER sae, authenticate as the SLAVE (dest) SAE
        url = f"{dest_kms['base_url']}/api/v1/keys/{master_sae_id}/dec_keys"
        body = {"key_IDs": [{"key_ID": k} for k in key_ids]}
        async with httpx.AsyncClient(timeout=settings.http_timeout, **_ndks_kwargs(dest_kms)) as c:
            r = await c.post(url, json=body); r.raise_for_status(); return r.json().get("keys", [])
    url = f"{dest_kms['base_url']}/api/v1/keys/{dest_kms['sae_id']}/dec_keys"
    async with httpx.AsyncClient(timeout=settings.http_timeout) as c:
        r = await c.get(url, params={"key_ID": key_ids})
        r.raise_for_status(); return r.json().get("keys", [])
