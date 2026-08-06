"""
KPI 2 — Latency as a function of hop count, L(h).

Sweeps many source/destination pairs, groups the measured end-to-end latency by
the hop count the PCE actually chose (read from the audit trail), and plots the
*median* per hop with interquartile (25th-75th percentile) whiskers and a linear
fit. Median + IQR are used deliberately instead of mean ± std: the end-to-end
latency has a heavy right tail (occasional container/GC/scheduler stalls push a
few samples to 150-270 ms), and both the mean and the standard deviation are
dominated by those rare outliers. The median is unaffected by them and the IQR
describes the spread of the bulk of the distribution, so the per-hop points sit
where the typical request actually lands and the whiskers no longer overlap
across every hop. A roughly linear L(h) empirically backs the additive-cost
premise of the routing objective function.
"""
from __future__ import annotations

import itertools
import time

import common as c
import style
from style import SERIES, STATUS

CITIES = ["milano", "torino", "genova", "venezia", "bologna", "parma",
          "la_spezia", "padova", "pavia", "ferrara", "verona"]
REPS = 20           # repetitions per pair (more samples -> tighter percentiles)
MAX_PAIRS = 55      # all C(11,2) pairs, so the sparse 4-hop bucket is well filled


def run() -> list[dict]:
    pairs = [p for p in itertools.combinations(CITIES, 2)][:MAX_PAIRS]
    rows: list[dict] = []
    with c.new_client() as client:
        for src, dst in pairs:
            for i in range(REPS):
                rid = f"kpi2-{src}-{dst}-{int(time.time()*1000)}-{i}"
                status, _, latency = c.post_circuit(
                    client, c.make_request(src, dst, rid))
                if status != 200:
                    continue
                events = c.fetch_events(client, rid)
                st = c.stage_latencies_ms(events)
                info = c.path_info(events)
                if st is None or info["hops"] is None:
                    continue
                rows.append({"src": src, "dst": dst, "hops": int(info["hops"]),
                             "e2e_ms": round(sum(st.values()), 3),
                             "http_ms": round(latency, 3),
                             "cost": info["cost"]})
    print(f"  collected {len(rows)} samples "
          f"across hops {sorted({r['hops'] for r in rows})}")
    return rows


def plot(rows: list[dict]) -> None:
    import statistics as stats
    style.apply_style()
    import matplotlib.pyplot as plt

    by_hop: dict[int, list[float]] = {}
    for r in rows:
        by_hop.setdefault(r["hops"], []).append(r["e2e_ms"])
    hops = sorted(by_hop)
    # Median as the central value (outlier-robust), interquartile range as the
    # whiskers. yerr is asymmetric: lower = median-p25, upper = p75-median.
    meds = [stats.median(by_hop[h]) for h in hops]
    lo_err = [meds[i] - c.percentile(by_hop[h], 25) for i, h in enumerate(hops)]
    hi_err = [c.percentile(by_hop[h], 75) - meds[i] for i, h in enumerate(hops)]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(hops, meds, yerr=[lo_err, hi_err], fmt="o-", color=SERIES[0],
                ecolor=style.INK["baseline"], elinewidth=1.5, capsize=4,
                markersize=8, linewidth=2,
                label="Latenza mediana misurata L(h)  (baffi = IQR)",
                zorder=3)
    for h, m in zip(hops, meds):
        ax.annotate(f"{m:.1f} ms", (h, m), textcoords="offset points",
                    xytext=(0, 12), ha="center", fontsize=9,
                    color=style.INK["primary"])

    # linear fit L(h) = a + b·h on the medians to show additivity
    if len(hops) >= 2:
        n = len(hops)
        sx, sy = sum(hops), sum(meds)
        sxx = sum(h * h for h in hops)
        sxy = sum(h * m for h, m in zip(hops, meds))
        b = (n * sxy - sx * sy) / (n * sxx - sx * sx)
        a = (sy - b * sx) / n
        xs = [min(hops), max(hops)]
        ax.plot(xs, [a + b * x for x in xs], "--", color=STATUS["serious"],
                linewidth=1.8, zorder=2,
                label=f"Fit lineare: L(h) = {a:.1f} + {b:.1f}·h")

    ax.set_xlabel("Numero di hop sul percorso (h)")
    ax.set_ylabel("Latenza end-to-end (ms)")
    ax.set_title("KPI 2 — Latenza in funzione degli hop  L(h)")
    ax.set_xticks(hops)
    ax.legend(loc="upper left")
    fig.tight_layout()
    style.savefig(fig, "kpi2_hops_latency.png")


if __name__ == "__main__":
    print("KPI 2 — latency vs hop count")
    rows = run()
    c.write_csv("kpi2_hops_latency.csv", rows,
                ["src", "dst", "hops", "e2e_ms", "http_ms", "cost"])
    plot(rows)
