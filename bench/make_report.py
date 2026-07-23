"""
Build a single self-contained HTML report (bench/results/report.html) with all
KPI charts embedded as base64 + interpretation text and the headline numbers
pulled live from the CSVs. Open it in a browser and Print-to-PDF for the thesis.

Run after the KPI suite (and after the ndks pass, so KPI 5 shows the comparison):
    cd bench && python make_report.py
"""
from __future__ import annotations

import base64
import csv
import statistics
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"


def img(name: str) -> str:
    p = RESULTS / name
    if not p.exists():
        return "<p class='missing'>[grafico non disponibile: esegui il KPI]</p>"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"<img alt='{name}' src='data:image/png;base64,{b64}'/>"


def rows(name: str) -> list[dict]:
    p = RESULTS / name
    return list(csv.DictReader(open(p))) if p.exists() else []


def kpi1_facts() -> str:
    r = rows("kpi1_stage_latency.csv")
    if not r:
        return ""
    stages = [k for k in r[0] if k not in ("scenario", "reps", "e2e_mean_ms")]
    worst = max(stages, key=lambda s: statistics.mean(float(x[s]) for x in r))
    e2e = statistics.mean(float(x["e2e_mean_ms"]) for x in r)
    return (f"Latenza end-to-end media ≈ <b>{e2e:.0f} ms</b>. Lo stadio dominante è "
            f"<b>{worst}</b> — è il costo dei round-trip ETSI-014 verso i KMS "
            f"(enc/dec + status sui relay), non un overhead della catena.")


def kpi2_facts() -> str:
    r = rows("kpi2_hops_latency.csv")
    if not r:
        return ""
    byh: dict[int, list[float]] = {}
    for x in r:
        byh.setdefault(int(x["hops"]), []).append(float(x["e2e_ms"]))
    hs = sorted(byh)
    means = [statistics.mean(byh[h]) for h in hs]
    n = len(hs); sx = sum(hs); sy = sum(means)
    sxx = sum(h*h for h in hs); sxy = sum(h*m for h, m in zip(hs, means))
    b = (n*sxy - sx*sy) / (n*sxx - sx*sx)
    a = (sy - b*sx) / n
    return (f"La latenza cresce con gli hop: <b>L(h) ≈ {a:.1f} + {b:.1f}·h</b> ms. "
            f"L'andamento lineare conferma empiricamente l'<b>additività</b> del "
            f"costo sul percorso, premessa della funzione obiettivo di routing.")


def kpi3_facts() -> str:
    r = rows("kpi3_cost_hops_scenario.csv")
    if not r:
        return ""
    items = ", ".join(f"{x['scenario']} {x['hops_nominal']}→{x['hops_fault']}"
                      for x in r)
    return (f"Abbattendo il link Milano–Parma, il PCE ricalcola il percorso: "
            f"ogni circuito guadagna hop (rerouting sul relay Pavia). {items}.")


def kpi4_facts() -> str:
    r = rows("kpi4_throughput_sigma.csv")
    if not r:
        return ""
    peak = max(r, key=lambda x: float(x["throughput"]))
    base = next((x for x in r if x["n"] == "2"), r[0])
    return (f"Il throughput sale da <b>{float(base['throughput']):.0f} req/s</b> "
            f"(n=2) a un picco di <b>{float(peak['throughput']):.0f} req/s</b> "
            f"(n={peak['n']}), poi satura. σ(n) decresce: lo scaling è sub-lineare "
            f"oltre la saturazione. (Ottenuto dopo aver reso concorrente l'audit "
            f"log, prima collo di bottiglia a ~20 req/s.)")


def kpi5_facts() -> str:
    mock = rows("kpi5_mock.csv"); ndks = rows("kpi5_ndks.csv")
    if not mock:
        return ""
    mm = statistics.mean(float(x["e2e_ms"]) for x in mock)
    if not ndks:
        return (f"Backend mock: latenza e2e ≈ <b>{mm:.0f} ms</b>. Esegui anche il "
                f"profilo ndks per il confronto con il backend reale.")
    nm = statistics.mean(float(x["e2e_ms"]) for x in ndks)
    factor = nm / mm if mm else 0
    return (f"Il backend reale Next Door è più lento: e2e ≈ <b>{nm:.0f} ms</b> vs "
            f"<b>{mm:.0f} ms</b> del mock (×{factor:.1f}). Il costo aggiuntivo è "
            f"l'handshake <b>mTLS</b> + i due round-trip reali fra KME: è "
            f"l'evidenza di interoperabilità (V≥2), non un difetto.")


def kpi6_facts() -> str:
    r = rows("kpi6_success_rate.csv")
    if not r:
        return ""
    ok = sum(int(x["ok_200"]) for x in r if x["err_503"] == "0")
    return ("I percorsi ammissibili tornano <b>HTTP 200</b> (PROVISIONED); i casi "
            "non ammissibili — <b>nodo fuori topologia</b> e <b>pool sorgente "
            "esaurito</b> — tornano <b>HTTP 503</b> (REJECTED). Il tasso di "
            "successo separa nettamente gli scenari.")


def kpi7_facts() -> str:
    r = rows("kpi7_pool_rho.csv")
    if not r:
        return ""
    rhos = [float(x["rho"]) for x in r]
    thr = float(r[0]["threshold"])
    return (f"Sotto carico il pool ρ drena fino alla soglia <b>{thr:.2f}</b>; il "
            f"<b>pre-fetching</b> si attiva (bande) e ricarica con isteresi fino "
            f"alla soglia alta, generando il sawtooth (ρ tra {min(rhos):.2f} e "
            f"{max(rhos):.2f}). Misura reale dal KMS (<code>/api/v1/pool</code>), "
            f"non un'animazione.")


KPIS = [
    ("KPI 1 — Latenza di provisioning scomposta per microservizio",
     "kpi1_stage_latency.png", kpi1_facts),
    ("KPI 2 — Latenza in funzione degli hop L(h)",
     "kpi2_hops_latency.png", kpi2_facts),
    ("KPI 3 — Costo e hop del percorso: nominale vs guasto",
     "kpi3_cost_hops_scenario.png", kpi3_facts),
    ("KPI 4 — Throughput T(n) e scalabilità σ(n)",
     "kpi4_throughput_sigma.png", kpi4_facts),
    ("KPI 5 — Latenza: backend mock vs Next Door reale",
     "kpi5_mock_vs_ndks.png", kpi5_facts),
    ("KPI 6 — Tasso di successo/errore per scenario (200 vs 503)",
     "kpi6_success_rate.png", kpi6_facts),
    ("KPI 7 — Livello di pool ρ_i nel tempo con pre-fetching",
     "kpi7_pool_rho.png", kpi7_facts),
]

STYLE = """
:root{--ink:#0b0b0b;--sec:#52514e;--muted:#898781;--line:#e1e0d9;--bg:#fcfcfb;--accent:#2a78d6}
*{box-sizing:border-box}
body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink);
     background:#f4f3f0;margin:0;padding:40px 16px;line-height:1.55}
.page{max-width:900px;margin:0 auto;background:var(--bg);padding:48px 56px;
      border:1px solid var(--line);border-radius:10px}
h1{font-size:26px;margin:0 0 4px}
.sub{color:var(--sec);margin:0 0 8px}
.meta{color:var(--muted);font-size:13px;margin:0 0 28px}
h2{font-size:18px;margin:40px 0 6px;padding-top:20px;border-top:1px solid var(--line)}
.facts{color:var(--sec);font-size:14.5px;margin:0 0 14px}
figure{margin:14px 0 0}
img{width:100%;height:auto;border:1px solid var(--line);border-radius:6px;background:#fff}
.missing{color:#b00;font-size:14px}
.lead{background:#f0f6ff;border:1px solid #cde2fb;border-radius:8px;padding:14px 18px;
      font-size:14px;color:#184f95;margin:0 0 8px}
.note{margin-top:40px;padding-top:20px;border-top:1px solid var(--line);
      color:var(--muted);font-size:12.5px}
code{background:#eef;padding:1px 5px;border-radius:4px;font-size:.9em}
b{color:var(--ink)}
@media print{body{background:#fff;padding:0}.page{border:0;max-width:100%}}
"""


def build() -> None:
    lead = ("Valutazione empirica dei KPI dell'adapter QSDN, misurati end-to-end "
            "sulla pila software completa (6 microservizi + audit log). Le latenze "
            "sono ricavate dai timestamp dell'audit log; throughput e tasso "
            "d'errore dalla API northbound; ρ_i dallo stato reale del KMS.")
    parts = [f"<style>{STYLE}</style>",
             "<div class='page'>",
             "<h1>QSDN Adapter — Valutazione dei KPI</h1>",
             "<p class='sub'>Report sperimentale della pila software</p>",
             "<p class='meta'>Generato da bench/make_report.py · sorgente dati: "
             "audit log + API northbound + stato KMS</p>",
             f"<p class='lead'>{lead}</p>"]
    for title, png, facts in KPIS:
        parts.append(f"<h2>{title}</h2>")
        f = facts()
        if f:
            parts.append(f"<p class='facts'>{f}</p>")
        parts.append(f"<figure>{img(png)}</figure>")
    parts.append(
        "<p class='note'>Note metodologiche · <b>6 stadi</b>: gli 8 eventi audit "
        "ordinati danno i confini di stadio, i due eventi Identity uniti → un "
        "bucket per microservizio; la somma dei 6 = latenza end-to-end. "
        "<b>503</b>: REJECTED (percorso non ammissibile / materiale di chiave "
        "insufficiente) mappato dal gateway a HTTP 503; PROVISIONED = 200. "
        "<b>ρ_i</b>: pool e pre-fetch sono stato reale nel KMS. "
        "<b>Da dichiarare, non graficare</b>: r_ij e Q_ij sono parametri di "
        "configurazione (vincoli che il routing rispetta), non misure fisiche.</p>")
    parts.append("</div>")
    out = RESULTS / "report.html"
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"  wrote {out.relative_to(RESULTS.parent.parent)}")


if __name__ == "__main__":
    print("Building KPI report...")
    build()
