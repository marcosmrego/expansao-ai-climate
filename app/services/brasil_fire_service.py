"""Consultas da área Brasil — focos de calor (leitura de fire_hotspot / fire_daily_agg)."""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from app.core.cache import TTLCache
from app.services import brasil_fire_calc as calc
from database.db import conectar

CACHE_TTL_S = 300
LIMITE_PONTOS_PADRAO = 3000
LIMITE_PONTOS_MAX = 10000
PERIODO_MAPA_MAX_DIAS = 14
STATUS_FONTES = {"inpe_focos": 3, "sar_reservatorios": 24, "deter_desmatamento": 24}  # fonte -> frequência esperada de coleta (horas)
FATOR_DEFASAGEM = 2
STATEMENT_TIMEOUT_MS = 8000
PRECISAO_BBOX_CACHE = 1

cache = TTLCache(ttl=CACHE_TTL_S)


def invalidar_cache() -> None:
    cache.clear()


def ultimo_dia_completo(agora: Optional[datetime] = None) -> date:
    """Dias UTC ainda em coleta não entram nas comparações; vale até ontem."""
    return (agora or datetime.now(timezone.utc)).date() - timedelta(days=1)


def _com_conexao(fn):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = %s", (STATEMENT_TIMEOUT_MS,))
        return fn(conn)
    finally:
        conn.close()


def _somas_atuais(cur, nivel: str, ini: date, fim: date) -> dict:
    cur.execute(
        """
        SELECT codigo, SUM(focos), COALESCE(SUM(frp_soma), 0)
          FROM climate.fire_daily_agg
         WHERE nivel = %s AND data BETWEEN %s AND %s
         GROUP BY codigo
        """,
        (nivel, ini, fim),
    )
    return {cod: (int(f), float(frp)) for cod, f, frp in cur.fetchall()}


def _anos_com_dados(cur) -> set:
    cur.execute("SELECT DISTINCT EXTRACT(YEAR FROM data)::int FROM climate.fire_daily_agg WHERE nivel = 'brasil'")
    return {a for (a,) in cur.fetchall()}


def _medias_base(cur, nivel: str, janelas: list, comprimento: int) -> dict:
    """codigo -> lista de médias diárias, uma por ano anterior com dados."""
    anos_ok = _anos_com_dados(cur)
    janelas = [j for j in janelas if j[2] in anos_ok]
    if not janelas:
        return {}
    cur.execute(
        """
        SELECT r.ano, a.codigo, SUM(a.focos)
          FROM unnest(%s::date[], %s::date[], %s::int[]) AS r(ini, fim, ano)
          JOIN climate.fire_daily_agg a
            ON a.nivel = %s AND a.data BETWEEN r.ini AND r.fim
         GROUP BY r.ano, a.codigo
        """,
        ([j[0] for j in janelas], [j[1] for j in janelas], [j[2] for j in janelas], nivel),
    )
    por_ano: dict = {}
    for ano, cod, soma in cur.fetchall():
        por_ano.setdefault(cod, {})[ano] = float(soma) / comprimento
    anos = [j[2] for j in janelas]
    return {cod: [vals.get(a, 0.0) for a in anos] for cod, vals in por_ano.items()}


def _linha_resumo(nivel: str, cod: str, focos: int, frp: float, dias: int, base: dict) -> dict:
    media = focos / dias
    return {
        "codigo": cod,
        "nome": calc.nome_codigo(nivel, cod),
        "focos": focos,
        "frp_soma": round(frp, 1),
        "media_diaria": round(media, 2),
        **calc.anomalia(media, base.get(cod, [])),
    }


def _contagem_24h(cur) -> dict:
    cur.execute(
        """
        SELECT COUNT(*), COUNT(*) FILTER (WHERE is_ref), MAX(detectado_em)
          FROM climate.fire_hotspot
         WHERE detectado_em >= NOW() - INTERVAL '24 hours'
        """
    )
    total, ref, ultimo = cur.fetchone()
    return {
        "total": total,
        "referencia": ref,
        "ultima_deteccao": ultimo.isoformat() if ultimo else None,
    }


_COLUNA_NIVEL = {"uf": "uf", "bioma": "bioma"}


def _ultimas_24h_por_codigo(cur, nivel: str) -> dict:
    coluna = _COLUNA_NIVEL.get(nivel)
    if coluna is None:
        return {}
    cur.execute(
        f"""
        SELECT {coluna}, COUNT(*), COUNT(*) FILTER (WHERE is_ref)
          FROM climate.fire_hotspot
         WHERE detectado_em >= NOW() - INTERVAL '24 hours' AND {coluna} IS NOT NULL
         GROUP BY 1
        """
    )
    return {cod: {"total": t, "referencia": r} for cod, t, r in cur.fetchall()}


def _bioma_predominante_por_uf(cur) -> dict:
    cur.execute(
        """
        SELECT DISTINCT ON (uf) uf, bioma FROM (
            SELECT uf, bioma, COUNT(*) AS n FROM climate.fire_hotspot
             WHERE detectado_em >= NOW() - INTERVAL '14 days'
               AND uf IS NOT NULL AND bioma IS NOT NULL
             GROUP BY uf, bioma
        ) t ORDER BY uf, n DESC
        """
    )
    return {uf: calc.nome_codigo("bioma", bioma) for uf, bioma in cur.fetchall()}


def _montar_itens(nivel: str, atuais: dict, base: dict, dias: int, extras: dict) -> list[dict]:
    """Todos os códigos do nível entram, com 0 focos quando não houve detecção."""
    itens = []
    for cod in calc.codigos_do_nivel(nivel):
        focos, frp = atuais.get(cod, (0, 0.0))
        item = _linha_resumo(nivel, cod, focos, frp, dias, base)
        item["ultimas_24h"] = extras["24h"].get(cod, {"total": 0, "referencia": 0})
        if nivel == "uf":
            item["bioma_predominante"] = extras["bioma"].get(cod)
        itens.append(item)
    itens.sort(key=lambda i: (-i["focos"], i["nome"]))
    return [{**item, "posicao": n} for n, item in enumerate(itens, start=1)]


def resumo(nivel: str, periodo: str, agora: Optional[datetime] = None) -> dict:
    dias = calc.parse_periodo(periodo)
    fim = ultimo_dia_completo(agora)
    ini = fim - timedelta(days=dias - 1)
    chave = f"resumo:{nivel}:{dias}:{fim}"
    if (hit := cache.get(chave)) is not None:
        return hit

    def _run(conn):
        with conn.cursor() as cur:
            atuais = _somas_atuais(cur, nivel, ini, fim)
            base = _medias_base(cur, nivel, calc.janelas_base(fim, dias), calc.comprimento_base(dias))
            ultimas = _contagem_24h(cur)
            extras = {
                "24h": _ultimas_24h_por_codigo(cur, nivel),
                "bioma": _bioma_predominante_por_uf(cur) if nivel == "uf" else {},
            }
        itens = _montar_itens(nivel, atuais, base, dias, extras)
        return {
            "nivel": nivel,
            "periodo": periodo,
            "janela": {"inicio": ini.isoformat(), "fim": fim.isoformat()},
            "itens": itens,
            "ultimas_24h": ultimas,
            "metodologia": _METODOLOGIA,
        }

    resultado = _com_conexao(_run)
    cache.set(chave, resultado)
    return resultado


_METODOLOGIA = (
    "Contagem do satélite de referência (AQUA_M-T), única série comparável desde 2003. "
    "Média histórica: mesmo período nos anos anteriores. Dias em coleta ficam de fora."
)


def serie(nivel: str, codigo: str, periodo: str, agora: Optional[datetime] = None) -> dict:
    dias = calc.parse_periodo(periodo)
    fim = ultimo_dia_completo(agora)
    ini = fim - timedelta(days=dias - 1)
    chave = f"serie:{nivel}:{codigo}:{dias}:{fim}"
    if (hit := cache.get(chave)) is not None:
        return hit

    def _run(conn):
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT data, focos FROM climate.fire_daily_agg
                 WHERE nivel = %s AND codigo = %s AND data BETWEEN %s AND %s
                """,
                (nivel, codigo, ini, fim),
            )
            atual = dict(cur.fetchall())
            base = _baseline_por_dia(cur, nivel, codigo, fim.year)
        pontos = []
        for n in range(dias):
            dia = ini + timedelta(days=n)
            media, desvio = base.get((dia.month, dia.day), (None, None))
            pontos.append({"data": dia.isoformat(), "focos": int(atual.get(dia, 0)),
                           "media_historica": media, "desvio": desvio})
        return {"nivel": nivel, "codigo": codigo, "nome": calc.nome_codigo(nivel, codigo),
                "periodo": periodo, "pontos": pontos, "metodologia": _METODOLOGIA}

    resultado = _com_conexao(_run)
    cache.set(chave, resultado)
    return resultado


def _baseline_por_dia(cur, nivel: str, codigo: str, ano_atual: int) -> dict:
    """(mês, dia) -> (média, desvio) nos anos anteriores; dia sem registro conta como zero."""
    cur.execute(
        """
        SELECT EXTRACT(MONTH FROM data)::int, EXTRACT(DAY FROM data)::int,
               SUM(focos), SUM(focos::bigint * focos)
          FROM climate.fire_daily_agg
         WHERE nivel = %s AND codigo = %s AND data >= %s AND data < %s
         GROUP BY 1, 2
        """,
        (nivel, codigo, date(calc.ANO_INICIAL_SERIE, 1, 1), date(ano_atual, 1, 1)),
    )
    n_anos = ano_atual - calc.ANO_INICIAL_SERIE
    if n_anos < calc.MIN_ANOS_BASE:
        return {}
    return {
        (mes, dia): (round(float(soma) / n_anos, 2),
                         round(calc.desvio_de_somas(float(soma), float(soma_q), n_anos), 2))
        for mes, dia, soma, soma_q in cur.fetchall()
    }


def mapa(periodo: str, bbox: Optional[tuple], zoom: int, limite: int, somente_ref: bool) -> dict:
    dias = min(calc.parse_periodo(periodo), PERIODO_MAPA_MAX_DIAS)
    limite = max(1, min(limite, LIMITE_PONTOS_MAX))
    bbox_chave = None if bbox is None else tuple(round(v, PRECISAO_BBOX_CACHE) for v in bbox)
    chave = f"mapa:{dias}:{bbox_chave}:{zoom}:{limite}:{somente_ref}"
    if (hit := cache.get(chave)) is not None:
        return hit

    celula = calc.celula_mapa(zoom)
    filtros, params = _filtros_mapa(dias, bbox, somente_ref)

    def _run(conn):
        with conn.cursor() as cur:
            if celula is None:
                return _pontos(cur, filtros, params, limite)
            return _celulas(cur, filtros, params, celula)

    resultado = _com_conexao(_run)
    resultado["periodo_dias"] = dias
    cache.set(chave, resultado)
    return resultado


def _filtros_mapa(dias: int, bbox: Optional[tuple], somente_ref: bool) -> tuple[str, list]:
    filtros = ["detectado_em >= NOW() - make_interval(days => %s)"]
    params: list = [dias]
    if somente_ref:
        filtros.append("is_ref")
    if bbox:
        filtros.append("longitude BETWEEN %s AND %s AND latitude BETWEEN %s AND %s")
        params += [bbox[0], bbox[2], bbox[1], bbox[3]]
    return " AND ".join(filtros), params


def _pontos(cur, filtros: str, params: list, limite: int) -> dict:
    cur.execute(
        f"""
        SELECT latitude, longitude, frp, satelite, detectado_em, municipio, uf
          FROM climate.fire_hotspot WHERE {filtros}
         ORDER BY detectado_em DESC LIMIT %s
        """,
        [*params, limite + 1],
    )
    linhas = cur.fetchall()
    itens = [
        {"lat": float(la), "lon": float(lo), "frp": None if frp is None else float(frp),
         "satelite": sat, "detectado_em": ts.isoformat(), "municipio": mun, "uf": uf}
        for la, lo, frp, sat, ts, mun, uf in linhas[:limite]
    ]
    return {"tipo": "pontos", "itens": itens, "truncado": len(linhas) > limite}


def _celulas(cur, filtros: str, params: list, celula: float) -> dict:
    cur.execute(
        f"""
        SELECT FLOOR(latitude / %s) * %s + %s / 2, FLOOR(longitude / %s) * %s + %s / 2,
               COUNT(*), MAX(frp)
          FROM climate.fire_hotspot WHERE {filtros}
         GROUP BY 1, 2
        """,
        [celula, celula, celula, celula, celula, celula, *params],
    )
    itens = [{"lat": float(la), "lon": float(lo), "n": n, "frp_max": None if f is None else float(f)}
             for la, lo, n, f in cur.fetchall()]
    return {"tipo": "celulas", "celula_graus": celula, "itens": itens, "truncado": False}


def status(agora: Optional[datetime] = None) -> dict:
    agora = agora or datetime.now(timezone.utc)

    def _run(conn):
        fontes = []
        with conn.cursor() as cur:
            for fonte, freq_h in STATUS_FONTES.items():
                fontes.append(_status_fonte(cur, fonte, freq_h, agora))
            cur.execute("SELECT MAX(detectado_em) FROM climate.fire_hotspot")
            ultimo = cur.fetchone()[0]
        return {"fontes": fontes, "ultima_deteccao": ultimo.isoformat() if ultimo else None}

    return _com_conexao(_run)


def _status_fonte(cur, fonte: str, freq_h: int, agora: datetime) -> dict:
    cur.execute(
        "SELECT MAX(fim) FROM climate.collector_run WHERE fonte = %s AND status = 'ok'",
        (fonte,),
    )
    ultimo_ok = cur.fetchone()[0]
    defasagem_h = None if ultimo_ok is None else round((agora - ultimo_ok).total_seconds() / 3600, 1)
    return {
        "fonte": fonte,
        "ultima_coleta_ok": ultimo_ok.isoformat() if ultimo_ok else None,
        "defasagem_horas": defasagem_h,
        "defasada": defasagem_h is None or defasagem_h > freq_h * FATOR_DEFASAGEM,
        "frequencia_esperada_horas": freq_h,
    }
