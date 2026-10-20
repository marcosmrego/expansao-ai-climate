"""Consultas da área Brasil — reservatórios (leitura de reservoir / reservoir_reading)."""
import unicodedata
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from app.core.cache import TTLCache
from app.services import brasil_fire_calc as fc
from app.services import brasil_reservoir_calc as rc
from database.db import conectar

CACHE_TTL_S = 300
STATEMENT_TIMEOUT_MS = 8000
JANELA_VARIACAO_DIAS = 30
TOLERANCIA_VARIACAO_DIAS = 5
LIMITE_LISTA_MAX = 200
PERIODOS_SERIE = ("1y", "2y", "5y", "10y")
ORDENS = ("volume", "-volume", "nome", "variacao", "-variacao")

cache = TTLCache(ttl=CACHE_TTL_S)
_SERIES_MAX_ENTRIES = 64
cache_series = TTLCache(ttl=CACHE_TTL_S, max_entries=_SERIES_MAX_ENTRIES)  # separado: séries não expulsam o snapshot
_FUSO = ZoneInfo("America/Sao_Paulo")

_SQL_SNAPSHOT = """
SELECT r.id, r.nome, r.sistema, r.uf, r.municipio, r.capacidade_hm3,
       cur.data, cur.volume_pct, prev.volume_pct
  FROM climate.reservoir r
  JOIN LATERAL (
        SELECT data, volume_pct FROM climate.reservoir_reading
         WHERE reservoir_id = r.id AND volume_pct IS NOT NULL AND data <= %(hoje)s
         ORDER BY data DESC LIMIT 1) cur ON TRUE
  LEFT JOIN LATERAL (
        SELECT volume_pct FROM climate.reservoir_reading
         WHERE reservoir_id = r.id AND volume_pct IS NOT NULL
           AND data BETWEEN cur.data - %(max)s AND cur.data - %(min)s
         ORDER BY ABS(data - (cur.data - %(alvo)s)), data DESC LIMIT 1) prev ON TRUE
 ORDER BY r.id
"""


def invalidar_cache() -> None:
    cache.clear()
    cache_series.clear()


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


def _float(v) -> Optional[float]:
    return None if v is None else float(v)


def _montar_item(linha: tuple, hoje: date) -> dict:
    rid, nome, sistema, uf, municipio, cap, data, pct, pct_prev = linha
    pct, pct_prev, cap = _float(pct), _float(pct_prev), _float(cap)
    variacao = rc.variacao_pp(pct, pct_prev)
    return {
        "id": rid, "nome": nome.strip(), "sistema": sistema, "uf": uf, "municipio": municipio,
        "capacidade_hm3": cap, "volume_pct": pct, "data_medicao": data.isoformat(),
        "dias_desde_medicao": (hoje - data).days,
        "recente": rc.recente(sistema, data, hoje),
        "faixa": rc.faixa_de(pct),
        "volume_pct_30d_atras": pct_prev,
        "variacao_30d_pp": None if variacao is None else round(variacao, 2),
    }


def _snapshot(hoje: date) -> list[dict]:
    chave = f"snapshot:{hoje}"
    if (hit := cache.get(chave)) is not None:
        return hit

    def _run(conn):
        with conn.cursor() as cur:
            cur.execute(_SQL_SNAPSHOT, {
                "hoje": hoje, "alvo": JANELA_VARIACAO_DIAS,
                "min": JANELA_VARIACAO_DIAS - TOLERANCIA_VARIACAO_DIAS,
                "max": JANELA_VARIACAO_DIAS + TOLERANCIA_VARIACAO_DIAS,
            })
            return cur.fetchall()

    itens = [_montar_item(l, hoje) for l in _com_conexao(_run)]
    cache.set(chave, itens)
    return itens


# ── Resumo por sistema ────────────────────────────────────────────────────────

def _resumo_sistema(sistema: str, itens: list[dict]) -> dict:
    do_sistema = [i for i in itens if i["sistema"] == sistema]
    recentes = [i for i in do_sistema if i["recente"]]
    media, metodo = rc.media_pct([(i["volume_pct"], i["capacidade_hm3"]) for i in recentes])
    com_prev = [i for i in recentes if i["volume_pct_30d_atras"] is not None]
    media_agora, _ = rc.media_pct([(i["volume_pct"], i["capacidade_hm3"]) for i in com_prev])
    media_antes, _ = rc.media_pct([(i["volume_pct_30d_atras"], i["capacidade_hm3"]) for i in com_prev])
    variacao = rc.variacao_pp(media_agora, media_antes)
    faixas = {nome: 0 for nome in (*(n for n, _ in rc.FAIXAS), rc.FAIXA_TOPO)}
    for i in recentes:
        faixas[i["faixa"]] += 1
    return {
        "sistema": sistema,
        "nome": rc.SISTEMA_NOMES[sistema],
        "total": len(do_sistema),
        "com_medicao_recente": len(recentes),
        "sem_medicao_recente": len(do_sistema) - len(recentes),
        "volume_pct_medio": None if media is None else round(media, 1),
        "metodo_media": metodo,
        "variacao_30d_pp": None if variacao is None else round(variacao, 1),
        "base_variacao": len(com_prev),
        "faixas": faixas,
        "data_mais_recente": max((i["data_medicao"] for i in do_sistema), default=None),
    }


def resumo(agora: Optional[datetime] = None) -> dict:
    hoje = _hoje(agora)
    itens = _snapshot(hoje)
    return {
        "sistemas": [_resumo_sistema(s, itens) for s in rc.SISTEMA_NOMES],
        "faixas": rc.FAIXA_NOMES,
        "metodologia": _METODOLOGIA,
    }


_METODOLOGIA = (
    "Volume útil (%) no SIN e volume (%) da capacidade nos demais sistemas, conforme a ANA (SAR). "
    "A média do sistema usa só reservatórios com medição recente e é ponderada pela capacidade "
    "quando todos têm capacidade informada. Variação: diferença em pontos percentuais para a "
    "medição de cerca de 30 dias antes."
)


# ── Lista ─────────────────────────────────────────────────────────────────────

def _nome_ordenavel(nome: str) -> str:
    base = unicodedata.normalize("NFKD", nome)
    return "".join(ch for ch in base if not unicodedata.combining(ch)).casefold()


def _chave_ordem(ordem: str):
    def _vol(i):
        return i["volume_pct"]

    def _var(i):
        return i["variacao_30d_pp"]
    return {"volume": _vol, "-volume": _vol, "variacao": _var, "-variacao": _var,
            "nome": lambda i: _nome_ordenavel(i["nome"])}[ordem]


def _filtrar(itens: list[dict], sistema: Optional[str], uf: Optional[str], faixa: Optional[str],
             q: Optional[str]) -> list[dict]:
    termo = _nome_ordenavel(q or "")
    return [
        i for i in itens
        if (not sistema or i["sistema"] == sistema)
        and (not uf or i["uf"] == uf)
        and (not faixa or i["faixa"] == faixa)
        and (not termo or termo in _nome_ordenavel(i["nome"]) or termo in _nome_ordenavel(i["municipio"] or ""))
    ]


def _ordenar(itens: list[dict], ordem: str) -> list[dict]:
    chave = _chave_ordem(ordem)
    desempate = lambda i: (_nome_ordenavel(i["nome"]), i["id"])  # ordem estável entre páginas
    com_valor = [i for i in itens if chave(i) is not None]
    sem_valor = sorted((i for i in itens if chave(i) is None), key=desempate)
    base = sorted(com_valor, key=desempate)
    return sorted(base, key=chave, reverse=ordem.startswith("-")) + sem_valor


def listar(sistema: Optional[str], uf: Optional[str], faixa: Optional[str], q: Optional[str],
           ordem: str, offset: int, limite: int, agora: Optional[datetime] = None) -> dict:
    filtrados = _filtrar(_snapshot(_hoje(agora)), sistema, uf, faixa, q)
    ordenados = _ordenar(filtrados, ordem)
    limite = max(1, min(limite, LIMITE_LISTA_MAX))
    return {"total": len(ordenados), "offset": offset, "limite": limite,
            "itens": ordenados[offset:offset + limite]}


# ── Série de um reservatório ──────────────────────────────────────────────────

def serie(reservatorio_id: int, periodo: str, agora: Optional[datetime] = None) -> Optional[dict]:
    dias = fc.parse_periodo(periodo)
    hoje = _hoje(agora)
    if reservatorio_id not in {i["id"] for i in _snapshot(hoje)}:
        return None  # evita consultar o banco por ids inexistentes
    chave = f"serie:{reservatorio_id}:{dias}:{hoje}"
    if (hit := cache_series.get(chave)) is not None:
        return hit

    def _run(conn):
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome, sistema, uf, municipio, capacidade_hm3 FROM climate.reservoir WHERE id = %s",
                        (reservatorio_id,))
            meta = cur.fetchone()
            if meta is None:
                return None
            cur.execute(
                """
                SELECT data, volume_pct, cota_m FROM climate.reservoir_reading
                 WHERE reservoir_id = %s AND data BETWEEN %s AND %s AND volume_pct IS NOT NULL
                 ORDER BY data
                """,
                (reservatorio_id, hoje - timedelta(days=dias), hoje),
            )
            return meta, cur.fetchall()

    achado = _com_conexao(_run)
    if achado is None:
        return None
    (rid, nome, sistema, uf, municipio, cap), linhas = achado
    resultado = {
        "id": rid, "nome": nome.strip(), "sistema": sistema, "sistema_nome": rc.SISTEMA_NOMES[sistema],
        "uf": uf, "municipio": municipio, "capacidade_hm3": _float(cap), "periodo": periodo,
        "pontos": [{"data": d.isoformat(), "volume_pct": float(p), "cota_m": _float(c)} for d, p, c in linhas],
        "metodologia": _METODOLOGIA,
    }
    cache_series.set(chave, resultado)
    return resultado
