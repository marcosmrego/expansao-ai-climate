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
    const [rOni, rArctic, rAntarctic, rIod, rMjo, rMjoH,
           rPdoH, rNaoH, rAmoH, rQboH, rSeismic, rWeekly] = await Promise.allSettled([
        fetch(`${API_BASE}/climate/history`),
        fetch(`${API_BASE}/climate/arctic_ice/history`),
        fetch(`${API_BASE}/climate/antarctic_ice/history`),
        fetch(`${API_BASE}/climate/iod/history`),
        fetch(`${API_BASE}/climate/mjo`),
        fetch(`${API_BASE}/climate/mjo/history`),
        fetch(`${API_BASE}/climate/pdo/history`),
        fetch(`${API_BASE}/climate/nao/history`),
        fetch(`${API_BASE}/climate/amo/history`),
        fetch(`${API_BASE}/climate/qbo/history`),
        fetch(`${API_BASE}/climate/seismic?days=${new Date().getDate() + 1}&min_mag=5.5`),
        fetch(`${API_BASE}/climate/nino34/weekly`),
    ])
    const jj = async r => r.status === "fulfilled" && r.value.ok ? r.value.json() : null
    const [oniData, arcticData, antarcticData, iodData, mjoData, mjoHist,
           pdoHist, naoHist, amoHist, qboHist, seismicData, weeklyData] = await Promise.all([
        jj(rOni), jj(rArctic), jj(rAntarctic), jj(rIod), jj(rMjo), jj(rMjoH),
        jj(rPdoH), jj(rNaoH), jj(rAmoH), jj(rQboH), jj(rSeismic), jj(rWeekly)
    ])
    if (!oniData || !oniData.length) return
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

    // MJO por mês: fase dominante (mais frequente) e amplitude média
    const mjoByMonth = (() => {
        const acc = {}
        ;(mjoHist||[]).forEach(d => {
            const key = d.data_referencia?.slice(0,7)
            if (!key) return
            if (!acc[key]) acc[key] = { phases: [], amps: [] }
            acc[key].phases.push(d.phase)
            acc[key].amps.push(d.amplitude)
        })
        return Object.fromEntries(Object.entries(acc).map(([k, {phases, amps}]) => {
            // fase mais frequente do mês
            const freq = {}
            phases.forEach(p => { freq[p] = (freq[p]||0) + 1 })
            const domPhase = +Object.keys(freq).reduce((a,b) => freq[a]>freq[b]?a:b)
            const avgAmp = amps.reduce((a,b)=>a+b,0)/amps.length
            return [k, { phase: domPhase, amplitude: avgAmp }]
        }))
    })()

    const pdoByMonth = Object.fromEntries((pdoHist||[]).map(d => [d.data_referencia?.slice(0,7), d.value]))
    const naoByMonth = Object.fromEntries((naoHist||[]).map(d => [d.data_referencia?.slice(0,7), d.value]))
    const amoByMonth = Object.fromEntries((amoHist||[]).map(d => [d.data_referencia?.slice(0,7), d.value]))
    // AMO só tem dados até 2023 — usar último valor disponível como fallback
    const amoLastVal = (amoHist||[]).length ? (amoHist[amoHist.length-1].value) : null
    const qboByMonth = Object.fromEntries((qboHist||[]).map(d => [d.data_referencia?.slice(0,7), {v:d.value, cls:d.classificacao}]))

    // 3. Build 2-month dataset (last 2 months only)
    const frames = oniData.slice(-2).map(o => ({
        period: o.periodo,
        oni: o.oni,
        classificacao: o.classificacao,
        arctic: arcticByMonth[o.periodo] ?? 11.0,
        antarctic: antarcticByMonth[o.periodo] ?? 10.0,
        iod: iodByMonth[o.periodo] ?? 0,
        pdo: pdoByMonth[o.periodo] ?? null,
        nao: naoByMonth[o.periodo] ?? null,
        amo: amoByMonth[o.periodo] ?? amoLastVal,
        qbo: qboByMonth[o.periodo] ?? null,
        mjoMonth: mjoByMonth[o.periodo] ?? null,
    }))

    // ── Termômetro ONI ────────────────────────────────────────────────
    const weeklyLatest = weeklyData && weeklyData.length ? weeklyData[weeklyData.length - 1].nino34_anom : null

    function desenharTermometro(oniMensal) {
        const svgEl = document.getElementById("oniThermometer")
        if (!svgEl) return

        const W = 56, H = 200  // coordenadas fixas — CSS controla o tamanho real
        svgEl.setAttribute("viewBox", `0 0 ${W} ${H}`)
        svgEl.removeAttribute("width")
        svgEl.removeAttribute("height")

        const mt = 10, mb = 10
        const scale = d3.scaleLinear().domain([2.5, -2.5]).range([mt, H - mb])
        const barX = 12, barW = 16, cx = barX + barW / 2

        const thColor = v =>
            v >= 1.5 ? "#FF5252" : v >= 0.5 ? "#FF7043" : v >= 0.3 ? "#FFB74D" :
            v <= -1.5 ? "#1E88E5" : v <= -0.5 ? "#42A5F5" : v <= -0.3 ? "#80DEEA" : "#78909C"

        const s = d3.select(svgEl)
        s.selectAll("*").remove()

        // Trilho de fundo
        s.append("rect")
            .attr("x", barX).attr("y", mt).attr("width", barW).attr("height", H - mt - mb)
            .attr("fill", "rgba(255,255,255,0.05)").attr("rx", 4)

        // Linha de zero
        const zy = scale(0)
        s.append("line").attr("x1", barX - 2).attr("x2", barX + barW + 2)
            .attr("y1", zy).attr("y2", zy)
            .attr("stroke", "rgba(255,255,255,0.25)").attr("stroke-width", 1)
        s.append("text").attr("x", barX + barW + 3).attr("y", zy + 3)
            .attr("font-size", 7).attr("fill", "rgba(255,255,255,0.3)").text("0")

        // Linhas de limiar
        ;[{v:1.5,c:"rgba(255,82,82,.55)"},{v:0.5,c:"rgba(255,112,67,.6)"},
          {v:-0.5,c:"rgba(66,165,245,.6)"},{v:-1.5,c:"rgba(30,136,229,.55)"}]
          .forEach(({v, c}) => {
            const y = scale(v)
            s.append("line").attr("x1", barX - 2).attr("x2", barX + barW + 2)
                .attr("y1", y).attr("y2", y)
                .attr("stroke", c).attr("stroke-width", 1).attr("stroke-dasharray","2,2")
            s.append("text").attr("x", barX + barW + 3).attr("y", y + 3)
                .attr("font-size", 7).attr("fill", c)
                .text(`${v > 0 ? "+" : ""}${v.toFixed(1)}`)
        })

        // Barra semanal (ghost, mais larga)
        if (weeklyLatest !== null) {
            const wy1 = scale(Math.max(0, weeklyLatest)), wy2 = scale(Math.min(0, weeklyLatest))
            s.append("rect")
                .attr("x", barX - 3).attr("y", Math.min(wy1, wy2))
                .attr("width", barW + 6).attr("height", Math.max(2, Math.abs(wy2 - wy1)))
                .attr("fill", thColor(weeklyLatest)).attr("opacity", 0.22).attr("rx", 3)
        }

        // Barra ONI mensal (sólida)
        const oy1 = scale(Math.max(0, oniMensal)), oy2 = scale(Math.min(0, oniMensal))
        const oniBarColor = thColor(oniMensal)
        s.append("rect")
            .attr("x", barX).attr("y", Math.min(oy1, oy2))
            .attr("width", barW).attr("height", Math.max(2, Math.abs(oy2 - oy1)))
            .attr("fill", oniBarColor).attr("opacity", 0.9).attr("rx", 3)

        // Label valor ONI no topo da barra
        s.append("text").attr("x", cx).attr("y", Math.min(oy1, oy2) - 3)
            .attr("text-anchor", "middle").attr("font-size", 7.5).attr("font-weight", "700")
            .attr("fill", oniBarColor)
            .text(`${oniMensal >= 0 ? "+" : ""}${oniMensal.toFixed(2)}`)

        // Label semanal no rodapé
        if (weeklyLatest !== null) {
            const weeklyEl = document.getElementById("thermoWeeklyVal")
            if (weeklyEl) {
                const sign = weeklyLatest >= 0 ? "+" : ""
                weeklyEl.textContent = `${sign}${weeklyLatest.toFixed(1)}°C`
                weeklyEl.style.color = thColor(weeklyLatest)
            }
        }
    }

    // MJO phase → equatorial longitude center
    const MJO_LON = { 1: 55, 2: 75, 3: 95, 4: 115, 5: 140, 6: 165, 7: -160, 8: -100 }

    // 4. Extent → geo radius (spherical cap formula: area = 2πR²(1−sinφ))
    const R2 = 255.03  // 2πR² in Mkm²
    function extentToRadius(extMkm2, pole) {
        const sinPhi = 1 - Math.min(extMkm2, R2 * 0.95) / R2
        const phiDeg = Math.asin(Math.max(0, Math.min(1, sinPhi))) * 180 / Math.PI
        return 90 - phiDeg + 2  // +2° buffer for visual clarity
    }

    // 5. Color scales
    // Paleta mais vibrante e saturada
    const oniColor = d3.scaleLinear()
        .domain([-2, -1, -0.5, 0, 0.5, 1, 2])
        .range(["#00B0FF","#29B6F6","#B3E5FC","#90A4AE","#FF8A65","#FF3D00","#B71C1C"])
        .clamp(true)
    const iodColor = d3.scaleLinear()
        .domain([-1, 0, 1])
        .range(["#00E676","#546A84","#7E57C2"])
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

    // Definições SVG: gradientes radiais para gelo polar
    const defs = svg.append("defs")

    // Filtro de blur para suavizar bordas do gelo
    const iceFilter = defs.append("filter").attr("id","iceBlur")
        .attr("x","-20%").attr("y","-20%").attr("width","140%").attr("height","140%")
    iceFilter.append("feGaussianBlur").attr("stdDeviation","6")

    // Gradiente ártico: branco → ciano → transparente
    const gradArctic = defs.append("radialGradient")
        .attr("id", "gradArctic").attr("cx","50%").attr("cy","20%")
        .attr("r","70%")
    gradArctic.append("stop").attr("offset","0%").attr("stop-color","#FFFFFF").attr("stop-opacity","0.95")
    gradArctic.append("stop").attr("offset","40%").attr("stop-color","#B3E5FC").attr("stop-opacity","0.75")
    gradArctic.append("stop").attr("offset","100%").attr("stop-color","#4FC3F7").attr("stop-opacity","0")

    // Gradiente antártico: branco → azul gelo → transparente
    const gradAntarctic = defs.append("radialGradient")
        .attr("id","gradAntarctic").attr("cx","50%").attr("cy","80%")
        .attr("r","70%")
    gradAntarctic.append("stop").attr("offset","0%").attr("stop-color","#FFFFFF").attr("stop-opacity","0.9")
    gradAntarctic.append("stop").attr("offset","40%").attr("stop-color","#E1F5FE").attr("stop-opacity","0.7")
    gradAntarctic.append("stop").attr("offset","100%").attr("stop-color","#81D4FA").attr("stop-opacity","0")

    // Sphere (ocean background) — azul mais profundo
    svg.append("path")
        .datum({type: "Sphere"})
        .attr("fill","#061020")
        .attr("d", path)

    // Graticule grid — ligeiramente mais visível
    svg.append("path")
        .datum(d3.geoGraticule()())
        .attr("fill","none")
        .attr("stroke","rgba(255,255,255,.07)")
        .attr("stroke-width","0.5")
        .attr("d", path)

    // 7. Load world topojson
    let world
    try {
        world = await d3.json("/world-110m.json")
    } catch { return }

    // Countries — cor levemente mais clara para contrastar com o gelo
    svg.append("g")
        .selectAll("path")
        .data(topojson.feature(world, world.objects.countries).features)
        .join("path")
        .attr("fill","#1e3348")
        .attr("stroke","#0d1f30")
        .attr("stroke-width","0.4")
        .attr("d", path)

    // 8. Marcadores sísmicos — só mês corrente, M≥7.5 pulsantes
    const seismicTip = document.getElementById("seismicTooltip")
    const curMonth = new Date().toISOString().slice(0, 7)
    const sevenDaysAgo = new Date(Date.now() - 7 * 864e5).toISOString().slice(0, 10)
    const seismicCurrent = (seismicData || []).filter(ev => {
        if (!ev.data_referencia) return false
        // M≥7.0: mês inteiro | abaixo: últimos 7 dias
        return ev.magnitude >= 7.0
            ? ev.data_referencia.slice(0, 7) === curMonth
            : ev.data_referencia >= sevenDaysAgo
    })

    if (seismicCurrent.length) {
        const seismicG = svg.append("g")

        seismicCurrent.forEach(ev => {
            const pos = projection([ev.longitude, ev.latitude])
            if (!pos) return
            const [sx, sy] = pos
            const sz = Math.max(5, (ev.magnitude - 5) * 3.5)
            const triPath = `M ${sx},${sy - sz*1.3} L ${sx + sz},${sy + sz*0.7} L ${sx - sz},${sy + sz*0.7} Z`
            const col = ev.magnitude >= 7.5 ? "#FF1744"
                      : ev.magnitude >= 7.0 ? "#FF5252"
                      : ev.magnitude >= 6.5 ? "#FF7043"
                      : "#FFD740"

            const g = seismicG.append("g").attr("cursor","pointer")

            // Anel pulsante para M≥7.5
            if (ev.magnitude >= 7.5) {
                const pulse = g.append("circle")
                    .attr("cx", sx).attr("cy", sy + sz*0.1)
                    .attr("r", sz * 1.2)
                    .attr("fill", "none")
                    .attr("stroke", col)
                    .attr("stroke-width", 1.5)
                    .attr("opacity", 0.8)
                const animPulse = () => pulse
                    .transition().duration(900).attr("r", sz * 2.5).attr("opacity", 0)
                    .transition().duration(0).attr("r", sz * 1.2).attr("opacity", 0.8)
                    .on("end", animPulse)
                animPulse()
            }

            // Triângulo
            g.append("path")
                .attr("d", triPath)
                .attr("fill", col)
                .attr("fill-opacity", 0.85)
                .attr("stroke","rgba(0,0,0,.3)")
                .attr("stroke-width", 0.5)

            // Tooltip
            g.on("mouseover", function(event) {
                    if (!seismicTip) return
                    const etype = ev.event_type?.includes("volcanic") ? "🌋 Vulcânico" : "🔴 Terremoto"
                    seismicTip.innerHTML = `<strong>M${ev.magnitude} — ${etype}</strong><br>${ev.place}<br><span style="color:var(--text-3)">${ev.data_referencia}</span>`
                    seismicTip.classList.remove("hidden")
                    seismicTip.style.left = (event.clientX + 15) + "px"
                    seismicTip.style.top  = (event.clientY - 10) + "px"
                })
                .on("mousemove", function(event) {
                    if (!seismicTip) return
                    seismicTip.style.left = (event.clientX + 15) + "px"
                    seismicTip.style.top  = (event.clientY - 10) + "px"
                })
                .on("mouseout", function() {
                    if (seismicTip) seismicTip.classList.add("hidden")
                })
        })
    }

    // 9. Niño 3.4 region polygon (5N-5S, 120W-170W → lon -170 to -120)
    const nino34 = {
        type: "Feature",
        geometry: {
            type: "Polygon",
            coordinates: [[
                [-170, 5], [-120, 5], [-120, -5], [-170, -5], [-170, 5]
            ]]
        }
    }
    // (polígonos ONI e IOD removidos — substituídos pelos marcadores pulsantes)

    // MJO: marcador no mapa + badge externo
    const mjoPhase = mjoData?.phase ?? null
    const mjoAmp   = mjoData?.amplitude ?? 0
    const MJO_DESC = {
        1: "África/Índico O.", 2: "Índico O.", 3: "Índico L.",
        4: "Cont. Marítimo",  5: "Pacífico O.", 6: "Pacífico C.",
        7: "Pacífico L.",     8: "Hemis. Ocidental"
    }

    // Badge externo MJO (atualizado por frame)
    const mjoFooter = document.getElementById("mapMjoBadge")
    const mjoSep    = document.getElementById("mapMjoSep")
    if (mjoSep) mjoSep.style.display = ""

    // Marcador MJO animado — criado no mapa, cx/cy atualizado por frame
    const mjoR = Math.max(7, W * 0.011)
    const mjoCircle = svg.append("circle")
        .attr("r", mjoR).attr("fill","rgba(255,152,0,0.2)")
        .attr("stroke","rgba(255,152,0,0.9)").attr("stroke-width",1.5)
        .attr("cx", -999).attr("cy", -999) // escondido até primeiro frame
        .style("pointer-events","none")
    const mjoPulse = svg.append("circle")
        .attr("r", mjoR).attr("fill","none")
        .attr("stroke","rgba(255,152,0,0.7)").attr("stroke-width",1)
        .attr("cx", -999).attr("cy", -999)
        .style("pointer-events","none")
    const mjoLabel = svg.append("text")
        .attr("text-anchor","middle")
        .attr("font-size", Math.max(8, W * 0.009)).attr("font-weight","700")
        .attr("fill","rgba(255,152,0,0.9)")
        .style("pointer-events","none").text("")

    // Inicia pulso contínuo
    const mjoPulseAnim = () => mjoPulse
        .transition().duration(900).attr("r", mjoR * 1.8).attr("stroke-opacity", 0)
        .transition().duration(0).attr("r", mjoR).attr("stroke-opacity", 0.7)
        .on("end", mjoPulseAnim)
    mjoPulseAnim()

    // 11. Marcadores pulsantes dos índices de modulação — estáticos (valor atual)
    // Marcadores de modulação — criados com cor neutra, atualizados por frame
    const r = Math.max(5, W * 0.008)
    function createModMarker(lon, lat, label) {
        const pos = projection([lon, lat])
        if (!pos) return null
        const [mx, my] = pos
        const g = svg.append("g").style("pointer-events","none")
        const dot = g.append("circle").attr("cx",mx).attr("cy",my)
            .attr("r",r).attr("fill","#78909C").attr("fill-opacity",0.3)
            .attr("stroke","#78909C").attr("stroke-width",1.5)
        const pulse = g.append("circle").attr("cx",mx).attr("cy",my)
            .attr("r",r).attr("fill","none").attr("stroke","#78909C")
            .attr("stroke-width",1).attr("stroke-opacity",0)
        g.append("text").attr("x",mx).attr("y",my - r - 4)
            .attr("text-anchor","middle")
            .attr("font-size", Math.max(7, W*0.008)).attr("font-weight","600")
            .attr("fill","rgba(255,255,255,0.7)").text(label)
        return { dot, pulse }
    }

    const modMarkers = {
        pdo: createModMarker(-170, 45, "PDO"),
        nao: createModMarker(-30,  60, "NAO"),
        amo: createModMarker(-45,  28, "AMO"),
        qbo: createModMarker( 20,   5, "QBO"),
    }

    function updateModMarker(m, color, active) {
        if (!m) return
        m.dot.attr("fill",color).attr("stroke",color)
        if (active) {
            const anim = () => m.pulse.attr("stroke",color).attr("stroke-opacity",1)
                .transition().duration(1000).attr("r",r*2.2).attr("stroke-opacity",0)
                .transition().duration(0).attr("r",r)
                .on("end", anim)
            anim()
        }
    }

    function modColor(val, posThresh, negThresh, posColor, negColor) {
        if (val === null || val === undefined) return "#78909C"
        return val >= posThresh ? posColor : val <= negThresh ? negColor : "#78909C"
    }

    function setBadge(id, label, val, unit, color) {
        const el = document.getElementById(id)
        if (!el || val === null || val === undefined) return
        const sign = val >= 0 ? "+" : ""
        el.textContent = `${label} ${sign}${parseFloat(val).toFixed(2)}${unit||""}`
        el.style.color = color
    }

    // ONI: marcador animado junto com o frame (sobre a região Niño 3.4)
    const oniMarkerG = svg.append("g").style("pointer-events","none")
    const oniCx = projection([-145,0])?.[0] || W*0.2
    const oniCy = projection([-145,0])?.[1] || H*0.5
    const oniR  = Math.max(5, W*0.008)

    // Anel pulsante — visível apenas no limiar El Niño/La Niña
    const oniPulse = oniMarkerG.append("circle")
        .attr("cx", oniCx).attr("cy", oniCy)
        .attr("r", oniR * 1.2)
        .attr("fill", "none")
        .attr("stroke", "#FF8A65")
        .attr("stroke-width", 1.5)
        .attr("opacity", 0)

    let _oniPulseActive = false
    function _startOniPulse(color) {
        if (_oniPulseActive) return
        _oniPulseActive = true
        oniPulse.attr("stroke", color).attr("opacity", 0.85)
        const loop = () => oniPulse
            .transition().duration(900).attr("r", oniR * 2.8).attr("opacity", 0)
            .transition().duration(0).attr("r", oniR * 1.2).attr("opacity", 0.85)
            .on("end", () => { if (_oniPulseActive) loop() })
        loop()
    }
    function _stopOniPulse() {
        if (!_oniPulseActive) return
        _oniPulseActive = false
        oniPulse.transition().duration(300).attr("opacity", 0)
    }

    const oniDot = oniMarkerG.append("circle")
        .attr("cx", oniCx).attr("cy", oniCy)
        .attr("r", oniR)
        .attr("fill-opacity", 0.35)
        .attr("stroke-width", 1.5)

    // IOD: marcador animado junto com o frame (sobre a região do Índico)
    const iodMarkerG = svg.append("g").style("pointer-events","none")
    const iodDot = iodMarkerG.append("circle")
        .attr("cx", projection([70,0])?.[0] || W*0.65)
        .attr("cy", projection([70,0])?.[1] || H*0.5)
        .attr("r", Math.max(5, W*0.008))
        .attr("fill-opacity", 0.35)
        .attr("stroke-width", 1.5)

    // Labels fixos para ONI e IOD
    ;[{g:oniMarkerG,lon:-145,lat:0,txt:"ONI"},{g:iodMarkerG,lon:70,lat:0,txt:"IOD"}]
        .forEach(({g,lon,lat,txt}) => {
            const pos = projection([lon,lat])
            if (!pos) return
            g.append("text").attr("x",pos[0]).attr("y",pos[1] - Math.max(5,W*0.008) - 4)
                .attr("text-anchor","middle")
                .attr("font-size",Math.max(7,W*0.008)).attr("font-weight","600")
                .attr("fill","rgba(255,255,255,0.7)")
                .text(txt)
        })

    // 10. Ice caps
    const arcticPath = svg.append("path")
        .attr("fill","url(#gradArctic)")
        .attr("stroke","none")
        .attr("filter","url(#iceBlur)")
    const antarcticPath = svg.append("path")
        .attr("fill","url(#gradAntarctic)")
        .attr("stroke","none")
        .attr("filter","url(#iceBlur)")

    // 12. Animation — start at most recent frame
    let frameIdx = frames.length - 1
    let timer = null

    function renderFrame(i) {
        const f = frames[i]
        const color = oniColor(f.oni)
        const icolor = iodColor(f.iod ?? 0)

        // Marcadores ONI e IOD animados por frame
        oniDot.attr("fill", color).attr("stroke", color)
        iodDot.attr("fill", icolor).attr("stroke", icolor)

        // Pulse de limiar ONI
        if (f.oni >= 0.3 && f.oni < 0.5) _startOniPulse("#FF8A65")       // quase El Niño — âmbar
        else if (f.oni <= -0.3 && f.oni > -0.5) _startOniPulse("#42A5F5") // quase La Niña — azul
        else _stopOniPulse()

        // Atualiza termômetro
        desenharTermometro(f.oni)

        // Marcador MJO animado por frame
        const mjoM = f.mjoMonth
        if (mjoM && mjoM.amplitude >= 1.0 && MJO_LON[mjoM.phase]) {
            const mjoPos = projection([MJO_LON[mjoM.phase], 0])
            if (mjoPos) {
                mjoCircle.attr("cx", mjoPos[0]).attr("cy", mjoPos[1])
                mjoPulse.attr("cx", mjoPos[0]).attr("cy", mjoPos[1])
                mjoLabel.attr("x", mjoPos[0]).attr("y", mjoPos[1] - mjoR - 4).text(`MJO F${mjoM.phase}`)
            }
        } else {
            mjoCircle.attr("cx", -999).attr("cy", -999)
            mjoPulse.attr("cx", -999).attr("cy", -999)
            mjoLabel.text("")
        }

        // Badge MJO
        if (mjoFooter) {
            const m = mjoM || { phase: mjoPhase, amplitude: mjoAmp }
            const active = m && m.amplitude >= 1.0
            mjoFooter.innerHTML = m && m.phase
                ? `<span class="map-mjo-dot ${active?"active":""}"></span> MJO F${m.phase} · ${MJO_DESC[m.phase]||""}${active?` · ${m.amplitude.toFixed(2)}`:""}`
                : ""
        }

        // Marcadores PDO/NAO/AMO/QBO animados por frame
        const pdoVal = f.pdo, naoVal = f.nao, amoVal = f.amo, qboObj = f.qbo
        const pdoC = modColor(pdoVal,  0.5, -0.5, "#FF7043","#42A5F5")
        const naoC = modColor(naoVal,  0.5, -0.5, "#42A5F5","#EF5350")
        const amoC = modColor(amoVal,  0.1, -0.1, "#EF5350","#42A5F5")
        const qboC = qboObj?.cls === "LESTE" ? "#7E57C2" : qboObj?.cls === "OESTE" ? "#4DD0E1" : "#78909C"
        updateModMarker(modMarkers.pdo, pdoC, pdoVal !== null && Math.abs(pdoVal||0) >= 0.5)
        updateModMarker(modMarkers.nao, naoC, naoVal !== null && Math.abs(naoVal||0) >= 0.5)
        updateModMarker(modMarkers.amo, amoC, amoVal !== null && Math.abs(amoVal||0) >= 0.1)
        updateModMarker(modMarkers.qbo, qboC, qboObj && qboObj.cls !== "NEUTRO")

        // Badges footer linha 2 — animados por frame
        setBadge("mapPdoBadge","PDO",pdoVal,"",pdoC)
        setBadge("mapNaoBadge","NAO",naoVal,"",naoC)
        setBadge("mapAmoBadge","AMO",amoVal,"°C",amoC)
        if (qboObj) {
            const el = document.getElementById("mapQboBadge")
            if (el) {
                const sign = (qboObj.v||0) >= 0 ? "+" : ""
                el.textContent = `QBO ${sign}${parseFloat(qboObj.v||0).toFixed(1)} m/s`
                el.style.color = qboC
            }
        }

        // Ice caps
        const arcticR    = extentToRadius(f.arctic)
        const antarcticR = extentToRadius(f.antarctic)
        // Transição suave D3 para o gelo — mostra expansão/contração
        arcticPath.datum(d3.geoCircle().center([0, 90]).radius(arcticR)())
            .transition().duration(1000).ease(d3.easeCubicInOut)
            .attr("d", path)
        antarcticPath.datum(d3.geoCircle().center([0, -90]).radius(antarcticR)())
            .transition().duration(1000).ease(d3.easeCubicInOut)
            .attr("d", path)

        // UI labels
        const [y, m] = f.period.split("-")
        const monthNames = ["","Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
        document.getElementById("mapMonthLabel").textContent = `${monthNames[+m]} ${y}`

        const oniSign = f.oni >= 0 ? "+" : ""
        const iodSign = f.iod >= 0 ? "+" : ""
        const stateMap = { EL_NINO: "El Niño", LA_NINA: "La Niña", NEUTRO: "Neutro" }

        // ONI badge — destaque no limiar
        const oniEl = document.getElementById("mapOniLabel")
        if (f.oni >= 0.3 && f.oni < 0.5) {
            oniEl.textContent = `⚠ Limiar El Niño · ONI ${oniSign}${f.oni.toFixed(2)}`
            oniEl.style.color = "#FF8A65"
        } else if (f.oni <= -0.3 && f.oni > -0.5) {
            oniEl.textContent = `⚠ Limiar La Niña · ONI ${oniSign}${f.oni.toFixed(2)}`
            oniEl.style.color = "#42A5F5"
        } else {
            oniEl.textContent = `${stateMap[f.classificacao] || f.classificacao} ONI ${oniSign}${f.oni.toFixed(2)}`
            oniEl.style.color = ""
        }

        // IOD badge — classifica por limiar ±0.4
        const iodClass = f.iod >= 0.4 ? "Positivo" : f.iod <= -0.4 ? "Negativo" : "Neutro"
        const iodEl = document.getElementById("mapIodLabel")
        if (iodEl) iodEl.textContent = `IOD ${iodSign}${f.iod.toFixed(2)} · ${iodClass}`

    }

    function nextFrame() {
        renderFrame(frameIdx)
        frameIdx = (frameIdx + 1) % frames.length
    }

    nextFrame()
    timer = setInterval(nextFrame, 1500)
    window._climateMapTimer = timer

    // Termômetro inicial após SVG pronto
    desenharTermometro(frames[frames.length - 1].oni)
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
