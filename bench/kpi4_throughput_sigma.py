"""
KPI 4 — Throughput T(n) and scalability index sigma(n) under concurrent load.

For each concurrency level n, fires a fixed batch of circuits with n workers in
flight and measures throughput T(n) = completed / elapsed. The scalability index
is sigma(n) = T(n)/T(2) · 2/n  (1.0 = perfect scaling relative to the n=2
baseline). Two panels, one measure each (never a dual axis).
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import httpx

import common as c
import style
from style import SERIES, STATUS

LEVELS = [2, 4, 8, 16, 32, 64]
REQUESTS_PER_LEVEL = 240
SCENARIO = ("Torino", "Genova")   # short path: stress the stack, not routing


def _one(client: httpx.Client, i: int) -> int:
    rid = f"kpi4-{int(time.time()*1000)}-{i}"
    status, _, _ = c.post_circuit(client, c.make_request(*SCENARIO, rid))
    return status


def measure_level(n: int) -> dict:
    limits = httpx.Limits(max_connections=n + 8, max_keepalive_connections=n + 8)
    with httpx.Client(timeout=30.0, limits=limits) as client:
        # small warmup so connections are established before timing
        _one(client, -1)
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=n) as pool:
            results = list(pool.map(lambda i: _one(client, i),
                                    range(REQUESTS_PER_LEVEL)))
        elapsed = time.perf_counter() - t0
    ok = sum(1 for s in results if s == 200)
    tput = REQUESTS_PER_LEVEL / elapsed
    print(f"  n={n:>3}: {tput:7.1f} req/s  ({ok}/{REQUESTS_PER_LEVEL} ok, "
          f"{elapsed:.2f}s)")
    return {"n": n, "throughput": round(tput, 2), "ok": ok,
            "total": REQUESTS_PER_LEVEL, "elapsed_s": round(elapsed, 3)}


def run() -> list[dict]:
    rows = [measure_level(n) for n in LEVELS]
    base = next((r["throughput"] for r in rows if r["n"] == 2), rows[0]["throughput"])
    for r in rows:
        r["sigma"] = round((r["throughput"] / base) * (2.0 / r["n"]), 4)
    return rows


def plot(rows: list[dict]) -> None:
    style.apply_style()
    import matplotlib.pyplot as plt

    ns = [r["n"] for r in rows]
    tput = [r["throughput"] for r in rows]
    sigma = [r["sigma"] for r in rows]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    ax1.plot(ns, tput, "o-", color=SERIES[0], linewidth=2, markersize=8)
    for x, y in zip(ns, tput):
        ax1.annotate(f"{y:.0f}", (x, y), textcoords="offset points",
                     xytext=(0, 10), ha="center", fontsize=9)
    ax1.set_xscale("log", base=2)
    ax1.set_xticks(ns); ax1.set_xticklabels(ns)
    ax1.set_xlabel("Concorrenza n (richieste in volo)")
    ax1.set_ylabel("Throughput T(n)  (req/s)")
    ax1.set_title("Throughput T(n)")

    ax2.axhline(1.0, color=STATUS["good"], linestyle="--", linewidth=1.6,
                label="Scaling ideale (σ=1)")
    ax2.plot(ns, sigma, "o-", color=SERIES[6], linewidth=2, markersize=8,
             label="σ(n) misurato")
    for x, y in zip(ns, sigma):
        ax2.annotate(f"{y:.2f}", (x, y), textcoords="offset points",
                     xytext=(0, 10), ha="center", fontsize=9)
    ax2.set_xscale("log", base=2)
    ax2.set_xticks(ns); ax2.set_xticklabels(ns)
    ax2.set_xlabel("Concorrenza n")
    ax2.set_ylabel("Indice di scalabilità σ(n)")
    ax2.set_ylim(0, max(sigma + [1.0]) * 1.15)
    ax2.set_title("Scalabilità σ(n) = T(n)/T(2)·2/n")
    ax2.legend(loc="upper right")

    fig.suptitle("KPI 4 — Throughput e scalabilità sotto carico concorrente",
                 fontsize=13, fontweight="bold", color=style.INK["primary"])
    fig.tight_layout()
    style.savefig(fig, "kpi4_throughput_sigma.png")


if __name__ == "__main__":
    print("KPI 4 — throughput T(n) and scalability sigma(n)")
    rows = run()
    c.write_csv("kpi4_throughput_sigma.csv", rows,
                ["n", "throughput", "sigma", "ok", "total", "elapsed_s"])
    plot(rows)
