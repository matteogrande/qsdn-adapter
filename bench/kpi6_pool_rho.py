"""
KPI 7 — Key-pool level rho_i(t) with pre-fetching that activates below threshold.

Drives a real experiment against the Milano KMS pool and samples rho_i over time:

  Phase A (idle)   — pool full, rho flat.
  Phase B (load)   — concurrent circuits drain Milano below threshold; the
                     pre-fetch kicks in and rho oscillates around the threshold.
  Phase C (drain off) — load stops, pre-fetch tops the pool back up, then idles.

The measured rho comes straight from the KMS `GET /api/v1/pool`, so this is a
backend measurement, not a dashboard animation. Shaded bands mark the intervals
where the pre-fetch reported itself active.
"""
from __future__ import annotations

import threading
import time

import httpx

import common as c
import style
from style import SERIES, STATUS

KMS_URL = "http://localhost:9001"          # Milano KMS
SCENARIO = ("Milano", "Venezia")           # Milano è la sorgente -> drena il suo pool
NUM_KEYS = 5
LOAD_WORKERS = 4
# IMPORTANT: sample MUCH finer than prefetch_tick, otherwise the sampler aliases
# with the refill ticks and misses the saw-tooth bottom (making a valley look
# like it stops above the threshold). 0.03s sampling vs 0.10s tick = ~3 samples
# per tick, so the touch of the 0.30 line is always captured.
SAMPLE_DT = 0.03
PHASE_A, PHASE_B, PHASE_C = 5.0, 26.0, 9.0

# Clean saw-tooth (low-/high-watermark model). The pre-fetch trigger is
# deterministic in the KMS: the instant a draw brings rho down to the 0.30 low
# watermark, the refill arms and carries rho smoothly back up to the 0.90 high
# watermark. A short prefetch_tick keeps the undershoot tiny so the bottoms sit
# right on the threshold line.
POOL_CFG = {"capacity": 500, "threshold": 0.30, "refill_target": 0.90,
            "prefetch_rate": 20, "prefetch_tick": 0.10, "level": 1.0}


def _config_pool() -> None:
    httpx.post(f"{KMS_URL}/api/v1/pool", json=POOL_CFG, timeout=10.0)


def _sample() -> dict:
    return httpx.get(f"{KMS_URL}/api/v1/pool", timeout=10.0).json()


def _load_worker(stop: threading.Event) -> None:
    with c.new_client() as client:
        while not stop.is_set():
            rid = f"kpi7-{int(time.time()*1e6)}"
            c.post_circuit(client, c.make_request(*SCENARIO, rid, num_keys=NUM_KEYS))
            time.sleep(0.12)


def run() -> list[dict]:
    _config_pool()
    samples: list[dict] = []
    t0 = time.perf_counter()
    stop = threading.Event()
    workers: list[threading.Thread] = []

    def poll_until(deadline: float) -> None:
        while time.perf_counter() - t0 < deadline:
            s = _sample()
            samples.append({"t": round(time.perf_counter() - t0, 2),
                            "rho": s["rho"], "stored": s["stored"],
                            "prefetching": bool(s["prefetching"]),
                            "threshold": s["threshold"]})
            time.sleep(SAMPLE_DT)

    print("  phase A (idle)...")
    poll_until(PHASE_A)

    print("  phase B (load, draining below threshold)...")
    for _ in range(LOAD_WORKERS):
        t = threading.Thread(target=_load_worker, args=(stop,), daemon=True)
        t.start(); workers.append(t)
    poll_until(PHASE_A + PHASE_B)

    print("  phase C (load off, pre-fetch recovers)...")
    stop.set()
    for t in workers:
        t.join(timeout=2.0)
    poll_until(PHASE_A + PHASE_B + PHASE_C)

    _config_pool()   # leave the pool full again
    print(f"  collected {len(samples)} samples over "
          f"{samples[-1]['t'] if samples else 0:.1f}s")
    return samples


def plot(samples: list[dict]) -> None:
    style.apply_style()
    import matplotlib.pyplot as plt

    t = [s["t"] for s in samples]
    rho = [s["rho"] for s in samples]
    thr = samples[0]["threshold"] if samples else 0.3

    fig, ax = plt.subplots(figsize=(11, 5.5))

    # shade intervals where pre-fetch was active
    in_band = False
    start = 0.0
    for s in samples:
        if s["prefetching"] and not in_band:
            in_band, start = True, s["t"]
        elif not s["prefetching"] and in_band:
            ax.axvspan(start, s["t"], color=STATUS["warning"], alpha=0.15, lw=0)
            in_band = False
    if in_band:
        ax.axvspan(start, t[-1], color=STATUS["warning"], alpha=0.15, lw=0)
    ax.axvspan(0, 0, color=STATUS["warning"], alpha=0.15, lw=0,
               label="Pre-fetch attivo")

    ax.axhline(thr, color=STATUS["critical"], linestyle="--", linewidth=1.6,
               label=f"Soglia ρ = {thr:.2f}")
    ax.plot(t, rho, "-", color=SERIES[0], linewidth=2, label="ρ Milano (misurato)")

    # phase separators
    for x in (PHASE_A, PHASE_A + PHASE_B):
        ax.axvline(x, color=style.INK["baseline"], linewidth=1, linestyle=":")
    ax.text(PHASE_A/2, 1.02, "idle", ha="center", color=style.INK["muted"], fontsize=9)
    ax.text(PHASE_A + PHASE_B/2, 1.02, "carico (drain)", ha="center",
            color=style.INK["muted"], fontsize=9)
    ax.text(PHASE_A + PHASE_B + PHASE_C/2, 1.02, "carico off (pool stabile)",
            ha="center", color=style.INK["muted"], fontsize=9)

    ax.set_xlabel("Tempo (s)")
    ax.set_ylabel("Livello pool  ρ_i = stored / capacity")
    ax.set_ylim(0, 1.1)
    ax.set_xlim(0, t[-1] if t else 1)
    ax.set_title("KPI 7 — Livello di pool ρ_i nel tempo con pre-fetching alla soglia")
    ax.legend(loc="lower right", ncol=1)
    fig.tight_layout()
    style.savefig(fig, "kpi7_pool_rho.png")


if __name__ == "__main__":
    print("KPI 7 — pool level rho_i(t) with pre-fetching")
    samples = run()
    c.write_csv("kpi7_pool_rho.csv", samples,
                ["t", "rho", "stored", "prefetching", "threshold"])
    plot(samples)
