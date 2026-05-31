const API_BASE = ""

// ── Phase config ────────────────────────────────────────────────────
const PHASE_CONFIG = {
    EL_NINO: {
        bodyClass: "el-nino",
        label: "El Niño",
        desc: "Aquecimento anormal do Pacífico Equatorial — impactos climáticos em diversas regiões."
    },
    LA_NINA: {
        bodyClass: "la-nina",
        label: "La Niña",
        desc: "Resfriamento anormal do Pacífico Equatorial — padrões climáticos opostos ao El Niño."
    },
    NEUTRO: {
        bodyClass: "neutral",
        label: "Neutro",
        desc: "Condições dentro da variabilidade normal. Sem evento ENSO ativo."
    }
}

// ── Errors ──────────────────────────────────────────────────────────
const errors = new Set()

function registrarErro(componente) {
    errors.add(componente)
    const bar = document.getElementById("erro")
    bar.textContent = `Erro ao carregar: ${[...errors].join(", ")}`
    bar.classList.remove("hidden")
}

// ── ONI bar ─────────────────────────────────────────────────────────
function atualizarBarraONI(oni) {
    const fill = document.getElementById("oni-bar-fill")
    if (!fill) return
    const pct = Math.min(Math.abs(oni) / 2.5, 1) * 50
    if (oni >= 0) {
        fill.style.left = "50%"
        fill.style.marginLeft = "0"
        fill.style.width = pct + "%"
    } else {
        fill.style.left = (50 - pct) + "%"
        fill.style.marginLeft = "0"
        fill.style.width = pct + "%"
    }
}

// ── Status ───────────────────────────────────────────────────────────
async function carregarStatus() {
    try {
        const res = await fetch(`${API_BASE}/climate/status`)
        if (!res.ok) throw new Error(res.status)
        const d = await res.json()

        const cfg = PHASE_CONFIG[d.classificacao] || PHASE_CONFIG.NEUTRO

        // Dynamic theme
        document.body.className = cfg.bodyClass

        // Phase pill
        document.getElementById("phase-label").textContent = cfg.label

        // Hero value
        document.getElementById("oni").textContent = d.oni.toFixed(2)
        atualizarBarraONI(d.oni)

        // Phase card
        document.getElementById("status").textContent = d.classificacao.replace("_", " ")
        document.getElementById("fase").textContent = cfg.label
        document.getElementById("phase-desc").textContent = cfg.desc

        // Niño 3.4
        document.getElementById("nino34").textContent = d.nino34.toFixed(2)

    } catch {
        registrarErro("status")
        document.getElementById("oni").textContent = "—"
        document.getElementById("status").textContent = "—"
        document.getElementById("nino34").textContent = "—"
    }
}

// ── SOI ──────────────────────────────────────────────────────────────
async function carregarSOI() {
    try {
        const res = await fetch(`${API_BASE}/climate/soi`)
        if (!res.ok) throw new Error(res.status)
        const d = await res.json()
        const faseTexts = { EL_NINO: "Sinal El Niño", LA_NINA: "Sinal La Niña", NEUTRO: "Neutro" }
        document.getElementById("soi-value").textContent = d.soi.toFixed(2)
        document.getElementById("soi-fase").textContent = faseTexts[d.classificacao] || d.classificacao
    } catch {
        registrarErro("SOI")
        document.getElementById("soi-value").textContent = "—"
        document.getElementById("soi-fase").textContent = "—"
    }
}

// ── History ──────────────────────────────────────────────────────────
async function carregarHistorico() {
    try {
        const [resONI, resSOI] = await Promise.all([
            fetch(`${API_BASE}/climate/history`),
            fetch(`${API_BASE}/climate/soi/history`).catch(() => null)
        ])
        if (!resONI.ok) throw new Error(resONI.status)
        const dadosONI = await resONI.json()
        const dadosSOI = resSOI?.ok ? await resSOI.json() : []
        montarGrafico(dadosONI, dadosSOI)
    } catch {
        registrarErro("histórico ONI")
    }
}

// ── Analysis ─────────────────────────────────────────────────────────
function renderInsight(text) {
    return text
        .replace(/^#+\s*/gm, "")                        // remove headings (#, ##, ...)
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>") // **bold**
        .replace(/\*(.*?)\*/g, "<em>$1</em>")            // *italic*
        .trim()
}

async function carregarInsight() {
    try {
        const res = await fetch(`${API_BASE}/climate/analysis`)
        if (!res.ok) throw new Error(res.status)
        const d = await res.json()
        document.getElementById("analysis").innerHTML = renderInsight(d.analysis)
    } catch {
        registrarErro("análise")
        document.getElementById("analysis").textContent = "Não foi possível carregar a análise."
    }
}

// ── Trend ────────────────────────────────────────────────────────────
async function carregarTendencia() {
    try {
        const res = await fetch(`${API_BASE}/climate/trend`)
        if (!res.ok) throw new Error(res.status)
        const d = await res.json()

        const arrows = { SUBINDO: "↑", CAINDO: "↓", ESTAVEL: "→" }
        const arrow = arrows[d.tendencia] || "→"

        document.getElementById("tendencia").textContent = `${arrow} ${d.tendencia}`
        document.getElementById("variacao").textContent = `Δ ${d.variacao >= 0 ? "+" : ""}${d.variacao.toFixed(2)}`

    } catch {
        registrarErro("tendência")
        document.getElementById("tendencia").textContent = "—"
        document.getElementById("variacao").textContent = "—"
    }
}

// ── Update ───────────────────────────────────────────────────────────
async function carregarAtualizacao() {
    try {
        const res = await fetch(`${API_BASE}/climate/update`)
        if (!res.ok) throw new Error(res.status)
        const d = await res.json()
        document.getElementById("ultimaAtualizacao").textContent = d.ultima_atualizacao || "—"
        document.getElementById("fonte").textContent = d.fonte
    } catch {
        registrarErro("atualização NOAA")
        document.getElementById("ultimaAtualizacao").textContent = "—"
    }
}

async function carregarFreshness() {
    try {
        const res = await fetch(`${API_BASE}/climate/freshness`)
        if (!res.ok) return
        const d = await res.json()
        const el = document.getElementById("brand-freshness")
        if (el && d.ultima_coleta && d.ultima_coleta !== "—") {
            el.textContent = `Última atualização: ${d.ultima_coleta}`
        }
    } catch { /* silencioso — não é crítico */ }
}

// ── Modulation Indices ───────────────────────────────────────────────
async function carregarPDO() {
    try {
        const res = await fetch(`${API_BASE}/climate/pdo`)
        if (!res.ok) throw new Error(res.status)
        const d = await res.json()
        document.getElementById("pdo-value").textContent = d.value.toFixed(2)
        document.getElementById("pdo-fase").textContent = d.fase
    } catch {
        document.getElementById("pdo-value").textContent = "—"
        document.getElementById("pdo-fase").textContent = "sem dados"
    }
}

async function carregarNAO() {
    try {
        const res = await fetch(`${API_BASE}/climate/nao`)
        if (!res.ok) throw new Error(res.status)
        const d = await res.json()
        document.getElementById("nao-value").textContent = d.value.toFixed(2)
        document.getElementById("nao-fase").textContent = d.fase
    } catch {
        document.getElementById("nao-value").textContent = "—"
        document.getElementById("nao-fase").textContent = "sem dados"
    }
}

async function carregarAMO() {
    try {
        const res = await fetch(`${API_BASE}/climate/amo`)
        if (!res.ok) throw new Error(res.status)
        const d = await res.json()
        document.getElementById("amo-value").textContent = d.value.toFixed(4)
        document.getElementById("amo-fase").textContent = d.fase
    } catch {
        document.getElementById("amo-value").textContent = "—"
        document.getElementById("amo-fase").textContent = "sem dados"
    }
}

async function carregarQBO() {
    try {
        const res = await fetch(`${API_BASE}/climate/qbo`)
        if (!res.ok) throw new Error(res.status)
        const d = await res.json()
        document.getElementById("qbo-value").textContent = `${d.value.toFixed(1)} m/s`
        document.getElementById("qbo-fase").textContent = d.fase
    } catch {
        document.getElementById("qbo-value").textContent = "—"
        document.getElementById("qbo-fase").textContent = "sem dados"
    }
}

async function carregarIOD() {
    try {
        const res = await fetch(`${API_BASE}/climate/iod`)
        if (!res.ok) throw new Error(res.status)
        const d = await res.json()
        document.getElementById("iod-value").textContent = `${d.dmi >= 0 ? '+' : ''}${d.dmi.toFixed(4)}`
        document.getElementById("iod-fase").textContent = d.classificacao
        document.getElementById("iod-date").textContent = d.data_referencia || ""
    } catch {
        document.getElementById("iod-value").textContent = "—"
        document.getElementById("iod-fase").textContent = "sem dados"
        document.getElementById("iod-date").textContent = ""
    }
}

// ── Alert Ticker ─────────────────────────────────────────────────────
async function carregarAlertas() {
    try {
        const res = await fetch(`${API_BASE}/api/climate/alerts`)
        if (!res.ok) throw new Error(res.status)
        const d = await res.json()
        renderizarTicker(d.items)
    } catch {
        registrarErro("alertas")
        const track = document.getElementById("ticker-track")
        if (track) track.innerHTML = '<span class="ticker-skeleton">Erro ao carregar alertas.</span>'
    }
}

function renderizarTicker(alertas) {
    const track = document.getElementById("ticker-track")
    if (!track) return

    if (!alertas || alertas.length === 0) {
        track.innerHTML = '<span class="ticker-skeleton">Nenhum alerta operacional ativo.</span>'
        track.style.animation = "none"
        return
    }

    // Build one set of items, then duplicate for seamless loop
    function buildItems() {
        return alertas.map(a => {
            const cls = a.severity.toLowerCase()
            return `<span class="ticker-item ${cls}"><span class="ticker-severity">${a.severity}</span>${a.title} — ${a.message}</span><span class="ticker-sep">|</span>`
        }).join("")
    }

    const set = buildItems()
    track.innerHTML = set + set  // duplicate for seamless wrap
}

// ── Chart ────────────────────────────────────────────────────────────
function montarGrafico(dados, dadosSOI = []) {
    const ctx = document.getElementById("oniChart")
    if (!ctx) return

    const labels = dados.map(x => x.periodo)
    const valores = dados.map(x => x.oni)

    const soiMap = Object.fromEntries(dadosSOI.map(x => [x.periodo, x.soi]))
    const soiValores = labels.map(l => soiMap[l] ?? null)

    const gradient = ctx.getContext("2d").createLinearGradient(0, 0, 0, 280)
    gradient.addColorStop(0,   "rgba(94,200,248,.25)")
    gradient.addColorStop(0.6, "rgba(94,200,248,.05)")
    gradient.addColorStop(1,   "rgba(94,200,248,0)")

    if (window._oniChart) window._oniChart.destroy()
    window._oniChart = new Chart(ctx, {
        type: "line",
        data: {
            labels,
            datasets: [
                {
                    label: "ONI",
                    data: valores,
                    borderColor: "#5EC8F8",
                    borderWidth: 2.5,
                    backgroundColor: gradient,
                    fill: true,
                    tension: .35,
                    pointRadius: valores.map(v => (Math.abs(v) >= 0.5 ? 5 : 3)),
                    pointHoverRadius: 7,
                    pointBackgroundColor: valores.map(v =>
                        v >= 1.5  ? "#FF5252" :
                        v >= 0.5  ? "#FF7043" :
                        v <= -1.5 ? "#1E88E5" :
                        v <= -0.5 ? "#42A5F5" :
                                    "#78909C"
                    ),
                    pointBorderColor: "transparent",
                    pointBorderWidth: 0,
                },
                {
                    label: "El Niño +0.5",
                    data: labels.map(() => 0.5),
                    borderDash: [4, 4],
                    borderColor: "rgba(255,112,67,.5)",
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: false,
                },
                {
                    label: "La Niña −0.5",
                    data: labels.map(() => -0.5),
                    borderDash: [4, 4],
                    borderColor: "rgba(66,165,245,.5)",
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: false,
                },
                {
                    label: "El Niño forte +1.5",
                    data: labels.map(() => 1.5),
                    borderDash: [2, 6],
                    borderColor: "rgba(255,82,82,.35)",
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: false,
                },
                {
                    label: "La Niña forte −1.5",
                    data: labels.map(() => -1.5),
                    borderDash: [2, 6],
                    borderColor: "rgba(30,136,229,.35)",
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: false,
                },
                {
                    label: "SOI",
                    data: soiValores,
                    borderColor: "#AB47BC",
                    borderWidth: 2,
                    borderDash: [6, 3],
                    backgroundColor: "transparent",
                    fill: false,
                    tension: .35,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    spanGaps: false,
                },
                {
                    label: "SOI +1.0",
                    data: labels.map(() => 1.0),
                    borderDash: [3, 5],
                    borderColor: "rgba(171,71,188,.3)",
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: false,
                },
                {
                    label: "SOI −1.0",
                    data: labels.map(() => -1.0),
                    borderDash: [3, 5],
                    borderColor: "rgba(171,71,188,.3)",
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: false,
                },
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: "index" },
            plugins: {
                legend: {
                    position: "bottom",
                    labels: {
                        color: "#546A84",
                        boxWidth: 20,
                        boxHeight: 2,
                        font: { size: 11 },
                        filter: item => item.text === "ONI" || item.text === "SOI",
                    }
                },
                tooltip: {
                    backgroundColor: "#0E1E30",
                    borderColor: "rgba(255,255,255,.1)",
                    borderWidth: 1,
                    titleColor: "#E8EEF5",
                    bodyColor: "#8EA2BE",
                    padding: 12,
                    callbacks: {
                        label: ctx => {
                            if (ctx.dataset.label === "ONI") return ` ONI: ${ctx.parsed.y.toFixed(2)}`
                            if (ctx.dataset.label === "SOI" && ctx.parsed.y !== null) return ` SOI: ${ctx.parsed.y.toFixed(2)}`
                            return null
                        },
                        afterLabel: ctx => {
                            if (ctx.dataset.label !== "ONI") return null
                            const v = ctx.parsed.y
                            return v >= 1.5  ? " ⚠ El Niño forte"
                                 : v >= 0.5  ? " El Niño"
                                 : v <= -1.5 ? " ⚠ La Niña forte"
                                 : v <= -0.5 ? " La Niña"
                                 : " Neutro"
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid:   { color: "rgba(255,255,255,.04)" },
                    ticks:  { color: "#546A84", font: { size: 11 }, maxRotation: 0,
                              callback: (_, i) => i % 3 === 0 ? labels[i] : "" }
                },
                y: {
                    grid:   { color: "rgba(255,255,255,.05)" },
                    ticks:  { color: "#546A84", font: { size: 11 },
                              callback: v => v.toFixed(1) },
                    border: { dash: [4, 4] }
                }
            }
        }
    })
}

// ── MJO ──────────────────────────────────────────────────────────────
const MJO_PHASE_DESC = {
    1: "África/Índico O.",
    2: "Índico Oeste",
    3: "Índico Leste",
    4: "Cont. Marítimo",
    5: "Pacífico Oeste",
    6: "Pacífico Central",
    7: "Pacífico Leste",
    8: "Hemis. Ocidental"
}

async function carregarMJO() {
    try {
        const res = await fetch(`${API_BASE}/climate/mjo`)
        if (!res.ok) throw new Error(res.status)
        const d = await res.json()
        const phaseDesc = MJO_PHASE_DESC[d.phase] || `Fase ${d.phase}`
        document.getElementById("mjo-phase").textContent = `Fase ${d.phase}`
        document.getElementById("mjo-amplitude").textContent = `Amp. ${d.amplitude.toFixed(2)}`
        document.getElementById("mjo-fase").textContent = phaseDesc
        document.getElementById("mjo-date").textContent = d.data_referencia || ""
    } catch {
        document.getElementById("mjo-phase").textContent = "—"
        document.getElementById("mjo-amplitude").textContent = "sem dados"
        document.getElementById("mjo-fase").textContent = ""
        document.getElementById("mjo-date").textContent = ""
    }
}

// ── CO₂ ──────────────────────────────────────────────────────────────
async function carregarCO2() {
    try {
        const res = await fetch(`${API_BASE}/climate/co2`)
        if (!res.ok) throw new Error(res.status)
        const d = await res.json()
        document.getElementById("co2-value").textContent = `${d.co2_ppm.toFixed(2)} ppm`
        document.getElementById("co2-date").textContent = d.data_referencia
    } catch {
        document.getElementById("co2-value").textContent = "—"
        document.getElementById("co2-date").textContent = "sem dados"
    }
}

// ── Sea Ice ───────────────────────────────────────────────────────────
async function carregarGeloArtico() {
    try {
        const res = await fetch(`${API_BASE}/climate/arctic_ice`)
        if (!res.ok) throw new Error(res.status)
        const d = await res.json()
        document.getElementById("arctic-value").textContent = `${d.extent_mkm2.toFixed(3)} Mkm²`
        document.getElementById("arctic-date").textContent = d.data_referencia
    } catch {
        document.getElementById("arctic-value").textContent = "—"
        document.getElementById("arctic-date").textContent = "sem dados"
    }
}

async function carregarGeloAntartico() {
    try {
        const res = await fetch(`${API_BASE}/climate/antarctic_ice`)
        if (!res.ok) throw new Error(res.status)
        const d = await res.json()
        document.getElementById("antarctic-value").textContent = `${d.extent_mkm2.toFixed(3)} Mkm²`
        document.getElementById("antarctic-date").textContent = d.data_referencia
    } catch {
        document.getElementById("antarctic-value").textContent = "—"
        document.getElementById("antarctic-date").textContent = "sem dados"
    }
}

// ── Prediction ────────────────────────────────────────────────────────
// ── Zhora Conversacional ─────────────────────────────────────────────
// ── Home / Início ────────────────────────────────────────────────────
const _track = (event, data) => { try { if (typeof umami !== "undefined") umami.track(event, data) } catch {} }

function irParaAba(tab) {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"))
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"))
    const btn = document.querySelector(`[data-tab="${tab}"]`)
    if (btn) btn.classList.add("active")
    const panel = document.getElementById(`tab-${tab}`)
    if (panel) panel.classList.add("active")
    _track("tab_view", { tab })
    // lazy-load modulation charts if needed
    if (tab === "modulacao" && !_modulacaoLoaded) {
        _modulacaoLoaded = true
        montarGraficosPDO(); montarGraficosNAO(); montarGraficosAMO()
        montarGraficosQBO(); montarGraficosIOD()
    }
    setTimeout(() => {
        ;(_CHART_KEYS[tab] || []).forEach(k => { if (window[k]) window[k].resize() })
    }, 50)
}

async function carregarHome() {
    const FASE = { EL_NINO: "El Niño ativo", LA_NINA: "La Niña ativa", NEUTRO: "Fase Neutra" }
    const COR  = { EL_NINO: "var(--warning)", LA_NINA: "var(--info)", NEUTRO: "var(--accent)" }

    // Busca em paralelo: status + insight_plain + iod + mjo + co2 + prediction
    const [rStatus, rPlain, rIod, rMjo, rCo2, rPred] = await Promise.allSettled([
        fetch(`${API_BASE}/climate/status`),
        fetch(`${API_BASE}/climate/insight_plain`),
        fetch(`${API_BASE}/climate/iod`),
        fetch(`${API_BASE}/climate/mjo`),
        fetch(`${API_BASE}/climate/co2`),
        fetch(`${API_BASE}/climate/plain`),
    ])

    const j = async r => r.status === "fulfilled" && r.value.ok ? r.value.json() : null
    const [status, plain, iod, mjo, co2, pred] = await Promise.all([
        j(rStatus), j(rPlain), j(rIod), j(rMjo), j(rCo2), j(rPred)
    ])

    // Estado atual (hero)
    if (status) {
        const el = document.getElementById("home-status")
        el.textContent = FASE[status.classificacao] || status.classificacao
        el.style.color = COR[status.classificacao] || "var(--accent)"
    }
    if (plain) {
        document.getElementById("home-status-plain").textContent = plain.plain
    }

    // Badge ENSO
    if (status) {
        document.getElementById("home-oni-badge").textContent =
            `ONI ${status.oni >= 0 ? "+" : ""}${status.oni?.toFixed(2)} · ${FASE[status.classificacao] || status.classificacao}`
    }

    // Badge Modulação (usa IOD como destaque)
    if (iod) {
        const iodDesc = iod.classificacao === "POSITIVO" ? "IOD Positivo" :
                        iod.classificacao === "NEGATIVO" ? "IOD Negativo" : "IOD Neutro"
        document.getElementById("home-mod-badge").textContent = `${iodDesc} · PDO/NAO/AMO/QBO ativos`
    }

    // Badge Diários (MJO + CO₂)
    if (mjo && co2) {
        const mjoDesc = mjo.amplitude >= 1.0 ? `MJO Fase ${mjo.phase} ativo` : "MJO inativo"
        document.getElementById("home-daily-badge").textContent =
            `${mjoDesc} · CO₂ ${co2.co2_ppm?.toFixed(1)} ppm`
    } else if (co2) {
        document.getElementById("home-daily-badge").textContent = `CO₂ ${co2.co2_ppm?.toFixed(1)} ppm`
    }

    // Badge Análise preditiva
    if (pred) {
        const snippet = pred.plain.split(".")[0] + "."
        document.getElementById("home-pred-badge").textContent =
            snippet.length > 80 ? snippet.slice(0, 80) + "…" : snippet
    }
}

function abrirZhora() {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"))
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"))
    const btn = document.querySelector("[data-tab='zhora']")
    if (btn) btn.classList.add("active")
    const panel = document.getElementById("tab-zhora")
    if (panel) panel.classList.add("active")
    setTimeout(() => document.getElementById("zhora-input")?.focus(), 100)
}

function abrirZhoraComPergunta() {
    abrirZhora()
    _track("regional_cta_click")
    setTimeout(() => {
        const input = document.getElementById("zhora-input")
        if (input && !input.value) {
            input.value = "Como o clima atual vai impactar a agricultura na minha região nos próximos meses?"
            input.focus()
        }
    }, 150)
}

function preencherPergunta(btn) {
    const input = document.getElementById("zhora-input")
    input.value = btn.textContent
    input.focus()
    _track("zhora_chip", { text: btn.textContent.slice(0, 60) })
}

async function perguntarZhora() {
    const input  = document.getElementById("zhora-input")
    const btn    = document.getElementById("zhora-btn")
    const label  = document.getElementById("zhora-btn-label")
    const wrap   = document.getElementById("zhora-response-wrap")
    const resp   = document.getElementById("zhora-response")

    const question = input.value.trim()
    if (!question) return
    _track("zhora_question_sent")

    // Loading state
    btn.disabled  = true
    input.disabled = true
    label.textContent = "Pensando..."
    wrap.classList.remove("hidden")
    resp.innerHTML = `
        <div class="zhora-thinking">
            <div class="zhora-thinking-dots">
                <span></span><span></span><span></span>
            </div>
            Consultando os dados climáticos...
        </div>`

    try {
        const res = await fetch(`${API_BASE}/api/zhora/ask`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question })
        })
        if (!res.ok) throw new Error(res.status)
        const d = await res.json()
        resp.innerHTML = typeof marked !== "undefined"
            ? marked.parse(d.answer)
            : renderInsight(d.answer)
    } catch {
        resp.innerHTML = `<span style="color:var(--critical)">Não foi possível obter resposta. Tente novamente em alguns instantes.</span>`
    } finally {
        btn.disabled   = false
        input.disabled = false
        label.textContent = "Enviar"
        input.value    = ""
        input.focus()
    }
}

async function carregarPredicao() {
    try {
        const res = await fetch(`${API_BASE}/climate/prediction`)
        if (!res.ok) throw new Error(res.status)
        const d = await res.json()
        document.getElementById("prediction").innerHTML = renderInsight(d.prediction)
    } catch {
        document.getElementById("prediction").textContent = "Não foi possível carregar a análise preditiva."
    }
}

async function carregarPlain() {
    try {
        const res = await fetch(`${API_BASE}/climate/plain`)
        if (!res.ok) throw new Error(res.status)
        const d = await res.json()
        document.getElementById("plain-text").textContent = d.plain
    } catch {
        document.getElementById("plain-text").textContent = "Resumo não disponível ainda."
    }
}

async function carregarInsightPlain() {
    try {
        const res = await fetch(`${API_BASE}/climate/insight_plain`)
        if (!res.ok) throw new Error(res.status)
        const d = await res.json()
        document.getElementById("insight-plain-text").textContent = d.plain
    } catch {
        document.getElementById("insight-plain-text").textContent = "Resumo não disponível ainda."
    }
}

// ── Mapa Climático Global Animado ────────────────────────────────────
async function montarMapaClimatico() {
    const svgEl = document.getElementById("climateMap")
    if (!svgEl || typeof d3 === "undefined" || typeof topojson === "undefined") return

    // 1. Fetch data in parallel
    const [rOni, rArctic, rAntarctic, rIod, rMjo, rSst] = await Promise.allSettled([
        fetch(`${API_BASE}/climate/history`),
        fetch(`${API_BASE}/climate/arctic_ice/history`),
        fetch(`${API_BASE}/climate/antarctic_ice/history`),
        fetch(`${API_BASE}/climate/iod/history`),
        fetch(`${API_BASE}/climate/mjo`),
        fetch(`${API_BASE}/climate/sst/history`),
    ])
    const jj = async r => r.status === "fulfilled" && r.value.ok ? r.value.json() : []
    const [oniData, arcticData, antarcticData, iodData, mjoData, sstData] = await Promise.all([
        jj(rOni), jj(rArctic), jj(rAntarctic), jj(rIod), jj(rMjo), jj(rSst)
    ])
    if (!oniData.length) return

    // 2. Build monthly ice averages from daily data
    function monthlyAvg(daily) {
        const acc = {}
        daily.forEach(d => {
            const key = d.data_referencia.slice(0, 7)
            if (!acc[key]) acc[key] = []
            acc[key].push(d.extent_mkm2)
        })
        return Object.fromEntries(Object.entries(acc).map(([k, v]) => [k, v.reduce((a, b) => a + b, 0) / v.length]))
    }
    const arcticByMonth    = monthlyAvg(arcticData)
    const antarcticByMonth = monthlyAvg(antarcticData)
    const iodByMonth = Object.fromEntries((iodData||[]).map(d => [d.data_referencia?.slice(0,7), d.value]))
    const sstByMonth = Object.fromEntries((sstData||[]).map(d => [d.periodo, d]))

    // 3. Build 12-month dataset
    const frames = oniData.slice(-12).map(o => {
        const sst = sstByMonth[o.periodo] || {}
        return {
            period: o.periodo,
            oni: o.oni,
            classificacao: o.classificacao,
            arctic: arcticByMonth[o.periodo] ?? 11.0,
            antarctic: antarcticByMonth[o.periodo] ?? 10.0,
            iod: iodByMonth[o.periodo] ?? 0,
            nino12: sst.nino12 ?? o.oni,
            nino3:  sst.nino3  ?? o.oni,
            nino34: sst.nino34 ?? o.oni,
            nino4:  sst.nino4  ?? o.oni,
        }
    })

    // MJO phase → equatorial longitude center
    const MJO_LON = { 1: 55, 2: 75, 3: 95, 4: 115, 5: 140, 6: 165, 7: -160, 8: -100 }

    // 4. Extent → geo radius (spherical cap formula: area = 2πR²(1−sinφ))
    const R2 = 255.03  // 2πR² in Mkm²

    // 5. Color scales
    // Paleta mais vibrante e saturada
    const oniColor = d3.scaleLinear()
        .domain([-2, -1, -0.5, 0, 0.5, 1, 2])
        .range(["#00B0FF","#29B6F6","#B3E5FC","#90A4AE","#FF8A65","#FF3D00","#B71C1C"])
        .clamp(true)
    const iodColor = d3.scaleLinear()
        .domain([-1, 0, 1])
        .range(["#00E676","#546A84","#FFD740"])
        .clamp(true)

    // 6. Setup SVG
    const W = svgEl.parentElement.clientWidth || 800
    const H = Math.round(W * 0.52)
    svgEl.setAttribute("viewBox", `0 0 ${W} ${H}`)

    const projection = d3.geoNaturalEarth1()
        .scale(W / 6.28)
        .translate([W / 2, H / 2])
    const path = d3.geoPath().projection(projection)

    const svg = d3.select(svgEl)
    svg.selectAll("*").remove()

    // Sphere (ocean background)
    svg.append("path")
        .datum({type: "Sphere"})
        .attr("fill","#061020")
        .attr("d", path)

    // Graticule grid
    svg.append("path")
        .datum(d3.geoGraticule()())
        .attr("fill","none")
        .attr("stroke","rgba(255,255,255,.07)")
        .attr("stroke-width","0.5")
        .attr("d", path)

    // Gelo polar: gradiente radial com userSpaceOnUse centrado nos polos projetados
    const [, py_n] = projection([0, 88]) || [W/2, 8]
    const [, py_s] = projection([0,-88]) || [W/2, H-8]
    const [, py_70n] = projection([0, 70]) || [W/2, py_n + 60]
    const [, py_70s] = projection([0,-70]) || [W/2, py_s - 60]
    const iceNRef = Math.abs(py_70n - py_n)  // pixels de 70°N ao polo
    const iceSRef = Math.abs(py_70s - py_s)

    const defs = svg.append("defs")
    const gradN = defs.append("radialGradient")
        .attr("id","gradN").attr("gradientUnits","userSpaceOnUse")
        .attr("cx", W/2).attr("cy", py_n).attr("r", iceNRef)
    gradN.append("stop").attr("offset","0%").attr("stop-color","#FFFFFF").attr("stop-opacity","0.9")
    gradN.append("stop").attr("offset","55%").attr("stop-color","#B3E5FC").attr("stop-opacity","0.55")
    gradN.append("stop").attr("offset","100%").attr("stop-color","#4FC3F7").attr("stop-opacity","0")

    const gradS = defs.append("radialGradient")
        .attr("id","gradS").attr("gradientUnits","userSpaceOnUse")
        .attr("cx", W/2).attr("cy", py_s).attr("r", iceSRef)
    gradS.append("stop").attr("offset","0%").attr("stop-color","#FFFFFF").attr("stop-opacity","0.85")
    gradS.append("stop").attr("offset","55%").attr("stop-color","#B3E5FC").attr("stop-opacity","0.5")
    gradS.append("stop").attr("offset","100%").attr("stop-color","#4FC3F7").attr("stop-opacity","0")

    // Aplicado à esfera completa — países renderizados por cima naturalizam o efeito
    const iceN = svg.append("path").datum({type:"Sphere"}).attr("fill","url(#gradN)").attr("d", path)
    const iceS = svg.append("path").datum({type:"Sphere"}).attr("fill","url(#gradS)").attr("d", path)

    // 7. Load world topojson
    let world
    try {
        world = await d3.json("https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json")
    } catch { return }

    // Countries
    svg.append("g")
        .selectAll("path")
        .data(topojson.feature(world, world.objects.countries).features)
        .join("path")
        .attr("fill","#1e3348")
        .attr("stroke","#0d1f30")
        .attr("stroke-width","0.4")
        .attr("d", path)

    // 8. Regiões SST do Pacífico (4 faixas não sobrepostas, oeste → leste)
    const sst_regions = [
        // Niño 4: Pacífico oeste (cruza antimeridiano — dividido em 2 partes)
        { id: "nino4a", coords: [[[160,-5],[180,-5],[180,5],[160,5],[160,-5]]], label: "Niño 4",  llon: 170 },
        { id: "nino4b", coords: [[[-180,-5],[-150,-5],[-150,5],[-180,5],[-180,-5]]], label: null,    llon: null },
        // Niño 3.4: central
        { id: "nino34", coords: [[[-170,-5],[-120,-5],[-120,5],[-170,5],[-170,-5]]], label: "Niño 3.4", llon: -145 },
        // Niño 3: centro-leste
        { id: "nino3",  coords: [[[-120,-5],[-90,-5],[-90,5],[-120,5],[-120,-5]]],  label: "Niño 3",   llon: -105 },
        // Niño 1+2: extremo leste (0-10°S)
        { id: "nino12", coords: [[[-90,-10],[-80,-10],[-80,0],[-90,0],[-90,-10]]],   label: "1+2",      llon: -85  },
    ]

    const sstPaths = {}
    sst_regions.forEach(r => {
        sstPaths[r.id] = svg.append("path")
            .datum({ type: "Feature", geometry: { type: "Polygon", coordinates: r.coords }})
            .attr("class", "map-nino34")
            .attr("d", path)
        if (r.label && r.llon) {
            const [lx, ly] = projection([r.llon, 0]) || [0,0]
            svg.append("text")
                .attr("x", lx).attr("y", ly + 4)
                .attr("text-anchor", "middle")
                .attr("font-size", Math.max(7, W * 0.008))
                .attr("font-weight", "600")
                .attr("fill", "rgba(255,255,255,0.55)")
                .style("pointer-events", "none")
                .text(r.label)
        }
    })

    // 9. IOD region (Índico: 50-110°E, 10S-10N)
    // IOD: contorno do Oceano Índico (sem fill — evita polígono escuro sobre terra/mar)
    const iodGeo = {
        type: "Feature",
        geometry: {
            type: "Polygon",
            coordinates: [[[50,-8],[90,-8],[90,8],[50,8],[50,-8]]]
        }
    }
    const iodPath = svg.append("path")
        .datum(iodGeo)
        .attr("fill", "none")
        .attr("stroke-width", 1.5)
        .attr("stroke-dasharray", "4 3")
        .attr("d", path)


    // 11. MJO badge externo inline com ONI
    const mjoPhase = mjoData?.phase ?? null
    const mjoAmp   = mjoData?.amplitude ?? 0
    const MJO_DESC = {
        1: "África/Índico O.", 2: "Índico O.", 3: "Índico L.",
        4: "Cont. Marítimo",  5: "Pacífico O.", 6: "Pacífico C.",
        7: "Pacífico L.",     8: "Hemis. Ocidental"
    }
    const mjoFooter = document.getElementById("mapMjoBadge")
    const mjoSep    = document.getElementById("mapMjoSep")
    if (mjoFooter && mjoPhase) {
        const active = mjoAmp >= 1.0
        mjoFooter.innerHTML = `<span class="map-mjo-dot ${active ? "active" : ""}"></span> MJO F${mjoPhase} · ${MJO_DESC[mjoPhase] || ""}${active ? ` · ${mjoAmp.toFixed(2)}` : ""}`
        if (mjoSep) mjoSep.style.display = ""
    }

    // 12. Animation
    let frameIdx = 0
    let timer = null

    function renderFrame(i) {
        const f = frames[i]
        const color = oniColor(f.oni)
        const icolor = iodColor(f.iod ?? 0)

        // Colorir cada região SST com sua anomalia real
        sstPaths.nino4a?.attr("fill", oniColor(f.nino4))
        sstPaths.nino4b?.attr("fill", oniColor(f.nino4))
        sstPaths.nino34?.attr("fill", oniColor(f.nino34))
        sstPaths.nino3?.attr("fill",  oniColor(f.nino3))
        sstPaths.nino12?.attr("fill", oniColor(f.nino12))

        // IOD: contorno colorido (stroke only — sem fill para nao escurecer o mapa)
        iodPath.attr("stroke", icolor)


        // UI labels
        const [y, m] = f.period.split("-")
        const monthNames = ["","Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
        document.getElementById("mapMonthLabel").textContent = `${monthNames[+m]} ${y}`

        const oniSign = f.oni >= 0 ? "+" : ""
        const iodSign = f.iod >= 0 ? "+" : ""
        const stateMap = { EL_NINO: "El Niño", LA_NINA: "La Niña", NEUTRO: "Neutro" }

        // ONI badge
        document.getElementById("mapOniLabel").textContent =
            `${stateMap[f.classificacao] || f.classificacao} ONI ${oniSign}${f.oni.toFixed(2)}`

        // IOD badge — classifica por limiar ±0.4
        const iodClass = f.iod >= 0.4 ? "Positivo" : f.iod <= -0.4 ? "Negativo" : "Neutro"
        const iodEl = document.getElementById("mapIodLabel")
        if (iodEl) iodEl.textContent = `IOD ${iodSign}${f.iod.toFixed(2)} · ${iodClass}`

        // Timeline fill
        document.getElementById("mapTimelineFill").style.width =
            ((i + 1) / frames.length * 100).toFixed(1) + "%"
    }

    function nextFrame() {
        renderFrame(frameIdx)
        frameIdx = (frameIdx + 1) % frames.length
    }

    nextFrame()
    timer = setInterval(nextFrame, 1500)
    window._climateMapTimer = timer
}

// ── Wheeler-Hendon MJO Phase Diagram ────────────────────────────────
async function montarWheelerHendon() {
    const canvas = document.getElementById("whChart")
    if (!canvas) return
    try {
        const res = await fetch(`${API_BASE}/climate/mjo/history`)
        if (!res.ok) throw new Error(res.status)
        const dados = await res.json()
        if (!dados.length) return

        // Colours per classification
        const COR = {
            FAVORAVEL_LANINA: "#42A5F5",
            FAVORAVEL_ELNINO: "#FF7043",
            ATIVO:            "#FFA726",
            FRACO:            "#546A84",
        }

        // Phase wedge definitions: [startAngle, endAngle] in math-degrees
        // Phase N centre at math angle 90 + (N-1)*45
        const WEDGES = [
            { phase: 1, label: "1", cor: "rgba(66,165,245,.18)",  start: 67.5,  end: 112.5 },
            { phase: 2, label: "2", cor: "rgba(66,165,245,.12)",  start: 22.5,  end:  67.5 },
            { phase: 3, label: "3", cor: "rgba(66,165,245,.08)",  start: -22.5, end:  22.5 },
            { phase: 4, label: "4", cor: "rgba(120,144,156,.07)", start: -67.5, end: -22.5 },
            { phase: 5, label: "5", cor: "rgba(255,112,67,.08)",  start: -112.5,end: -67.5 },
            { phase: 6, label: "6", cor: "rgba(255,112,67,.12)",  start: -157.5,end: -112.5},
            { phase: 7, label: "7", cor: "rgba(255,112,67,.18)",  start:  157.5,end:  202.5},
            { phase: 8, label: "8", cor: "rgba(120,144,156,.07)", start:  112.5,end:  157.5},
        ]

        const bgPlugin = {
            id: "whBackground",
            beforeDraw(chart) {
                if (!chart.chartArea || !chart.scales?.x) return
                const { ctx, chartArea: ca } = chart
                const cx = (ca.left + ca.right) / 2
                const cy = (ca.top  + ca.bottom) / 2
                const rOuter = Math.min(ca.width, ca.height) / 2
                const toCanvas = deg => (360 - deg) * Math.PI / 180

                // Draw phase wedges
                WEDGES.forEach(w => {
                    ctx.beginPath()
                    ctx.moveTo(cx, cy)
                    ctx.arc(cx, cy, rOuter, toCanvas(w.end), toCanvas(w.start), false)
                    ctx.closePath()
                    ctx.fillStyle = w.cor
                    ctx.fill()

                    // Phase number label at 75% radius
                    const mid = (w.start + w.end) / 2
                    const rad = mid * Math.PI / 180
                    const lx  = cx + rOuter * 0.75 * Math.cos(rad)
                    const ly  = cy - rOuter * 0.75 * Math.sin(rad)
                    ctx.fillStyle = "rgba(200,215,230,.55)"
                    ctx.font = `bold ${Math.max(10, rOuter * 0.07)}px Inter,sans-serif`
                    ctx.textAlign = "center"
                    ctx.textBaseline = "middle"
                    ctx.fillText(w.label, lx, ly)
                })

                // Amplitude = 1.0 unit circle (dashed)
                const scaleMax = chart.scales.x.max || maxAmp
                const rUnit = rOuter / scaleMax
                ctx.beginPath()
                ctx.arc(cx, cy, rUnit, 0, 2 * Math.PI)
                ctx.strokeStyle = "rgba(255,255,255,.25)"
                ctx.lineWidth = 1.5
                ctx.setLineDash([4, 4])
                ctx.stroke()
                ctx.setLineDash([])

                // Axes
                ctx.beginPath()
                ctx.moveTo(ca.left, cy)
                ctx.lineTo(ca.right, cy)
                ctx.moveTo(cx, ca.top)
                ctx.lineTo(cx, ca.bottom)
                ctx.strokeStyle = "rgba(255,255,255,.10)"
                ctx.lineWidth = 1
                ctx.stroke()
            }
        }

        // Build scatter points with trajectory line via showLine
        const n = dados.length
        const trajPoints = dados.map(d => ({ x: d.rmm1, y: d.rmm2 }))

        // Colour each scatter point
        const pColors = dados.map(d => COR[d.classificacao] || "#546A84")
        const pBorder = dados.map((_, i) => i === n - 1 ? "#FFFFFF" : "transparent")
        const pRadius = dados.map((_, i) => i === n - 1 ? 7 : 3.5)

        const maxAmp = Math.ceil(Math.max(...dados.map(d => d.amplitude), 2.5) * 1.15)

        if (window._whChart) window._whChart.destroy()
        window._whChart = new Chart(canvas, {
            type: "scatter",
            data: {
                datasets: [
                    {
                        label: "Trajetória",
                        data: trajPoints,
                        showLine: true,
                        borderColor: "rgba(180,210,240,.28)",
                        backgroundColor: "transparent",
                        borderWidth: 1.5,
                        pointRadius: pRadius,
                        pointHoverRadius: 6,
                        pointBackgroundColor: pColors,
                        pointBorderColor: pBorder,
                        pointBorderWidth: 2,
                        tension: 0.3,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                aspectRatio: 1,
                animation: { duration: 600 },
                scales: {
                    x: {
                        min: -maxAmp, max: maxAmp,
                        grid: { color: "rgba(255,255,255,.05)" },
                        ticks: { color: "#546A84", font: { size: 10 }, maxTicksLimit: 7 },
                        title: { display: true, text: "RMM1", color: "#546A84", font: { size: 11 } }
                    },
                    y: {
                        min: -maxAmp, max: maxAmp,
                        grid: { color: "rgba(255,255,255,.05)" },
                        ticks: { color: "#546A84", font: { size: 10 }, maxTicksLimit: 7 },
                        title: { display: true, text: "RMM2", color: "#546A84", font: { size: 11 } }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: ctx => {
                                const d = dados[ctx.dataIndex]
                                if (!d) return null
                                return [`${d.data_referencia}`, `RMM1: ${d.rmm1.toFixed(3)}  RMM2: ${d.rmm2.toFixed(3)}`, `Fase ${d.phase} · ${d.amplitude.toFixed(3)}`]
                            }
                        },
                        backgroundColor: "rgba(12,22,40,.92)",
                        borderColor: "rgba(255,255,255,.12)",
                        borderWidth: 1,
                        titleColor: "#E8EEF5",
                        bodyColor: "#8EA2BE",
                        padding: 10,
                    }
                }
            },
            plugins: [bgPlugin]
        })
    } catch {
        /* silently skip if no data yet */
    }
}

// ── CO₂ Keeling Curve ────────────────────────────────────────────────
async function montarCO2Chart() {
    const canvas = document.getElementById("co2Chart")
    if (!canvas) return
    try {
        const res = await fetch(`${API_BASE}/climate/co2/history`)
        if (!res.ok) throw new Error(res.status)
        const dados = await res.json()
        if (!dados.length) return

        const ctx2 = canvas.getContext("2d")
        const grad = ctx2.createLinearGradient(0, 0, 0, 280)
        grad.addColorStop(0, "rgba(255,167,38,.22)")
        grad.addColorStop(1, "rgba(255,167,38,.01)")

        // Tick every Jan or Jul for readability
        const labels = dados.map(d => d.data_referencia)
        const tickIdx = labels.reduce((acc, lbl, i) => {
            const m = lbl.slice(5, 7)
            if (m === "01" || m === "07") acc.push(i)
            return acc
        }, [])

        if (window._co2Chart) window._co2Chart.destroy()
        window._co2Chart = new Chart(canvas, {
            type: "line",
            data: {
                labels,
                datasets: [{
                    label: "CO₂ (ppm)",
                    data: dados.map(d => d.co2_ppm),
                    borderColor: "#FFA726",
                    backgroundColor: grad,
                    borderWidth: 1.5,
                    pointRadius: 0,
                    tension: 0.3,
                    fill: true,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 600 },
                scales: {
                    x: {
                        type: "category",
                        grid: { color: "rgba(255,255,255,.04)" },
                        ticks: {
                            color: "#546A84",
                            font: { size: 10 },
                            maxRotation: 0,
                            callback: (_, i) => tickIdx.includes(i) ? labels[i].slice(0, 7) : null,
                        }
                    },
                    y: {
                        grid: { color: "rgba(255,255,255,.05)" },
                        ticks: { color: "#546A84", font: { size: 10 } },
                        title: { display: true, text: "ppm", color: "#546A84", font: { size: 11 } }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: { label: ctx => `${ctx.parsed.y.toFixed(2)} ppm` },
                        backgroundColor: "rgba(12,22,40,.92)",
                        borderColor: "rgba(255,255,255,.12)",
                        borderWidth: 1,
                        titleColor: "#E8EEF5",
                        bodyColor: "#FFA726",
                        padding: 10,
                    }
                }
            }
        })
    } catch {
        /* silently skip if no data yet */
    }
}

// ── Polar Ice Extent (Arctic + Antarctic) ────────────────────────────
async function montarGeloChart() {
    const canvas = document.getElementById("iceChart")
    if (!canvas) return
    try {
        const [rA, rAn] = await Promise.all([
            fetch(`${API_BASE}/climate/arctic_ice/history`),
            fetch(`${API_BASE}/climate/antarctic_ice/history`),
        ])
        if (!rA.ok || !rAn.ok) throw new Error("ice fetch failed")
        const [dadosArtico, dadosAntartico] = await Promise.all([rA.json(), rAn.json()])
        if (!dadosArtico.length && !dadosAntartico.length) return

        // Merge all dates for a unified label axis
        const allDates = [...new Set([
            ...dadosArtico.map(d => d.data_referencia),
            ...dadosAntartico.map(d => d.data_referencia),
        ])].sort()

        const idxArtico    = Object.fromEntries(dadosArtico.map(d => [d.data_referencia, d.extent_mkm2]))
        const idxAntartico = Object.fromEntries(dadosAntartico.map(d => [d.data_referencia, d.extent_mkm2]))

        const tickIdx = allDates.reduce((acc, lbl, i) => {
            const m = lbl.slice(5, 7)
            if (m === "01" || m === "07") acc.push(i)
            return acc
        }, [])

        if (window._iceChart) window._iceChart.destroy()
        window._iceChart = new Chart(canvas, {
            type: "line",
            data: {
                labels: allDates,
                datasets: [
                    {
                        label: "Ártico",
                        data: allDates.map(d => idxArtico[d] ?? null),
                        borderColor: "#42A5F5",
                        backgroundColor: "rgba(66,165,245,.06)",
                        borderWidth: 1.8,
                        pointRadius: 0,
                        tension: 0.3,
                        fill: true,
                        spanGaps: true,
                    },
                    {
                        label: "Antártico",
                        data: allDates.map(d => idxAntartico[d] ?? null),
                        borderColor: "#4DB6AC",
                        backgroundColor: "rgba(77,182,172,.04)",
                        borderWidth: 1.8,
                        pointRadius: 0,
                        tension: 0.3,
                        fill: true,
                        spanGaps: true,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 600 },
                interaction: { mode: "index", intersect: false },
                scales: {
                    x: {
                        type: "category",
                        grid: { color: "rgba(255,255,255,.04)" },
                        ticks: {
                            color: "#546A84",
                            font: { size: 10 },
                            maxRotation: 0,
                            callback: (_, i) => tickIdx.includes(i) ? allDates[i].slice(0, 7) : null,
                        }
                    },
                    y: {
                        grid: { color: "rgba(255,255,255,.05)" },
                        ticks: { color: "#546A84", font: { size: 10 } },
                        title: { display: true, text: "Mkm²", color: "#546A84", font: { size: 11 } }
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        labels: { color: "#8EA2BE", font: { size: 11 }, boxWidth: 12, padding: 14 }
                    },
                    tooltip: {
                        callbacks: {
                            label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y?.toFixed(3) ?? "—"} Mkm²`
                        },
                        backgroundColor: "rgba(12,22,40,.92)",
                        borderColor: "rgba(255,255,255,.12)",
                        borderWidth: 1,
                        titleColor: "#E8EEF5",
                        bodyColor: "#8EA2BE",
                        padding: 10,
                    }
                }
            }
        })
    } catch {
        /* silently skip if no data yet */
    }
}

// ── Modulation index charts (PDO / NAO / AMO / QBO) ─────────────────
async function montarModulacaoChart(canvasId, endpoint, cor, label, unidade) {
    const canvas = document.getElementById(canvasId)
    if (!canvas) return
    try {
        const res = await fetch(`${API_BASE}${endpoint}`)
        if (!res.ok) throw new Error(res.status)
        const dados = await res.json()
        if (!dados.length) return

        const labels = dados.map(d => d.data_referencia)
        const values = dados.map(d => d.value)
        const bgColors = values.map(v => v >= 0
            ? cor.pos
            : cor.neg
        )
        const ctx2 = canvas.getContext("2d")
        const grad = ctx2.createLinearGradient(0, 0, 0, 280)
        grad.addColorStop(0, cor.gradTop)
        grad.addColorStop(1, cor.gradBot)

        const key = `_${canvasId}`
        if (window[key]) window[key].destroy()
        window[key] = new Chart(canvas, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    label,
                    data: values,
                    backgroundColor: bgColors,
                    borderWidth: 0,
                    borderRadius: 2,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 500 },
                scales: {
                    x: {
                        grid: { color: "rgba(255,255,255,.04)" },
                        ticks: {
                            color: "#546A84",
                            font: { size: 10 },
                            maxRotation: 0,
                            callback: (_, i) => {
                                const lbl = labels[i]
                                return (lbl && (lbl.endsWith("-01") || lbl.endsWith("-07"))) ? lbl.slice(0, 7) : null
                            }
                        }
                    },
                    y: {
                        grid: { color: "rgba(255,255,255,.05)" },
                        ticks: { color: "#546A84", font: { size: 10 } },
                        title: unidade ? { display: true, text: unidade, color: "#546A84", font: { size: 10 } } : undefined
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: { label: ctx => `${ctx.parsed.y.toFixed(2)}${unidade ? " " + unidade : ""}` },
                        backgroundColor: "rgba(12,22,40,.92)",
                        borderColor: "rgba(255,255,255,.12)",
                        borderWidth: 1,
                        titleColor: "#E8EEF5",
                        bodyColor: "#8EA2BE",
                        padding: 10,
                    }
                }
            }
        })
    } catch {
        /* silently skip if no data */
    }
}

const _MOD_COLORS = {
    pdo: { pos: "rgba(66,165,245,.75)",  neg: "rgba(239,83,80,.65)",  gradTop: "rgba(66,165,245,.2)",  gradBot: "transparent" },
    nao: { pos: "rgba(171,71,188,.75)",  neg: "rgba(38,198,218,.65)", gradTop: "rgba(171,71,188,.2)",  gradBot: "transparent" },
    amo: { pos: "rgba(255,112,67,.75)",  neg: "rgba(66,165,245,.65)", gradTop: "rgba(255,112,67,.2)",  gradBot: "transparent" },
    qbo: { pos: "rgba(38,198,218,.75)",  neg: "rgba(212,225,87,.65)", gradTop: "rgba(38,198,218,.2)",  gradBot: "transparent" },
    iod: { pos: "rgba(255,167,38,.75)",  neg: "rgba(66,165,245,.65)", gradTop: "rgba(255,167,38,.2)",  gradBot: "transparent" },
}

async function montarGraficosPDO()  { await montarModulacaoChart("pdoChart",  "/climate/pdo/history", _MOD_COLORS.pdo, "PDO", null) }
async function montarGraficosNAO()  { await montarModulacaoChart("naoChart",  "/climate/nao/history", _MOD_COLORS.nao, "NAO", null) }
async function montarGraficosAMO()  { await montarModulacaoChart("amoChart",  "/climate/amo/history", _MOD_COLORS.amo, "AMO", "°C") }
async function montarGraficosQBO()  { await montarModulacaoChart("qboChart",  "/climate/qbo/history", _MOD_COLORS.qbo, "QBO", "m/s") }
async function montarGraficosIOD()  { await montarModulacaoChart("iodChart",  "/climate/iod/history", _MOD_COLORS.iod, "DMI", null) }

// ── Tab switching ─────────────────────────────────────────────────────
const _CHART_KEYS = {
    inicio:    [],
    enso:      ["_oniChart"],
    modulacao: ["_pdoChart", "_naoChart", "_amoChart", "_qboChart", "_iodChart"],
    diarios:   ["_whChart", "_co2Chart", "_iceChart"],
    analise:   [],
    zhora:     [],
}

let _modulacaoLoaded = false

document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"))
        document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"))
        btn.classList.add("active")
        const tab = btn.dataset.tab
        document.getElementById("tab-" + tab).classList.add("active")
        _track("tab_view", { tab })
        try { if (typeof umami !== "undefined") umami.track({ url: "/" + tab, title: tab }) } catch {}

        // Lazy-load modulation charts on first visit
        if (tab === "modulacao" && !_modulacaoLoaded) {
            _modulacaoLoaded = true
            montarGraficosPDO()
            montarGraficosNAO()
            montarGraficosAMO()
            montarGraficosQBO()
            montarGraficosIOD()
        }

        // Resize charts so they fill the now-visible canvas
        setTimeout(() => {
            ;(_CHART_KEYS[tab] || []).forEach(k => { if (window[k]) window[k].resize() })
        }, 50)
    })
})

// ── Init ─────────────────────────────────────────────────────────────
carregarHome()
carregarFreshness()
montarMapaClimatico()
carregarStatus()
carregarHistorico()
carregarSOI()
carregarInsight()
carregarInsightPlain()
carregarTendencia()
carregarAtualizacao()
carregarAlertas()
carregarPDO()
carregarNAO()
carregarAMO()
carregarQBO()
carregarIOD()
carregarMJO()
carregarCO2()
carregarGeloArtico()
carregarGeloAntartico()
carregarPredicao()
carregarPlain()
montarWheelerHendon()
montarCO2Chart()
montarGeloChart()
