"""Backfill do histórico de reservatórios (SIN e Nordeste) pelas páginas públicas do SAR/ANA.

A API oficial só entrega a última medição, então o histórico vem das páginas de
consulta do próprio SAR. Execução única, em ritmo educado (1 requisição por reservatório,
com pausa), identificando o projeto no User-Agent. Autorizado pelo autor em 2026-10-19.

Uso (na raiz do projeto):
    PYTHONPATH=. python scripts/backfill_sar_historico.py [--desde 2016-01-01] [--refazer]
"""
import argparse
import logging
import time
from datetime import date

from collector import sar_reservoir_collector as sar
from collector.run_log import finalizar_execucao, iniciar_execucao
from database.db import conectar

logger = logging.getLogger("backfill_sar")
RUN_FONTE = "sar_historico_backfill"
SISTEMAS_COM_PAGINA = ("SIN", "NORDESTE")
PAUSA_ENTRE_REQUISICOES_S = 1.5


def _reservatorios(conn, refazer: bool) -> list[tuple[int, str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT r.id, r.sistema, r.nome FROM climate.reservoir r
             WHERE r.sistema = ANY(%s)
               AND (%s OR NOT EXISTS (
                    SELECT 1 FROM climate.reservoir_reading l
                     WHERE l.reservoir_id = r.id AND l.fonte = %s))
             ORDER BY r.sistema, r.id
            """,
            (list(SISTEMAS_COM_PAGINA), refazer, sar.FONTE_PAGINA),
        )
        return cur.fetchall()


def main(desde: date, refazer: bool) -> None:
    hoje = sar.hoje_local()
    conn = conectar()
    run_id = iniciar_execucao(conn, RUN_FONTE, desde, hoje)
    total, falhas, sem_leituras = 0, [], []
    abortado = None
    try:
        alvos = _reservatorios(conn, refazer)
        if not alvos:
            logger.warning("Nenhum reservatório a carregar (a coleta diária já rodou?)")
        logger.info("%s reservatórios para carregar", len(alvos))
        for n, (rid, sistema, nome) in enumerate(alvos, start=1):
            try:
                leituras = [x for x in sar.baixar_historico(rid, sistema, desde, hoje, nome) if x.data <= hoje]
                if not leituras:
                    sem_leituras.append(rid)
                total += sar.gravar_leituras(conn, leituras)
                conn.commit()
                logger.info("[%s/%s] %s %s: %s leituras", n, len(alvos), sistema, nome.strip(), len(leituras))
            except Exception as e:
                conn.rollback()
                falhas.append(rid)
                logger.warning("Falha em %s (%s): %s", rid, nome.strip(), type(e).__name__)
            time.sleep(PAUSA_ENTRE_REQUISICOES_S)
    except BaseException as e:  # Ctrl+C incluso: a execução abortada não pode constar como "ok"
        abortado = f"abortado: {type(e).__name__}"
        raise
    finally:
        avisos = []
        if falhas:
            avisos.append(f"{len(falhas)} reservatórios com falha: {falhas[:20]}")
        if sem_leituras:
            avisos.append(f"{len(sem_leituras)} sem leituras na página: {sem_leituras[:20]}")
        erro = abortado or "; ".join(avisos) or None
        finalizar_execucao(conn, run_id, registros=total, erro=erro)
        conn.close()
    logger.info("Backfill concluído: %s leituras, %s falhas, %s sem leituras", total, len(falhas), len(sem_leituras))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desde", type=date.fromisoformat, default=date(2016, 1, 1))
    parser.add_argument("--refazer", action="store_true", help="recarrega também os já carregados")
    args = parser.parse_args()
    main(args.desde, args.refazer)
