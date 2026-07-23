"""
KPI 1 — End-to-end provisioning latency decomposed per microservice.

Fires N repetitions of a few representative circuits, reads each request's audit
trail, splits the end-to-end latency into the six microservice stages, and draws
a horizontal stacked bar per scenario (mean over the repetitions). This is the
headline chart: it shows the whole stack AND where the time goes (the Key
Orchestration stage dominates — that is the KMS round-trip cost).
"""
from __future__ import annotations

import time

import common as c
import style
from style import SERIES

# Representative circuits spanning medium/long paths, all from real KMS nodes.
SCENARIOS = [
    ("Genova", "Verona"),      # lungo  (4 hop: Genova-La Spezia-Parma-Padova-Verona)
    ("Torino", "Bologna"),     # medio  (3 hop: Torino-Milano-Parma-Bologna)
    ("Milano", "Venezia"),     # medio  (3 hop: Milano-Parma-Padova-Venezia)
]
REPS = 30


def run() -> list[dict]:
    rows: list[dict] = []
    with c.new_client() as client:
        for src, dst in SCENARIOS:
            acc: dict[str, list[float]] = {s: [] for s in c.STAGE_LABELS}
            e2e: list[float] = []
            for i in range(REPS):
                rid = f"kpi1-{src}-{dst}-{int(time.time()*1000)}-{i}"
                status, _, latency = c.post_circuit(
                    client, c.make_request(src, dst, rid))
                if status != 200:
                    continue
                events = c.fetch_events(client, rid)
                st = c.stage_latencies_ms(events)
                if st is None:
                    continue
                for k, v in st.items():
                    acc[k].append(v)
                e2e.append(sum(st.values()))
            row = {"scenario": f"{src}→{dst}", "reps": len(e2e),
                   "e2e_mean_ms": round(sum(e2e) / len(e2e), 2) if e2e else 0}
            for s in c.STAGE_LABELS:
                row[s] = round(sum(acc[s]) / len(acc[s]), 3) if acc[s] else 0.0
            rows.append(row)
            print(f"  {row['scenario']}: e2e {row['e2e_mean_ms']} ms "
                  f"over {row['reps']} reps")
    return rows


def plot(rows: list[dict]) -> None:
    style.apply_style()
    import matplotlib.pyplot as plt

    labels = [r["scenario"] for r in rows]
    fig, ax = plt.subplots(figsize=(9, 0.9 * len(rows) + 1.6))
    left = [0.0] * len(rows)
    for si, stage in enumerate(c.STAGE_LABELS):
        vals = [r[stage] for r in rows]
        bars = ax.barh(labels, vals, left=left, height=0.55,
                       color=SERIES[si], label=stage,
                       edgecolor=style.INK["surface"], linewidth=2)
        # direct-label only the segments wide enough to fit their value
        for rect, v, base in zip(bars, vals, left):
            if v > 0.4:
                ax.text(base + v / 2, rect.get_y() + rect.get_height() / 2,
                        f"{v:.1f}", ha="center", va="center", fontsize=8,
                        color="white", fontweight="bold")
        left = [a + b for a, b in zip(left, vals)]
    for y, total in enumerate(left):
        ax.text(total + max(left) * 0.01, y, f"{total:.1f} ms", va="center",
                ha="left", fontsize=10, color=style.INK["primary"],
                fontweight="bold")

    ax.set_xlabel("Latenza end-to-end (ms)")
    ax.set_title("KPI 1 — Latenza di provisioning scomposta per microservizio")
    ax.set_xlim(0, max(left) * 1.18)
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.18))
    fig.tight_layout()
    style.savefig(fig, "kpi1_stage_latency.png")


if __name__ == "__main__":
    print("KPI 1 — per-microservice latency breakdown")
    rows = run()
    c.write_csv("kpi1_stage_latency.csv", rows,
                ["scenario", "reps", "e2e_mean_ms", *c.STAGE_LABELS])
    plot(rows)
