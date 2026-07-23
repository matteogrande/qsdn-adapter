(() => {
  "use strict";

  /* =====================================================================
     QSDN Adapter Live Demo — client-side orchestration narrative.
     Deterministic simulation of the end-to-end QKD service flow:
       ONOS → Northbound API Gateway → Identity & Authentication →
       Topology Manager → Path Computation Engine →
       Key Orchestration Manager → Service Provisioning → ONOS
     The UI is agnostic to how the topology is obtained: the Topology
     Manager simply provides the current QKD/KMS network state.
     ===================================================================== */

  const STAGE_ANIM_MS = 520;   // perceptible, sober pacing for the pipeline
  const KOM_STEP_MS = 300;     // per-KMS reveal inside Key Orchestration
  const API_TIMEOUT_MS = 4500;

  // Nominal per-microservice resolution time (ms), shown on every stage even
  // before a run. Once a stage completes it is replaced by the measured value.
  const STAGE_BASE_MS = { gateway: 32, identity: 41, topology: 68, pce: 18, kom: 360, prov: 102 };

  // Five MAIN KMS SITES + three TRUSTED RELAY NODES, plus optional
  // expansion sites reachable from Advanced controls.
  const CITY_LIBRARY = {
    milano:    { id: "milano",    label: "Milano",    kmsId: "KMS-01", kind: "main",  x: 330,  y: 140, pool: 92, description: "Main KMS site" },
    torino:    { id: "torino",    label: "Torino",    kmsId: "KMS-02", kind: "main",  x: 150,  y: 250, pool: 84, description: "Main KMS site" },
    genova:    { id: "genova",    label: "Genova",    kmsId: "KMS-03", kind: "main",  x: 190,  y: 460, pool: 80, description: "Main KMS site" },
    bologna:   { id: "bologna",   label: "Bologna",   kmsId: "KMS-04", kind: "main",  x: 720,  y: 430, pool: 88, description: "Main KMS site" },
    venezia:   { id: "venezia",   label: "Venezia",   kmsId: "KMS-05", kind: "main",  x: 1070, y: 150, pool: 86, description: "Main KMS site" },
    parma:     { id: "parma",     label: "Parma",     kmsId: "KMS-09", kind: "relay", x: 470,  y: 300, pool: 90, description: "Trusted relay node" },
    la_spezia: { id: "la_spezia", label: "La Spezia", kmsId: "KMS-10", kind: "relay", x: 390,  y: 510, pool: 87, description: "Trusted relay node" },
    padova:    { id: "padova",    label: "Padova",    kmsId: "KMS-11", kind: "relay", x: 910,  y: 250, pool: 89, description: "Trusted relay node" },
    pavia:     { id: "pavia",     label: "Pavia",     kmsId: "KMS-12", kind: "relay", x: 300,  y: 300, pool: 85, description: "Trusted relay node" },
    ferrara:   { id: "ferrara",   label: "Ferrara",   kmsId: "KMS-13", kind: "relay", x: 930,  y: 410, pool: 83, description: "Trusted relay node" },
    verona:    { id: "verona",    label: "Verona",    kmsId: "KMS-14", kind: "main",  x: 700,  y: 185, pool: 82, description: "Main KMS site" },
    firenze:   { id: "firenze",   label: "Firenze",   kmsId: "KMS-06", kind: "main",  x: 720,  y: 580, pool: 78, status: "inactive", description: "Main KMS site (espansione)" },
    roma:      { id: "roma",      label: "Roma",      kmsId: "KMS-07", kind: "main",  x: 910,  y: 580, pool: 76, status: "inactive", description: "Main KMS site (espansione)" },
    napoli:    { id: "napoli",    label: "Napoli",    kmsId: "KMS-08", kind: "main",  x: 1080, y: 580, pool: 74, status: "inactive", description: "Main KMS site (espansione)" },
  };

  // Partially-meshed QKD/KMS network. Every link is a physical QKD span within
  // the ~150 km fibre reach: longer distances between main sites are always
  // bridged by trusted relay nodes (Parma, La Spezia, Padova) or by the Bologna
  // hub. The La Spezia–Bologna Apennine span gives the PCE a genuine alternative
  // route, so rerouting keeps the circuit alive when a link or key pool degrades.
  const INITIAL_NODE_IDS = ["milano", "torino", "genova", "bologna", "venezia", "parma", "la_spezia", "padova", "pavia", "ferrara", "verona"];
  const INITIAL_LINKS = [
    { source: "torino",    target: "milano",    cost: 1 }, // ~125 km
    { source: "torino",    target: "genova",    cost: 1 }, // ~125 km
    { source: "genova",    target: "la_spezia", cost: 1 }, // ~90 km
    { source: "la_spezia", target: "parma",     cost: 1 }, // ~100 km
    { source: "milano",    target: "parma",     cost: 1 }, // ~110 km
    { source: "parma",     target: "bologna",   cost: 1 }, // ~95 km
    { source: "la_spezia", target: "bologna",   cost: 1 }, // ~120 km (Apennine relay span)
    { source: "bologna",   target: "padova",    cost: 1 }, // ~110 km
    { source: "padova",    target: "venezia",   cost: 1 }, // ~40 km
    // Pavia relay — west redundancy (alternative to the direct Milano-Parma hop).
    { source: "milano",    target: "pavia",     cost: 1 }, // ~35 km
    { source: "pavia",     target: "genova",    cost: 1 }, // ~100 km
    { source: "pavia",     target: "parma",     cost: 1 }, // ~65 km
    // Ferrara relay — east redundancy (second corridor towards Venezia).
    { source: "bologna",   target: "ferrara",   cost: 1 }, // ~50 km
    { source: "ferrara",   target: "padova",    cost: 1 }, // ~75 km
    { source: "ferrara",   target: "venezia",   cost: 1 }, // ~110 km
    // Verona main KMS — dense north-east mesh on the approach to Venezia.
    { source: "verona",    target: "padova",    cost: 1 }, // ~80 km
    { source: "verona",    target: "ferrara",   cost: 1 }, // ~90 km
    { source: "verona",    target: "venezia",   cost: 1 }, // ~115 km
  ];

  const STAGES = [
    { id: "gateway",  title: "Northbound API Gateway",   desc: "riceve la richiesta REST dal controller ONOS" },
    { id: "identity", title: "Identity & Authentication", desc: "valida client, SAE_ID e permessi di accesso" },
    { id: "topology", title: "Topology Manager",          desc: "mantiene lo stato aggiornato della rete QKD/KMS" },
    { id: "pce",      title: "Path Computation Engine",   desc: "calcola il path migliore in base a costo, stato dei link e disponibilità delle chiavi" },
    { id: "kom",      title: "Key Orchestration Manager", desc: "coordina i KMS lungo il percorso e richiede o alloca le chiavi" },
    { id: "prov",     title: "Service Provisioning",      desc: "crea il circuito virtuale e restituisce la risposta al client ONOS" },
  ];

  // Architecturally-neutral status indicators (no external connectivity is
  // actually probed, so nothing claims to be "CONNECTED").
  const DEFAULT_BADGES = [
    { label: "ONOS REST Interface", value: "INTERFACE READY", tone: "good" },
    { label: "QSDN Adapter",        value: "RUNNING",         tone: "good" },
    { label: "KMS Network",         value: "READY",           tone: "good" },
    { label: "ETSI 014 API",        value: "ACTIVE",          tone: "good" },
  ];

  const linkPaint = { up: "#39d27d", down: "#ff6079", path: "#f6b94d", circuit: "#69d8ff", neutral: "#8ea3c4" };

  // High-level architecture "schedina": the three protagonists of the QKD
  // orchestration and the logical direction of information between them. The
  // connecting arrows light up in sync with the provisioning pipeline.
  const ARCH_BLOCKS = [
    { key: "onos",    x: 40,  role: "CLIENT SDN",         titleLines: ["ONOS / Mininet"],                  sub: "SDN Controller · Network Emulator", caption: "ONOS emette la richiesta di servizio QKD via REST e riceve il circuito virtuale provisionato; Mininet emula la rete dati sottostante." },
    { key: "adapter", x: 450, role: "ORCHESTRATORE",      titleLines: ["QSDN Adapter"],                    sub: "Path computation · KMS orchestration", caption: "Il QSDN Adapter autentica la richiesta, calcola il percorso ottimo, coordina i KMS lungo il path e provisiona il circuito virtuale." },
    { key: "kms",     x: 860, role: "KEY LAYER · ETSI 014", titleLines: ["KMS — Next Door", "Key Simulator (NDKS)"], sub: "Fornitore di chiavi quantistiche", caption: "Il KMS (Next Door Key Simulator) espone le API ETSI GS QKD 014 e consegna le chiavi quantistiche ai nodi lungo il percorso scelto." },
  ];

  const ARCH_PILL = { idle: "IN ATTESA", active: "IN ELABORAZIONE", done: "COMPLETATO", fail: "ERRORE" };

  const CATEGORY_TAG = {
    system: "SYSTEM", onos: "ONOS", auth: "AUTH", topology: "TOPOLOGY",
    path: "PATH", kms: "KMS", provisioning: "PROVISIONING",
    rerouting: "REROUTING", error: "ERROR",
  };

  const state = createInitialState();

  const ui = {
    badges: document.getElementById("statusBadges"),
    kpis: document.getElementById("kpiGrid"),
    svg: document.getElementById("topologySvg"),
    arch: document.getElementById("archSvg"),
    archCaption: document.getElementById("archCaption"),
    pipeline: document.getElementById("pipelineStages"),
    komPanel: document.getElementById("komPanel"),
    komNodes: document.getElementById("komNodes"),
    result: document.getElementById("resultArea"),
    reroutePanel: document.getElementById("reroutePanel"),
    rerouteArea: document.getElementById("rerouteArea"),
    requestJson: document.getElementById("requestJson"),
    responseJson: document.getElementById("responseJson"),
    requestMeta: document.getElementById("requestJsonMeta"),
    responseMeta: document.getElementById("responseJsonMeta"),
    requestFeedback: document.getElementById("requestFeedback"),
    nodeFeedback: document.getElementById("nodeFeedback"),
    linkFeedback: document.getElementById("linkFeedback"),
    scenarioFeedback: document.getElementById("scenarioFeedback"),
    scenarioRunFeedback: document.getElementById("scenarioRunFeedback"),
    eventLog: document.getElementById("eventLog"),
    reqId: document.getElementById("reqId"),
    reqSource: document.getElementById("reqSource"),
    reqDest: document.getElementById("reqDest"),
    reqKeySize: document.getElementById("reqKeySize"),
    reqKeys: document.getElementById("reqKeys"),
    provisionBtn: document.getElementById("provisionBtn"),
    nodePicker: document.getElementById("nodePicker"),
    addNodeBtn: document.getElementById("addNodeBtn"),
    linkSource: document.getElementById("linkSource"),
    linkTarget: document.getElementById("linkTarget"),
    linkCost: document.getElementById("linkCost"),
    addLinkBtn: document.getElementById("addLinkBtn"),
    faultLinkSource: document.getElementById("faultLinkSource"),
    faultLinkTarget: document.getElementById("faultLinkTarget"),
    toggleLinkBtn: document.getElementById("toggleLinkBtn"),
    faultLinkFeedback: document.getElementById("faultLinkFeedback"),
    poolNode: document.getElementById("poolNode"),
    poolValue: document.getElementById("poolValue"),
    setPoolBtn: document.getElementById("setPoolBtn"),
    poolFeedback: document.getElementById("poolFeedback"),
    resetTopologyBtn: document.getElementById("resetTopologyBtn"),
    clearLogBtn: document.getElementById("clearLogBtn"),
    presentationToggle: document.getElementById("presentationToggle"),
    advanced: document.getElementById("advancedControls"),
  };

  bootstrap();
  bindEvents();

  /* ------------------------------ state ------------------------------ */

  function createInitialState() {
    return {
      topology: createDefaultTopology(),
      activeCircuit: null,
      lastRequest: null,
      lastResponse: null,
      lastReroute: null,
      lastProvisionMs: null,
      lastPathCost: null,
      rerouteCount: 0,
      requestSeq: 42,
      circuitSeq: 1,
      jobId: 0,
      logs: [],
      stageStatus: Object.fromEntries(STAGES.map((s) => [s.id, "idle"])),
      stageTimes: {},
      komNodes: [],
      pathPulse: null,
      badges: DEFAULT_BADGES.map((b) => ({ ...b })),
      payloadView: "compact",
      revealedNodes: new Set(),
      running: false,
      arch: createInitialArch(),
    };
  }

  // State of the architecture flow diagram. Each block and each directed flow
  // segment is idle | active | done | fail, driven by the pipeline lifecycle.
  function createInitialArch() {
    return {
      blocks: { onos: "idle", adapter: "idle", kms: "idle" },
      flows: { reqOnosAdapter: "idle", reqAdapterKms: "idle", respKmsAdapter: "idle", respAdapterOnos: "idle" },
      selected: null,
    };
  }

  function createDefaultTopology() {
    return {
      nodes: INITIAL_NODE_IDS.map((id) => cloneNode(CITY_LIBRARY[id], true)),
      links: INITIAL_LINKS.map((link) => cloneLink(link)),
    };
  }

  function cloneNode(source, active = true) {
    const baseStatus = source.status === "inactive" ? "active" : (source.status || "active");
    return {
      id: source.id,
      label: source.label,
      kmsId: source.kmsId,
      kind: source.kind,
      x: source.x,
      y: source.y,
      pool: source.pool,
      status: active ? normalizeNodeStatus(baseStatus, source.pool) : "inactive",
      description: source.description,
    };
  }

  function cloneLink(source) {
    return {
      source: source.source,
      target: source.target,
      cost: Number(source.cost) || 1,
      status: source.status || "up",
      kind: source.kind || "physical",
    };
  }

  /* ------------------------------ boot ------------------------------ */

  function bootstrap() {
    hydrateControls();
    setDefaultFormValues();
    addEvent("system", "QSDN Adapter Live Demo pronto. In attesa di richieste dal controller ONOS.", "neutral");
    addEvent("topology", `Stato rete QKD/KMS disponibile: ${state.topology.nodes.length} nodi, ${activeLinkCount()} link attivi.`);
    renderAll();
  }

  function bindEvents() {
    ui.provisionBtn.addEventListener("click", () => { void provisionCircuit(); });

    ui.svg.addEventListener("click", (event) => {
      // A click on a node reveals/hides its details; a click on a link edge
      // toggles the link up/down (topology editor).
      const nodeEl = event.target.closest?.("[data-node-id]");
      if (nodeEl) { toggleNodeReveal(nodeEl.getAttribute("data-node-id")); return; }
      const target = event.target.closest?.("[data-link-source]");
      if (!target) return;
      const source = target.getAttribute("data-link-source");
      const to = target.getAttribute("data-link-target");
      if (source && to) void toggleLinkState(source, to);
    });

    ui.arch.addEventListener("click", (event) => {
      const blockEl = event.target.closest?.("[data-arch-block]");
      if (!blockEl) return;
      const key = blockEl.getAttribute("data-arch-block");
      state.arch.selected = state.arch.selected === key ? null : key;
      renderArchFlow();
      renderArchCaption();
    });

    ui.addNodeBtn.addEventListener("click", () => { void addNodeFromPicker(); });
    ui.addLinkBtn.addEventListener("click", () => { void addLinkFromForm(); });
    ui.toggleLinkBtn.addEventListener("click", () => { void toggleFaultLinkFromForm(); });
    ui.setPoolBtn.addEventListener("click", () => { void setNodePoolFromForm(); });
    ui.resetTopologyBtn.addEventListener("click", () => { void resetTopology(); });
    ui.clearLogBtn.addEventListener("click", () => { state.logs = []; renderAll(); });

    document.querySelectorAll("[data-scenario]").forEach((button) => {
      button.addEventListener("click", () => { void runScenario(button.getAttribute("data-scenario")); });
    });

    document.querySelectorAll("[data-payload-view]").forEach((button) => {
      button.addEventListener("click", () => setPayloadView(button.getAttribute("data-payload-view")));
    });

    ui.presentationToggle.addEventListener("click", togglePresentationMode);

    [ui.reqSource, ui.reqDest].forEach((select) => {
      select.addEventListener("change", () => {
        if (ui.reqSource.value === ui.reqDest.value) {
          setFeedback(ui.requestFeedback, "Sorgente e destinazione devono essere diverse.", "warn");
        } else {
          clearFeedback(ui.requestFeedback);
        }
        renderPayloads();
      });
    });
    [ui.reqKeySize, ui.reqKeys, ui.reqId].forEach((el) => el.addEventListener("input", renderPayloads));
  }

  /* ------------------------------ controls ------------------------------ */

  function hydrateControls() {
    populateCitySelects();
    populateTopologySelects();
    populateRequestSelects();
  }

  function populateCitySelects() {
    const available = getAvailableCities();
    const selectedValue = ui.nodePicker.value;
    ui.nodePicker.innerHTML = available
      .map((c) => `<option value="${c.id}">${escapeHtml(c.label)} (${c.kmsId})</option>`)
      .join("") || `<option value="">(tutte le città sono già nella topologia)</option>`;
    restoreSelectValue(ui.nodePicker, selectedValue);
  }

  function populateTopologySelects() {
    const nodes = state.topology.nodes.slice().sort((a, b) => a.label.localeCompare(b.label, "it"));
    const options = nodes.map((n) => `<option value="${n.id}">${escapeHtml(n.label)} (${n.kmsId})</option>`).join("");
    for (const select of [ui.linkSource, ui.linkTarget, ui.faultLinkSource, ui.faultLinkTarget, ui.poolNode]) {
      if (!select) continue;
      const selected = select.value;
      select.innerHTML = options;
      restoreSelectValue(select, selected);
    }
  }

  function populateRequestSelects() {
    const nodes = state.topology.nodes.slice().sort((a, b) => a.label.localeCompare(b.label, "it"));
    const selectedSource = ui.reqSource.value;
    const selectedDest = ui.reqDest.value;
    const options = nodes.map((n) => `<option value="${n.id}">${escapeHtml(endpointLabel(n.id))} (${n.kmsId})</option>`).join("");
    ui.reqSource.innerHTML = options;
    ui.reqDest.innerHTML = options;
    restoreSelectValue(ui.reqSource, selectedSource);
    restoreSelectValue(ui.reqDest, selectedDest);
  }

  function setDefaultFormValues() {
    ui.reqSource.value = pickId("milano");
    ui.reqDest.value = pickId("venezia");
    ui.reqId.value = `onos-req-${pad4(state.requestSeq)}`;
    ui.reqKeySize.value = "256";
    ui.reqKeys.value = "1";
    ui.linkCost.value = "1";
    const firstLink = state.topology.links.find((l) => l.source === "parma" || l.target === "parma") || state.topology.links[0];
    if (firstLink) {
      restoreSelectValue(ui.faultLinkSource, firstLink.source);
      restoreSelectValue(ui.faultLinkTarget, firstLink.target);
    }
    restoreSelectValue(ui.poolNode, state.topology.nodes.find((n) => n.kind === "relay")?.id);
    ui.poolValue.value = "8";
    syncSelectAvailability();
  }

  function pickId(preferred) {
    return state.topology.nodes.find((n) => n.id === preferred)?.id || state.topology.nodes[0]?.id || preferred;
  }

  function syncSelectAvailability() {
    const present = new Set(state.topology.nodes.map((n) => n.id));
    const notPresent = getAvailableCities().filter((c) => !present.has(c.id));
    ui.nodePicker.disabled = notPresent.length === 0;
    ui.addNodeBtn.disabled = notPresent.length === 0;
  }

  function restoreSelectValue(select, selectedValue) {
    if (!select || selectedValue == null) return;
    if (Array.from(select.options).some((o) => o.value === selectedValue)) select.value = selectedValue;
  }

  function getAvailableCities() {
    return Object.values(CITY_LIBRARY).filter((c) => !state.topology.nodes.some((n) => n.id === c.id));
  }

  /* ------------------------------ render ------------------------------ */

  function renderAll() {
    renderBadges();
    renderKpis();
    renderArchFlow();
    renderArchCaption();
    renderTopology();
    renderPipeline();
    renderKomPanel();
    renderResult();
    renderReroute();
    renderPayloads();
    renderEventLog();
    populateRequestSelects();
    populateTopologySelects();
    populateCitySelects();
    syncSelectAvailability();
  }

  function renderBadges() {
    ui.badges.innerHTML = state.badges
      .map((b) => `<div class="status-card ${b.tone}"><div class="label">${escapeHtml(b.label)}</div><div class="value">${escapeHtml(b.value)}</div></div>`)
      .join("");
  }

  function renderKpis() {
    const nodes = state.topology.nodes;
    const linksUp = state.topology.links.filter((l) => l.status === "up").length;
    const avgPool = nodes.length ? Math.round(nodes.reduce((s, n) => s + n.pool, 0) / nodes.length) : 0;
    const circuitCount = state.activeCircuit ? 1 : 0;
    const pathCost = state.lastPathCost ?? "—";
    const provTime = state.lastProvisionMs == null ? "—" : `${state.lastProvisionMs} ms`;
    const relaysInvolved = state.activeCircuit
      ? (state.activeCircuit.plan.pathIds.filter((id) => getNode(id)?.kind === "relay").length)
      : 0;

    const cards = [
      { label: "Nodi KMS", value: `${nodes.length}`, note: "siti nella topologia" },
      { label: "Link attivi", value: `${linksUp}/${state.topology.links.length}`, note: "solo link in stato up" },
      { label: "Circuiti attivi", value: `${circuitCount}`, note: circuitCount ? "circuito virtuale in servizio" : "nessun circuito attivo" },
      { label: "Key pool medio", value: `${avgPool}%`, note: avgPool >= 60 ? "rete stabile" : avgPool >= 35 ? "attenzione al consumo" : "pool critico" },
      { label: "Ultimo path cost", value: `${pathCost}`, note: "costo del percorso scelto" },
      { label: "Tempo provisioning", value: `${provTime}`, note: "end-to-end" },
      { label: "Rerouting", value: `${state.rerouteCount}`, note: "ricalcoli su circuito attivo" },
      { label: "Trusted relay coinvolti", value: `${relaysInvolved}`, note: "sul circuito attivo" },
    ];

    ui.kpis.innerHTML = cards
      .map((c) => `<div class="kpi-card"><div class="k-label">${escapeHtml(c.label)}</div><div class="k-value">${escapeHtml(c.value)}</div><div class="k-note">${escapeHtml(c.note)}</div></div>`)
      .join("");
  }

  function renderTopology() {
    const pathIds = state.activeCircuit?.plan?.pathIds || [];
    const pathEdgeKeys = new Set();
    for (let i = 0; i < pathIds.length - 1; i += 1) pathEdgeKeys.add(edgeKey(pathIds[i], pathIds[i + 1]));
    const nodesById = new Map(state.topology.nodes.map((n) => [n.id, n]));
    const phase = state.komPhase || {};

    const svg = [];
    svg.push(`<defs>
      <linearGradient id="linkGlow" x1="0" x2="1" y1="0" y2="0">
        <stop offset="0%" stop-color="${linkPaint.circuit}" stop-opacity="0" />
        <stop offset="50%" stop-color="${linkPaint.circuit}" stop-opacity="0.9" />
        <stop offset="100%" stop-color="${linkPaint.circuit}" stop-opacity="0" />
      </linearGradient>
      <filter id="softGlow" x="-60%" y="-60%" width="220%" height="220%">
        <feGaussianBlur stdDeviation="4" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
      </filter>
    </defs>`);

    svg.push(`<rect x="0" y="0" width="1200" height="640" fill="rgba(6, 13, 23, 0.26)" rx="24" />`);
    svg.push(`<g opacity="0.3" stroke="rgba(110, 139, 189, 0.14)" stroke-width="1">
      ${Array.from({ length: 12 }, (_, i) => `<line x1="0" y1="${i * 60}" x2="1200" y2="${i * 60}" />`).join("")}
      ${Array.from({ length: 20 }, (_, i) => `<line x1="${i * 62}" y1="0" x2="${i * 62}" y2="640" />`).join("")}
    </g>`);

    // Links
    svg.push(`<g class="links">`);
    state.topology.links.forEach((link) => {
      const s = nodesById.get(link.source);
      const t = nodesById.get(link.target);
      if (!s || !t) return;
      const hot = pathEdgeKeys.has(edgeKey(link.source, link.target));
      const down = link.status === "down";
      const stroke = hot ? linkPaint.path : down ? linkPaint.down : linkPaint.up;
      const width = hot ? 6 : 3;
      const dash = down ? `stroke-dasharray="10 7"` : "";
      const midX = (s.x + t.x) / 2;
      const midY = (s.y + t.y) / 2;
      const latency = computeLinkLatency(link);
      const availability = computeLinkAvailability(link, s, t);
      // On the graph: show the per-link latency (ms). The routing weight is the
      // same quantity by construction (latency = cost·11 + jitter), so we label
      // links by latency directly to avoid a separate "cost" unit on screen.
      const label = `${latency} ms`;
      const tip = `${s.label} ↔ ${t.label}\nLatency: ${latency} ms\nKey availability: ${availability}%\nStatus: ${down ? "DOWN" : "ACTIVE"}`;
      const overlay = hot
        ? `<line x1="${s.x}" y1="${s.y}" x2="${t.x}" y2="${t.y}" stroke="url(#linkGlow)" stroke-width="11" opacity="0.4" filter="url(#softGlow)" />`
        : "";
      svg.push(`<g>
        ${overlay}
        <line x1="${s.x}" y1="${s.y}" x2="${t.x}" y2="${t.y}" stroke="${stroke}" stroke-width="${width}" ${dash} stroke-linecap="round" opacity="${hot ? 1 : 0.82}" filter="${hot ? "url(#softGlow)" : "none"}" />
        <line data-link-source="${link.source}" data-link-target="${link.target}" x1="${s.x}" y1="${s.y}" x2="${t.x}" y2="${t.y}" stroke="transparent" stroke-width="20" style="cursor:pointer"><title>${escapeHtml(tip)}</title></line>
        <rect x="${midX - label.length * 3.2 - 5}" y="${midY - 20}" width="${label.length * 6.4 + 10}" height="15" rx="7" fill="rgba(6,12,21,0.72)" />
        <text x="${midX}" y="${midY - 9}" text-anchor="middle" class="link-label${hot ? " hot" : ""}">${escapeHtml(label)}</text>
      </g>`);
    });
    svg.push(`</g>`);

    // Virtual circuit polyline (gentle animated flow)
    if (state.activeCircuit && pathIds.length >= 2) {
      const pts = pathIds.map((id) => nodesById.get(id)).filter(Boolean).map((n) => `${n.x},${n.y}`).join(" ");
      svg.push(`<g opacity="0.9">
        <polyline points="${pts}" fill="none" stroke="rgba(106, 215, 255, 0.16)" stroke-width="13" stroke-linecap="round" stroke-linejoin="round" filter="url(#softGlow)" />
        <polyline points="${pts}" fill="none" stroke="${linkPaint.circuit}" stroke-width="3.4" stroke-dasharray="10 8" stroke-linecap="round" stroke-linejoin="round" opacity="0.92">
          <animate attributeName="stroke-dashoffset" from="36" to="0" dur="1.6s" repeatCount="indefinite" />
        </polyline>
      </g>`);
    }

    // Provisioning pulse traveling along the chosen path
    if (state.pathPulse && state.pathPulse.length >= 2) {
      const d = "M " + state.pathPulse.map((id) => { const n = nodesById.get(id); return `${n.x} ${n.y}`; }).join(" L ");
      const dur = Math.max(1.6, state.pathPulse.length * 0.55);
      svg.push(`<circle r="6" class="path-pulse"><animateMotion dur="${dur}s" repeatCount="indefinite" path="${d}" /></circle>`);
    }

    // Nodes — details stay hidden for a clean graph and are revealed on click
    // (nodes on the active path / under orchestration reveal automatically).
    svg.push(`<g class="nodes">`);
    state.topology.nodes.forEach((node) => {
      const nodePhase = phase[node.id];
      const status = computeNodeStatus(node);
      const inPath = pathIds.includes(node.id);
      const revealed = state.revealedNodes.has(node.id) || inPath || !!nodePhase;
      const isRelay = node.kind === "relay";
      const r = isRelay ? 21 : 28;
      const fill = nodeColor(status, isRelay);
      const ringColor = nodePhase === "ready" ? linkPaint.up : nodePhase === "requesting" ? linkPaint.circuit : inPath ? linkPaint.path : isRelay ? linkPaint.neutral : linkPaint.up;
      const ringOpacity = (inPath || nodePhase) ? 1 : 0.42;
      const darkFill = status === "unavailable" || status === "inactive";
      const roleText = isRelay ? "TRUSTED RELAY" : "MAIN KMS";
      const roleFill = isRelay ? "rgba(90,166,255,0.2)" : "rgba(55,214,122,0.22)";
      const roleColor = isRelay ? "#bcd6ff" : "#b6f2cf";
      const statusText = nodePhase ? nodePhase.toUpperCase() : status.toUpperCase();
      const statusFill = nodePhase === "requesting" ? linkPaint.circuit : nodePhase === "ready" ? linkPaint.up : statusColor(status);

      const shape = isRelay
        ? `<polygon points="0,-${r} ${r},0 0,${r} -${r},0" fill="${fill}" stroke="rgba(6,12,21,0.95)" stroke-width="3" />`
        : `<circle cx="0" cy="0" r="${r}" fill="${fill}" stroke="rgba(6,12,21,0.95)" stroke-width="3" />`;
      const ring = isRelay
        ? `<polygon points="0,-${r + 6} ${r + 6},0 0,${r + 6} -${r + 6},0" fill="none" stroke="${ringColor}" stroke-width="2" opacity="${ringOpacity}" />`
        : `<circle cx="0" cy="0" r="${r + 6}" fill="none" stroke="${ringColor}" stroke-width="2" opacity="${ringOpacity}" />`;
      const halo = (inPath || nodePhase) ? `<circle cx="0" cy="0" r="${r + 15}" fill="none" stroke="${nodePhase === "requesting" ? "rgba(106,215,255,0.25)" : "rgba(246,185,77,0.28)"}" stroke-width="3" filter="url(#softGlow)" />` : "";

      const roleW = roleText.length * 5.4 + 14;
      const tip = `${endpointLabel(node.id)} · ${node.kmsId}\n${node.description}\nKey pool: ${Math.round(node.pool)}%\nStatus: ${statusText}\n(clicca per mostrare/nascondere i dettagli)`;

      // Always-on: the shape (colour = status) and the city name, so the graph
      // stays legible. Everything else appears only when the node is revealed.
      const details = revealed ? `
        <text class="node-kms" x="0" y="${-(r + 10)}" text-anchor="middle">${escapeHtml(node.kmsId)}</text>
        <text class="node-pool ${darkFill ? "dark" : ""}" x="0" y="5" text-anchor="middle">${Math.round(node.pool)}%</text>
        <rect x="${-roleW / 2}" y="${r + 7}" width="${roleW}" height="16" rx="8" fill="${roleFill}" stroke="rgba(255,255,255,0.08)" />
        <text class="node-role" x="0" y="${r + 18}" text-anchor="middle" fill="${roleColor}">${roleText}</text>
        <text class="node-status" x="0" y="${r + 38}" text-anchor="middle" fill="${statusFill}">${escapeHtml(statusText)}</text>`
        : `<circle cx="0" cy="0" r="3.5" fill="rgba(255,255,255,0.72)" />`;

      svg.push(`<g data-node-id="${node.id}" transform="translate(${node.x}, ${node.y})" style="cursor:pointer">
        ${halo}${ring}${shape}
        <text class="node-name" x="0" y="${-(r + 24)}" text-anchor="middle">${escapeHtml(node.label)}</text>
        ${details}
        <title>${escapeHtml(tip)}</title>
      </g>`);
    });
    svg.push(`</g>`);

    // Virtual circuit badge (fixed corner, never overlaps nodes)
    if (state.activeCircuit) {
      const c = state.activeCircuit;
      const stateLabel = c.state === "ACTIVE_REROUTED" ? "ACTIVE · REROUTED" : c.state === "DEGRADED" ? "DEGRADED" : "ACTIVE";
      const stateColor = c.state === "DEGRADED" ? linkPaint.down : c.state === "ACTIVE_REROUTED" ? linkPaint.path : linkPaint.up;
      svg.push(`<g transform="translate(918, 20)">
        <rect x="0" y="0" width="262" height="70" rx="14" fill="rgba(8,18,30,0.92)" stroke="rgba(106,215,255,0.3)" stroke-width="1.5" />
        <text class="circuit-badge-title" x="16" y="22">VIRTUAL CIRCUIT</text>
        <text class="circuit-badge-id" x="16" y="45">${escapeHtml(c.circuitId)}</text>
        <text class="circuit-badge-state" x="16" y="61" fill="${stateColor}">${escapeHtml(stateLabel)}</text>
      </g>`);
    }

    ui.svg.innerHTML = svg.join("");
  }

  function renderPipeline() {
    ui.pipeline.innerHTML = STAGES.map((stage) => {
      const status = state.stageStatus[stage.id] || "idle";
      const measured = state.stageTimes[stage.id];
      // Every microservice always advertises a resolution time: the measured
      // value once completed, otherwise its nominal target.
      const time = measured != null ? measured : STAGE_BASE_MS[stage.id];
      const timeTone = measured != null ? "measured" : "nominal";
      const label = status === "idle" ? "idle" : status;
      return `<div class="stage ${status}">
        <div class="bullet"></div>
        <div><div class="title">${escapeHtml(stage.title)}</div><div class="desc">${escapeHtml(stage.desc)}</div></div>
        <div class="state"><div class="state-label">${escapeHtml(label)}</div><div class="state-time ${timeTone}">${time} ms</div></div>
      </div>`;
    }).join("");
  }

  function renderKomPanel() {
    const nodes = state.komNodes;
    if (!nodes || !nodes.length) {
      ui.komPanel.hidden = true;
      return;
    }
    ui.komPanel.hidden = false;
    ui.komNodes.innerHTML = nodes.map((n) => `
      <div class="kom-node ${n.phase}">
        <span class="kn-dot"></span>
        <div><div class="kn-name">${escapeHtml(n.name)}</div><div class="kn-role">${escapeHtml(n.roleLabel)}</div></div>
        <div class="kn-state">${n.phase === "ready" ? "✓ " : ""}${escapeHtml(n.stateLabel)}</div>
      </div>`).join("");
  }

  function renderResult() {
    if (!state.lastResponse) {
      ui.result.innerHTML = `<div class="empty-state">${state.running ? "Provisioning in corso…" : "Nessuna richiesta ancora inviata."}</div>`;
      return;
    }
    const res = state.lastResponse;
    const ok = res.status === "ACTIVE" || res.status === "PROVISIONED";
    const pathLabels = Array.isArray(res.path) ? res.path : [];
    const kms = Array.isArray(res.kms_involved) ? res.kms_involved : [];
    const relayCount = state.activeCircuit ? state.activeCircuit.plan.pathIds.filter((id) => getNode(id)?.kind === "relay").length : 0;
    const stateTone = ok ? "good" : "bad";
    const responseText = res.onos_response || (ok ? "200 OK" : "503 Service Unavailable");

    if (!ok) {
      const stats = [
        { k: "Stato", v: res.status || "FAILED", tone: "bad" },
        { k: "Sorgente", v: res.source || "—" },
        { k: "Destinazione", v: res.destination || "—" },
        { k: "Risposta a ONOS", v: responseText, tone: "bad" },
      ];
      ui.result.innerHTML = `
        <div class="result-banner bad">
          <div class="headline"><h3>Provisioning fallito</h3><span class="chip warn">${escapeHtml(res.status || "FAILED")}</span></div>
          <div class="subtitle">Il sistema non ha potuto stabilire un circuito QKD sicuro end-to-end.</div>
        </div>
        <div class="result-stats">${stats.map(statHtml).join("")}</div>
        ${res.reason ? `<div class="flow-block bad"><span class="flow-k">Motivo</span><div class="flow-reason">${escapeHtml(res.reason)}</div></div>` : ""}`;
      return;
    }

    const stats = [
      { k: "Circuit ID", v: res.circuit_id || "—", tone: "circuit" },
      { k: "Status", v: state.activeCircuit?.state === "ACTIVE_REROUTED" ? "ACTIVE · REROUTED" : "ACTIVE", tone: "good" },
      { k: "Source", v: res.source || "—" },
      { k: "Destination", v: res.destination || "—" },
      { k: "Total cost", v: String(res.total_cost ?? "—") },
      { k: "Key size", v: `${res.key_size ?? "—"} bit` },
      { k: "Keys", v: String(res.keys_allocated ?? "—") },
      { k: "KMS involved", v: String(kms.length) },
      { k: "Trusted relays", v: String(relayCount) },
      { k: "Provisioning time", v: `${res.provisioning_ms ?? state.lastProvisionMs ?? "—"} ms` },
      { k: "ONOS response", v: responseText, tone: "good" },
    ];
    ui.result.innerHTML = `
      <div class="result-banner good">
        <div class="headline"><h3>✓ Circuito QKD provisionato</h3><span class="chip good">${escapeHtml(res.status)}</span></div>
        <div class="subtitle">La richiesta ONOS ha attraversato la pipeline: autenticazione, topologia, path computation, orchestrazione KMS e provisioning completati.</div>
        <div class="result-highlight">Circuito virtuale sicuro end-to-end disponibile per il controller ONOS.</div>
      </div>
      <div class="result-stats">${stats.map(statHtml).join("")}</div>
      <div class="result-flow">
        <div class="flow-block">
          <span class="flow-k">Selected path</span>
          <div class="path-chips">${pathChipsHtml(pathLabels)}</div>
        </div>
      </div>`;
  }

  function statHtml(stat) {
    return `<div class="stat"><span class="stat-k">${escapeHtml(stat.k)}</span><span class="stat-v${stat.tone ? ` ${stat.tone}` : ""}">${escapeHtml(stat.v)}</span></div>`;
  }

  function pathChipsHtml(labels) {
    if (!labels.length) return `<span class="chip">—</span>`;
    return labels.map((label, i) => {
      const node = state.topology.nodes.find((n) => n.label === label);
      const cls = node?.kind === "relay" ? "chip relay" : "chip path";
      return `${i ? `<span class="arrow">→</span>` : ""}<span class="${cls}">${escapeHtml(label)}</span>`;
    }).join("");
  }

  function renderReroute() {
    if (!state.lastReroute) {
      ui.reroutePanel.hidden = true;
      return;
    }
    ui.reroutePanel.hidden = false;
    const r = state.lastReroute;

    if (!r.ok) {
      ui.rerouteArea.innerHTML = `
        <div class="reroute-banner bad"><h3>REROUTING FAILED</h3><span class="chip warn">${escapeHtml(r.circuitState)}</span></div>
        <div class="reroute-meta">
          ${statHtml({ k: "Cause", v: r.cause })}
          ${statHtml({ k: "Reason", v: r.reason || "No feasible QKD path available" })}
          ${statHtml({ k: "Circuit state", v: r.circuitState, tone: "bad" })}
          ${statHtml({ k: "ONOS response", v: r.onos || "503 Service Unavailable", tone: "bad" })}
        </div>`;
      return;
    }

    ui.rerouteArea.innerHTML = `
      <div class="reroute-banner"><h3>REROUTING COMPLETATO</h3><span class="chip warn">${escapeHtml(r.circuitState)}</span></div>
      <div class="reroute-compare">
        <div class="reroute-col old"><span class="rc-k">Previous path</span><div class="path-chips rc-path">${r.previousPath.map((l) => `<span class="chip">${escapeHtml(l)}</span>`).join('<span class="arrow">→</span>')}</div></div>
        <div class="reroute-mid">➜</div>
        <div class="reroute-col new"><span class="rc-k">New path</span><div class="path-chips">${pathChipsHtml(r.newPath)}</div></div>
      </div>
      <div class="reroute-meta">
        ${statHtml({ k: "Cause", v: r.cause })}
        ${statHtml({ k: "Recalculation time", v: `${r.recomputeMs} ms` })}
        ${statHtml({ k: "New cost", v: String(r.newCost) })}
        ${statHtml({ k: "Circuit state", v: r.circuitState, tone: "good" })}
      </div>`;
  }

  function renderPayloads() {
    const compact = state.payloadView === "compact";
    const request = state.lastRequest || previewRequest();
    const response = state.lastResponse || previewResponse();
    ui.requestJson.textContent = JSON.stringify(compact ? compactRequest(request) : request, null, 2);
    ui.responseJson.textContent = JSON.stringify(compact ? compactResponse(response) : response, null, 2);
    ui.requestMeta.textContent = state.lastRequest ? state.lastRequest.request_id : "idle";
    ui.responseMeta.textContent = state.lastResponse ? state.lastResponse.status : "idle";
  }

  function renderEventLog() {
    if (!state.logs.length) {
      ui.eventLog.innerHTML = `<li class="empty-state">Nessun evento registrato. Avvia uno scenario o una richiesta per vedere la timeline live.</li>`;
      return;
    }
    ui.eventLog.innerHTML = state.logs.slice().reverse().map((e) => `
      <li class="event cat-${e.category}">
        <div class="time">[${escapeHtml(e.time)}]</div>
        <div class="cat">${escapeHtml(CATEGORY_TAG[e.category] || e.category.toUpperCase())}</div>
        <div class="msg">${escapeHtml(e.message)}</div>
      </li>`).join("");
  }

  /* ------------------------------ architecture flow ------------------------------ */

  function renderArchFlow() {
    if (!ui.arch) return;
    const a = state.arch;
    const parts = [];
    parts.push(`<rect x="0" y="0" width="1200" height="280" rx="20" fill="rgba(6,13,23,0.24)" />`);

    ARCH_BLOCKS.forEach((b) => parts.push(archBlockSvg(b, a.blocks[b.key] || "idle")));

    // Request direction (top, left→right): ONOS → Adapter → KMS.
    parts.push(archArrowSvg(350, 440, 112, a.flows.reqOnosAdapter, "req", "richiesta QKD"));
    parts.push(archArrowSvg(760, 850, 112, a.flows.reqAdapterKms, "req", "richiesta chiavi"));
    // Response direction (bottom, right→left): KMS → Adapter → ONOS.
    parts.push(archArrowSvg(850, 760, 160, a.flows.respKmsAdapter, "resp", "chiavi QKD"));
    parts.push(archArrowSvg(440, 350, 160, a.flows.respAdapterOnos, "resp", "200 OK"));

    ui.arch.innerHTML = parts.join("");
  }

  function archBlockSvg(b, status) {
    const cx = b.x + 150;
    const two = b.titleLines.length === 2;
    const selected = state.arch.selected === b.key ? " selected" : "";
    const titleSvg = two
      ? `<text class="an-title" x="${cx}" y="116" text-anchor="middle">${escapeHtml(b.titleLines[0])}</text>
         <text class="an-title" x="${cx}" y="140" text-anchor="middle">${escapeHtml(b.titleLines[1])}</text>`
      : `<text class="an-title" x="${cx}" y="126" text-anchor="middle">${escapeHtml(b.titleLines[0])}</text>`;
    const subY = two ? 164 : 150;
    const pill = ARCH_PILL[status] || ARCH_PILL.idle;
    return `<g class="arch-node ${status}${selected}" data-arch-block="${b.key}" style="cursor:pointer">
      <rect x="${b.x}" y="60" width="300" height="150" rx="18" />
      <text class="an-role" x="${cx}" y="94" text-anchor="middle">${escapeHtml(b.role)}</text>
      ${titleSvg}
      <text class="an-sub" x="${cx}" y="${subY}" text-anchor="middle">${escapeHtml(b.sub)}</text>
      <rect class="an-pill-bg" x="${cx - 60}" y="180" width="120" height="20" rx="10" />
      <text class="an-pill" x="${cx}" y="194" text-anchor="middle">${escapeHtml(pill)}</text>
      <title>${escapeHtml(b.caption)}</title>
    </g>`;
  }

  function archArrowSvg(tailX, headX, y, status, dir, label) {
    const flowColor = dir === "req" ? "#f6b94d" : "#37d67a";
    const active = status === "active";
    const done = status === "done";
    const fail = status === "fail";
    const lineColor = fail ? "#ff647c" : (active || done) ? flowColor : "rgba(142,163,196,0.32)";
    const width = (active || done || fail) ? 3 : 2;
    const baseOpacity = active ? 0.45 : done ? 0.9 : fail ? 0.9 : 0.7;
    const goRight = headX > tailX;
    const ax = goRight ? headX - 11 : headX + 11;
    const headOpacity = (active || done || fail) ? 1 : 0.6;

    const baseLine = `<line x1="${tailX}" y1="${y}" x2="${headX}" y2="${y}" stroke="${lineColor}" stroke-width="${width}" stroke-linecap="round" opacity="${baseOpacity}" />`;
    const arrowHead = `<path d="M ${headX} ${y} L ${ax} ${y - 6} L ${ax} ${y + 6} Z" fill="${lineColor}" opacity="${headOpacity}" />`;
    const flow = active
      ? `<line x1="${tailX}" y1="${y}" x2="${headX}" y2="${y}" stroke="${flowColor}" stroke-width="3" stroke-linecap="round" stroke-dasharray="1 11" opacity="0.95" style="filter:drop-shadow(0 0 5px ${flowColor})">
           <animate attributeName="stroke-dashoffset" from="0" to="-24" dur="0.7s" repeatCount="indefinite" />
         </line>
         <circle r="4.5" fill="${flowColor}" style="filter:drop-shadow(0 0 6px ${flowColor})">
           <animateMotion dur="0.9s" repeatCount="indefinite" path="M ${tailX} ${y} L ${headX} ${y}" />
         </circle>`
      : "";
    const midX = (tailX + headX) / 2;
    const labelY = dir === "req" ? y - 12 : y + 20;
    const labelColor = fail ? "#ff647c" : (active || done) ? (dir === "req" ? "#f6cf85" : "#7ee0a6") : "rgba(142,163,196,0.72)";
    const labelText = `<text x="${midX}" y="${labelY}" text-anchor="middle" class="arch-flow-label" fill="${labelColor}">${escapeHtml(label)}</text>`;

    return `<g>${baseLine}${arrowHead}${flow}${labelText}</g>`;
  }

  function renderArchCaption() {
    if (!ui.archCaption) return;
    const selected = ARCH_BLOCKS.find((b) => b.key === state.arch.selected);
    ui.archCaption.textContent = selected
      ? selected.caption
      : "Flusso logico: ONOS/Mininet richiede il servizio, il QSDN Adapter orchestra path e KMS, il KMS consegna le chiavi ETSI 014 e il circuito ritorna a ONOS. Le frecce si illuminano quando l'informazione passa. Clicca un blocco per i dettagli.";
  }

  // Map the pipeline lifecycle onto the three-block architecture diagram so the
  // arrows animate exactly while the corresponding hand-off is happening.
  function archFromStage(id, status) {
    if (status === "idle") return;
    const b = state.arch.blocks;
    const f = state.arch.flows;
    switch (id) {
      case "gateway":
        if (status === "running") { b.onos = "active"; b.adapter = "active"; f.reqOnosAdapter = "active"; }
        else if (status === "completed") { f.reqOnosAdapter = "done"; }
        else if (status === "failed") { f.reqOnosAdapter = "fail"; b.adapter = "fail"; }
        break;
      case "identity":
      case "topology":
      case "pce":
        if (status === "running") { b.onos = "done"; f.reqOnosAdapter = "done"; b.adapter = "active"; }
        else if (status === "failed") { b.adapter = "fail"; }
        break;
      case "kom":
        if (status === "running") { b.adapter = "active"; b.kms = "active"; f.reqAdapterKms = "active"; }
        else if (status === "completed") { f.reqAdapterKms = "done"; b.kms = "done"; f.respKmsAdapter = "active"; }
        else if (status === "failed") { f.reqAdapterKms = "fail"; b.kms = "fail"; }
        break;
      case "prov":
        if (status === "running") { f.respKmsAdapter = "done"; f.respAdapterOnos = "active"; b.adapter = "active"; }
        else if (status === "completed") { f.respAdapterOnos = "done"; b.adapter = "done"; b.onos = "done"; }
        else if (status === "failed") { f.respAdapterOnos = "fail"; }
        break;
    }
    renderArchFlow();
  }

  /* ------------------------------ provisioning ------------------------------ */

  async function provisionCircuit() {
    if (ui.reqSource.value === ui.reqDest.value) {
      setFeedback(ui.requestFeedback, "Sorgente e destinazione devono essere diverse.", "warn");
      return;
    }
    const request = buildRequestFromForm();
    const token = ++state.jobId;
    state.running = true;
    resetStages();
    state.arch = createInitialArch();
    state.stageTimes = {};
    state.komNodes = [];
    state.komPhase = {};
    state.pathPulse = null;
    state.lastRequest = request;
    state.lastResponse = null;
    state.activeCircuit = null;
    state.lastReroute = null;
    state.lastPathCost = null;
    state.lastProvisionMs = null;
    ui.provisionBtn.disabled = true;
    addEvent("onos", `Richiesta servizio QKD ${endpointLabel(request.source)} → ${endpointLabel(request.destination)} ricevuta.`);
    renderAll();

    try {
      // Gateway
      setStage("gateway", "running"); await animStep(token); if (!isJobCurrent(token)) return;
      completeStage("gateway", 32); addEvent("onos", "Richiesta REST accettata dal Northbound API Gateway.");

      // Identity
      setStage("identity", "running"); await animStep(token); if (!isJobCurrent(token)) return;
      completeStage("identity", 41); addEvent("auth", `Client ONOS, SAE_ID e parametri validati (key size ${request.key_size}).`);

      // Topology
      setStage("topology", "running"); await animStep(token); if (!isJobCurrent(token)) return;
      completeStage("topology", 68); addEvent("topology", `Topologia QKD/KMS corrente disponibile: ${state.topology.nodes.length} nodi, ${activeLinkCount()} link attivi.`);

      // Path computation
      setStage("pce", "running"); await animStep(token); if (!isJobCurrent(token)) return;
      const plan = computeBestPath(request);
      if (!plan.ok) return failProvision(token, "pce", request, plan.reason, plan.onosResponse || "503 Service Unavailable", plan.totalCost);
      completeStage("pce", 15 + plan.hops * 3);
      state.pathPulse = plan.pathIds.slice();
      addEvent("path", `Percorso selezionato: ${plan.pathLabels.join(" → ")} (cost ${plan.totalCost}).`);
      renderTopology();

      // Key orchestration — reveal exactly the KMS on the chosen path
      setStage("kom", "running");
      initKomNodes(plan, request);
      renderAll();
      const allocation = allocateKeys(plan, request);
      if (!allocation.ok) {
        await animateKomFailure(token, allocation.failIndex);
        if (!isJobCurrent(token)) return;
        return failProvision(token, "kom", request, allocation.reason, "503 Service Unavailable", plan.totalCost);
      }
      await animateKomOrchestration(token);
      if (!isJobCurrent(token)) return;
      completeStage("kom", 90 * plan.kmsInvolved.length);
      addEvent("kms", `Coordinamento completato sui ${plan.kmsInvolved.length} KMS coinvolti: chiavi allocate.`);

      // Service provisioning
      setStage("prov", "running"); await animStep(token); if (!isJobCurrent(token)) return;
      completeStage("prov", 102);
      const circuitId = `vc-${new Date().getFullYear()}-${pad4(state.circuitSeq++)}`;
      const totalMs = Object.values(state.stageTimes).reduce((a, b) => a + b, 0);
      const response = buildSuccessResponse(request, plan, circuitId, totalMs);
      state.activeCircuit = { circuitId, request, plan, state: "ACTIVE", startedAt: Date.now() };
      state.lastResponse = response;
      state.lastProvisionMs = totalMs;
      state.lastPathCost = plan.totalCost;
      state.pathPulse = null;
      state.komPhase = {};
      addEvent("provisioning", `Circuito ${circuitId} attivo su ${plan.pathLabels.join(" → ")}.`);
      addEvent("onos", `Risposta inviata al client ONOS: ${response.onos_response}.`);
      consumePoolsAlongPath(plan.pathIds, request);
      state.running = false;
      ui.provisionBtn.disabled = false;
      renderAll();
      void syncBackendProvision(request, response);
    } catch (error) {
      const message = error instanceof Error ? error.message : "errore inatteso";
      failProvision(token, "pce", request, `Errore interno: ${message}`, "500 Internal Server Error", null);
    }
  }

  function failProvision(token, stageId, request, reason, onos, cost) {
    if (!isJobCurrent(token)) return;
    setStage(stageId, "failed");
    ["kom", "prov"].forEach((s) => { if (state.stageStatus[s] !== "failed") setStage(s, "idle"); });
    const category = stageId === "pce" ? "path" : stageId === "kom" ? "kms" : "error";
    addEvent(category, reason, "bad");
    const response = buildFailureResponse(request, reason, onos);
    state.lastResponse = response;
    state.lastPathCost = cost ?? "—";
    state.lastProvisionMs = Object.values(state.stageTimes).reduce((a, b) => a + b, 0) || null;
    state.activeCircuit = null;
    state.pathPulse = null;
    state.running = false;
    ui.provisionBtn.disabled = false;
    addEvent("onos", `Risposta inviata al client ONOS: ${onos}.`, "bad");
    renderAll();
    void syncBackendProvision(request, response);
  }

  function initKomNodes(plan, request) {
    const budget = computeKeyBudget(request);
    state.komNodes = plan.pathIds.map((id, i) => {
      const node = getNode(id);
      const isDest = i === plan.pathIds.length - 1;
      const isSrc = i === 0;
      const roleLabel = isSrc ? "Source · Main KMS" : isDest ? "Destination · Main KMS" : node.kind === "relay" ? "Trusted relay" : "Main KMS";
      return { id, name: endpointLabel(id), roleLabel, phase: "requesting", stateLabel: "REQUESTING", budget };
    });
    state.komPhase = Object.fromEntries(plan.pathIds.map((id) => [id, "requesting"]));
  }

  async function animateKomOrchestration(token) {
    for (let i = 0; i < state.komNodes.length; i += 1) {
      await delay(KOM_STEP_MS);
      if (!isJobCurrent(token)) return;
      const n = state.komNodes[i];
      const node = getNode(n.id);
      const isDest = i === state.komNodes.length - 1;
      n.phase = "ready";
      n.stateLabel = isDest ? "DESTINATION READY" : node.kind === "relay" ? "TRUSTED RELAY READY" : "READY";
      state.komPhase[n.id] = "ready";
      renderKomPanel();
      renderTopology();
    }
  }

  async function animateKomFailure(token, failIndex) {
    for (let i = 0; i < state.komNodes.length; i += 1) {
      await delay(KOM_STEP_MS);
      if (!isJobCurrent(token)) return;
      const n = state.komNodes[i];
      if (i < failIndex) {
        n.phase = "ready"; n.stateLabel = "READY"; state.komPhase[n.id] = "ready";
      } else {
        n.phase = "requesting"; n.stateLabel = "KEY POOL INSUFFICIENTE";
        renderKomPanel();
        return;
      }
      renderKomPanel();
      renderTopology();
    }
  }

  function buildRequestFromForm() {
    const requestId = (ui.reqId.value || `onos-req-${pad4(state.requestSeq)}`).trim();
    const request = {
      request_id: requestId,
      source: ui.reqSource.value,
      destination: ui.reqDest.value,
      key_size: Number(ui.reqKeySize.value) || 256,
      number_of_keys: Math.max(1, Number(ui.reqKeys.value) || 1),
      sla: "lowest_cost",
      service_type: "qkd_virtual_circuit",
    };
    state.requestSeq += 1;
    ui.reqId.value = `onos-req-${pad4(state.requestSeq)}`;
    return request;
  }

  /* ------------------------------ path computation ------------------------------ */

  function computeBestPath(request) {
    const source = normalizeId(request.source);
    const target = normalizeId(request.destination);
    if (!source || !target) return failPlan("Sorgente o destinazione non valide.", "400 Bad Request");
    if (source === target) return failPlan("Sorgente e destinazione coincidono: nessun circuito richiesto.", "409 Conflict");
    const nodeMap = new Map(state.topology.nodes.map((n) => [n.id, n]));
    if (!nodeMap.has(source) || !nodeMap.has(target)) return failPlan("Endpoint non presenti nella topologia corrente.", "404 Not Found");

    const requiredBudget = computeKeyBudget(request);
    const pathIds = computePathByCost(source, target, requiredBudget);
    if (!pathIds.length) return failPlan("No feasible QKD path available: disponibilità chiavi insufficiente o rete disconnessa.", "503 Service Unavailable");
    return buildPlanFromPath(pathIds);
  }

  function buildPlanFromPath(pathIds) {
    const nodeMap = new Map(state.topology.nodes.map((n) => [n.id, n]));
    const pathNodes = pathIds.map((id) => nodeMap.get(id)).filter(Boolean);
    return {
      ok: true,
      pathIds,
      pathLabels: pathNodes.map((n) => n.label || prettyLabel(n.id)),
      kmsInvolved: pathNodes.map((n) => n.label),
      totalCost: calculateCost(pathIds),
      hops: Math.max(0, pathIds.length - 1),
    };
  }

  function computePathByCost(source, target, requiredBudget) {
    const adjacency = buildAdjacency();
    const nodeIds = Array.from(adjacency.keys());
    const dist = new Map(nodeIds.map((id) => [id, Number.POSITIVE_INFINITY]));
    const prev = new Map();
    const visited = new Set();
    dist.set(source, 0);

    while (visited.size < nodeIds.length) {
      let current = null, currentDist = Number.POSITIVE_INFINITY;
      for (const id of nodeIds) {
        if (visited.has(id)) continue;
        const d = dist.get(id) ?? Number.POSITIVE_INFINITY;
        if (d < currentDist) { currentDist = d; current = id; }
      }
      if (current == null || !Number.isFinite(currentDist)) break;
      if (current === target) break;
      visited.add(current);
      for (const edge of adjacency.get(current) || []) {
        if (edge.status !== "up") continue;
        const nextNode = getNode(edge.next);
        if (!nextNode || !canTraverseNode(nextNode, edge.next !== target)) continue;
        const budgetPenalty = edge.next !== target && nextNode.pool < requiredBudget ? (requiredBudget - nextNode.pool) * 0.9 : 0;
        const warnPenalty = nextNode.pool < 35 ? (35 - nextNode.pool) * 0.15 : 0;
        const candidate = currentDist + (edge.cost || 1) + budgetPenalty + warnPenalty;
        if (candidate < (dist.get(edge.next) ?? Number.POSITIVE_INFINITY)) {
          dist.set(edge.next, candidate);
          prev.set(edge.next, current);
        }
      }
    }
    return reconstructPath(prev, source, target);
  }

  function reconstructPath(prev, source, target) {
    if (source === target) return [source];
    if (!prev.has(target)) return [];
    const out = [target];
    let cursor = target;
    while (cursor !== source) {
      const parent = prev.get(cursor);
      if (!parent) return [];
      out.push(parent);
      cursor = parent;
    }
    out.reverse();
    return out;
  }

  function allocateKeys(plan, request) {
    const nodeMap = new Map(state.topology.nodes.map((n) => [n.id, n]));
    const budget = computeKeyBudget(request);
    const failIndex = plan.pathIds.findIndex((id) => (nodeMap.get(id)?.pool ?? 0) < budget);
    if (failIndex >= 0) {
      return { ok: false, failIndex, reason: `Key pool insufficiente su ${cityLabel(plan.pathIds[failIndex])}: budget richiesto ${budget}, disponibile ${nodeMap.get(plan.pathIds[failIndex]).pool}.` };
    }
    return { ok: true, budget };
  }

  function consumePoolsAlongPath(pathIds, request) {
    const delta = Math.max(4, Math.ceil(computeKeyBudget(request) / 2));
    pathIds.forEach((id) => {
      const node = getNode(id);
      if (!node) return;
      node.pool = clamp(node.pool - delta, 0, 100);
      node.status = normalizeNodeStatus(node.status, node.pool);
    });
  }

  /* ------------------------------ responses ------------------------------ */

  function buildSuccessResponse(request, plan, circuitId, elapsedMs) {
    return {
      request_id: request.request_id,
      circuit_id: circuitId,
      status: "ACTIVE",
      source: endpointLabel(request.source),
      destination: endpointLabel(request.destination),
      path: plan.pathIds.map((id) => cityLabel(id)),
      total_cost: plan.totalCost,
      key_size: request.key_size,
      keys_allocated: request.number_of_keys,
      kms_involved: plan.pathIds.map((id) => cityLabel(id)),
      provisioning_ms: elapsedMs,
      onos_response: "200 OK",
      etsi_014_reference: {
        enc_keys_endpoint: "/api/v1/keys/{SAE_ID}/enc_keys",
        dec_keys_endpoint: "/api/v1/keys/{SAE_ID}/dec_keys",
      },
    };
  }

  function buildFailureResponse(request, reason, onosResponse) {
    return {
      request_id: request.request_id,
      status: "FAILED",
      source: endpointLabel(request.source),
      destination: endpointLabel(request.destination),
      reason,
      onos_response: onosResponse,
      path: [],
      kms_involved: [],
      total_cost: null,
      key_size: request.key_size,
      keys_allocated: 0,
    };
  }

  function compactRequest(req) {
    return {
      request_id: req.request_id,
      source: req.source && getNode(normalizeId(req.source)) ? endpointLabel(req.source) : req.source,
      destination: req.destination && getNode(normalizeId(req.destination)) ? endpointLabel(req.destination) : req.destination,
      key_size: req.key_size,
      number_of_keys: req.number_of_keys,
    };
  }

  function compactResponse(res) {
    if (res.status === "FAILED") {
      return { request_id: res.request_id, status: res.status, reason: res.reason, onos_response: res.onos_response };
    }
    return {
      request_id: res.request_id,
      circuit_id: res.circuit_id,
      status: res.status,
      path: res.path,
      onos_response: res.onos_response,
    };
  }

  function previewRequest() {
    const src = ui.reqSource?.value || "milano";
    const dst = ui.reqDest?.value || "venezia";
    return {
      request_id: ui.reqId?.value || `onos-req-${pad4(state.requestSeq)}`,
      source: endpointLabel(src),
      destination: endpointLabel(dst),
      key_size: Number(ui.reqKeySize?.value || 256),
      number_of_keys: Math.max(1, Number(ui.reqKeys?.value || 1)),
      sla: "lowest_cost",
      service_type: "qkd_virtual_circuit",
    };
  }

  function previewResponse() {
    return {
      request_id: previewRequest().request_id,
      circuit_id: "—",
      status: "IDLE",
      path: [],
      total_cost: null,
      key_size: Number(ui.reqKeySize?.value || 256),
      keys_allocated: 0,
      kms_involved: [],
      onos_response: "—",
      etsi_014_reference: {
        enc_keys_endpoint: "/api/v1/keys/{SAE_ID}/enc_keys",
        dec_keys_endpoint: "/api/v1/keys/{SAE_ID}/dec_keys",
      },
    };
  }

  /* ------------------------------ rerouting ------------------------------ */

  async function rerouteActiveCircuit(cause) {
    if (!state.activeCircuit) return;
    const request = state.activeCircuit.request;
    const previousPlan = state.activeCircuit.plan;
    const plan = computeBestPath(request);
    state.rerouteCount += 1;
    addEvent("rerouting", `Rerouting avviato dal QSDN Adapter. Causa: ${cause}.`, "warn");

    if (!plan.ok) {
      state.activeCircuit.state = "DEGRADED";
      state.lastResponse = { ...state.lastResponse, status: "DEGRADED", onos_response: "503 Service Unavailable", reason: plan.reason };
      state.lastPathCost = "—";
      state.lastReroute = { ok: false, cause, reason: plan.reason, circuitState: "DEGRADED", onos: "503 Service Unavailable" };
      addEvent("path", `Nessun percorso alternativo disponibile: circuito in stato DEGRADED.`, "bad");
      addEvent("onos", "Risposta inviata al client ONOS: 503 Service Unavailable.", "bad");
      renderAll();
      return;
    }

    const recomputeMs = 30 + plan.hops * 4 + plan.kmsInvolved.length * 2;
    state.activeCircuit.plan = plan;
    state.activeCircuit.state = "ACTIVE_REROUTED";
    state.lastPathCost = plan.totalCost;
    state.lastResponse = {
      ...state.lastResponse,
      status: "ACTIVE",
      path: plan.pathIds.map((id) => cityLabel(id)),
      kms_involved: plan.pathIds.map((id) => cityLabel(id)),
      total_cost: plan.totalCost,
      onos_response: "200 OK",
      rerouted: true,
    };
    state.lastReroute = {
      ok: true,
      cause,
      previousPath: previousPlan.pathLabels,
      newPath: plan.pathLabels,
      recomputeMs,
      newCost: plan.totalCost,
      circuitState: "ACTIVE · REROUTED",
    };
    addEvent("path", `Nuovo percorso disponibile: ${plan.pathLabels.join(" → ")} (cost ${plan.totalCost}).`);
    addEvent("provisioning", `Circuito ${state.activeCircuit.circuitId} aggiornato: ACTIVE · REROUTED.`);
    renderAll();
  }

  /* ------------------------------ one-click scenarios ------------------------------ */

  async function runScenario(action) {
    switch (action) {
      case "scenario-1": return void executeNormalProvisioningScenario();
      case "scenario-2": return void executeFailureAndReroutingScenario();
      case "scenario-3": return void executeKeyPoolFailureScenario();
      case "restore-links":
        restoreMainLinks();
        addEvent("topology", "Tutti i link ripristinati (stato up).");
        if (state.activeCircuit) await rerouteActiveCircuit("link ripristinati");
        renderAll();
        return;
      case "add-firenze":
        if (!state.topology.nodes.some((n) => n.id === "firenze")) state.topology.nodes.push(cloneNode(CITY_LIBRARY.firenze, true));
        upsertLink("firenze", "bologna", 1, "up");
        addEvent("topology", "Aggiunto Firenze KMS e link di interconnessione a Bologna.");
        refreshControlsAfterTopologyChange();
        renderAll();
        await syncTopologyChange({ type: "scenario", name: "add-firenze" });
        if (state.activeCircuit) await rerouteActiveCircuit("Firenze KMS aggiunto");
        return;
      case "reset-demo": return void resetDemoState();
      case "clear-log":
        state.logs = [];
        addEvent("system", "Log pulito.");
        renderAll();
        return;
      default: return;
    }
  }

  async function executeNormalProvisioningScenario() {
    setFeedback(ui.scenarioRunFeedback, "Scenario 1 — provisioning normale in corso…", "good");
    resetDemoTopologyOnly();
    ui.reqSource.value = pickId("milano");
    ui.reqDest.value = pickId("venezia");
    ui.reqKeySize.value = "256";
    ui.reqKeys.value = "1";
    addEvent("system", "Scenario 1 — Provisioning normale avviato.");
    await provisionCircuit();
    setFeedback(ui.scenarioRunFeedback, state.activeCircuit ? "Scenario 1 completato: circuito attivo, 200 OK." : "Scenario 1 terminato.", "good");
  }

  async function executeFailureAndReroutingScenario() {
    if (!state.activeCircuit) {
      setFeedback(ui.scenarioRunFeedback, "Nessun circuito attivo: eseguo prima il provisioning…", "warn");
      await executeNormalProvisioningScenario();
    }
    if (!state.activeCircuit) return;
    setFeedback(ui.scenarioRunFeedback, "Scenario 2 — guasto e rerouting in corso…", "warn");
    addEvent("system", "Scenario 2 — Guasto e rerouting avviato.");
    const link = pickPathLinkToFail();
    if (!link) {
      setFeedback(ui.scenarioRunFeedback, "Nessun link del percorso disponibile per il guasto.", "warn");
      return;
    }
    link.status = "down";
    addEvent("topology", `Network event: link ${cityLabel(link.source)} — ${cityLabel(link.target)} non disponibile.`, "warn");
    refreshControlsAfterTopologyChange();
    renderAll();
    await delay(600);
    await rerouteActiveCircuit(`Link ${cityLabel(link.source)} — ${cityLabel(link.target)} DOWN`);
    await syncTopologyChange({ type: "link", source: link.source, target: link.target, status: "down" });
    setFeedback(ui.scenarioRunFeedback, state.activeCircuit?.state === "ACTIVE_REROUTED" ? "Scenario 2 completato: circuito ACTIVE · REROUTED." : "Scenario 2 terminato.", "good");
  }

  async function executeKeyPoolFailureScenario() {
    if (!state.activeCircuit) {
      setFeedback(ui.scenarioRunFeedback, "Nessun circuito attivo: eseguo prima il provisioning…", "warn");
      await executeNormalProvisioningScenario();
    }
    if (!state.activeCircuit) return;
    setFeedback(ui.scenarioRunFeedback, "Scenario 3 — key pool insufficiente in corso…", "warn");
    addEvent("system", "Scenario 3 — Key pool insufficiente avviato.");
    const target = pickPoolNodeToDrain();
    if (!target) {
      setFeedback(ui.scenarioRunFeedback, "Nessun nodo intermedio sul percorso.", "warn");
      return;
    }
    target.pool = 8;
    target.status = normalizeNodeStatus("active", target.pool);
    addEvent("kms", `Key pool di ${target.label} sceso a ${target.pool}%: nodo non disponibile per il relay.`, "warn");
    refreshControlsAfterTopologyChange();
    renderAll();
    await delay(600);
    await rerouteActiveCircuit(`Key pool ${target.label} insufficiente (${target.pool}%)`);
    await syncTopologyChange({ type: "scenario", name: "set-pool", node: target.id, pool: target.pool });
    setFeedback(ui.scenarioRunFeedback, state.lastReroute?.ok ? "Scenario 3 completato: percorso alternativo calcolato." : "Scenario 3 terminato.", "good");
  }

  // An intermediate KMS on the active path whose key-pool exhaustion still
  // leaves a feasible alternative — preferring a trusted relay — so the
  // scenario shows the PCE rerouting rather than a dead circuit.
  function pickPoolNodeToDrain() {
    const request = state.activeCircuit.request;
    const source = normalizeId(request.source);
    const dest = normalizeId(request.destination);
    const intermediates = state.activeCircuit.plan.pathIds
      .map((id) => getNode(id))
      .filter((n) => n && n.id !== source && n.id !== dest);
    const feasible = intermediates.filter((n) => {
      const prev = n.pool;
      n.pool = 8;
      const ok = computeBestPath(request).ok;
      n.pool = prev;
      return ok;
    });
    const pool = feasible.length ? feasible : intermediates;
    return pool.find((n) => n.kind === "relay") || pool[0] || null;
  }

  function pickPathLinkToFail() {
    const ids = state.activeCircuit.plan.pathIds;
    const request = state.activeCircuit.request;
    const source = normalizeId(request.source);
    const dest = normalizeId(request.destination);
    const candidates = [];
    for (let i = 0; i < ids.length - 1; i += 1) {
      const link = getLink(ids[i], ids[i + 1]);
      if (link && link.status === "up") candidates.push({ link, a: ids[i], b: ids[i + 1] });
    }
    // Prefer a link whose failure still leaves a feasible QKD path, so the
    // scenario demonstrates a live reroute rather than a dead circuit. Among
    // those, favour a truly intermediate hop (not incident to source/dest).
    const feasible = candidates.filter((c) => {
      const prev = c.link.status;
      c.link.status = "down";
      const ok = computeBestPath(request).ok;
      c.link.status = prev;
      return ok;
    });
    const pool = feasible.length ? feasible : candidates;
    const intermediate = pool.find((c) => c.a !== source && c.a !== dest && c.b !== source && c.b !== dest);
    return (intermediate || pool[0])?.link || null;
  }

  function resetDemoTopologyOnly() {
    state.topology = createDefaultTopology();
    state.activeCircuit = null;
    state.lastReroute = null;
    refreshControlsAfterTopologyChange();
  }

  /* ------------------------------ topology editing ------------------------------ */

  function toggleNodeReveal(nodeId) {
    const id = normalizeId(nodeId);
    if (state.revealedNodes.has(id)) state.revealedNodes.delete(id);
    else state.revealedNodes.add(id);
    renderTopology();
  }

  async function toggleLinkState(sourceId, targetId) {
    const link = getLink(sourceId, targetId);
    if (!link) return;
    link.status = link.status === "up" ? "down" : "up";
    addEvent("topology", `Link ${cityLabel(sourceId)} — ${cityLabel(targetId)} ${link.status === "up" ? "ripristinato" : "non disponibile"}.`, link.status === "up" ? "info" : "warn");
    refreshControlsAfterTopologyChange();
    renderAll();
    await syncTopologyChange({ type: "link", source: sourceId, target: targetId, status: link.status });
    if (state.activeCircuit) await rerouteActiveCircuit(`link ${cityLabel(sourceId)} — ${cityLabel(targetId)} ${link.status === "up" ? "ripristinato" : "DOWN"}`);
  }

  async function addNodeFromPicker() {
    const nodeId = ui.nodePicker.value;
    if (!nodeId) return setFeedback(ui.nodeFeedback, "Nessun nodo disponibile da aggiungere.", "warn");
    if (state.topology.nodes.some((n) => n.id === nodeId)) return setFeedback(ui.nodeFeedback, "Il nodo è già presente nella topologia.", "warn");
    const source = CITY_LIBRARY[nodeId];
    if (!source) return setFeedback(ui.nodeFeedback, "Nodo non riconosciuto.", "bad");
    state.topology.nodes.push(cloneNode(source, true));
    setFeedback(ui.nodeFeedback, `${source.label} aggiunto alla topologia.`, "good");
    addEvent("topology", `Aggiunto nodo ${source.label} (${source.kmsId}).`);
    await connectAddedNode(source.id);
    refreshControlsAfterTopologyChange();
    renderAll();
    await syncTopologyChange({ type: "node", node: source.id, action: "upsert" });
    if (state.activeCircuit) await rerouteActiveCircuit(`nodo ${source.label} aggiunto`);
  }

  async function connectAddedNode(nodeId) {
    const links = [];
    if (nodeId === "firenze") {
      if (hasNode("bologna")) links.push(["firenze", "bologna", 1]);
      if (hasNode("roma")) links.push(["firenze", "roma", 2]);
    } else if (nodeId === "roma") {
      if (hasNode("firenze")) links.push(["roma", "firenze", 2]);
      if (hasNode("napoli")) links.push(["roma", "napoli", 2]);
    } else if (nodeId === "napoli") {
      if (hasNode("roma")) links.push(["napoli", "roma", 2]);
    }
    for (const [s, t, c] of links) upsertLink(s, t, c, "up");
  }

  async function addLinkFromForm() {
    const source = ui.linkSource.value;
    const target = ui.linkTarget.value;
    const cost = Number(ui.linkCost.value);
    if (!source || !target) return setFeedback(ui.linkFeedback, "Seleziona due nodi validi.", "warn");
    if (source === target) return setFeedback(ui.linkFeedback, "Non è possibile creare un link verso sé stesso.", "bad");
    if (!Number.isFinite(cost) || cost <= 0) return setFeedback(ui.linkFeedback, "Il costo del link deve essere maggiore di 0.", "bad");
    if (getLink(source, target)) return setFeedback(ui.linkFeedback, "Questo link esiste già.", "warn");
    upsertLink(source, target, cost, "up");
    setFeedback(ui.linkFeedback, `Link ${cityLabel(source)} — ${cityLabel(target)} aggiunto.`, "good");
    addEvent("topology", `Aggiunto link ${cityLabel(source)} — ${cityLabel(target)} (cost ${cost}).`);
    refreshControlsAfterTopologyChange();
    renderAll();
    await syncTopologyChange({ type: "link", source, target, cost, status: "up", action: "upsert" });
    if (state.activeCircuit) await rerouteActiveCircuit(`nuovo link ${cityLabel(source)} — ${cityLabel(target)}`);
  }

  async function toggleFaultLinkFromForm() {
    const source = ui.faultLinkSource.value;
    const target = ui.faultLinkTarget.value;
    if (!source || !target || source === target) return setFeedback(ui.faultLinkFeedback, "Seleziona due nodi diversi.", "warn");
    const link = getLink(source, target);
    if (!link) return setFeedback(ui.faultLinkFeedback, `Nessun link diretto tra ${cityLabel(source)} e ${cityLabel(target)}.`, "warn");
    const willBe = link.status === "up" ? "down" : "up";
    setFeedback(ui.faultLinkFeedback, `Link ${cityLabel(source)} — ${cityLabel(target)} ${willBe === "up" ? "ripristinato" : "non disponibile"}.`, willBe === "up" ? "good" : "warn");
    await toggleLinkState(source, target);
  }

  async function setNodePoolFromForm() {
    const nodeId = ui.poolNode.value;
    const value = Number(ui.poolValue.value);
    const node = getNode(nodeId);
    if (!node) return setFeedback(ui.poolFeedback, "Seleziona un nodo valido.", "warn");
    if (!Number.isFinite(value) || value < 0 || value > 100) return setFeedback(ui.poolFeedback, "Il key pool deve essere tra 0 e 100.", "bad");
    node.pool = clamp(Math.round(value), 0, 100);
    node.status = normalizeNodeStatus("active", node.pool);
    const tone = node.pool <= 35 ? "warn" : "good";
    setFeedback(ui.poolFeedback, `Key pool ${cityLabel(nodeId)} impostato a ${node.pool}% (${node.status}).`, tone);
    addEvent("kms", `Key pool ${cityLabel(nodeId)} = ${node.pool}% (${node.status}).`, tone === "good" ? "info" : "warn");
    refreshControlsAfterTopologyChange();
    renderAll();
    await syncTopologyChange({ type: "scenario", name: "set-pool", node: nodeId, pool: node.pool });
    if (state.activeCircuit) await rerouteActiveCircuit(`key pool ${cityLabel(nodeId)} = ${node.pool}%`);
  }

  function upsertLink(source, target, cost = 1, status = "up") {
    const existing = getLink(source, target);
    if (existing) { existing.cost = Number(cost) || existing.cost || 1; existing.status = status; return existing; }
    const link = { source, target, cost: Number(cost) || 1, status, kind: "physical" };
    state.topology.links.push(link);
    return link;
  }

  function restoreMainLinks() {
    state.topology.links.forEach((l) => { if (l.status === "down") l.status = "up"; });
    refreshControlsAfterTopologyChange();
  }

  async function resetTopology() {
    state.topology = createDefaultTopology();
    state.activeCircuit = null;
    state.lastResponse = null;
    state.lastRequest = null;
    state.lastReroute = null;
    state.lastPathCost = null;
    state.lastProvisionMs = null;
    state.komNodes = [];
    state.komPhase = {};
    state.pathPulse = null;
    state.arch = createInitialArch();
    resetStages();
    setDefaultFormValues();
    clearFeedbacks();
    addEvent("topology", "Topologia ripristinata alla rete QKD/KMS iniziale.");
    renderAll();
    await syncTopologyChange({ type: "reset" });
  }

  async function resetDemoState() {
    Object.assign(state, {
      topology: createDefaultTopology(),
      activeCircuit: null,
      lastRequest: null,
      lastResponse: null,
      lastReroute: null,
      lastPathCost: null,
      lastProvisionMs: null,
      rerouteCount: 0,
      requestSeq: 42,
      circuitSeq: 1,
      logs: [],
      stageTimes: {},
      komNodes: [],
      komPhase: {},
      pathPulse: null,
      running: false,
      revealedNodes: new Set(),
      badges: DEFAULT_BADGES.map((b) => ({ ...b })),
      arch: createInitialArch(),
    });
    state.jobId += 1;
    resetStages();
    setDefaultFormValues();
    clearFeedbacks();
    setFeedback(ui.scenarioRunFeedback, "", "");
    addEvent("system", "Reset demo eseguito: topologia, pipeline, risultato e log ripristinati.");
    renderAll();
    await syncTopologyChange({ type: "reset" });
  }

  function clearFeedbacks() {
    [ui.requestFeedback, ui.nodeFeedback, ui.linkFeedback, ui.scenarioFeedback, ui.faultLinkFeedback, ui.poolFeedback].forEach((el) => { if (el) { el.textContent = ""; el.className = "feedback"; } });
  }

  /* ------------------------------ silent backend sync (best-effort) ------------------------------ */

  async function syncTopologyChange(payload) {
    if (!payload || typeof payload !== "object") return;
    if (payload.type === "node") {
      const cat = CITY_LIBRARY[normalizeId(payload.node)] || {};
      await safeFetchJson("/api/topology/node", { method: "POST", body: JSON.stringify({ id: payload.node, label: cat.label || prettyLabel(payload.node), kmsId: cat.kmsId, action: payload.action || "upsert" }) });
    } else if (payload.type === "link") {
      await safeFetchJson("/api/topology/link", { method: "POST", body: JSON.stringify(payload) });
    } else if (payload.type === "reset") {
      await safeFetchJson("/api/topology/reset", { method: "POST", body: "{}" });
    }
  }

  async function syncBackendProvision(request, response) {
    void response;
    await safeFetchJson("/api/provision", {
      method: "POST",
      body: JSON.stringify({
        request_id: request.request_id,
        source: endpointLabel(request.source),
        destination: endpointLabel(request.destination),
        service_type: request.service_type,
        key_size: request.key_size,
        num_keys: request.number_of_keys,
        priority: "normal",
      }),
    });
  }

  /* ------------------------------ presentation & payload view ------------------------------ */

  function togglePresentationMode() {
    const on = document.body.classList.toggle("presentation");
    ui.presentationToggle.setAttribute("aria-pressed", on ? "true" : "false");
    ui.presentationToggle.querySelector(".mode-label").textContent = on ? "Vista standard" : "Modalità Presentazione";
    if (on && ui.advanced) ui.advanced.open = false;
    addEvent("system", on ? "Modalità Presentazione attivata." : "Modalità standard ripristinata.");
  }

  function setPayloadView(view) {
    state.payloadView = view === "full" ? "full" : "compact";
    document.querySelectorAll("[data-payload-view]").forEach((btn) => {
      btn.classList.toggle("active", btn.getAttribute("data-payload-view") === state.payloadView);
    });
    renderPayloads();
  }

  /* ------------------------------ stage helpers ------------------------------ */

  function resetStages() { state.stageStatus = Object.fromEntries(STAGES.map((s) => [s.id, "idle"])); }
  function setStage(id, status) { state.stageStatus[id] = status; archFromStage(id, status); renderPipeline(); }
  function completeStage(id, ms) { state.stageStatus[id] = "completed"; state.stageTimes[id] = ms; archFromStage(id, "completed"); renderPipeline(); }
  function animStep(token) { renderAll(); return delay(STAGE_ANIM_MS).then(() => isJobCurrent(token)); }

  function refreshControlsAfterTopologyChange() {
    populateCitySelects();
    populateTopologySelects();
    populateRequestSelects();
    syncSelectAvailability();
    renderKpis();
  }

  /* ------------------------------ events ------------------------------ */

  function addEvent(category, message, level = "info") {
    void level;
    state.logs.push({ time: formatClock(new Date()), category, message });
    if (state.logs.length > 90) state.logs = state.logs.slice(-90);
    renderEventLog();
  }

  /* ------------------------------ graph helpers ------------------------------ */

  function buildAdjacency() {
    const adjacency = new Map();
    state.topology.nodes.forEach((n) => adjacency.set(n.id, []));
    state.topology.links.forEach((link) => {
      if (!getNode(link.source) || !getNode(link.target)) return;
      if (!adjacency.has(link.source)) adjacency.set(link.source, []);
      if (!adjacency.has(link.target)) adjacency.set(link.target, []);
      adjacency.get(link.source).push({ next: link.target, cost: Number(link.cost) || 1, status: link.status });
      adjacency.get(link.target).push({ next: link.source, cost: Number(link.cost) || 1, status: link.status });
    });
    return adjacency;
  }

  function calculateCost(pathIds) {
    let total = 0;
    for (let i = 0; i < pathIds.length - 1; i += 1) total += Number(getLink(pathIds[i], pathIds[i + 1])?.cost || 1);
    return total;
  }

  function getLink(source, target) {
    return state.topology.links.find((l) => edgeKey(l.source, l.target) === edgeKey(source, target));
  }

  function edgeKey(a, b) { return [normalizeId(a), normalizeId(b)].sort().join("~"); }
  function getNode(id) { return state.topology.nodes.find((n) => n.id === normalizeId(id)); }
  function hasNode(id) { return state.topology.nodes.some((n) => n.id === id); }

  function canTraverseNode(node, isIntermediate) {
    if (!node || node.status === "inactive") return false;
    if (node.pool <= 0) return false;
    if (isIntermediate && node.pool <= 10) return false;
    return true;
  }

  function computeKeyBudget(request) {
    return Math.max(6, Math.round((Number(request.key_size) || 256) / 128) * Math.max(1, Number(request.number_of_keys) || 1) * 4);
  }

  function computeLinkLatency(link) {
    const base = Math.round(Number(link.cost) * 11);
    const jitter = (hashCode(edgeKey(link.source, link.target)) % 7) + 4;
    return base + jitter;
  }

  function computeLinkAvailability(link, source, target) {
    return clamp(Math.round((source.pool + target.pool) / 2) + (link.status === "up" ? 0 : -12), 0, 100);
  }

  function computeNodeStatus(node) {
    if (!node || node.status === "inactive") return "inactive";
    if (node.pool <= 10) return "unavailable";
    if (node.pool <= 35) return "warning";
    return "active";
  }

  function normalizeNodeStatus(status, pool) {
    if (status === "inactive") return "inactive";
    if (pool <= 10) return "unavailable";
    if (pool <= 35) return "warning";
    return "active";
  }

  function nodeColor(status, isRelay) {
    if (status === "unavailable") return "rgba(79, 91, 117, 0.9)";
    if (status === "inactive") return "rgba(70, 84, 107, 0.8)";
    if (status === "warning") return "rgba(245, 184, 75, 0.92)";
    return isRelay ? "rgba(89, 166, 255, 0.95)" : "rgba(54, 211, 154, 0.95)";
  }

  function statusColor(status) {
    switch (status) {
      case "active": return "#37d67a";
      case "warning": return "#f2b84b";
      case "unavailable": return "#ff647c";
      default: return "#8ea3c4";
    }
  }

  function activeLinkCount() { return state.topology.links.filter((l) => l.status === "up").length; }

  function cityLabel(id) {
    return getNode(id)?.label || CITY_LIBRARY[normalizeId(id)]?.label || prettyLabel(id);
  }

  // Main KMS sites are surfaced to ONOS with a " KMS" suffix; relays keep the
  // bare city name. Path arrays always use the bare city label.
  function endpointLabel(id) {
    const node = getNode(id) || CITY_LIBRARY[normalizeId(id)];
    if (!node) return prettyLabel(id);
    return node.kind === "relay" ? node.label : `${node.label} KMS`;
  }

  /* ------------------------------ misc utils ------------------------------ */

  function failPlan(reason, onosResponse) {
    return { ok: false, reason, onosResponse, pathIds: [], pathLabels: [], kmsInvolved: [], totalCost: null, hops: 0 };
  }

  function normalizeId(value) { return String(value || "").trim().toLowerCase().replace(/\s+/g, "-"); }
  function prettyLabel(value) { return String(value || "").replace(/[-_]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()); }
  function formatClock(date) { return [date.getHours(), date.getMinutes(), date.getSeconds()].map((p) => String(p).padStart(2, "0")).join(":"); }
  function pad4(n) { return String(n).padStart(4, "0"); }
  function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }

  function hashCode(input) {
    let hash = 0;
    for (let i = 0; i < input.length; i += 1) { hash = ((hash << 5) - hash) + input.charCodeAt(i); hash |= 0; }
    return Math.abs(hash);
  }

  function escapeHtml(value) {
    return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function setFeedback(element, text, tone = "neutral") { if (element) { element.textContent = text; element.className = `feedback ${tone}`; } }
  function clearFeedback(element) { if (element) { element.textContent = ""; element.className = "feedback"; } }
  function isJobCurrent(token) { return token === state.jobId; }
  function delay(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

  async function safeFetchJson(path, options = {}) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), API_TIMEOUT_MS);
    try {
      const response = await fetch(path, {
        method: options.method || "GET",
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
        body: options.body,
        signal: controller.signal,
      });
      const raw = await response.text();
      let data = {};
      if (raw) { try { data = JSON.parse(raw); } catch { data = { raw }; } }
      return { ok: response.ok, status: response.status, data };
    } catch (error) {
      return { ok: false, status: 0, error };
    } finally {
      window.clearTimeout(timeout);
    }
  }
})();
