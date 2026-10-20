/* Aba Brasil — módulo Reservatórios (ANA/SAR). Carrega ao abrir o módulo pela primeira vez. */
;(function () {
    const API = "/api/brasil"
    const fmt = (n, d = 0) => Number(n).toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d })
    const el = id => document.getElementById(id)
    const PAGINA = 50
    const FAIXAS = [
        ["critico", "Abaixo de 20%", "#EF5350"], ["baixo", "20% a 40%", "#FFA726"],
        ["medio", "40% a 60%", "#FFD54F"], ["bom", "60% a 80%", "#66BB6A"], ["alto", "Acima de 80%", "#5EC8F8"],
    ]
    const COR_FAIXA = Object.fromEntries(FAIXAS.map(([k, , c]) => [k, c]))
    const UFS = ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"]

    const state = { sistema: "", uf: "", faixa: "", q: "", ordem: "-volume", offset: 0, total: 0, carregado: false, chart: null, debounce: null }

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

    function badgePP(v, rotulo = "vs 30 d") {
        const b = criar("span", "br-badge")
        if (v == null) { b.textContent = "sem base de 30 dias"; return b }
        const txt = `${v > 0 ? "+" : ""}${fmt(v, 1)} p.p. ${rotulo}`
        b.textContent = txt
        b.classList.add(v >= 1 ? "sobe" : v <= -1 ? "desce" : "estavel")
        return b
    }

    // ── Cards por sistema ────────────────────────────────────────────
    function barraFaixas(faixas, total) {
        const barra = criar("div", "rs-faixas")
        barra.setAttribute("role", "img")
        const partes = FAIXAS.map(([k, nome]) => `${nome}: ${faixas[k] || 0}`).join(", ")
        barra.setAttribute("aria-label", `Reservatórios por faixa de volume. ${partes}`)
        FAIXAS.forEach(([k, nome, cor]) => {
            const n = faixas[k] || 0
            if (!n || !total) return
            const seg = criar("span")
            seg.style.width = `${(n / total) * 100}%`
            seg.style.background = cor
            seg.title = `${nome}: ${n}`
            barra.appendChild(seg)
        })
        return barra
    }

    function cardSistema(s) {
        const card = criar("button", "card rs-card")
        card.type = "button"
        card.dataset.sistema = s.sistema
        card.setAttribute("aria-pressed", String(state.sistema === s.sistema))
        card.appendChild(criar("div", "card-label", s.nome))
        const valor = criar("div", "br-value", s.volume_pct_medio == null ? "—" : `${fmt(s.volume_pct_medio, 1)}%`)
        card.appendChild(valor)
        const sub = criar("div", "br-card-sub")
        sub.appendChild(badgePP(s.variacao_30d_pp))
        const info = criar("div", null, s.total
            ? `${fmt(s.com_medicao_recente)} de ${fmt(s.total)} com medição recente${s.metodo_media === "ponderada" ? " · média ponderada pela capacidade" : " · média simples"}`
            : "Sem leituras")
        sub.appendChild(info)
        card.appendChild(sub)
        if (s.com_medicao_recente) card.appendChild(barraFaixas(s.faixas, s.com_medicao_recente))
        card.addEventListener("click", () => {
            state.sistema = state.sistema === s.sistema ? "" : s.sistema
            el("rs-f-sistema").value = state.sistema
            marcarCards()
            recarregarLista()
        })
        return card
    }

    function marcarCards() {
        document.querySelectorAll(".rs-card").forEach(c => {
            const ativo = c.dataset.sistema === state.sistema
            c.classList.toggle("ativo", ativo)
            c.setAttribute("aria-pressed", String(ativo))
        })
    }

    function renderResumo(r) {
        const box = el("rs-cards")
        limpar(box)
        if (!r) { mensagem(box, "Dado indisponível no momento."); return }
        r.sistemas.forEach(s => box.appendChild(cardSistema(s)))
        const leg = el("rs-legenda")
        limpar(leg)
        FAIXAS.forEach(([, nome, cor]) => {
            const item = criar("span", "rs-leg-item")
            const dot = criar("i")
            dot.style.background = cor
            item.append(dot, document.createTextNode(nome))
            leg.appendChild(item)
        })
    }

    // ── Lista ────────────────────────────────────────────────────────
    function linhaReservatorio(i) {
        const li = criar("li")
        const btn = criar("button", "rs-row")
        btn.type = "button"
        btn.addEventListener("click", () => abrirDetalhe(i.id))
        const nome = criar("span", "rs-nome")
        nome.appendChild(criar("strong", null, i.nome))
        nome.appendChild(criar("small", null, [i.municipio, i.uf].filter(Boolean).join(" · ")))
        const vol = criar("span", "rs-vol")
        const trilho = criar("span", "rs-trilho")
        const barra = criar("span")
        barra.style.width = `${Math.min(100, Math.max(0, i.volume_pct))}%`
        barra.style.background = COR_FAIXA[i.faixa]
        trilho.appendChild(barra)
        vol.append(trilho, criar("b", null, `${fmt(i.volume_pct, 1)}%`))
        const variacao = criar("span", "rs-var")
        if (i.variacao_30d_pp == null) {
            variacao.textContent = "—"
            variacao.title = "Sem medição de cerca de 30 dias atrás para comparar"
        } else {
            variacao.appendChild(badgePP(i.variacao_30d_pp, ""))
        }
        const data = criar("span", "rs-data", dataBR(i.data_medicao))
        if (!i.recente) {
            data.classList.add("defasado")
            data.title = `Última medição há ${i.dias_desde_medicao} dias`
            data.appendChild(criar("small", null, "sem medição recente"))
        }
        btn.append(nome, vol, variacao, data)
        li.appendChild(btn)
        return li
    }

    function parametrosLista(offset) {
        const p = new URLSearchParams({ ordem: state.ordem, offset, limite: PAGINA })
        if (state.sistema) p.set("sistema", state.sistema)
        if (state.uf) p.set("uf", state.uf)
        if (state.faixa) p.set("faixa", state.faixa)
        if (state.q) p.set("q", state.q)
        return p
    }

    let geracaoLista = 0
    let geracaoDetalhe = 0

    async function carregarLista(anexar) {
        const lista = el("rs-lista")
        const geracao = ++geracaoLista  // descarta respostas de filtros já substituídos
        const offset = anexar ? state.offset + PAGINA : 0
        if (!anexar) mensagem(lista, "Carregando…")
        const r = await getJSON(`${API}/reservatorios?${parametrosLista(offset)}`)
        if (geracao !== geracaoLista) return
        if (!r) { if (!anexar) mensagem(lista, "Dado indisponível no momento."); return }
        state.offset = offset  // só avança quando a página chegou
        if (!anexar) limpar(lista)
        r.itens.forEach(i => lista.appendChild(linhaReservatorio(i)))
        state.total = r.total
        if (!r.total) mensagem(lista, "Nenhum reservatório com esses filtros.")
        el("rs-contagem").textContent = r.total ? `${fmt(r.total)} reservatório(s)` : ""
        const mais = el("rs-mais")
        mais.hidden = state.offset + r.itens.length >= r.total
    }

    function recarregarLista() {
        state.offset = 0
        carregarLista(false)
    }

    // ── Detalhe ──────────────────────────────────────────────────────
    function desenharSerie(s) {
        const canvas = el("rs-chart")
        const msg = el("rs-chart-msg")
        if (state.chart) { state.chart.destroy(); state.chart = null }
        if (!s || !s.pontos.length) { mensagem(msg, "Sem histórico para este reservatório."); canvas.style.display = "none"; return }
        limpar(msg)
        canvas.style.display = ""
        state.chart = new Chart(canvas, {
            type: "line",
            data: {
                labels: s.pontos.map(p => dataBR(p.data)),
                datasets: [{ label: "Volume (%)", data: s.pontos.map(p => p.volume_pct), borderColor: "#5EC8F8",
                             backgroundColor: "rgba(94,200,248,.12)", borderWidth: 1.6, pointRadius: 0, fill: true, tension: .2 }],
            },
            options: {
                responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: "#546A84", maxTicksLimit: 8 }, grid: { display: false } },
                    y: { min: 0, suggestedMax: 100, ticks: { color: "#546A84", callback: v => `${v}%` }, grid: { color: "rgba(255,255,255,.05)" } },
                },
            },
        })
    }

    async function abrirDetalhe(id) {
        const painel = el("rs-detalhe")
        painel.hidden = false
        el("rs-detalhe-titulo").textContent = "Carregando…"
        el("rs-detalhe-sub").textContent = ""
        painel.scrollIntoView({ behavior: "smooth", block: "nearest" })
        const geracao = ++geracaoDetalhe
        const s = await getJSON(`${API}/reservatorios/${id}/serie?periodo=5y`)
        if (geracao !== geracaoDetalhe) return
        el("rs-detalhe-titulo").textContent = s ? s.nome : "Dado indisponível"
        if (s) {
            const ult = s.pontos[s.pontos.length - 1]
            const partes = [s.sistema_nome, s.municipio, s.uf].filter(Boolean)
            if (s.capacidade_hm3) partes.push(`capacidade ${fmt(s.capacidade_hm3, 1)} hm³`)
            if (ult) partes.push(`última medição ${dataBR(ult.data)}: ${fmt(ult.volume_pct, 1)}%`)
            partes.push(`${fmt(s.pontos.length)} medições nos últimos 5 anos`)
            el("rs-detalhe-sub").textContent = partes.join(" · ")
        }
        desenharSerie(s)
    }

    // ── Status e controles ───────────────────────────────────────────
    function renderStatus(status) {
        const box = el("rs-status")
        limpar(box)
        const f = status && status.fontes && status.fontes.find(x => x.fonte === "sar_reservatorios")
        box.appendChild(criar("span", null, "Fonte: ANA · Sistema de Acompanhamento de Reservatórios (SAR)"))
        if (!f || !f.ultima_coleta_ok) { box.appendChild(criar("span", "br-warn", "⚠ Coleta ainda não registrada")); return }
        box.appendChild(criar("span", null, `Última coleta: ${new Date(f.ultima_coleta_ok).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}`))
        if (f.defasada) box.appendChild(criar("span", "br-warn", `⚠ Dados defasados (${fmt(f.defasagem_horas, 0)} h sem coleta)`))
    }

    function popularFiltros() {
        const uf = el("rs-f-uf")
        UFS.forEach(u => { const o = criar("option", null, u); o.value = u; uf.appendChild(o) })
        const faixa = el("rs-f-faixa")
        FAIXAS.forEach(([k, nome]) => { const o = criar("option", null, nome); o.value = k; faixa.appendChild(o) })
    }

    function ligarControles() {
        const mudou = (id, chave) => el(id).addEventListener("change", e => {
            state[chave] = e.target.value
            if (chave === "sistema") marcarCards()
            recarregarLista()
        })
        mudou("rs-f-sistema", "sistema"); mudou("rs-f-uf", "uf"); mudou("rs-f-faixa", "faixa"); mudou("rs-f-ordem", "ordem")
        el("rs-f-q").addEventListener("input", e => {
            clearTimeout(state.debounce)
            state.debounce = setTimeout(() => { state.q = e.target.value.trim(); recarregarLista() }, 300)
        })
        el("rs-mais").addEventListener("click", () => carregarLista(true))
        el("rs-fechar").addEventListener("click", () => { el("rs-detalhe").hidden = true })
    }

    async function carregar() {
        if (state.carregado) return
        state.carregado = true
        popularFiltros()
        ligarControles()
        const [resumo, status] = await Promise.all([getJSON(`${API}/reservatorios/resumo`), getJSON(`${API}/status`)])
        renderResumo(resumo)
        renderStatus(status)
        carregarLista(false)
    }

    window.carregarReservatorios = carregar
})()
