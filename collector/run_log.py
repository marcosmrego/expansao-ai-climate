"""Registro de execução dos coletores da área Brasil (tabela climate.collector_run)."""
import logging
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_ERRO = 1000
_MAX_ETAPA = 120


def iniciar_execucao(conn, fonte: str, janela_inicio: Optional[date], janela_fim: Optional[date]) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO climate.collector_run (fonte, janela_inicio, janela_fim)
            VALUES (%s, %s, %s) RETURNING id;
            """,
            (fonte, janela_inicio, janela_fim),
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    return run_id


def registrar_progresso(conn, fonte: str, etapa: str, feitas: int, total: int) -> None:
    """Atualiza o progresso da execução em andamento da fonte. Nunca derruba a coleta.

    Deve ser chamada logo após um commit: se a migração 009 ainda não existir, o UPDATE falha,
    o rollback descarta só ele e a coleta segue sem monitor.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE climate.collector_run
                   SET etapa = %s, etapas_feitas = %s, etapas_total = %s, atualizado_em = NOW()
                 WHERE id = (SELECT id FROM climate.collector_run
                              WHERE fonte = %s AND status = 'running'
                              ORDER BY inicio DESC LIMIT 1);
                """,
                (etapa[:_MAX_ETAPA], feitas, total, fonte),
            )
        conn.commit()
    except Exception:
        logger.warning("Não foi possível registrar o progresso de %s", fonte, exc_info=True)
        conn.rollback()


def finalizar_execucao(conn, run_id: int, registros: int = 0, erro: Optional[str] = None) -> None:
    status = "erro" if erro else "ok"
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE climate.collector_run
               SET fim = NOW(), status = %s, registros = %s, erro = %s
             WHERE id = %s;
            """,
            (status, registros, erro[:_MAX_ERRO] if erro else None, run_id),
        )
    conn.commit()
