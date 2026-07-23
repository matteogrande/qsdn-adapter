"""
KPI 5 — Latency: mock backend vs real Next Door (ETSI 014) backend.

Run this script once with the mock stack up, then once with the ndks profile up
(KMS_REGISTRY=...ndks.yaml docker compose --profile ndks up). It auto-detects the
backend from the `keys_retrieved` audit event and saves one CSV per backend; the
plot then compares whatever backends are present. The real backend is slower —
mTLS + two real KME round-trips — which is exactly the V>=2 interoperability
evidence, shown as a chart instead of a table.
"""
from __future__ import annotations

import glob
import time
from pathlib import Path

import common as c
import style
from style import SERIES

SCENARIO = ("Monza", "Venezia")
REPS = 25


def _backend_of(events: list[dict]) -> str:
    for ev in events:
        if ev["event_type"] == "keys_retrieved":
            b = ev.get("backend") or {}
            return b.get("source", "mock")
    return "unknown"


def run() -> tuple[str, list[dict]]:
    rows: list[dict] = []
    backend = "unknown"
    with c.new_client() as client:
        for i in range(REPS):
            rid = f"kpi5-{int(time.time()*1000)}-{i}"
            status, _, latency = c.post_circuit(
                client, c.make_request(*SCENARIO, rid))
            if status != 200:
                continue
            events = c.fetch_events(client, rid)
            st = c.stage_latencies_ms(events)
            if st is None:
                continue
            backend = _backend_of(events)
            rows.append({"backend": backend,
                         "e2e_ms": round(sum(st.values()), 3),
                         "kom_ms": round(st["Key Orchestration"], 3),
                         "http_ms": round(latency, 3)})
    print(f"  backend detected: {backend} — {len(rows)} samples")
    return backend, rows


def plot() -> None:
    import csv as _csv
    import statistics as stats
    style.apply_style()
    import matplotlib.pyplot as plt
    import numpy as np

    data: dict[str, dict[str, list[float]]] = {}
    for path in sorted(glob.glob(str(c.RESULTS_DIR / "kpi5_*.csv"))):
        with open(path) as f:
            rows = list(_csv.DictReader(f))
        if not rows:
            continue
        b = rows[0]["backend"]
        data[b] = {
            "e2e": [float(r["e2e_ms"]) for r in rows],
            "kom": [float(r["kom_ms"]) for r in rows],
        }
    if not data:
        return

    backends = list(data)                       # e.g. ["mock", "ndks"]
    order = {"mock": 0, "ndks": 1}
    backends.sort(key=lambda b: order.get(b, 9))
    metrics = [("e2e", "Latenza end-to-end"), ("kom", "Stadio Key Orchestration")]
    x = np.arange(len(metrics))
    w = 0.8 / max(len(backends), 1)
    color = {"mock": SERIES[0], "ndks": SERIES[5]}
    label = {"mock": "Mock (HTTP)", "ndks": "Next Door reale (mTLS)"}

    fig, ax = plt.subplots(figsize=(9, 5.5))
    for bi, b in enumerate(backends):
        means = [stats.mean(data[b][m]) for m, _ in metrics]
        errs = [stats.pstdev(data[b][m]) if len(data[b][m]) > 1 else 0
                for m, _ in metrics]
        bars = ax.bar(x + (bi - (len(backends)-1)/2) * w, means, w,
                      yerr=errs, capsize=4, color=color.get(b, SERIES[bi]),
                      label=label.get(b, b), edgecolor=style.INK["surface"],
                      linewidth=2, ecolor=style.INK["baseline"])
        for rect, m in zip(bars, means):
            ax.text(rect.get_x() + rect.get_width()/2, rect.get_height(),
                    f"{m:.0f}", ha="center", va="bottom", fontsize=9,
                    color=style.INK["primary"], fontweight="bold")

    ax.set_xticks(x, [m[1] for m in metrics])
    ax.set_ylabel("Latenza (ms)")
    ax.set_title("KPI 5 — Latenza: backend mock vs Next Door reale")
    ax.legend(loc="upper left")
    if len(backends) < 2:
        ax.text(0.5, 0.95, "Esegui anche col profilo ndks per il confronto",
                transform=ax.transAxes, ha="center", va="top",
                fontsize=9, color=style.INK["muted"])
    fig.tight_layout()
    style.savefig(fig, "kpi5_mock_vs_ndks.png")


if __name__ == "__main__":
    print("KPI 5 — mock vs Next Door latency")
    backend, rows = run()
    if rows:
        c.write_csv(f"kpi5_{backend}.csv", rows,
                    ["backend", "e2e_ms", "kom_ms", "http_ms"])
    plot()
