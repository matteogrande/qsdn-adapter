"""
KPI 6 — Success/error rate per scenario (HTTP 200 vs 503).

Exercises admissible and non-admissible scenarios and measures the fraction of
200 (PROVISIONED) vs 503 (REJECTED) responses. Non-admissible cases are induced
honestly: a destination with no KMS in the mesh (no path), and a source KMS with
an exhausted key pool (insufficient key material). Both surface as 503 through
the gateway mapping.
"""
from __future__ import annotations

import time

import common as c
import style
from style import STATUS

# city -> mock KMS port (see docker-compose)
KMS_PORT = {"milano": 9001, "torino": 9002, "genova": 9003, "venezia": 9004,
            "bologna": 9005, "parma": 9009, "padova": 9011}
REPS = 20


def _set_pool(city: str, **fields) -> None:
    import httpx
    port = KMS_PORT[city]
    httpx.post(f"http://localhost:{port}/api/v1/pool", json=fields, timeout=10.0)


def _batch(client, src, dst, reps) -> tuple[int, int]:
    ok = err = 0
    for i in range(reps):
        rid = f"kpi6-{src}-{dst}-{int(time.time()*1000)}-{i}"
        status, _, _ = c.post_circuit(client, c.make_request(src, dst, rid))
        if status == 200:
            ok += 1
        else:
            err += 1
    return ok, err


def run() -> list[dict]:
    rows: list[dict] = []
    with c.new_client() as client:
        # 1-2: admissible circuits
        for src, dst, name in [("Torino", "Bologna", "Percorso valido\n(Torino→Bologna)"),
                               ("Milano", "Venezia", "Percorso valido\n(Milano→Venezia)")]:
            ok, err = _batch(client, src, dst, REPS)
            rows.append({"scenario": name, "ok_200": ok, "err_503": err})

        # 3: destination not in the mesh (Roma has a domain but no topology node)
        ok, err = _batch(client, "Milano", "Roma", REPS)
        rows.append({"scenario": "Nodo fuori topologia\n(Milano→Roma)",
                     "ok_200": ok, "err_503": err})

        # 4: source key pool exhausted -> insufficient key material (503).
        # Disable pre-fetch (rate 0) so the pool stays empty for the batch.
        try:
            _set_pool("milano", level=0.0, prefetch_rate=0)
            time.sleep(0.3)
            ok, err = _batch(client, "Milano", "Venezia", REPS)
            rows.append({"scenario": "Pool sorgente esaurito\n(Milano ρ=0)",
                         "ok_200": ok, "err_503": err})
        finally:
            _set_pool("milano", level=1.0, prefetch_rate=200)

    for r in rows:
        tot = r["ok_200"] + r["err_503"]
        r["success_rate"] = round(100.0 * r["ok_200"] / tot, 1) if tot else 0.0
        print(f"  {r['scenario'].replace(chr(10),' ')}: "
              f"{r['ok_200']} OK / {r['err_503']} 503")
    return rows


def plot(rows: list[dict]) -> None:
    style.apply_style()
    import matplotlib.pyplot as plt

    labels = [r["scenario"] for r in rows]
    ok = [r["ok_200"] for r in rows]
    err = [r["err_503"] for r in rows]
    tot = [o + e for o, e in zip(ok, err)]
    ok_pct = [100.0 * o / t if t else 0 for o, t in zip(ok, tot)]
    err_pct = [100.0 * e / t if t else 0 for e, t in zip(err, tot)]

    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    b1 = ax.bar(labels, ok_pct, color=STATUS["good"], label="200 PROVISIONED",
                edgecolor=style.INK["surface"], linewidth=2)
    b2 = ax.bar(labels, err_pct, bottom=ok_pct, color=STATUS["critical"],
                label="503 REJECTED", edgecolor=style.INK["surface"], linewidth=2)
    for rects, vals, base in [(b1, ok_pct, [0]*len(rows)), (b2, err_pct, ok_pct)]:
        for rect, v, bs in zip(rects, vals, base):
            if v > 6:
                ax.text(rect.get_x() + rect.get_width()/2, bs + v/2,
                        f"{v:.0f}%", ha="center", va="center", color="white",
                        fontsize=10, fontweight="bold")

    ax.set_ylabel("Quota risposte (%)")
    ax.set_ylim(0, 100)
    ax.set_title("KPI 6 — Tasso di successo/errore per scenario (200 vs 503)")
    ax.legend(loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.28))
    fig.tight_layout()
    style.savefig(fig, "kpi6_success_rate.png")


if __name__ == "__main__":
    print("KPI 6 — success/error rate (200 vs 503)")
    rows = run()
    c.write_csv("kpi6_success_rate.csv", rows,
                ["scenario", "ok_200", "err_503", "success_rate"])
    plot(rows)
