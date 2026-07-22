# QSDN Southbound Adapter

Layer di astrazione **QKD Southbound Adapter** che si interpone tra un controller
**SDN/ONOS** (simulato) e una rete **QKD/KMS** (simulata, ispirata a
**ETSI GS QKD 014**). Implementa i sei microservizi dell'architettura concordata,
più un Audit Log orizzontale e un KMS mock ETSI 014.

> Tesi magistrale — l'obiettivo **non** è realizzare una rete QKD fisica, ma
> simulare il comportamento architetturale e l'orchestrazione di una rete
> QKD interoperabile.

---

## 1. Scopo del progetto

ONOS riceve/genera una richiesta di *circuito virtuale* tra due endpoint
(es. `Monza → Venezia`) e chiede all'adapter una chiave condivisa. L'adapter:

1. riceve la richiesta REST (Northbound API Gateway);
2. la autentica e risolve gli endpoint logici su domini KMS (Identity & Auth);
3. carica la topologia QKD/KMS (Topology Manager);
4. calcola il percorso ottimale (Path Computation Engine);
5. interroga i KMS lungo il path via ETSI 014 e recupera/simula le chiavi
   (Key Orchestration Manager — **unico** servizio che parla con i KMS);
6. compone la risposta JSON finale (Service Provisioning);
7. ogni passo scrive sull'Audit Log orizzontale.

## 2. I tre livelli (cosa è reale, cosa è simulato)

| Livello | Componente | In questo progetto |
|---|---|---|
| Alto | **ONOS / Mininet (SDN)** | *Esterno, reale.* Mininet costruisce la rete (il mesh), ONOS la scopre e la espone via REST. **Crea la topologia** che l'adapter legge. ONOS non gestisce le chiavi: richiede un circuito virtuale (REST client demo in `scripts/`). |
| Intermedio | **QKD Southbound Adapter** | *Implementato qui.* I 6 microservizi FastAPI + Audit Log. È il cuore della tesi. |
| Basso | **KMS / rete QKD (ETSI 014)** | *Simulato.* `kms_mock` (una istanza per città della rete) che espone endpoint ETSI 014. Nessuna QKD reale: le chiavi sono generate/simulate. |

**Topologia attuale: mesh a 11 città con 5 nodi relay trusted.** I 5 nodi principali
(Milano, Torino, Genova, Bologna, Venezia) non rispettavano i vincoli di distanza
per collegamenti QKD in fibra diretti (es. Milano↔Bologna, Genova↔Venezia), quindi
sono stati aggiunti **Parma**, **La Spezia** e **Padova** come nodi relay trusted.
La topologia è poi stata **densificata** con i relay **Pavia** (ovest) e **Ferrara**
(est) e con **Verona** (main KMS), che aggiungono corridoi ridondanti su cui il PCE
può fare rerouting:

```
Milano – Torino – Genova – La Spezia – Parma –   (torna a Milano: anello ovest)
Parma – Bologna                                   (diramazione)
Parma – Padova – Venezia                          (diramazione)
Milano – Pavia – Genova / Pavia – Parma           (ridondanza ovest)
Bologna – Ferrara – Padova / Ferrara – Venezia    (secondo corridoio verso Venezia)
Verona – Padova / Verona – Ferrara / Verona – Venezia  (mesh nord-est)
```

Da Milano a Venezia il percorso corto resta `Milano → Parma → Padova → Venezia`
(3 hop); se cade il link diretto Milano-Parma, il relay **Pavia** offre un backup
breve `Milano → Pavia → Parma → Padova → Venezia` (4 hop) invece dell'intero anello
ovest. Bologna e Venezia non sono più foglie: hanno ora rotte alternative via Ferrara.

**Sorgente della topologia (pluggable, `TOPOLOGY_SOURCE`):**
- `static` — legge `config/topology.yaml` (default per test e dev senza Docker).
- `onos` — interroga ONOS (`/onos/v1/devices`, `/onos/v1/links`) e mappa i device OpenFlow sulle città via `config/onos_mapping.yaml`. È la modalità usata dallo stack Docker.

## 3. Flusso end-to-end e vincoli architetturali

```
ONOS REST client
  → Northbound API Gateway      (POST /adapter/v1/virtual-circuits)
  → Identity & Auth             (autentica + risolve Monza → Milano KMS)
  → Topology Manager            (topologia da ONOS, vedi sotto)
  → Path Computation Engine     (shortest path su networkx)
  → Key Orchestration Manager   (ETSI 014 → KMS → chiavi)
  → Service Provisioning        (compone JSON finale)
  → … la risposta risale la catena …
  → Northbound API Gateway → ONOS
```

Ci sono **due canali distinti verso ONOS**: la *richiesta di circuito* che entra dal
Northbound Gateway (ingresso) e la *scoperta della topologia* che il Topology Manager
fa leggendo la REST di ONOS (uscita, sola lettura). Sono cose diverse, quindi l'invariante
sul gateway non è violata.

Due **invarianti** (verificati da `tests/test_architecture_constraints.py`):

1. Il **Northbound API Gateway** è l'unico ingresso per le *richieste* ONOS e chiama **solo** Identity & Auth.
2. Il **Key Orchestration Manager** è l'**unico** a chiamare i KMS.

Modello a *catena*: ogni servizio arricchisce un `AdapterContext` e lo inoltra al
successivo; la risposta finale risale la catena fino al gateway.

## 4. Avvio con Docker Compose

```bash
docker compose up --build              # adapter + KMS + ONOS + Mininet
# attendi ~30-60s che ONOS sia su, poi:
./scripts/onos_activate_apps.sh        # abilita le app OpenFlow su ONOS
docker exec -it mininet-c python ring_topology.py   # costruisce il mesh (lascia la CLI aperta)
# in un altro terminale, quando ONOS ha scoperto gli 11 switch:
./scripts/demo_onos_request.sh         # demo Monza → Venezia
```

Verifica che ONOS abbia scoperto la topologia prima della demo:
```bash
curl -u onos:rocks http://localhost:8181/onos/v1/devices | python3 -m json.tool   # 11 switch
curl http://localhost:8082/topology/v1/graph | python3 -m json.tool               # 11 nodi, 17 link
```

| Servizio | URL host |
|---|---|
| Northbound API Gateway | http://localhost:8080 |
| Topology Manager (vista) | http://localhost:8082/topology/v1/graph |
| Audit Log | http://localhost:8086 |
| ONOS (GUI/REST, onos/rocks) | http://localhost:8181/onos/ui |
| KMS (milano…verona) | http://localhost:9001 … 9014 |

Ogni servizio dell'adapter espone `GET /health` e la doc OpenAPI su `/docs`.

> Sviluppo/demo senza ONOS: imposta `TOPOLOGY_SOURCE=static` sul `topology-manager` (legge `config/topology.yaml`). I test e `scripts/run_local_e2e.py` usano già la sorgente statica.

## 5. Eseguire la demo

```bash
./scripts/demo_onos_request.sh           # versione curl (richiede lo stack su)
python scripts/demo_monza_venezia.py     # versione Python (richiede lo stack su)
```

**Senza Docker** (utile per dev rapido o se sulla macchina d'esame manca il
daemon Docker): l'intera catena + i 14 KMS girano in un solo processo,
instradando le chiamate inter-servizio in memoria.

```bash
pip install -r requirements.txt
python scripts/run_local_e2e.py                                   # Monza → Venezia
python scripts/run_local_e2e.py --source Monza --destination Napoli --num-keys 2
```

Esempio di richiesta / risposta:

```jsonc
// POST /adapter/v1/virtual-circuits
{ "request_id": "req-001", "source": "Monza", "destination": "Venezia",
  "service_type": "qkd_virtual_circuit", "key_size": 256, "num_keys": 1 }

// risposta
{ "request_id": "req-001", "status": "PROVISIONED",
  "resolved_source_domain": "Milano KMS", "resolved_destination_domain": "Venezia KMS",
  "selected_path": ["Milano KMS", "Parma KMS", "Padova KMS", "Venezia KMS"],
  "kms_chain": ["Milano KMS", "Parma KMS", "Padova KMS", "Venezia KMS"],
  "keys": [{"key_id": "milano-…", "size": 256, "status": "available"}],
  "message": "Virtual QKD service provisioned successfully" }
```

> Il path ottimale Monza→Venezia passa dal nodo relay trusted **Parma** (hub) e poi
> **Padova** (3 hop). Per mostrare il fallback via il relay **Pavia**
> `Milano → Pavia → Parma → Padova → Venezia` (4 hop), in
> `config/topology.yaml` imposta `status: down` sul link `milano-parma`.

## 5b. Dashboard web (QSDN Control Panel)

Uno strato di sola presentazione sopra l'adapter: apri **http://localhost:8090** nel
browser. È servito dal servizio `dashboard`, che fa da proxy alle stesse REST API
usate da ONOS/operatore (nessuna logica di business duplicata, nessun CORS).

Cosa puoi fare dalla pagina:
- vedere la **topologia** (mesh + 5 nodi relay trusted) dal vivo (link verdi = su, rossi
  tratteggiati = giù);
- inviare una **richiesta di circuito** (Monza→Venezia, o qualsiasi coppia) e vedere il
  percorso evidenziato, i domini risolti, i KMS e le chiavi;
- guardare la **catena dei 6 microservizi** accendersi in sequenza (pilotata dall'audit);
- **cliccare un link** per abbatterlo/rialzarlo e vedere il ricalcolo del percorso (fallback);
- dal pannello **Scenario di simulazione** (editor generico): abbattere/ripristinare
  **qualsiasi link**, impostare il key pool di **qualsiasi nodo** (es. 8% per esaurirlo
  e forzare il rerouting), aggiungere città (Firenze/Roma/Napoli hanno già il KMS,
  quindi il provisioning ci passa davvero end-to-end) o link, resettare.

Le modifiche live usano gli endpoint `POST /topology/v1/node` e `/topology/v1/link` del
Topology Manager; `POST /topology/v1/refresh` ripristina la topologia iniziale.

## 5c. Backend KMS reale: Next Door in FULL MESH (interoperabilità ETSI 014)

Ogni città nel registro (`config/kms_registry.yaml`) dichiara un `backend`:

- `mock` — container `kms_mock`, HTTP GET in chiaro, chiavi simulate (default);
- `ndks` — **KME reale Next Door Key Simulator**, HTTPS + mutual-TLS + POST, chiavi
  realmente condivise tra i KME.

Il Key Orchestration Manager è **agnostico**: sceglie il client in base al `backend`,
ma orchestrazione e contratto ETSI 014 (enc_keys/dec_keys/status, ruoli SAE
master/slave, `key_ID`) non cambiano. Questa astrazione realizza l'interoperabilità:
lo stesso adapter pilota un KMS simulato e un'implementazione reale dello standard.

### Modalità full mesh reale (tutte le 8 città)

Con `config/kms_registry.ndks.yaml` **tutte le città sono KME Next Door reali** in
full mesh: qualunque coppia di endpoint scambia chiavi vere via ETSI 014 + mTLS.

```bash
./ndks/generate_certs.sh                       # CA + certificati per le 8 città
KMS_REGISTRY=/app/config/kms_registry.ndks.yaml \
  docker compose --profile ndks up -d --build  # adapter + 8 KME reali (immagine patchata)
# attendi ~25s (scan mesh + warm-up del pool), poi qualsiasi richiesta è reale:
./scripts/demo_onos_request.sh                 # Monza→Venezia con chiave vera
```

L'audit registra il backend usato e `key_shared_verified: true` quando la stessa
chiave è stata recuperata anche al KME di destinazione (`dec_keys`).

### La patch full-mesh (fork documentato di Next Door)

Next Door upstream va in **deadlock** con 3+ KME in mesh: lo scanner tiene un lock
globale mentre fa chiamate di rete bloccanti (senza timeout) verso tutti gli altri
KME; due scanner che si interrogano a vicenda creano attesa circolare. La patch
(vendorizzata in `ndks/patches/`, applicata dal `ndks/Dockerfile` sopra l'immagine
ufficiale) consiste in:

1. `scanner.py` — l'I/O di rete avviene **fuori** dal lock (il lock protegge solo lo
   swap della lista KME) + timeout esplicito per richiesta;
2. `broadcaster.py` — timeout esplicito sul broadcast dello scambio chiavi.

Validata con 8 KME in full mesh: scambi su coppie arbitrarie (anche sotto stress)
senza deadlock, con chiave identica ai due estremi.

## 6. Leggere i log (Audit)

```bash
# trace completa di una richiesta
curl "http://localhost:8086/audit/v1/events?request_id=req-demo-001" | python3 -m json.tool
# ultimi N eventi di tutte le richieste
curl "http://localhost:8086/audit/v1/events?limit=50"
```

Ogni evento contiene `request_id`, `timestamp`, `service`, `event_type` e i campi
pertinenti (endpoint, topologia, path scelto, KMS chiamati, key_id, errori).
Store: SQLite (`audit-data` volume).

## 7. Cambiare topologia

Dipende dalla sorgente attiva:

- `TOPOLOGY_SOURCE=onos` (stack Docker): la topologia la decide Mininet. Modifica
  `mininet/ring_topology.py` (aggiungi switch/link), aggiorna `config/onos_mapping.yaml`
  con i nuovi DPID → città, rilancia la topologia in Mininet e poi
  `curl -X POST http://localhost:8082/topology/v1/refresh` per invalidare la cache.
- `TOPOLOGY_SOURCE=static` (test/dev): modifica `config/topology.yaml` (nodi, link,
  `cost`, `status: up|down`, eventuali `virtual_links` di tipo `vpn`) e fai il refresh.

Per provare il fallback: abbassa il link Milano-Parma (in Mininet `link s1 s6 down`,
oppure `status: down` nello YAML sul link `milano`-`parma`) e rilancia la demo — il
path Milano→Venezia passa da `Milano → Parma → Padova → Venezia` a
`Milano → Torino → Genova → La Spezia → Parma → Padova → Venezia`.

## 8. Aggiungere un nuovo KMS / città

1. aggiungi lo switch in `mininet/ring_topology.py` (DPID univoco) e i link della mesh;
2. mappa il DPID in `config/onos_mapping.yaml` (e, per la sorgente statica, il nodo in `config/topology.yaml`);
3. aggiungi la voce in `config/kms_registry.yaml` (`label`, `base_url`, `sae_id`);
4. aggiungi un servizio `kms-<città>` in `docker-compose.yml` (`image: qsdn-kms-mock`, env `CITY/SAE_ID/PORT`, mapping porta).

## 9. Limiti della simulazione

- **Non è QKD reale**: nessuna distribuzione quantistica di chiavi.
- Le chiavi sono **simulate** (random/deterministiche), non sicure.
- Auth e sicurezza **non** sono production-grade (no token reali / mTLS).
- ETSI 014: gli endpoint reali usano tipicamente **POST** con body JSON per
  `enc_keys`/`dec_keys`; qui, come da specifica di tesi, si usa **GET** con query
  param. Il mock supporta lo schema dati ETSI (`key_ID`, `key`); passare a POST
  è una modifica minima in `key_orchestration_manager/app/etsi014_client.py`.

## 10. Struttura del progetto

```
qsdn-adapter/
  docker-compose.yml          config/{topology,kms_registry,onos_mapping}.yaml
  shared/                     models.py · settings.py · logging_client.py · topology_loader.py
  services/
    northbound_api_gateway/   identity_auth/   topology_manager/ (+ onos_client · onos_source)
    path_computation_engine/  key_orchestration_manager/  service_provisioning/
    audit_log/                kms_mock/
  mininet/                    ring_topology.py        (8-switch mesh: ring + 2 trusted-relay spurs)
  scripts/                    demo_onos_request.sh · demo_monza_venezia.py · run_local_e2e.py · onos_activate_apps.sh
  tests/                      test_topology · test_path_computation · test_onos_source
                              test_architecture_constraints · test_full_flow
```

## Test

```bash
pip install -r requirements-dev.txt
pytest                 # unit + invarianti (il test e2e si salta se lo stack è giù)
pytest -m integration  # end-to-end (richiede `docker compose up`)
```
