/* Aba Brasil — módulo Coletas: acompanha execuções dos coletores e o progresso das cargas longas. */
;(function () {
    const URL_EXECUCOES = "/api/brasil/coleta/execucoes"
    const INTERVALO_ATIVO_MS = 5000
    const INTERVALO_OCIOSO_MS = 60000
    const el = id => document.getElementById(id)
    const ESTADOS = {
        running: ["Em andamento", "sobe"], ok: ["Concluída", "estavel"],
        erro: ["Com erro", "desce"], parado: ["Sem sinal", "desce"],
    }
    const state = { carregado: false, timer: null, geracao: 0 }

    function criar(tag, classe, texto) {
        const n = document.createElement(tag)
        if (classe) n.className = classe
        if (texto != null) n.textContent = texto
        return n
    }

    function limpar(n) { while (n.firstChild) n.removeChild(n.firstChild) }

    async function getJSON(url) {
        try {
            const r = await fetch(url)
            return r.ok ? await r.json() : null
        } catch { return null }
    }

    function duracao(segundos) {
        if (segundos == null || segundos < 0) return "—"
        if (segundos < 90) return `${Math.round(segundos)} s`
        const min = Math.round(segundos / 60)
        if (min < 90) return `${min} min`
        const h = Math.floor(min / 60)
        return `${h} h ${String(min % 60).padStart(2, "0")} min`
    }

    function quando(iso) {
        if (!iso) return "—"
        const d = new Date(iso)
        return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })
    }

    function segundosDesde(iso) { return (Date.now() - new Date(iso).getTime()) / 1000 }

    // Estimativa só vale dentro do projeto atual: o total de etapas conta as janelas dele.
    function restante(e) {
        if (e.estado !== "running" || !e.etapas_feitas || e.etapas_feitas < 2 || e.etapas_feitas >= e.etapas_total) return null
        const decorrido = segundosDesde(e.inicio)
        return (decorrido / e.etapas_feitas) * (e.etapas_total - e.etapas_feitas)
    }

    function barra(e) {
        const caixa = criar("div", "co-barra")
        caixa.setAttribute("role", "progressbar")
        caixa.setAttribute("aria-valuemin", "0")
        caixa.setAttribute("aria-valuemax", "100")
        caixa.setAttribute("aria-valuenow", String(e.percentual))
        caixa.setAttribute("aria-label", `Progresso de ${e.rotulo}`)
        const preenchido = criar("span")
        preenchido.style.width = `${e.percentual}%`
        caixa.appendChild(preenchido)
        return caixa
    }

    function linhaProgresso(e) {
        const bloco = criar("div", "co-progresso")
        bloco.appendChild(barra(e))
        const faltam = restante(e)
        const partes = [`${e.etapa} · ${e.etapas_feitas}/${e.etapas_total} (${e.percentual.toLocaleString("pt-BR")}%)`]
        if (faltam != null) partes.push(`≈ ${duracao(faltam)} para concluir este projeto`)
        bloco.appendChild(criar("div", "co-detalhe", partes.join(" · ")))
        return bloco
    }

    function cartao(e) {
        const [rotulo, classe] = ESTADOS[e.estado] || [e.estado, "estavel"]
        const c = criar("article", `co-item co-${e.estado}`)
        const topo = criar("div", "co-topo")
        topo.appendChild(criar("strong", "co-nome", e.rotulo))
        topo.appendChild(criar("span", `br-badge ${classe}`, rotulo))
        c.appendChild(topo)
        if (e.percentual != null && (e.estado === "running" || e.estado === "parado")) c.appendChild(linhaProgresso(e))
        const meta = [`Início ${quando(e.inicio)}`]
        if (e.estado === "running") meta.push(`rodando há ${duracao(segundosDesde(e.inicio))}`, `último sinal há ${duracao(e.segundos_sem_sinal)}`)
        else if (e.estado === "parado") meta.push(`sem sinal há ${duracao(e.segundos_sem_sinal)}: o processo pode ter sido encerrado`)
        else if (e.fim) meta.push(`fim ${quando(e.fim)}`)
        if (e.registros != null) meta.push(`${e.registros.toLocaleString("pt-BR")} registros`)
        c.appendChild(criar("div", "co-detalhe", meta.join(" · ")))
        if (e.erro) c.appendChild(criar("div", "co-erro", e.erro))
        return c
    }

    function render(dados) {
        const lista = el("co-lista")
        limpar(lista)
        if (!dados || !dados.execucoes.length) {
            lista.appendChild(criar("div", "br-empty", dados ? "Nenhuma execução registrada." : "Não foi possível consultar as coletas."))
            return
        }
        dados.execucoes.forEach(e => lista.appendChild(cartao(e)))
        el("co-sub").textContent = dados.em_andamento ? "carga em andamento · atualiza a cada 5 s" : "atualiza a cada 60 s"
    }

    function moduloVisivel() {
        const m = el("br-mod-coletas")
        return !!m && !m.hidden && !document.hidden
    }

    async function atualizar() {
        clearTimeout(state.timer)
        const geracao = ++state.geracao
        const dados = await getJSON(URL_EXECUCOES)
        if (geracao !== state.geracao) return
        render(dados)
        if (!moduloVisivel()) return
        state.timer = setTimeout(atualizar, dados && dados.em_andamento ? INTERVALO_ATIVO_MS : INTERVALO_OCIOSO_MS)
    }

    function carregar() {
        if (!state.carregado) {
            state.carregado = true
            document.addEventListener("visibilitychange", () => { if (moduloVisivel()) atualizar() })
        }
        atualizar()
    }

    window.carregarColetas = carregar
})()
