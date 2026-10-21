/* Painel — mapa-herói do Brasil: camadas (focos, desmatamento, reservatórios), KPIs, detalhe por estado e ticker. */
;(function () {
    const API = "/api/brasil"
    const W = 1000, H = 860
    const AREA_MAPA_DESKTOP = [[250, 175], [750, 790]]   // sobra espaço para KPIs (topo) e ticker (base)
    const AREA_MAPA_CELULAR = [[30, 30], [970, 830]]      // no celular o mapa tem o palco só para ele
    const mediaCelular = window.matchMedia("(max-width: 720px)")
    const ATUALIZA_VIVO_MS = 60_000
    const ATUALIZA_MAPA_MS = 300_000
    const FOCOS_PULSANTES = 10
    const LIMITE_CRITICO_PCT = 20
    const PROJETOS_DETER = ["deter-amz", "deter-cerrado"]
    const reduzMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches

    const el = id => document.getElementById(id)
    const fmt = (n, d = 0) => Number(n).toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d })
    const sinal = n => (n > 0 ? "+" : "") + fmt(n, 1)
    const dataBR = iso => (iso ? iso.split("-").reverse().slice(0, 2).join("/") : "—")

    const state = {
        iniciado: false, geo: null, proj: null, ufs: {}, nomes: {}, camadas: { focos: true, desmat: true, agua: true },
        focosPorUf: {}, desmatPorUf: {}, aguaPorUf: {}, totais: { focos: 0, desmat: 0, agua: 0 }, selecionada: null,
        escalaDesmat: null,
    }

    async function getJSON(url) {
        try {
            const r = await fetch(url)
            return r.ok ? await r.json() : null
        } catch { return null }
    }

    function criar(tag, classe, texto) {
        const n = document.createElement(tag)
        if (classe) n.className = classe
        if (texto != null) n.textContent = texto
        return n
    }

    function limpar(n) { while (n.firstChild) n.removeChild(n.firstChild) }

    function visivel() {
        const p = el("tab-painel")
        return !!p && p.classList.contains("active") && !document.hidden
    }

    // ── KPIs ─────────────────────────────────────────────────────────
    function tween(n, para, formato) {
        if (reduzMovimento || !isFinite(para)) { n.textContent = formato(para); return }
        const t0 = performance.now(), dur = 900
        const passo = agora => {
            const k = Math.min((agora - t0) / dur, 1)
            n.textContent = formato(para * (1 - Math.pow(1 - k, 3)))
            if (k < 1) requestAnimationFrame(passo)
        }
        requestAnimationFrame(passo)
    }

    function kpi(id, valor, sub, { numero = null, formato = null } = {}) {
        const c = el(id)
        const v = c.querySelector(".px-kpi-value")
        if (numero != null && formato) tween(v, numero, formato)
        else v.textContent = valor
        const s = c.querySelector(".px-kpi-sub")
        limpar(s)
        sub.forEach(p => s.appendChild(typeof p === "string" ? document.createTextNode(p) : p))
    }

    function realce(texto, classe) { return criar("b", classe || "", texto) }

    function variacaoNode(pct) {
        if (pct == null) return realce("sem média histórica")
        return realce(`${pct > 0 ? "▲" : "▼"} ${fmt(Math.abs(pct), 1)}% vs média`, pct > 0 ? "px-up" : "px-down")
    }

    async function carregarKpis() {
        const [f24, desm, res, enso, status] = await Promise.all([
            getJSON(`${API}/focos/resumo?nivel=brasil&periodo=24h`),
            Promise.all(PROJETOS_DETER.map(p => getJSON(`${API}/desmatamento/resumo?projeto=${p}&periodo=30d`))),
            getJSON(`${API}/reservatorios/resumo`),
            getJSON("/climate/status"),
            getJSON(`${API}/status`),
        ])
        if (f24) {
            const dia = f24.itens[0]
            kpi("px-k-focos", "—", [`detecções · dia completo ${fmt(dia.focos)} `, variacaoNode(dia.variacao_pct)],
                { numero: f24.ultimas_24h.total, formato: n => fmt(n) })
        }
        const okDesm = desm.filter(Boolean)
        if (okDesm.length) {
            const km2 = okDesm.reduce((s, d) => s + d.desmatamento_km2, 0)
            const ate = okDesm.map(d => d.dados_ate).filter(Boolean).sort()[0]
            kpi("px-k-desmat", "—", [`km² · Amazônia + Cerrado · dados até ${dataBR(ate)}`], { numero: km2, formato: n => fmt(n) })
        }
        const sin = res && res.sistemas.find(s => s.sistema === "SIN")
        const ne = res && res.sistemas.find(s => s.sistema === "NORDESTE")
        if (sin && sin.volume_pct_medio != null) {
            kpi("px-k-agua", "—", [ne && ne.volume_pct_medio != null ? `Nordeste ${fmt(ne.volume_pct_medio, 1)}%` : "volume médio"],
                { numero: sin.volume_pct_medio, formato: n => fmt(n, 1) + "%" })
        }
        if (enso) kpi("px-k-enso", enso.fase, [`ONI ${sinal(enso.oni)} · Niño 3.4 ${sinal(enso.nino34)} °C`])
        const rodape = el("px-foot")
        if (status && status.ultima_deteccao) {
            rodape.textContent = `Última detecção de foco: ${new Date(status.ultima_deteccao).toLocaleString("pt-BR")}. ` +
                "Focos: INPE · Desmatamento: DETER/INPE · Reservatórios: ANA/SAR · ENSO: NOAA."
        }
        return { f24, okDesm, res, enso }
    }

    async function carregarOps() {
        const dados = await getJSON(`${API}/coleta/execucoes`)
        const card = el("px-k-ops")
        if (!dados) { kpi("px-k-ops", "—", ["indisponível"]); return null }
        const ultimaPorFonte = new Map()
        dados.execucoes.forEach(e => { if (!ultimaPorFonte.has(e.fonte)) ultimaPorFonte.set(e.fonte, e) })
        const ativas = [...ultimaPorFonte.values()].filter(e => e.estado === "running")
        const problema = [...ultimaPorFonte.values()].filter(e => e.estado === "erro" || e.estado === "parado")
        card.classList.toggle("is-live", ativas.length > 0)
        if (ativas.length) {
            const e = ativas[0]
            kpi("px-k-ops", e.percentual != null ? `${fmt(e.percentual)}%` : "···", [`carga: ${e.etapa || e.rotulo}`])
        } else if (problema.length) {
            kpi("px-k-ops", "Atenção", [`${problema.length} fonte(s) com falha`])
        } else {
            kpi("px-k-ops", "Em dia", [`${ultimaPorFonte.size} fontes monitoradas`])
        }
        return dados
    }

    // ── Mapa ─────────────────────────────────────────────────────────
    function corDesmat(km2) {
        return km2 > 0 && state.escalaDesmat ? state.escalaDesmat(km2) : null
    }

    function pintarUfs() {
        d3.selectAll(".px-uf").style("fill", d => (state.camadas.desmat && corDesmat(state.desmatPorUf[d.properties.uf])) || null)
    }

    function desenharBase(svg) {
        const caminho = d3.geoPath(state.proj)
        svg.append("g").attr("class", "px-ufs").selectAll("path").data(state.geo.features).join("path")
            .attr("class", "px-uf px-uf-in").attr("d", caminho).attr("data-uf", d => d.properties.uf)
            .style("animation-delay", (_, i) => `${i * 22}ms`)
            .attr("tabindex", 0).attr("role", "img").attr("aria-label", d => `Estado ${state.nomes[d.properties.uf] || d.properties.uf}`)
            .on("mouseenter focus", (_, d) => selecionar(d.properties.uf))
            .on("mouseleave blur", () => selecionar(null))
    }

    function desenharFocos(svg, dados) {
        const itens = [...dados.itens].sort((a, b) => a.n - b.n)
        const max = d3.max(itens, d => d.n) || 1
        const raio = d3.scaleSqrt().domain([1, max]).range([2, 14])
        const g = svg.append("g").attr("class", "px-layer-g px-focos").attr("data-camada", "focos").attr("pointer-events", "none")
        g.selectAll("circle").data(itens).join("circle")
            .attr("cx", d => state.proj([d.lon, d.lat])[0]).attr("cy", d => state.proj([d.lon, d.lat])[1])
            .attr("r", d => raio(d.n)).attr("fill", "#FFB02E").attr("fill-opacity", d => .28 + .5 * (d.n / max))
        g.append("g").selectAll("circle").data(itens.slice(-FOCOS_PULSANTES)).join("circle")
            .attr("class", reduzMovimento ? null : "px-pulse")
            .attr("cx", d => state.proj([d.lon, d.lat])[0]).attr("cy", d => state.proj([d.lon, d.lat])[1])
            .attr("r", d => raio(d.n)).attr("fill", "none").attr("stroke", "#FFB02E").attr("stroke-width", 1.2)
    }

    function desenharAgua(svg, dados) {
        const g = svg.append("g").attr("class", "px-layer-g px-agua").attr("data-camada", "agua")
        g.selectAll("circle").data(dados.itens).join("circle")
            .attr("cx", d => state.proj([d.lon, d.lat])[0]).attr("cy", d => state.proj([d.lon, d.lat])[1])
            .attr("r", 3).attr("fill", "#35D4E8").attr("fill-opacity", d => .22 + .7 * Math.min(d.volume_pct, 100) / 100)
            .attr("stroke", d => (d.volume_pct < LIMITE_CRITICO_PCT ? "#E0603F" : "rgba(53,212,232,.5)"))
            .attr("stroke-width", d => (d.volume_pct < LIMITE_CRITICO_PCT ? 1.6 : .6))
            .append("title").text(d => `${d.nome} (${d.uf || "—"}): ${fmt(d.volume_pct, 1)}%`)
    }

    function desenharLegenda(box) {
        const l = criar("div", "px-legend")
        ;[["var(--fire)", "Focos: maior círculo = mais detecções"], ["var(--land)", "Desmatamento: estado mais intenso = mais km²"],
          ["var(--water)", "Reservatório: mais opaco = mais cheio · contorno terra < 20%"]]
            .forEach(([cor, txt]) => {
                const s = criar("span"), i = criar("i")
                i.style.setProperty("--c", cor)
                s.append(i, document.createTextNode(txt))
                l.appendChild(s)
            })
        box.appendChild(l)
    }

    function agregarPorUf(foc, desm, agua) {
        state.focosPorUf = {}; state.desmatPorUf = {}; state.aguaPorUf = {}
        if (foc) foc.itens.forEach(i => { state.focosPorUf[i.codigo] = i.focos; state.nomes[i.codigo] = i.nome })
        desm.forEach(d => d.por_uf.forEach(u => { state.desmatPorUf[u.uf] = (state.desmatPorUf[u.uf] || 0) + u.area_km2 }))
        if (agua) agua.itens.forEach(r => {
            if (!r.uf) return
            const a = state.aguaPorUf[r.uf] || (state.aguaPorUf[r.uf] = { n: 0, soma: 0 })
            a.n += 1; a.soma += r.volume_pct
        })
        const soma = o => Object.values(o).reduce((s, v) => s + v, 0)
        state.totais = { focos: soma(state.focosPorUf), desmat: soma(state.desmatPorUf), agua: agua ? agua.total : 0 }
        const max = Math.max(0, ...Object.values(state.desmatPorUf))
        state.escalaDesmat = max > 0
            ? d3.scaleSqrt().domain([0, max]).range(["rgba(224,96,63,.05)", "rgba(224,96,63,.46)"]).interpolate(d3.interpolateRgb) : null
    }

    async function carregarMapa() {
        const palco = el("px-stage")
        const [geo, focos, desm, agua, focosUf] = await Promise.all([
            state.geo || getJSON("/br-ufs.geojson"),
            getJSON(`${API}/focos/mapa?periodo=7d&zoom=4`),
            Promise.all(PROJETOS_DETER.map(p => getJSON(`${API}/desmatamento/resumo?projeto=${p}&periodo=30d`))),
            getJSON(`${API}/reservatorios/mapa`),
            getJSON(`${API}/focos/resumo?nivel=uf&periodo=7d`),
        ])
        if (!geo) { limpar(palco); palco.appendChild(criar("div", "px-empty", "MAPA INDISPONÍVEL NO MOMENTO")); return }
        const primeira = !state.geo
        state.geo = geo
        state.proj = d3.geoMercator().fitExtent(mediaCelular.matches ? AREA_MAPA_CELULAR : AREA_MAPA_DESKTOP, geo)
        agregarPorUf(focosUf, desm.filter(Boolean), agua)
        limpar(palco)
        const svg = d3.select(palco).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("preserveAspectRatio", "xMidYMid meet")
        const defs = svg.append("defs")
        const brilho = defs.append("filter").attr("id", "px-glow").attr("x", "-50%").attr("y", "-50%").attr("width", "200%").attr("height", "200%")
        brilho.append("feGaussianBlur").attr("stdDeviation", 2.2).attr("result", "b")
        const fusao = brilho.append("feMerge")
        fusao.append("feMergeNode").attr("in", "b"); fusao.append("feMergeNode").attr("in", "SourceGraphic")
        desenharBase(svg)
        if (focos) desenharFocos(svg, focos)
        if (agua) desenharAgua(svg, agua)
        svg.selectAll(".px-focos, .px-agua").attr("filter", "url(#px-glow)")
        aplicarCamadas()
        pintarUfs()
        if (primeira) desenharLegenda(el("px-hero"))
        selecionar(state.selecionada)
    }

    // ── Camadas e detalhe ────────────────────────────────────────────
    function aplicarCamadas() {
        document.querySelectorAll("[data-camada]").forEach(g => g.classList.toggle("is-off", !state.camadas[g.dataset.camada]))
        pintarUfs()
    }

    function ligarCamadas() {
        document.querySelectorAll("[data-px-layer]").forEach(b => b.addEventListener("click", () => {
            const k = b.dataset.pxLayer
            state.camadas[k] = !state.camadas[k]
            b.classList.toggle("is-on", state.camadas[k])
            b.setAttribute("aria-pressed", String(state.camadas[k]))
            aplicarCamadas()
        }))
    }

    function linha(classe, rotulo, valor) {
        const r = criar("div", `px-row ${classe}`)
        r.append(criar("span", "", rotulo), criar("strong", "", valor))
        return r
    }

    function selecionar(uf) {
        state.selecionada = uf
        d3.selectAll(".px-uf").classed("is-sel", d => d.properties.uf === uf)
        const box = el("px-detail")
        limpar(box)
        box.appendChild(criar("h2", "px-h", uf ? "Estado" : "Visão nacional"))
        box.appendChild(criar("div", "px-detail-uf", uf ? (state.nomes[uf] || uf) : "Brasil"))
        box.appendChild(criar("div", "px-detail-sub", uf || "todos os estados"))
        const t = state.totais
        const focos = uf ? state.focosPorUf[uf] || 0 : t.focos
        const desm = uf ? state.desmatPorUf[uf] || 0 : t.desmat
        box.appendChild(linha("px-fire", "Focos · 7 dias", fmt(focos)))
        box.appendChild(linha("px-land", "Desmatamento · 30 d", `${fmt(desm, 1)} km²`))
        if (uf) {
            const a = state.aguaPorUf[uf]
            box.appendChild(linha("px-water", "Reservatórios", a ? `${a.n} · média ${fmt(a.soma / a.n, 0)}%` : "sem medição"))
        } else {
            box.appendChild(linha("px-water", "Reservatórios monitorados", fmt(t.agua)))
        }
    }

    // ── Ticker ───────────────────────────────────────────────────────
    function itemTicker(cor, destaque, texto) {
        const li = criar("li")
        li.style.setProperty("--c", cor)
        li.append(criar("b", "", destaque), document.createTextNode(texto))
        return li
    }

    async function carregarTicker(kp, ops) {
        const itens = []
        const alertas = await Promise.all(PROJETOS_DETER.map(p => getJSON(`${API}/desmatamento/alertas?projeto=${p}&periodo=30d&limite=3`)))
        const topUf = Object.entries(state.focosPorUf).sort((a, b) => b[1] - a[1]).slice(0, 3)
        topUf.forEach(([uf, n]) => itens.push(itemTicker("var(--fire)", `${state.nomes[uf] || uf}`, ` · ${fmt(n)} focos em 7 dias`)))
        alertas.filter(Boolean).forEach(a => a.itens.forEach(i => itens.push(itemTicker(
            "var(--land)", `DETER ${dataBR(i.data)}`,
            ` · ${i.classe.replaceAll("_", " ").toLowerCase()} ${fmt(i.area_km2, 2)} km² · ${i.municipio || "—"}/${i.uf || "—"}`))))
        const ne = kp.res && kp.res.sistemas.find(s => s.sistema === "NORDESTE")
        if (ne) itens.push(itemTicker("var(--water)", "Nordeste", ` · ${ne.faixas.critico} reservatórios abaixo de 20% de ${ne.com_medicao_recente} medidos`))
        if (kp.enso) itens.push(itemTicker("var(--accent)", kp.enso.fase, ` · ONI ${sinal(kp.enso.oni)}`))
        if (ops) {
            const ativa = ops.execucoes.find(e => e.estado === "running")
            if (ativa) itens.push(itemTicker("#7CE3B5", "Coleta em andamento", ` · ${ativa.rotulo} · ${ativa.etapa || ""}`))
        }
        const lista = el("px-ticker-list")
        limpar(lista)
        if (!itens.length) { lista.appendChild(itemTicker("var(--text-3)", "Sem eventos recentes", "")); return }
        itens.forEach(i => lista.appendChild(i))
        if (!reduzMovimento) {  // segunda cópia para o laço contínuo
            itens.forEach(i => lista.appendChild(i.cloneNode(true)))
            lista.style.setProperty("--px-dur", `${Math.max(40, itens.length * 7)}s`)
        }
    }

    // ── Ciclo de vida ────────────────────────────────────────────────
    async function atualizarVivo() {
        const [kp, ops] = await Promise.all([carregarKpis(), carregarOps()])
        await carregarTicker(kp, ops)
    }

    async function iniciar() {
        if (state.iniciado) return
        state.iniciado = true
        ligarCamadas()
        el("px-k-ops").addEventListener("click", () => {
            if (typeof irParaAba === "function") irParaAba("brasil")
            const b = el("br-tab-coletas")
            if (b) b.click()
        })
        await carregarMapa()          // o ticker usa os totais por estado do mapa
        await atualizarVivo()
        setInterval(() => { if (visivel()) atualizarVivo() }, ATUALIZA_VIVO_MS)
        setInterval(() => { if (visivel()) carregarMapa() }, ATUALIZA_MAPA_MS)
    }

    mediaCelular.addEventListener("change", () => { if (state.geo) carregarMapa() })
    window.carregarPainel = iniciar
    const aba = document.querySelector('[data-tab="painel"]')
    if (aba) aba.addEventListener("click", iniciar)
    if (visivel()) iniciar()
})()
