# bench/ — Harness di misura dei KPI

Strumento di misura che pilota lo stack (northbound API + audit log), raccoglie i
dati e genera i grafici della tesi in `bench/results/` (un `.png` + un `.csv` per
KPI). Le misure vengono prese **solo** dove le prenderebbe un operatore reale: la
API pubblica sul gateway (8080) e l'audit log (8086). Nessuno script parla
direttamente ai KMS (tranne il controllo del pool per il KPI 7).

## Prerequisiti

```bash
# 1) stack mock su
docker compose up -d --build      # 22 servizi "Up"

# 2) dipendenze del harness (nella venv del progetto)
source .venv/bin/activate
pip install -r bench/requirements.txt
```

## Esecuzione

Tutta la suite mock in un colpo (KPI 1,2,3,4,6,7 + KPI 5 lato mock):

```bash
cd bench && python run_all.py
```

Oppure un KPI alla volta:

```bash
cd bench
python kpi1_stage_latency.py      # barra impilata: 6 stadi per microservizio
python kpi2_hops_latency.py       # L(h): latenza vs hop + fit lineare
python kpi3_cost_hops_scenario.py # costo/hop nominale vs guasto Milano–Parma
python kpi4_throughput_sigma.py   # T(n) e sigma(n) al variare della concorrenza
python kpi6_success_rate.py       # 200 vs 503 per scenario
python kpi7_pool_rho.py           # rho_i(t) con pre-fetching sotto soglia
```

## KPI 5 — mock vs Next Door reale (due passaggi)

```bash
# passaggio 1: con lo stack mock su
cd bench && python kpi5_mock_vs_ndks.py        # scrive kpi5_mock.csv

# passaggio 2: riavvia in profilo reale, poi ripeti
./ndks/generate_certs.sh
KMS_REGISTRY=/app/config/kms_registry.ndks.yaml \
  docker compose --profile ndks up -d --build
sleep 25
cd bench && python kpi5_mock_vs_ndks.py        # rileva ndks -> kpi5_ndks.csv, grafico di confronto
```

## Cosa esce (in `bench/results/`)

| File | KPI |
|---|---|
| `kpi1_stage_latency.{png,csv}` | Latenza scomposta per microservizio |
| `kpi2_hops_latency.{png,csv}` | L(h) latenza vs hop |
| `kpi3_cost_hops_scenario.{png,csv}` | Costo/hop nominale vs guasto |
| `kpi4_throughput_sigma.{png,csv}` | Throughput T(n) e scalabilità sigma(n) |
| `kpi5_{mock,ndks}.csv`, `kpi5_mock_vs_ndks.png` | Mock vs Next Door reale |
| `kpi6_success_rate.{png,csv}` | Tasso 200 vs 503 per scenario |
| `kpi7_pool_rho.{png,csv}` | Livello pool rho_i(t) con pre-fetching |

## Note metodologiche

- **Scomposizione in 6 stadi** (KPI 1): gli 8 eventi audit ordinati danno i confini
  di stadio; i due eventi di Identity sono uniti così ogni bucket = un microservizio.
  La somma dei 6 stadi = latenza end-to-end da audit.
- **KPI 6 / 503**: un percorso non ammissibile (nodo fuori topologia, oppure pool
  sorgente esaurito) risale la catena come `REJECTED` e il gateway lo mappa a
  **HTTP 503**; un circuito valido è **HTTP 200**.
- **KPI 7 / rho_i**: il pool e il pre-fetching sono stato **reale** nel KMS
  (`GET /api/v1/pool`), non un'animazione della dashboard. L'esperimento configura
  il pool a runtime (`POST /api/v1/pool`) e misura rho mentre il carico lo drena.
