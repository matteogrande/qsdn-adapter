"""
Simulated KMS exposing ETSI GS QKD 014 -inspired endpoints. One instance per
city (configured via env: CITY, SAE_ID, PORT). Keys are simulated — no real
quantum key distribution happens here.

Key-pool model (rho_i)
----------------------
Each KMS keeps a *real* in-memory key pool: `stored` keys out of `capacity`.
  * rho_i = stored / capacity  is the pool level of node i.
  * every enc_keys draw consumes `number` keys (master side).
  * a background pre-fetching task refills the pool whenever it drops below
    `threshold` (rho_i < threshold): this is the "pre-fetching che si attiva
    sotto soglia" of the thesis. Above threshold the refill is idle.
  * if a draw asks for more keys than are stored, the KMS returns 503
    (insufficient key material) — the honest failure that propagates up the
    chain and shows up in the 200-vs-503 KPI.

`GET  /api/v1/pool` exposes the live level (for the rho_i(t) KPI plot).
`POST /api/v1/pool` lets an experiment set the level / tune the model at
runtime (e.g. drop Milano to 8% to force the pre-fetch to kick in) without a
container rebuild.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

CITY = os.getenv("CITY", "unknown")
SAE_ID = os.getenv("SAE_ID", f"{CITY}-sae")

# --- Pool configuration (env-overridable, per city) ------------------------ #
# Defaults are deliberately large so ordinary latency/throughput runs never
# deplete the pool (rho stays ~1, no spurious 503). The rho_i experiment shrinks
# capacity + level at runtime via POST /api/v1/pool to expose the sawtooth.
POOL_CAPACITY = int(os.getenv("POOL_CAPACITY", "100000"))
POOL_INIT = int(os.getenv("POOL_INIT", str(POOL_CAPACITY)))
POOL_THRESHOLD = float(os.getenv("POOL_THRESHOLD", "0.30"))   # low watermark: pre-fetch starts
POOL_REFILL_TARGET = float(os.getenv("POOL_REFILL_TARGET", "0.95"))  # high watermark: pre-fetch stops
PREFETCH_RATE = int(os.getenv("PREFETCH_RATE", "200"))        # keys added per tick
PREFETCH_TICK = float(os.getenv("PREFETCH_TICK", "0.5"))      # seconds between ticks


class PoolState:
    """Live key-pool state for this KMS (single instance per container)."""

    def __init__(self) -> None:
        self.capacity = POOL_CAPACITY
        self.stored = min(POOL_INIT, POOL_CAPACITY)
        self.threshold = POOL_THRESHOLD          # low watermark
        self.refill_target = POOL_REFILL_TARGET  # high watermark
        self.prefetch_rate = PREFETCH_RATE
        self.prefetch_tick = PREFETCH_TICK
        self.prefetching = False          # is the pre-fetch currently refilling?
        self.consumed_total = 0
        self.prefetched_total = 0
        self._lock = asyncio.Lock()

    @property
    def rho(self) -> float:
        return self.stored / self.capacity if self.capacity else 0.0

    async def consume(self, n: int) -> None:
        """Draw n keys, or raise 503 if the pool cannot cover the request."""
        async with self._lock:
            if n > self.stored:
                raise HTTPException(
                    status_code=503,
                    detail=(f"Insufficient key material on {CITY}: "
                            f"requested {n}, stored {self.stored}"),
                )
            self.stored -= n
            self.consumed_total += n
            # Deterministic low-watermark trigger: the instant a draw brings the
            # pool down to the threshold, arm the pre-fetch. The refill loop then
            # carries rho back up to the high watermark. Triggering here (not on
            # the poll) makes the saw-tooth bottom sit exactly on the threshold.
            if self.rho < self.threshold:
                self.prefetching = True

    async def prefetch_step(self) -> None:
        """One pre-fetch tick with hysteresis: dropping below the low watermark
        (threshold) starts a refill that continues until the high watermark
        (refill_target) is reached, then stops. This yields the classic pool
        saw-tooth instead of pinning rho at the threshold."""
        async with self._lock:
            if not self.prefetching and self.rho < self.threshold:
                self.prefetching = True           # crossed the low watermark
            if self.prefetching:
                target = int(self.refill_target * self.capacity)
                added = min(self.prefetch_rate, max(0, target - self.stored))
                self.stored += added
                self.prefetched_total += added
                if self.stored >= target:
                    self.prefetching = False       # reached the high watermark

    def snapshot(self) -> dict:
        return {
            "city": CITY,
            "stored": self.stored,
            "capacity": self.capacity,
            "rho": round(self.rho, 4),
            "threshold": self.threshold,
            "refill_target": self.refill_target,
            "prefetching": self.prefetching,
            "prefetch_rate": self.prefetch_rate,
            "consumed_total": self.consumed_total,
            "prefetched_total": self.prefetched_total,
            "ts": time.time(),
        }


pool = PoolState()


async def _prefetch_loop() -> None:
    while True:
        await pool.prefetch_step()
        await asyncio.sleep(pool.prefetch_tick)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_prefetch_loop())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title=f"KMS Mock · {CITY}", version="0.2.0", lifespan=lifespan)


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


# --- Pool observability / control (rho_i KPI) ------------------------------ #
@app.get("/api/v1/pool")
def get_pool() -> dict:
    return pool.snapshot()


class PoolUpdate(BaseModel):
    level: float | None = None          # set rho directly, 0..1 (e.g. 0.08)
    stored: int | None = None           # set absolute stored count
    threshold: float | None = None      # tune pre-fetch low watermark
    refill_target: float | None = None  # tune pre-fetch high watermark
    prefetch_rate: int | None = None    # tune refill speed (0 disables pre-fetch)
    prefetch_tick: float | None = None  # tune controller reaction delay (seconds)
    capacity: int | None = None
    prefetching: bool | None = None     # force the refill flag (e.g. reset)


@app.post("/api/v1/pool")
def set_pool(update: PoolUpdate) -> dict:
    if update.capacity is not None:
        pool.capacity = max(1, update.capacity)
    if update.threshold is not None:
        pool.threshold = min(max(update.threshold, 0.0), 1.0)
    if update.refill_target is not None:
        pool.refill_target = min(max(update.refill_target, 0.0), 1.0)
    if update.prefetch_rate is not None:
        pool.prefetch_rate = max(0, update.prefetch_rate)
    if update.prefetch_tick is not None:
        pool.prefetch_tick = max(0.05, update.prefetch_tick)
    if update.level is not None:
        pool.stored = int(min(max(update.level, 0.0), 1.0) * pool.capacity)
    if update.stored is not None:
        pool.stored = min(max(update.stored, 0), pool.capacity)
    if update.prefetching is not None:
        pool.prefetching = update.prefetching
    return pool.snapshot()


@app.get("/api/v1/keys/{sae_id}/status")
def status(sae_id: str) -> dict:
    return {
        "source_KME_ID": f"{CITY}-kme",
        "target_KME_ID": f"{sae_id}-kme",
        "master_SAE_ID": SAE_ID,
        "slave_SAE_ID": sae_id,
        "key_size": 256,
        "stored_key_count": pool.stored,
        "max_key_count": pool.capacity,
        "max_key_per_request": 128,
        "status": "available" if pool.stored > 0 else "exhausted",
    }


@app.get("/api/v1/keys/{sae_id}/enc_keys")
async def enc_keys(sae_id: str,
                   number: int = Query(1, ge=1),
                   size: int = Query(256, ge=8)) -> dict:
    # Master-side draw: consume from this KMS' own pool (503 if insufficient).
    await pool.consume(number)
    keys = [{"key_ID": f"{CITY}-{secrets.token_hex(8)}",
             "key": _random_key(size)} for _ in range(number)]
    return {"keys": keys}


@app.get("/api/v1/keys/{sae_id}/dec_keys")
def dec_keys(sae_id: str,
             key_ID: list[str] = Query(default=[]),
             size: int = Query(256, ge=8)) -> dict:
    # Slave-side retrieval by key_ID: reproduces the shared key, no pool draw.
    keys = [{"key_ID": kid, "key": _deterministic_key(kid, size)} for kid in key_ID]
    return {"keys": keys}
