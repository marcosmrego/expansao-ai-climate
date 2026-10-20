"""Carga histórica de focos de calor (INPE).

1. 2003..(ano-1): CSV anual do satélite de referência -> fire_daily_agg
2. Meses fechados do ano corrente: CSV mensal, só satélite de referência -> fire_daily_agg
3. Mês corrente: CSV diário; pontos de referência de todos os dias e de todos os
   satélites dos últimos dias -> fire_hotspot, depois reagrega os dias

Idempotente: pode ser repetido. Uso (na raiz do projeto):
    PYTHONPATH=. python scripts/backfill_inpe_fire.py [--ano-inicial 2003]
"""
import argparse
import logging
from datetime import date, datetime, timedelta, timezone

from collector import inpe_fire_collector as inpe
from collector.run_log import finalizar_execucao, iniciar_execucao
from database.db import conectar

logger = logging.getLogger("backfill_inpe")
ANO_INICIAL_REF = 2003
RUN_FONTE = "inpe_focos_backfill"


def _carregar_anos_fechados(conn, ano_inicial: int, ano_atual: int) -> int:
    total = 0
    for ano in range(ano_inicial, ano_atual):
        linhas = inpe.linhas_zip_anual(ano)
        if linhas is None:
            logger.warning("Sem arquivo anual para %s; usando os mensais", ano)
            total += _carregar_meses_fechados(conn, ano, 13)
            continue
        n = inpe.gravar_agregados(conn, inpe.agregar_anual_ref(linhas))
        conn.commit()
        logger.info("%s: %s agregados", ano, n)
        total += n
    return total


def _carregar_meses_fechados(conn, ano: int, mes_atual: int) -> int:
    total = 0
    for mes in range(1, mes_atual):
        linhas = inpe.abrir_linhas(inpe.url_mensal(ano, mes))
        if linhas is None:
            raise RuntimeError(f"Arquivo mensal ausente: {ano}-{mes:02d}")
        n = inpe.gravar_agregados(conn, inpe.agregar_focos(inpe.parse_focos(linhas)))
        conn.commit()
        logger.info("%s-%02d: %s agregados", ano, mes, n)
        total += n
    return total


def _carregar_mes_corrente(conn, hoje: date) -> int:
    total = 0
    corte_todos = hoje - timedelta(days=inpe.RETENCAO_NAO_REF_DIAS)
    dias = [date(hoje.year, hoje.month, 1) + timedelta(days=n) for n in range(hoje.day)]
    for dia in dias:
        linhas = inpe.abrir_linhas(inpe.url_diario(dia))
        if linhas is None:
            continue
        focos = [f for f in inpe.parse_focos(linhas) if f.is_ref or dia >= corte_todos]
        total += inpe.inserir_focos(conn, focos)
        conn.commit()
    inpe.reagregar_dias(conn, dias)
    conn.commit()
    return total


def main(ano_inicial: int) -> None:
    hoje = datetime.now(timezone.utc).date()
    conn = conectar()
    run_id = iniciar_execucao(conn, RUN_FONTE, date(ano_inicial, 1, 1), hoje)
    try:
        total = _carregar_anos_fechados(conn, ano_inicial, hoje.year)
        total += _carregar_meses_fechados(conn, hoje.year, hoje.month)
        total += _carregar_mes_corrente(conn, hoje)
    except Exception as e:
        conn.rollback()
        finalizar_execucao(conn, run_id, erro=f"{type(e).__name__}: {e}")
        raise
    else:
        finalizar_execucao(conn, run_id, registros=total)
    finally:
        conn.close()
    logger.info("Backfill concluído: %s registros", total)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ano-inicial", type=int, default=ANO_INICIAL_REF)
    main(parser.parse_args().ano_inicial)
