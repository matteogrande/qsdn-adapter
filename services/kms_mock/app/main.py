"""
Simulated KMS exposing ETSI GS QKD 014 -inspired endpoints. One instance per
city (configured via env: CITY, SAE_ID, PORT). Keys are simulated — no real
quantum key distribution happens here.
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets

from fastapi import FastAPI, Query

CITY = os.getenv("CITY", "unknown")
SAE_ID = os.getenv("SAE_ID", f"{CITY}-sae")

app = FastAPI(title=f"KMS Mock · {CITY}", version="0.1.0")


def _random_key(size_bits: int) -> str:
    raw = secrets.token_bytes(max(size_bits // 8, 1))
    return base64.b64encode(raw).decode()


def _deterministic_key(key_id: str, size_bits: int) -> str:
    # Reproducible "same key" for dec_keys given a key_ID.
    digest = hashlib.sha256(key_id.encode()).digest()
    raw = (digest * (size_bits // 8 // len(digest) + 1))[: max(size_bits // 8, 1)]
    return base64.b64encode(raw).decode()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "kms_mock", "city": CITY, "sae_id": SAE_ID}


@app.get("/api/v1/keys/{sae_id}/status")
def status(sae_id: str) -> dict:
    return {
        "source_KME_ID": f"{CITY}-kme",
        "target_KME_ID": f"{sae_id}-kme",
        "master_SAE_ID": SAE_ID,
        "slave_SAE_ID": sae_id,
        "key_size": 256,
        "stored_key_count": 1000,
        "max_key_count": 100000,
        "max_key_per_request": 128,
        "status": "available",
    }


@app.get("/api/v1/keys/{sae_id}/enc_keys")
def enc_keys(sae_id: str,
             number: int = Query(1, ge=1),
             size: int = Query(256, ge=8)) -> dict:
    keys = [{"key_ID": f"{CITY}-{secrets.token_hex(8)}",
             "key": _random_key(size)} for _ in range(number)]
    return {"keys": keys}


@app.get("/api/v1/keys/{sae_id}/dec_keys")
def dec_keys(sae_id: str,
             key_ID: list[str] = Query(default=[]),
             size: int = Query(256, ge=8)) -> dict:
    keys = [{"key_ID": kid, "key": _deterministic_key(kid, size)} for kid in key_ID]
    return {"keys": keys}
