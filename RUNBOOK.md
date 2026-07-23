# QSDN — Runbook di test e demo (dall'inizio alla fine)

Guida operativa per testare il progetto e mostrarlo live al professore.
Tutti i comandi vanno lanciati dalla cartella `qsdn-adapter/`.

Tre modalità, in ordine di importanza per la demo:

- **Mock** (default): tutto funziona, nessuna dipendenza esterna. È la demo principale.
- **Dashboard web**: la stessa cosa, ma visiva.
- **Full mesh reale (Next Door / ETSI 014)**: scambio chiavi reale via mTLS. Il "wow" di interoperabilità.

> ONOS/Mininet (topologia scoperta dal controller SDN) richiede hardware x86 e non
> gira su Mac Apple Silicon: per la demo la topologia è statica (`TOPOLOGY_SOURCE=static`,
> già di default). Il codice ONOS resta nel progetto ed è testato a parte.

---

## 0. Prerequisiti (una volta)

1. Avvia **Docker Desktop** e assegnagli almeno **4–6 GB** di RAM
   (Settings → Resources). Per la modalità full mesh reale, meglio 6–8 GB.
2. Scompatta il progetto ed entra nella cartella:
   ```bash
   unzip qsdn-adapter.zip
   cd qsdn-adapter
   chmod +x scripts/*.sh ndks/*.sh
   ```
3. Verifica di avere il file giusto:
   ```bash
   docker --version && docker compose version
   ```

---

## 1. Ripartire da zero (pulizia)

Da lanciare ogni volta che vuoi ripartire pulito (rimuove container/reti residui):

```bash
docker compose --profile ndks --profile sdn down --remove-orphans -v
docker rm -f $(docker ps -aq --filter "name=qsdn-") 2>/dev/null
docker rm -f onos-c mininet-c 2>/dev/null
docker network prune -f
docker ps -a          # non deve mostrare container qsdn-/kme-/onos/mininet
```

---

## 2. MODALITÀ MOCK — la demo principale

### 2.1 Avvio

```bash
docker compose up -d --build
docker compose ps        # devi vedere 22 servizi "Up"
```

I 22 servizi: 6 microservizi dell'adapter (gateway, identity, topology, pce, kom,
provisioning) + audit-log + dashboard + 14 KMS mock (milano…verona, inclusi i 5
nodi relay trusted Parma/La Spezia/Padova/Pavia/Ferrara).

### 2.2 Le "spie" (health check)

```bash
curl http://localhost:8080/health     # Northbound API Gateway
curl http://localhost:8082/health     # Topology Manager  -> "source":"static"
curl http://localhost:8086/health     # Audit Log
```

### 2.3 Guardare la topologia caricata

```bash
curl -s http://localhost:8082/topology/v1/graph | python3 -m json.tool
```
Devi vedere il mesh a 11 nodi (Milano, Torino, Genova, Venezia, Bologna, Verona +
i 5 nodi relay trusted Parma, La Spezia, Padova, Pavia, Ferrara) e 17 link.

### 2.4 La demo: richiesta di circuito Monza → Venezia

```bash
bash scripts/demo_onos_request.sh
```
Atteso: `status: PROVISIONED`, `resolved_source_domain: Milano KMS`,
`selected_path: ["Milano KMS","Parma KMS","Padova KMS","Venezia KMS"]` (via il nodo
relay trusted Parma, hub della rete), una chiave simulata, e in fondo l'audit trail
con gli 8 eventi della catena.

### 2.5 L'audit trail (la prova che la catena ha attraversato tutti i livelli)

```bash
curl -s "http://localhost:8086/audit/v1/events?request_id=req-demo-001" | python3 -m json.tool
```
Sequenza attesa: request_received → auth_validated → endpoints_resolved →
topology_attached → path_computed → keys_retrieved → service_provisioned → response_returned.

### 2.6 Provare altre richieste (per capire il path engine)

```bash
curl -s -X POST http://localhost:8080/adapter/v1/virtual-circuits \
  -H "Content-Type: application/json" \
  -d '{"request_id":"test-1","source":"Torino","destination":"Bologna","service_type":"qkd_virtual_circuit","key_size":256,"num_keys":2,"priority":"normal"}' \
  | python3 -m json.tool
```
Atteso: percorso `["Torino KMS","Milano KMS","Parma KMS","Bologna KMS"]` (3 hop, via
il relay trusted Parma — il percorso più corto per Bologna passa da Parma) e 2 chiavi.

### 2.7 Il fallback (l'effetto che piace al prof)

Modo semplice, dalla **dashboard** (vedi §3): clicca il link Milano–Parma nel grafo
per abbatterlo (oppure, nel pannello "Scenario di simulazione", scegli il link
Milano→Parma nel controllo "Guasto link" e premi "Abbatti / ripristina link"), poi
rilancia la richiesta → il percorso si ricalcola via il relay Pavia.

Modo da terminale: apri `config/topology.yaml`, sul link `milano`↔`parma` metti
`status: down`, poi:
```bash
curl -s -X POST http://localhost:8082/topology/v1/refresh >/dev/null
bash scripts/demo_onos_request.sh
```
Ora il percorso Monza→Venezia diventa
`["Milano KMS","Pavia KMS","Parma KMS","Padova KMS","Venezia KMS"]`
(4 hop) — il traffico usa il relay Pavia come backup breve verso Parma.
Per ripristinare: rimetti `status: up` e rifai il refresh.
(Il refresh vede subito la modifica perché `config/` è montata nei container.)

---

## 3. DASHBOARD WEB (demo visiva)

Con lo stack su (§2.1), apri nel browser:

```
http://localhost:8090
```

Cosa mostrare:
- la **topologia** (mesh + 5 nodi relay trusted Parma/La Spezia/Padova/Pavia/Ferrara, link verdi =
  su, rossi tratteggiati = giù);
- compila **sorgente/destinazione** (es. Monza / Venezia) e premi **Provisiona**:
  il percorso si evidenzia in oro, con domini risolti, KMS e chiavi;
- guarda la **catena dei 6 microservizi** accendersi in sequenza (pilotata dall'audit);
- **clicca un link** (es. Milano–Parma) per abbatterlo → rilancia → il percorso si
  ricalcola (fallback dal vivo);
- pannello **Scenario di simulazione** (editor completo e generico): abbatti/ripristina
  **qualsiasi link** ("Guasto link"), imposta il key pool di **qualsiasi nodo** a un
  valore 0-100% ("Key pool", es. 8% per esaurirlo e forzare il rerouting), aggiungi
  città (Firenze/Roma/Napoli hanno già il KMS) o link a runtime; "Reset topologia"
  torna alla topologia iniziale.

---

## 4. FULL MESH REALE — interoperabilità ETSI 014 (Next Door)

Tutte le 14 città — 9 main KMS + 5 trusted relay (Parma, La Spezia, Padova, Pavia,
Ferrara) — diventano KME Next Door reali; ogni coppia scambia chiavi vere via HTTPS +
mutual-TLS, relay inclusi. Serve un po' più di RAM e ~25s di warm-up.

### 4.1 Genera i certificati (una volta)

```bash
./ndks/generate_certs.sh        # crea ndks/certs/ (CA + certificati per le 14 città)
```

### 4.2 Avvia adapter + 14 KME reali

```bash
KMS_REGISTRY=/app/config/kms_registry.ndks.yaml \
  docker compose --profile ndks up -d --build
docker compose ps               # mock-stack + 14 kme-* "Up" (9 main + 5 relay)
```

### 4.3 Attendi il warm-up e verifica un KME

```bash
sleep 25
curl -sk -u none:none https://localhost:8011/api/v1/keys/health 2>/dev/null; echo   # (facoltativo)
```
(In alternativa, guarda i log: `docker compose logs --tail=20 kme-milano`.)

### 4.4 La demo: ora la chiave è REALE

```bash
# id univoco ad ogni run → niente eventi vecchi in mezzo (l'audit è append-only)
REQ_ID="req-demo-$(date +%s)"
curl -s -X POST "http://localhost:8080/adapter/v1/virtual-circuits" \
  -H "Content-Type: application/json" \
  -d "{\"request_id\":\"${REQ_ID}\",\"source\":\"Monza\",\"destination\":\"Venezia\",\"service_type\":\"qkd_virtual_circuit\",\"key_size\":256,\"num_keys\":1,\"priority\":\"normal\"}" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); print("status:",r["status"],"| path:",r.get("selected_path"))'
curl -s "http://localhost:8086/audit/v1/events?request_id=${REQ_ID}" \
  | python3 -c 'import json,sys; ev=[e for e in json.load(sys.stdin)["events"] if e["event_type"]=="keys_retrieved"]; e=ev[-1] if ev else None; print("backend:",e["backend"],"| key_shared_verified:",e["key_shared_verified"]) if e else print("nessun keys_retrieved: richiesta rifiutata")'
```
Usa sempre un `request_id` nuovo (lo `$(date +%s)` qui sopra): l'audit è
append-only, quindi con un id fisso rischi di leggere l'evento di una run vecchia.
Nell'evento `keys_retrieved` devi vedere `backend` `{"source":"ndks","destination":"ndks"}`
e `key_shared_verified: True`: la stessa chiave è stata recuperata anche al KME di
destinazione via `dec_keys`. **Ora anche i trusted relay (Parma, La Spezia, Padova)
sono KME Next Door reali**, quindi qualsiasi coppia è reale, incluse quelle che
attraversano o terminano su un relay (es. `Monza→Venezia` via Parma→Padova, o `Monza→Parma`).

### 4.5 Tornare al mock

```bash
docker compose --profile ndks down
docker compose up -d
```

---

## 5. TEST AUTOMATICI (da mostrare al prof)

Senza Docker, dimostra correttezza e invarianti architetturali:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest
python -m pytest -v          # 12 test passano (topologia, path, fallback, ONOS, invarianti)
```

E l'intera catena in-process, senza Docker:
```bash
python scripts/run_local_e2e.py    # PROVISIONED, path via Parma/Padova, audit completo
deactivate
```

I test degli **invarianti** (`tests/test_architecture_constraints.py`) provano che
il Gateway chiama solo Identity & Auth e che solo il KOM chiama i KMS.

---

## 6. SPEGNERE / PULIRE

```bash
docker compose --profile ndks down        # se avevi avviato la modalità reale
docker compose down                        # ferma lo stack mock
# per cancellare anche il volume dell'audit:
docker compose down -v
```

---

## 7. Riferimento rapido (porte e URL)

| Cosa | URL / porta |
|---|---|
| Northbound API Gateway (ingresso ONOS) | http://localhost:8080 · `/docs` |
| Dashboard web | http://localhost:8090 |
| Topology Manager (vista topologia) | http://localhost:8082/topology/v1/graph |
| Audit Log | http://localhost:8086/audit/v1/events |
| KMS mock (milano…verona) | http://localhost:9001 … 9014 |
| KME reali Next Door (profilo ndks) | https://localhost:8011 … 8018 |

Endpoint principale: `POST /adapter/v1/virtual-circuits` sul gateway (porta 8080).
Corpo: `{request_id, source, destination, service_type, key_size, num_keys, priority}`.

---

## Ordine minimo per una demo di 5 minuti

```bash
# 1) pulizia + avvio
docker compose down --remove-orphans -v 2>/dev/null
docker compose up -d --build
docker compose ps                      # 19 Up

# 2) demo + audit
bash scripts/demo_onos_request.sh

# 3) dashboard nel browser
open http://localhost:8090             # (su macOS apre il browser)

# 4) fallback: nella dashboard clicca il link Milano-Parma (o "Guasto link") e rilancia

# 5) (opzionale) interoperabilità reale
./ndks/generate_certs.sh
KMS_REGISTRY=/app/config/kms_registry.ndks.yaml docker compose --profile ndks up -d --build
sleep 25 && bash scripts/demo_onos_request.sh
```

---

## 8. VALUTAZIONE DEI KPI (i grafici per la tesi)

Gli script in `bench/` pilotano la pila, leggono l'audit log e generano **7 grafici**
(+ CSV) in `bench/results/`. Ogni KPI risponde a una domanda:

| KPI | Domanda | File |
|---|---|---|
| 1 | Dove va a finire il tempo? (latenza per microservizio) | `kpi1_stage_latency.png` |
| 2 | La latenza cresce con gli hop? L(h) | `kpi2_hops_latency.png` |
| 3 | Quanto costa il rerouting dopo un guasto? | `kpi3_cost_hops_scenario.png` |
| 4 | Regge il carico? Throughput T(n) e scalabilità σ(n) | `kpi4_throughput_sigma.png` |
| 5 | Quanto è più lento il backend reale (mTLS)? | `kpi5_mock_vs_ndks.png` |
| 6 | Accetta i validi e rifiuta gli impossibili? (200 vs 503) | `kpi6_success_rate.png` |
| 7 | Il pool si ricarica sotto soglia? ρ_i nel tempo | `kpi7_pool_rho.png` |

### 8.1 Preparazione (una volta)

```bash
# lo stack mock deve essere su (vedi §2.1)
docker compose up -d --build

# dipendenze del harness, nella venv del progetto
source .venv/bin/activate
pip install -r bench/requirements.txt
```

### 8.2 Generare tutti i grafici in un colpo

```bash
cd bench && python run_all.py       # KPI 1,2,3,4,6,7 + KPI 5 (lato mock)
```
I `.png` e `.csv` finiscono in `bench/results/`. (Dura ~3-4 min: ~2000 richieste + il KPI 7 che dura 40s.)

### 8.3 Un KPI alla volta (opzionale)

```bash
cd bench
python kpi1_stage_latency.py        # barra impilata dei 6 microservizi
python kpi2_hops_latency.py         # L(h): latenza vs hop + retta di fit
python kpi3_cost_hops_scenario.py   # hop nominale vs dopo guasto Milano-Parma
python kpi4_throughput_sigma.py     # T(n) e sigma(n) al variare della concorrenza
python kpi6_success_rate.py         # 200 vs 503 per scenario
python kpi7_pool_rho.py             # rho_i(t) con pre-fetching (dente di sega)
```

### 8.4 KPI 5 — confronto mock vs Next Door REALE (due passaggi)

```bash
# passaggio 1: con lo stack mock su
cd bench && python kpi5_mock_vs_ndks.py         # -> kpi5_mock.csv

# passaggio 2: avvia il backend reale, aspetta il warm-up, rimisura
cd ..
./ndks/generate_certs.sh                         # solo la prima volta
KMS_REGISTRY=/app/config/kms_registry.ndks.yaml docker compose --profile ndks up -d --build
sleep 30
cd bench && python kpi5_mock_vs_ndks.py          # rileva ndks -> kpi5_ndks.csv + grafico di confronto

# torna al mock quando hai finito
cd .. && docker compose --profile ndks down && docker compose up -d
```

### 8.5 Pagina-report unica per la tesi

```bash
cd bench && python make_report.py    # -> bench/results/report.html (grafici incorporati)
```
Aprila nel browser e **Stampa → Salva come PDF** per la tesi:
```bash
open bench/results/report.html       # su macOS
```

### 8.6 Dashboard live (le schermate visive)

Con lo stack su, apri `http://localhost:8090`: topologia, provisioning con percorso
in oro, fallback cliccando un link, e il pannello "Scenario di simulazione" per il pool.
(vedi §3 per il dettaglio di cosa mostrare)
