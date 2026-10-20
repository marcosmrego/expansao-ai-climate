/* Aba Brasil — focos de calor (INPE). Carrega no primeiro clique na aba. */
;(function () {
    const API = "/api/brasil"
    const fmt = n => Number(n).toLocaleString("pt-BR")
    const el = id => document.getElementById(id)
    const MAP_ZOOM = 5
    const MA_DIAS = 7

    const state = { periodo: "30d", nivel: "uf", serieSel: "brasil:BR", serieChart: null, carregado: false }

    async function getJSON(url) {
        try {
            const r = await fetch(url)
            return r.ok ? await r.json() : null
        } catch { return null }
    }

    function limpar(node) { while (node.firstChild) node.removeChild(node.firstChild) }

    function mensagem(node, texto) {
        limpar(node)
        const d = document.createElement("div")
        d.className = "br-empty"
        d.textContent = texto
        node.appendChild(d)
    }

    function badge(item) {
        const b = document.createElement("span")
        b.className = "br-badge"
        if (!item || item.variacao_pct == null) {
            b.textContent = "sem base histórica"
            return b
        }
        const v = item.variacao_pct
        b.textContent = `${v > 0 ? "+" : ""}${String(v).replace(".", ",")}% vs média`
        if (item.situacao === "acima" || item.situacao === "abaixo") b.classList.add(item.situacao)
        return b
    }

    function dataBR(iso) {
        if (!iso) return "—"
        return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })
    }

    // ── Status da fonte ──────────────────────────────────────────────
    function renderStatus(status, resumo) {
        const box = el("br-status")
        limpar(box)
        const add = (txt, cls) => {
            const s = document.createElement("span")
            if (cls) s.className = cls
            s.textContent = txt
            box.appendChild(s)
        }
        add("Fonte: INPE · Programa Queimadas")
        add("Satélite de referência: AQUA_M-T")
        const f = status && status.fontes && status.fontes[0]
        if (!f || !f.ultima_coleta_ok) { add("⚠ Coleta ainda não registrada", "br-warn"); return }
        add(`Última coleta: ${dataBR(f.ultima_coleta_ok)}`)
        if (f.defasada) add(`⚠ Dados defasados (${f.defasagem_horas} h sem coleta)`, "br-warn")
        if (resumo && resumo.janela) add(`Comparações até ${resumo.janela.fim.split("-").reverse().join("/")}`)
    }

    // ── Cards ────────────────────────────────────────────────────────
    function setCard(prefix, valor, sub, item) {
        const v = el(`${prefix}-valor`)
        v.textContent = valor == null ? "—" : fmt(valor)
        const s = el(`${prefix}-sub`)
        limpar(s)
        if (item) s.appendChild(badge(item))
        if (sub) {
            const t = document.createElement("div")
            t.textContent = sub
            s.appendChild(t)
        }
    }

    function renderCards(dia, mes, resumo24) {
        const b1 = dia && dia.itens.find(i => i.codigo === "BR")
        const b30 = mes && mes.itens.find(i => i.codigo === "BR")
        setCard("br-c1", b1 ? b1.focos : null,
            b1 ? `Último dia completo (${dia.janela.fim.split("-").reverse().join("/")}) · média histórica ${b1.media_historica == null ? "—" : fmt(b1.media_historica)}/dia` : "Dado indisponível", b1)
        setCard("br-c2", b30 ? b30.focos : null,
            b30 ? `Últimos 30 dias · média histórica ${b30.media_historica == null ? "—" : fmt(Math.round(b30.media_historica * 30))}` : "Dado indisponível", b30)
        const u = resumo24 || (mes && mes.ultimas_24h)
        setCard("br-c3", u ? u.total : null,
            u ? `Todos os satélites · ${fmt(u.referencia)} pelo de referência` : "Dado indisponível", null)
    }

    // ── Ranking ──────────────────────────────────────────────────────
    function renderRanking(resumo) {
        const box = el("br-rank")
        limpar(box)
        if (!resumo || !resumo.itens.length) { mensagem(box, "Sem dados para o período."); return }
        const itens = resumo.itens.slice(0, state.nivel === "uf" ? 10 : 6)
        const max = Math.max(...itens.map(i => i.focos), 1)
        itens.forEach(i => {
            const li = document.createElement("li")
            const nome = document.createElement("span")
            nome.className = "br-rank-nome"
            nome.textContent = i.nome
            const bar = document.createElement("span")
            bar.className = "br-rank-bar"
            const fill = document.createElement("span")
            fill.style.width = `${Math.max(2, (i.focos / max) * 100)}%`
            bar.appendChild(fill)
            const num = document.createElement("span")
            num.className = "br-rank-num"
            num.textContent = `${fmt(i.focos)} `
            num.appendChild(badge(i))
            li.append(nome, bar, num)
            box.appendChild(li)
        })
    }

    async function carregarRanking() {
        const box = el("br-rank")
        mensagem(box, "Carregando…")
        const r = await getJSON(`${API}/focos/resumo?nivel=${state.nivel}&periodo=${state.periodo}`)
        if (!r) { mensagem(box, "Dado indisponível no momento."); return }
        renderRanking(r)
    }

    // ── Série ────────────────────────────────────────────────────────
    function mediaMovel(valores) {
        return valores.map((_, i) => {
            if (i < MA_DIAS - 1) return null
            const janela = valores.slice(i - MA_DIAS + 1, i + 1).filter(v => v != null)
            return janela.length ? janela.reduce((a, b) => a + b, 0) / janela.length : null
        })
    }

    function renderSerie(s) {
        const canvas = el("br-serie-chart")
        const msg = el("br-serie-msg")
        if (state.serieChart) { state.serieChart.destroy(); state.serieChart = null }
        if (!s || !s.pontos.length) { mensagem(msg, "Dado indisponível no momento."); canvas.style.display = "none"; return }
        limpar(msg)
        canvas.style.display = ""
        const p = s.pontos
        const rotulos = p.map(x => x.data.slice(5).split("-").reverse().join("/"))
        const atual = mediaMovel(p.map(x => x.focos))
        const media = mediaMovel(p.map(x => x.media_historica))
        const sup = mediaMovel(p.map(x => x.media_historica == null ? null : x.media_historica + x.desvio))
        const inf = mediaMovel(p.map(x => x.media_historica == null ? null : Math.max(0, x.media_historica - x.desvio)))
        state.serieChart = new Chart(canvas, {
            type: "line",
            data: {
                labels: rotulos,
                datasets: [
                    { label: "Faixa ±1 desvio", data: sup, borderWidth: 0, pointRadius: 0, fill: "+1", backgroundColor: "rgba(142,162,190,.12)" },
                    { label: "_inf", data: inf, borderWidth: 0, pointRadius: 0, fill: false },
                    { label: "Média histórica (2003–ano anterior)", data: media, borderColor: "#8EA2BE", borderDash: [5, 4], borderWidth: 1.5, pointRadius: 0, fill: false },
                    { label: "Últimos 12 meses", data: atual, borderColor: "#FFA726", borderWidth: 2, pointRadius: 0, tension: .25, fill: false },
                ],
            },
            options: {
                responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { labels: { color: "#8EA2BE", filter: i => !i.text.startsWith("_") && i.text !== "Faixa ±1 desvio" } },
                    tooltip: { filter: i => !i.dataset.label.startsWith("_") && i.dataset.label !== "Faixa ±1 desvio" },
                },
                scales: {
                    x: { ticks: { color: "#546A84", maxTicksLimit: 12 }, grid: { display: false } },
                    y: { beginAtZero: true, ticks: { color: "#546A84" }, grid: { color: "rgba(255,255,255,.05)" },
                         title: { display: true, text: "focos/dia (média móvel 7 d)", color: "#546A84" } },
                },
            },
        })
    }

    async function carregarSerie() {
        const [nivel, codigo] = state.serieSel.split(":")
        mensagem(el("br-serie-msg"), "Carregando…")
        renderSerie(await getJSON(`${API}/focos/serie?nivel=${encodeURIComponent(nivel)}&codigo=${encodeURIComponent(codigo)}&periodo=365d`))
    }

    function popularSeletor(resumoUF, resumoBioma) {
        const sel = el("br-serie-sel")
        limpar(sel)
        const grupo = (rotulo, itens, nivel) => {
            const g = document.createElement("optgroup")
            g.label = rotulo
            itens.forEach(i => {
                const o = document.createElement("option")
                o.value = `${nivel}:${i.codigo}`
                o.textContent = i.nome
                g.appendChild(o)
            })
            sel.appendChild(g)
        }
        const br = document.createElement("option")
        br.value = "brasil:BR"
        br.textContent = "Brasil"
        sel.appendChild(br)
        if (resumoBioma) grupo("Biomas", resumoBioma.itens, "bioma")
        if (resumoUF) grupo("Estados", [...resumoUF.itens].sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR")), "uf")
        sel.value = state.serieSel
    }

    // ── Mapa ─────────────────────────────────────────────────────────
    async function renderMapa() {
        const box = el("br-map-wrap")
        const [dados, world] = await Promise.all([
            getJSON(`${API}/focos/mapa?periodo=7d&zoom=${MAP_ZOOM}`),
            d3.json("/world-110m.json").catch(() => null),
        ])
        if (!dados || !world) { mensagem(box, "Mapa indisponível no momento."); return }
        limpar(box)
        const brasil = topojson.feature(world, world.objects.countries).features.find(f => String(f.id) === "076")
        const W = 600, H = 600
        const svg = d3.select(box).append("svg").attr("class", "br-map").attr("viewBox", `0 0 ${W} ${H}`)
            .attr("role", "img").attr("aria-label", "Mapa de focos de calor no Brasil nos últimos 7 dias")
        const proj = d3.geoMercator().fitExtent([[10, 10], [W - 10, H - 10]], brasil)
        svg.append("path").datum(brasil).attr("d", d3.geoPath(proj))
            .attr("fill", "#132436").attr("stroke", "rgba(255,255,255,.18)")
        const max = d3.max(dados.itens, d => d.n) || 1
        const raio = d3.scaleSqrt().domain([1, max]).range([1.6, 11])
        const cor = d3.scaleSequentialLog(d3.interpolateYlOrRd).domain([1, max])
        svg.append("g").selectAll("circle").data([...dados.itens].sort((a, b) => a.n - b.n)).join("circle")
            .attr("cx", d => proj([d.lon, d.lat])[0]).attr("cy", d => proj([d.lon, d.lat])[1])
            .attr("r", d => raio(d.n)).attr("fill", d => cor(d.n)).attr("fill-opacity", .72)
            .append("title").text(d => `${fmt(d.n)} foco(s)${d.frp_max ? ` · FRP máx. ${d.frp_max} MW` : ""}`)
        const lg = document.createElement("div")
        lg.className = "br-legend"
        lg.textContent = `Últimos 7 dias · todos os satélites · células de ${dados.celula_graus}° · círculo maior = mais focos`
        box.appendChild(lg)
    }

    // ── Clima global (lado a lado, sem afirmar relação) ─────────────
    async function renderGlobal() {
        const [enso, iod, mjo] = await Promise.all(
            ["/climate/status", "/climate/iod", "/climate/mjo"].map(getJSON))
        const set = (id, valor, sub) => {
            const n = el(id)
            limpar(n)
            const v = document.createElement("div")
            v.className = "br-value"
            v.textContent = valor || "—"
            const s = document.createElement("div")
            s.className = "br-card-sub"
            s.textContent = sub || "Dado indisponível"
            n.append(v, s)
        }
        set("br-g-enso", enso && enso.fase, enso && `ONI ${enso.oni} · Niño 3.4 ${enso.nino34} °C`)
        set("br-g-iod", iod && iod.fase, iod && `DMI ${iod.dmi} · ${iod.data_referencia}`)
        set("br-g-mjo", mjo && `Fase ${mjo.phase}`, mjo && `Amplitude ${mjo.amplitude} · ${mjo.fase}`)
    }

    // ── Controles ────────────────────────────────────────────────────
    function ligarControles() {
        document.querySelectorAll("[data-br-periodo]").forEach(b => b.addEventListener("click", () => {
            state.periodo = b.dataset.brPeriodo
            document.querySelectorAll("[data-br-periodo]").forEach(x => x.classList.toggle("active", x === b))
            carregarRanking()
        }))
        document.querySelectorAll("[data-br-nivel]").forEach(b => b.addEventListener("click", () => {
            state.nivel = b.dataset.brNivel
            document.querySelectorAll("[data-br-nivel]").forEach(x => x.classList.toggle("active", x === b))
            carregarRanking()
        }))
        el("br-serie-sel").addEventListener("change", e => { state.serieSel = e.target.value; carregarSerie() })
    }

    async function carregar() {
        if (state.carregado) return
        state.carregado = true
        ligarControles()
        const [status, dia, mes, uf, bioma] = await Promise.all([
            getJSON(`${API}/status`),
            getJSON(`${API}/focos/resumo?nivel=brasil&periodo=24h`),
            getJSON(`${API}/focos/resumo?nivel=brasil&periodo=30d`),
            getJSON(`${API}/focos/resumo?nivel=uf&periodo=30d`),
            getJSON(`${API}/focos/resumo?nivel=bioma&periodo=30d`),
        ])
        renderStatus(status, mes)
        renderCards(dia, mes, null)
        popularSeletor(uf, bioma)
        renderRanking(uf)
        carregarSerie()
        renderMapa()
        renderGlobal()
    }

    const aba = document.querySelector('[data-tab="brasil"]')
    if (aba) aba.addEventListener("click", carregar)
    window.carregarBrasil = carregar
})()
