"""Registro de execução dos coletores da área Brasil (tabela climate.collector_run)."""
from datetime import date
from typing import Optional

_MAX_ERRO = 1000


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
