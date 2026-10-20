/* Aba Brasil — módulo Desmatamento (alertas DETER, INPE). Carrega ao abrir o módulo pela primeira vez. */
;(function () {
    const API = "/api/brasil"
    const fmt = (n, d = 0) => Number(n).toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d })
    const el = id => document.getElementById(id)
    const LIMITE_UF = 10
    const MESES_SERIE = 36
    const DEFASAGEM_ALERTA_DIAS = 15
    const ROTULO_PERIODO = { "30d": "30 dias", "90d": "90 dias", "365d": "12 meses" }

    const state = { projeto: "deter-amz", periodo: "90d", carregado: false, geracao: 0, chart: null }

    async function getJSON(url) {
        try {
            const r = await fetch(url)
            return r.ok ? await r.json() : null
        } catch { return null }
    }

    function limpar(n) { while (n.firstChild) n.removeChild(n.firstChild) }

    function mensagem(n, texto) {
        limpar(n)
        const d = document.createElement("div")
        d.className = "br-empty"
        d.textContent = texto
        n.appendChild(d)
    }

    function criar(tag, classe, texto) {
        const n = document.createElement(tag)
        if (classe) n.className = classe
        if (texto != null) n.textContent = texto
        return n
    }

    function dataBR(iso) { return iso ? iso.split("-").reverse().join("/") : "—" }

    // ── Aviso e status ───────────────────────────────────────────────
    function renderAviso(resumo) {
        const box = el("dm-aviso")
        limpar(box)
        box.hidden = !(resumo && resumo.experimental)
        if (!box.hidden) box.appendChild(criar("span", null, resumo.aviso_experimental))
    }

    function renderStatus(resumo, status) {
        const box = el("dm-status")
        limpar(box)
        box.appendChild(criar("span", null, "Fonte: INPE · TerraBrasilis · DETER"))
        if (!resumo) return
        if (resumo.dados_ate == null) {
            box.appendChild(criar("span", "br-warn", "Sem alertas coletados ainda para este projeto"))
            return
        }
        const atrasado = resumo.dias_defasagem > DEFASAGEM_ALERTA_DIAS
        box.appendChild(criar("span", atrasado ? "br-warn" : null,
            `Último alerta em ${dataBR(resumo.dados_ate)} (há ${fmt(resumo.dias_defasagem)} dia(s))`))
        const f = status && status.fontes && status.fontes.find(x => x.fonte === "deter_desmatamento")
        if (!f || !f.ultima_coleta_ok) { box.appendChild(criar("span", "br-warn", "⚠ Coleta ainda não registrada")); return }
        box.appendChild(criar("span", null, `Última coleta: ${new Date(f.ultima_coleta_ok).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}`))
        if (f.defasada) box.appendChild(criar("span", "br-warn", `⚠ Dados defasados (${fmt(f.defasagem_horas, 0)} h sem coleta)`))
    }

    // ── Cards ────────────────────────────────────────────────────────
    function card(rotulo, valor, unidade, sub) {
        const c = criar("div", "card")
        c.appendChild(criar("div", "card-label", rotulo))
        const v = criar("div", "br-value", valor)
        if (unidade) v.appendChild(criar("small", null, ` ${unidade}`))
        c.appendChild(v)
        if (sub) c.appendChild(sub)
        return c
    }

    function badgeVariacao(prodes) {
        const b = criar("span", "br-badge")
        if (prodes.variacao_pct == null) {
            b.textContent = prodes.anterior ? "sem base de comparação" : "comparação indisponível: histórico incompleto"
            return b
        }
        const v = prodes.variacao_pct
        b.textContent = `${v > 0 ? "+" : ""}${fmt(v, 1)}% vs mesmo período do ano PRODES ${prodes.anterior.ano}`
        b.classList.add(v >= 1 ? "acima" : v <= -1 ? "abaixo" : "estavel")
        return b
    }

    function subTexto(texto) { return criar("p", "br-card-sub", texto) }

    function renderCards(resumo) {
        const box = el("dm-cards")
        limpar(box)
        if (!resumo) { mensagem(box, "Dado indisponível no momento."); return }
        const periodo = ROTULO_PERIODO[resumo.periodo]
        const desmat = resumo.por_grupo.find(g => g.grupo === "desmatamento")
        const outras = resumo.por_grupo.filter(g => g.grupo !== "desmatamento")
        const km2Outras = outras.reduce((s, g) => s + g.area_km2, 0)

        box.appendChild(card(`Desmatamento · ${periodo}`, fmt(resumo.desmatamento_km2, 1), "km²",
            subTexto(`${fmt(desmat ? desmat.alertas : 0)} alertas de desmatamento, de ${dataBR(resumo.inicio)} a ${dataBR(resumo.fim)}.`)))
        const prodes = resumo.ano_prodes
        box.appendChild(card(`Ano PRODES ${prodes.ano} (desde ${dataBR(prodes.inicio)})`, fmt(prodes.acumulado_km2, 1), "km²",
            badgeVariacao(prodes)))
        const sub = subTexto(outras.length
            ? outras.map(g => `${g.nome}: ${fmt(g.area_km2, 1)} km²`).join(" · ")
            : "Nenhum alerta de outras classes no período.")
        box.appendChild(card(`Outras classes · ${periodo}`, fmt(km2Outras, 1), "km²", sub))
    }

    // ── Ranking por UF ───────────────────────────────────────────────
    function renderRanking(resumo) {
        const box = el("dm-rank")
        limpar(box)
        if (!resumo || !resumo.por_uf.length) { mensagem(box, "Sem alertas de desmatamento no período."); return }
        const itens = resumo.por_uf.slice(0, LIMITE_UF)
        const max = Math.max(...itens.map(i => i.area_km2), 0.01)
        itens.forEach(i => {
            const li = document.createElement("li")
            const bar = criar("span", "br-rank-bar")
            const fill = document.createElement("span")
            fill.style.width = `${i.area_km2 ? Math.max(2, (i.area_km2 / max) * 100) : 0}%`
            bar.appendChild(fill)
            li.append(criar("span", "br-rank-nome", i.uf), bar,
                criar("span", "br-rank-num", `${fmt(i.area_km2, 1)} km² · ${fmt(i.alertas)} alertas`))
            box.appendChild(li)
        })
    }

    // ── Série mensal ─────────────────────────────────────────────────
    function desenharSerie(serie) {
        const canvas = el("dm-chart")
        const msg = el("dm-chart-msg")
        if (state.chart) { state.chart.destroy(); state.chart = null }
        if (!serie || !serie.pontos.some(p => p.area_km2 > 0)) {
            mensagem(msg, serie ? "Sem histórico de desmatamento para este projeto." : "Dado indisponível no momento.")
            canvas.style.display = "none"
            return
        }
        limpar(msg)
        canvas.style.display = ""
        state.chart = new Chart(canvas, {
            type: "bar",
            data: {
                labels: serie.pontos.map(p => p.mes.split("-").reverse().join("/")),
                datasets: [{ label: "Desmatamento (km²)", data: serie.pontos.map(p => p.area_km2),
                             backgroundColor: "rgba(102,187,106,.75)", borderRadius: 3 }],
            },
            options: {
                responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: "#546A84", maxTicksLimit: 12 }, grid: { display: false } },
                    y: { beginAtZero: true, ticks: { color: "#546A84", callback: v => `${fmt(v)} km²` }, grid: { color: "rgba(255,255,255,.05)" } },
                },
            },
        })
    }

    // ── Carga e controles ────────────────────────────────────────────
    async function atualizar() {
        const geracao = ++state.geracao  // descarta respostas de seleções já substituídas
        const p = encodeURIComponent(state.projeto)
        const [resumo, serie, status] = await Promise.all([
            getJSON(`${API}/desmatamento/resumo?projeto=${p}&periodo=${state.periodo}`),
            getJSON(`${API}/desmatamento/serie?projeto=${p}&meses=${MESES_SERIE}`),
            getJSON(`${API}/status`),
        ])
        if (geracao !== state.geracao) return
        renderAviso(resumo)
        renderStatus(resumo, status)
        renderCards(resumo)
        renderRanking(resumo)
        el("dm-rank-titulo").textContent = `Desmatamento por estado · ${ROTULO_PERIODO[state.periodo]}`
        desenharSerie(serie)
    }

    function ligarSeletor(atributo, chave) {
        const botoes = document.querySelectorAll(`[${atributo}]`)
        botoes.forEach(b => b.addEventListener("click", () => {
            state[chave] = b.getAttribute(atributo)
            botoes.forEach(x => {
                const ativo = x === b
                x.classList.toggle("active", ativo)
                x.setAttribute("aria-pressed", String(ativo))
            })
            atualizar()
        }))
    }

    function carregar() {
        if (state.carregado) return
        state.carregado = true
        ligarSeletor("data-dm-projeto", "projeto")
        ligarSeletor("data-dm-periodo", "periodo")
        atualizar()
    }

    window.carregarDesmatamento = carregar
})()
