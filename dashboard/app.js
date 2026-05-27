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
async function carregarInsight() {
    try {
        const res = await fetch(`${API_BASE}/climate/analysis`)
        if (!res.ok) throw new Error(res.status)
        const d = await res.json()
        document.getElementById("analysis").textContent = d.analysis
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

    new Chart(ctx, {
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

// ── Init ─────────────────────────────────────────────────────────────
carregarStatus()
carregarHistorico()
carregarSOI()
carregarInsight()
carregarTendencia()
carregarAtualizacao()
carregarAlertas()
