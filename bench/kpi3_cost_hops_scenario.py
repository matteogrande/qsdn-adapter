"""
KPI 3 — Path cost and hop count per scenario: nominal vs after a link fault.

Records the chosen path (hops + cost) for several circuits, then brings the
Milano–Parma link down (runtime edit, reversible), re-runs the same circuits,
and quantifies the rerouting. The link is restored at the end.
"""
from __future__ import annotations

import time

import common as c
import style
from style import SERIES

FAULT = ("milano", "parma")
# Circuits whose nominal shortest path traverses the Milano–Parma link, so the
# fault forces a reroute (verified against the topology):
#   Milano→Venezia : milano-parma-padova-venezia            (3 hop)
#   Milano→Bologna : milano-parma-bologna                   (2 hop)
#   Milano→Padova  : milano-parma-padova                    (2 hop)
#   Torino→Bologna : torino-MILANO-PARMA-bologna            (3 hop)  <- passa per Milano-Parma
SCENARIOS = [
    ("Milano", "Venezia"),
    ("Milano", "Bologna"),
    ("Milano", "Padova"),
    ("Torino", "Bologna"),
]


def _set_link(client, source, target, status) -> None:
    client.post(f"{c.TOPOLOGY_URL}/topology/v1/link",
                json={"source": source, "target": target,
                      "status": status, "action": "set_status"})


def _measure(client, src, dst, tag) -> dict:
    rid = f"kpi3-{tag}-{src}-{dst}-{int(time.time()*1000)}"
    status, _, _ = c.post_circuit(client, c.make_request(src, dst, rid))
    events = c.fetch_events(client, rid)
    info = c.path_info(events)
    return {"hops": info["hops"], "cost": info["cost"],
            "path": " → ".join(info["path"] or []), "http_status": status}


def run() -> list[dict]:
    rows: list[dict] = []
    with c.new_client() as client:
        print("  nominal topology...")
        nominal = {sc: _measure(client, *sc, "nom") for sc in SCENARIOS}
        try:
            print(f"  bringing {FAULT[0]}–{FAULT[1]} DOWN...")
            _set_link(client, *FAULT, "down")
            time.sleep(0.5)
            faulted = {sc: _measure(client, *sc, "flt") for sc in SCENARIOS}
        finally:
            print(f"  restoring {FAULT[0]}–{FAULT[1]} UP...")
            _set_link(client, *FAULT, "up")
        for sc in SCENARIOS:
            n, f = nominal[sc], faulted[sc]
            rows.append({
                "scenario": f"{sc[0]}→{sc[1]}",
                "hops_nominal": n["hops"], "cost_nominal": n["cost"],
                "path_nominal": n["path"],
                "hops_fault": f["hops"], "cost_fault": f["cost"],
                "path_fault": f["path"],
                "d_hops": (f["hops"] or 0) - (n["hops"] or 0),
            })
            print(f"    {sc[0]}→{sc[1]}: {n['hops']}→{f['hops']} hop "
                  f"(+{(f['hops'] or 0)-(n['hops'] or 0)})")
    return rows


def plot(rows: list[dict]) -> None:
    style.apply_style()
    import matplotlib.pyplot as plt
    import numpy as np

    labels = [r["scenario"] for r in rows]
    x = np.arange(len(labels))
    w = 0.38
    nom = [r["hops_nominal"] or 0 for r in rows]
    flt = [r["hops_fault"] or 0 for r in rows]

    fig, ax = plt.subplots(figsize=(9, 5))
    b1 = ax.bar(x - w/2, nom, w, color=SERIES[0], label="Nominale",
                edgecolor=style.INK["surface"], linewidth=2)
    b2 = ax.bar(x + w/2, flt, w, color=SERIES[5], label="Dopo guasto Milano–Parma",
                edgecolor=style.INK["surface"], linewidth=2)
    for bars in (b1, b2):
        for rect in bars:
            h = rect.get_height()
            ax.text(rect.get_x() + rect.get_width()/2, h + 0.05, f"{int(h)}",
                    ha="center", va="bottom", fontsize=10,
                    color=style.INK["primary"], fontweight="bold")

    ax.set_xticks(x, labels)
    ax.set_ylabel("Hop del percorso")
    ax.set_ylim(0, max(flt + nom) + 1)
    ax.set_title("KPI 3 — Hop del percorso per scenario: nominale vs rerouting")
    ax.legend(loc="upper left")
    fig.tight_layout()
    style.savefig(fig, "kpi3_cost_hops_scenario.png")


if __name__ == "__main__":
    print("KPI 3 — path cost/hops, nominal vs fault")
    rows = run()
    c.write_csv("kpi3_cost_hops_scenario.csv", rows,
                ["scenario", "hops_nominal", "cost_nominal", "path_nominal",
                 "hops_fault", "cost_fault", "path_fault", "d_hops"])
    plot(rows)
