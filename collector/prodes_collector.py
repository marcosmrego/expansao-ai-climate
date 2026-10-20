"""Desmatamento — INPE, TerraBrasilis, PRODES: soma anual dos polígonos publicados, por UF.

Só atributos (sem geometria). A fonte publica uma vez por ano, então o uso normal é a CLI:
    python -m collector.prodes_collector            # últimos anos
    python -m collector.prodes_collector --desde 2008   # histórico completo
A soma dos polígonos pode diferir da taxa oficial divulgada pelo INPE, que passa por estimativa.
"""
import argparse
import logging
import math
import time
from datetime import date
from typing import Iterable, Optional

from psycopg2.extras import execute_values

from collector.deter_collector import _consultar, hoje_local
from collector.run_log import finalizar_execucao, iniciar_execucao

logger = logging.getLogger(__name__)

RUN_FONTE = "prodes_desmatamento"
LOCK_COLETA_ID = 7_010_004
CAMADAS = {"prodes-amazonia": "prodes-legal-amz:yearly_deforestation",
           "prodes-cerrado": "prodes-cerrado-nb:yearly_deforestation"}
ANO_INICIAL = {"prodes-amazonia": 2008, "prodes-cerrado": 2001}
CAMPOS = "state,year,area_km,main_class"
CLASSE_DESMATAMENTO = "DESMATAMENTO"
TOTAL = "TOTAL"
ANOS_INCREMENTAIS = 3      # a fonte reconsolida os anos recentes
PAGE_SIZE = 10_000
_MAX_PAGINAS = 100
_AREA_MAX_KM2 = 100_000.0
_PAUSA_S = 3
_FRACAO_MAX_DESCARTADA = 0.01  # acima disso, o schema da fonte provavelmente mudou


def filtro_cql(ano: int) -> str:
    return f"year={ano}"


def anos_a_coletar(hoje: date, desde: Optional[int], projeto: str) -> list[int]:
    primeiro = max(desde, ANO_INICIAL[projeto]) if desde else hoje.year - ANOS_INCREMENTAIS + 1
    return list(range(primeiro, hoje.year + 1))


def _chave(feicao) -> Optional[tuple[int, str, float]]:
    p = feicao.get("properties") if isinstance(feicao, dict) else None
    if not isinstance(p, dict) or str(p.get("main_class") or "").upper() != CLASSE_DESMATAMENTO:
        return None
    ano, uf, area = p.get("year"), p.get("state"), p.get("area_km")
    if not (isinstance(ano, int) and not isinstance(ano, bool) and 1980 <= ano <= date.today().year + 1):
        return None
    if not (isinstance(uf, str) and len(uf) == 2 and uf.isalpha()):
        return None
    if isinstance(area, bool) or not isinstance(area, (int, float)) or not math.isfinite(area) or not 0 <= area <= _AREA_MAX_KM2:
        return None
    return ano, uf.upper(), float(area)


def _descartadas(feicoes: list) -> int:
    """Feições de desmatamento que `_chave` rejeitou (as demais classes são ignoradas de propósito)."""
    def _desmatamento(f):
        p = f.get("properties") if isinstance(f, dict) else None
        return isinstance(p, dict) and str(p.get("main_class") or "").upper() == CLASSE_DESMATAMENTO
    return sum(1 for f in feicoes if _desmatamento(f) and _chave(f) is None)


def agregar(feicoes: Iterable) -> dict[tuple[int, str], float]:
    """Área de desmatamento somada por (ano, UF); descarta o que não for utilizável."""
    soma: dict[tuple[int, str], float] = {}
    for feicao in feicoes:
        chave = _chave(feicao)
        if chave:
            ano, uf, area = chave
            soma[(ano, uf)] = soma.get((ano, uf), 0.0) + area
    return soma


def linhas(projeto: str, soma: dict[tuple[int, str], float]) -> list[tuple]:
    total: dict[int, float] = {}
    for (ano, _), area in soma.items():
        total[ano] = total.get(ano, 0.0) + area
    return ([(projeto, ano, TOTAL, round(a, 3)) for ano, a in total.items()]
            + [(projeto, ano, uf, round(a, 3)) for (ano, uf), a in soma.items()])


def _baixar_ano(projeto: str, ano: int) -> tuple[int, dict[tuple[int, str], float]]:
    """(feições recebidas, soma). Pagina por fid, que é estável entre páginas."""
    recebidas, descartadas, soma = 0, 0, {}
    for pagina in range(_MAX_PAGINAS):
        resposta = _consultar({
            "service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": CAMADAS[projeto],
            "outputFormat": "application/json", "propertyName": CAMPOS, "sortBy": "fid",
            "cql_filter": filtro_cql(ano), "count": PAGE_SIZE, "startIndex": pagina * PAGE_SIZE})
        try:
            dados = resposta.json()
            feicoes, esperadas = dados["features"], dados.get("numberMatched")
        except (ValueError, KeyError, TypeError, AttributeError):
            raise RuntimeError(f"{projeto} {ano}: resposta do WFS não é uma FeatureCollection")
        if not isinstance(feicoes, list):
            raise RuntimeError(f"{projeto} {ano}: resposta do WFS não é uma FeatureCollection")
        recebidas += len(feicoes)
        descartadas += _descartadas(feicoes)
        for chave, area in agregar(feicoes).items():
            soma[chave] = soma.get(chave, 0.0) + area
        if len(feicoes) < PAGE_SIZE:
            _conferir(projeto, ano, recebidas, esperadas, descartadas)
            return recebidas, soma
        time.sleep(_PAUSA_S)
    raise RuntimeError(f"{projeto} {ano}: paginação não terminou em {_MAX_PAGINAS} páginas")


def _conferir(projeto: str, ano: int, recebidas: int, esperadas, descartadas: int) -> None:
    """Falha alto se o servidor truncou a resposta ou se boa parte do desmatamento era inutilizável."""
    if isinstance(esperadas, int) and esperadas != recebidas:
        raise RuntimeError(f"{projeto} {ano}: {recebidas} feições recebidas de {esperadas}; resposta truncada?")
    if recebidas and descartadas / recebidas > _FRACAO_MAX_DESCARTADA:
        raise RuntimeError(f"{projeto} {ano}: {descartadas} de {recebidas} feições descartadas; schema alterado?")
    if descartadas:
        logger.warning("%s %s: %s feições de desmatamento descartadas", projeto, ano, descartadas)


def gravar_ano(conn, projeto: str, ano: int, soma: dict[tuple[int, str], float]) -> int:
    """Troca de uma vez os recortes do ano (uma UF que deixou de existir não fica para trás)."""
    registros = [r for r in linhas(projeto, soma) if r[1] == ano]
    with conn.cursor() as cur:
        cur.execute("DELETE FROM climate.deforestation_rate WHERE projeto = %s AND ano_prodes = %s", (projeto, ano))
        execute_values(cur, "INSERT INTO climate.deforestation_rate (projeto, ano_prodes, recorte, area_km2) VALUES %s",
                       registros)
    return len(registros)


def _processar_projeto(conn, projeto: str, hoje: date, desde: Optional[int]) -> int:
    total = 0
    for ano in anos_a_coletar(hoje, desde, projeto):
        recebidas, soma = _baixar_ano(projeto, ano)
        if not soma:
            if recebidas:
                raise RuntimeError(f"{projeto} {ano}: {recebidas} feições, nenhuma utilizável; schema alterado?")
            logger.info("%s %s: sem dados publicados", projeto, ano)
            continue
        total += gravar_ano(conn, projeto, ano, soma)
        conn.commit()
        logger.info("%s %s: %s km² em %s feições", projeto, ano, round(sum(soma.values()), 1), recebidas)
        time.sleep(_PAUSA_S)
    return total


def coletar(conn, hoje: Optional[date] = None, desde: Optional[int] = None) -> dict:
    hoje = hoje or hoje_local()
    with conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_COLETA_ID,))
        if not cur.fetchone()[0]:
            return {"registros": 0, "erros": [], "ignorado": "coleta já em andamento"}
    try:
        run_id = iniciar_execucao(conn, RUN_FONTE, None, hoje)
        total, erros = 0, []
        for projeto in CAMADAS:
            try:
                total += _processar_projeto(conn, projeto, hoje, desde)
            except Exception as e:
                conn.rollback()
                logger.exception("Falha na coleta %s", projeto)
                erros.append(f"{projeto}: {type(e).__name__}")
        finalizar_execucao(conn, run_id, registros=total, erro="; ".join(erros) if erros else None)
        return {"registros": total, "erros": erros}
    finally:
        try:
            conn.rollback()
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (LOCK_COLETA_ID,))
            conn.commit()
        except Exception:
            logger.warning("Não foi possível liberar o lock da coleta PRODES", exc_info=True)


if __name__ == "__main__":
    from database.db import conectar

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desde", type=int, default=None, help="ano inicial (ex.: 2008); padrão: últimos anos")
    args = parser.parse_args()
    conexao = conectar()
    try:
        print(coletar(conexao, desde=args.desde))
    finally:
        conexao.close()
