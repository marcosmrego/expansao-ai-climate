"""Desmatamento (DETER): resumo por período, acumulado do ano PRODES, série mensal e últimos alertas."""
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from app.core.cache import TTLCache
from app.services import brasil_deforestation_calc as dc
from database.db import conectar

CACHE_TTL_S = 600
STATEMENT_TIMEOUT_MS = 8000
LIMITE_ALERTAS_MAX = 200
MESES_SERIE_MAX = 120
SEM_UF = "N/D"

cache = TTLCache(ttl=CACHE_TTL_S, max_entries=128)
cache_alertas = TTLCache(ttl=CACHE_TTL_S, max_entries=64)  # separado: combinações de filtros não expulsam o resumo
_FUSO = ZoneInfo("America/Sao_Paulo")

_AVISO_EXPERIMENTAL = (
    "Dado experimental, segundo o INPE: não use como definitivo."
)
_METODOLOGIA = (
    "Alertas DETER (INPE/TerraBrasilis). 'Desmatamento' soma as classes DESMATAMENTO_* (corte raso e com "
    "vegetação) e MINERACAO; degradação, corte seletivo e cicatriz de queimada aparecem separados. O ano PRODES vai de 1º de agosto "
    "a 31 de julho. Alertas não são a taxa oficial anual (PRODES) e podem ser reclassificados."
)
_GRUPOS_DESMAT = sorted(dc.GRUPOS_DESMATAMENTO)
_PRODES_DE = {"deter-amz": "prodes-amazonia", "deter-cerrado": "prodes-cerrado"}
_METODOLOGIA_PRODES = (
    "Soma anual dos polígonos de desmatamento publicados pelo PRODES (INPE/TerraBrasilis), sem estimativa para "
    "áreas com nuvem. Pode diferir da taxa oficial divulgada pelo INPE, e o último ano pode estar parcial. O ano PRODES vai de 1º de agosto a 31 de julho."
)


def _hoje(agora: Optional[datetime] = None) -> date:
    return (agora or datetime.now(_FUSO)).date()


def _com_conexao(fn):
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = %s", (STATEMENT_TIMEOUT_MS,))
        return fn(conn)
    finally:
        conn.close()


def invalidar_cache() -> None:
    cache.clear()
    cache_alertas.clear()


def inicio_periodo(hoje: date, periodo: str) -> date:
    """Primeiro dia de uma janela de N dias que termina em `hoje` (inclusive)."""
    return hoje - timedelta(days=dc.PERIODOS_ALERTAS[periodo] - 1)


def _validar_projeto(projeto: str) -> None:
    if projeto not in dc.PROJETOS_DETER:
        raise ValueError(f"projeto deve ser um de {', '.join(dc.PROJETOS_DETER)}")


def _km2(valor) -> float:
    return round(float(valor or 0), 2)


# ── Montagem (pura) ───────────────────────────────────────────────────────────

def _bloco_prodes(hoje: date, primeira_data: Optional[date], atual, anterior) -> dict:
    ano = dc.ano_prodes(hoje)
    inicio, _ = dc.janela_prodes(ano)
    inicio_anterior, _ = dc.janela_prodes(ano - 1)
    historico_completo = primeira_data is not None and primeira_data <= inicio_anterior
    acumulado, acumulado_anterior = _km2(atual), _km2(anterior)
    comparavel = historico_completo and acumulado_anterior > 0
    return {
        "ano": ano, "inicio": inicio.isoformat(), "ate": hoje.isoformat(), "acumulado_km2": acumulado,
        "anterior": {"ano": ano - 1, "acumulado_km2": acumulado_anterior,
                     "ate": dc.um_ano_antes(hoje).isoformat()} if historico_completo else None,
        "variacao_pct": round((acumulado - acumulado_anterior) / acumulado_anterior * 100, 1) if comparavel else None,
    }


def montar_resumo(projeto: str, periodo: str, hoje: date, ultima_data: Optional[date],
                  primeira_data: Optional[date], por_grupo: list, por_uf: list,
                  acumulado_atual, acumulado_anterior) -> dict:
    if periodo not in dc.PERIODOS_ALERTAS:
        raise ValueError(f"período deve ser um de {', '.join(dc.PERIODOS_ALERTAS)}")
    experimental = dc.experimental(projeto)
    return {
        "projeto": projeto, "projeto_nome": dc.PROJETO_NOMES[projeto], "periodo": periodo,
        "inicio": inicio_periodo(hoje, periodo).isoformat(), "fim": hoje.isoformat(),
        "dados_ate": ultima_data.isoformat() if ultima_data else None,
        "dias_defasagem": max(0, (hoje - ultima_data).days) if ultima_data else None,
        "experimental": experimental, "aviso_experimental": _AVISO_EXPERIMENTAL if experimental else None,
        "desmatamento_km2": _km2(sum(a for g, a, _ in por_grupo if g in dc.GRUPOS_DESMATAMENTO)),
        "desmatamento_alertas": sum(n for g, _, n in por_grupo if g in dc.GRUPOS_DESMATAMENTO),
        "por_grupo": [{"grupo": g, "nome": dc.GRUPO_NOMES.get(g, g), "area_km2": _km2(a), "alertas": n}
                      for g, a, n in por_grupo],
        "por_uf": [{"uf": uf or SEM_UF, "area_km2": _km2(a), "alertas": n} for uf, a, n in por_uf],
        "ano_prodes": _bloco_prodes(hoje, primeira_data, acumulado_atual, acumulado_anterior),
        "metodologia": _METODOLOGIA,
    }


def montar_serie(linhas: list, hoje: date, meses: int) -> list[dict]:
    """Série mensal contínua (meses sem alerta valem zero), terminando no mês de `hoje`."""
    por_mes = {(d.year, d.month): (a, n) for d, a, n in linhas}
    ano, mes = hoje.year, hoje.month
    chaves = []
    for _ in range(meses):
        chaves.append((ano, mes))
        ano, mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    return [{"mes": f"{a}-{m:02d}", "area_km2": _km2(por_mes.get((a, m), (0, 0))[0]),
             "alertas": por_mes.get((a, m), (0, 0))[1]} for a, m in reversed(chaves)]


# ── Consultas ─────────────────────────────────────────────────────────────────

def _consultar_resumo(conn, projeto: str, inicio: date, hoje: date) -> dict:
    ano = dc.ano_prodes(hoje)
    inicio_prodes, _ = dc.janela_prodes(ano)
    inicio_anterior, _ = dc.janela_prodes(ano - 1)
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(data_alerta), MIN(data_alerta) FROM climate.deforestation_alert WHERE projeto = %s",
                    (projeto,))
        ultima, primeira = cur.fetchone()
        cur.execute(
            """SELECT grupo, SUM(area_km2), COUNT(*) FROM climate.deforestation_alert
                WHERE projeto = %s AND data_alerta BETWEEN %s AND %s
                GROUP BY grupo ORDER BY SUM(area_km2) DESC""",
            (projeto, inicio, hoje))
        por_grupo = cur.fetchall()
        cur.execute(
            """SELECT uf, SUM(area_km2), COUNT(*) FROM climate.deforestation_alert
                WHERE projeto = %s AND grupo = ANY(%s) AND data_alerta BETWEEN %s AND %s
                GROUP BY uf ORDER BY SUM(area_km2) DESC""",
            (projeto, _GRUPOS_DESMAT, inicio, hoje))
        por_uf = cur.fetchall()
        cur.execute(
            """SELECT COALESCE(SUM(area_km2) FILTER (WHERE data_alerta BETWEEN %s AND %s), 0),
                      COALESCE(SUM(area_km2) FILTER (WHERE data_alerta BETWEEN %s AND %s), 0)
                 FROM climate.deforestation_alert WHERE projeto = %s AND grupo = ANY(%s)""",
            (inicio_prodes, hoje, inicio_anterior, dc.um_ano_antes(hoje), projeto, _GRUPOS_DESMAT))
        atual, anterior = cur.fetchone()
    return {"ultima_data": ultima, "primeira_data": primeira, "por_grupo": por_grupo, "por_uf": por_uf,
            "acumulado_atual": atual, "acumulado_anterior": anterior}


def resumo(projeto: str, periodo: str, agora: Optional[datetime] = None) -> dict:
    _validar_projeto(projeto)
    if periodo not in dc.PERIODOS_ALERTAS:
        raise ValueError(f"período deve ser um de {', '.join(dc.PERIODOS_ALERTAS)}")
    hoje = _hoje(agora)
    chave = f"resumo:{projeto}:{periodo}:{hoje}"
    if (hit := cache.get(chave)) is not None:
        return hit
    inicio = inicio_periodo(hoje, periodo)
    bruto = _com_conexao(lambda conn: _consultar_resumo(conn, projeto, inicio, hoje))
    resultado = montar_resumo(projeto, periodo, hoje, **bruto)
    cache.set(chave, resultado)
    return resultado


def serie(projeto: str, meses: int, agora: Optional[datetime] = None) -> dict:
    _validar_projeto(projeto)
    meses = max(1, min(meses, MESES_SERIE_MAX))
    hoje = _hoje(agora)
    chave = f"serie:{projeto}:{meses}:{hoje}"
    if (hit := cache.get(chave)) is not None:
        return hit
    primeiro_mes = _recuar_meses(hoje, meses - 1)

    def _run(conn):
        with conn.cursor() as cur:
            cur.execute(
                """SELECT date_trunc('month', data_alerta)::date, SUM(area_km2), COUNT(*)
                     FROM climate.deforestation_alert
                    WHERE projeto = %s AND grupo = ANY(%s) AND data_alerta BETWEEN %s AND %s
                    GROUP BY 1 ORDER BY 1""",
                (projeto, _GRUPOS_DESMAT, primeiro_mes, hoje))
            return cur.fetchall()

    resultado = {"projeto": projeto, "projeto_nome": dc.PROJETO_NOMES[projeto],
                 "experimental": dc.experimental(projeto),
                 "pontos": montar_serie(_com_conexao(_run), hoje, meses), "metodologia": _METODOLOGIA}
    cache.set(chave, resultado)
    return resultado


def _recuar_meses(dia: date, meses: int) -> date:
    total = dia.year * 12 + dia.month - 1 - meses
    return date(total // 12, total % 12 + 1, 1)


def montar_taxas(projeto: str, linhas: list) -> dict:
    """linhas: (ano_prodes, recorte, area_km2); recorte é TOTAL ou a sigla da UF."""
    totais = sorted((a, v) for a, r, v in linhas if r == "TOTAL")
    ultimo = totais[-1][0] if totais else None
    ranking = sorted(((r, v) for a, r, v in linhas if a == ultimo and r != "TOTAL"), key=lambda x: -x[1])
    variacao = None
    if len(totais) >= 2 and totais[-2][0] == ultimo - 1 and totais[-2][1] > 0:
        variacao = round((totais[-1][1] - totais[-2][1]) / totais[-2][1] * 100, 1)
    return {"projeto": projeto, "fonte": dc.PROJETO_NOMES[_PRODES_DE[projeto]],
            "anos": [{"ano": a, "area_km2": _km2(v)} for a, v in totais], "ultimo_ano": ultimo,
            "por_uf": [{"uf": r, "area_km2": _km2(v)} for r, v in ranking], "variacao_pct": variacao,
            "metodologia": _METODOLOGIA_PRODES}


def taxas(projeto: str) -> dict:
    _validar_projeto(projeto)
    chave = f"taxas:{projeto}"
    if (hit := cache.get(chave)) is not None:
        return hit

    def _run(conn):
        with conn.cursor() as cur:
            cur.execute("""SELECT ano_prodes, recorte, area_km2 FROM climate.deforestation_rate
                            WHERE projeto = %s""", (_PRODES_DE[projeto],))
            return cur.fetchall()

    resultado = montar_taxas(projeto, _com_conexao(_run))
    cache.set(chave, resultado)
    return resultado


def ultimos_alertas(projeto: str, periodo: str, uf: Optional[str], grupo: Optional[str],
                    limite: int, agora: Optional[datetime] = None) -> dict:
    _validar_projeto(projeto)
    if periodo not in dc.PERIODOS_ALERTAS:
        raise ValueError(f"período deve ser um de {', '.join(dc.PERIODOS_ALERTAS)}")
    limite = max(1, min(limite, LIMITE_ALERTAS_MAX))
    hoje = _hoje(agora)
    chave = f"alertas:{projeto}:{periodo}:{uf}:{grupo}:{limite}:{hoje}"
    if (hit := cache_alertas.get(chave)) is not None:
        return hit
    inicio = inicio_periodo(hoje, periodo)

    def _run(conn):
        with conn.cursor() as cur:
            cur.execute(
                """SELECT data_alerta, classe, grupo, area_km2, uf, municipio, experimental
                     FROM climate.deforestation_alert
                    WHERE projeto = %s AND data_alerta BETWEEN %s AND %s
                      AND (%s::text IS NULL OR uf = %s) AND (%s::text IS NULL OR grupo = %s)
                    ORDER BY data_alerta DESC, area_km2 DESC LIMIT %s""",
                (projeto, inicio, hoje, uf, uf, grupo, grupo, limite))
            return cur.fetchall()

    itens = [{"data": d.isoformat(), "classe": c, "grupo": g, "area_km2": round(float(a), 4), "uf": u,
              "municipio": m, "experimental": bool(e)} for d, c, g, a, u, m, e in _com_conexao(_run)]
    resultado = {"projeto": projeto, "periodo": periodo, "limite": limite, "itens": itens}
    cache_alertas.set(chave, resultado)
    return resultado
