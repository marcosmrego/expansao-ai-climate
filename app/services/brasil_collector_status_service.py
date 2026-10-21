"""Monitor das coletas da área Brasil (leitura de climate.collector_run). Sem cache: acompanha cargas em andamento."""
from typing import Optional

from database.db import conectar

STATEMENT_TIMEOUT_MS = 5000
LIMITE_EXECUCOES = 12
SEGUNDOS_SEM_SINAL = 15 * 60  # execução 'running' sem atualização por este tempo é dada como parada
_MAX_ERRO_EXIBIDO = 300

ROTULOS = {
    "deter_desmatamento": "Desmatamento · alertas DETER",
    "prodes_desmatamento": "Desmatamento · série anual PRODES",
    "inpe_focos": "Focos de calor · INPE",
    "inpe_focos_backfill": "Focos de calor · carga histórica",
    "sar_reservatorios": "Reservatórios · ANA/SAR",
    "sar_historico_backfill": "Reservatórios · carga histórica",
}

_SQL = """
SELECT id, fonte, status, inicio, fim, registros, erro, etapa, etapas_feitas, etapas_total,
       atualizado_em, EXTRACT(EPOCH FROM (NOW() - COALESCE(atualizado_em, inicio)))::INT
  FROM climate.collector_run
 ORDER BY inicio DESC
 LIMIT %s
"""


def estado(status: str, segundos_sem_sinal: Optional[int]) -> str:
    """'running' sem sinal recente vira 'parado' (processo morto ou travado)."""
    if status == "running" and (segundos_sem_sinal or 0) > SEGUNDOS_SEM_SINAL:
        return "parado"
    return status


def percentual(feitas: Optional[int], total: Optional[int]) -> Optional[float]:
    if not total or feitas is None or total < 0 or feitas < 0:
        return None
    return round(min(feitas / total, 1.0) * 100, 1)


def _execucao(linha) -> dict:
    (run_id, fonte, status, inicio, fim, registros, erro, etapa, feitas, total, atualizado, sem_sinal) = linha
    return {
        "id": run_id, "fonte": fonte, "rotulo": ROTULOS.get(fonte, fonte),
        "estado": estado(status, sem_sinal),
        "inicio": inicio.isoformat() if inicio else None, "fim": fim.isoformat() if fim else None,
        "atualizado_em": atualizado.isoformat() if atualizado else None,
        "segundos_sem_sinal": sem_sinal,
        "registros": registros, "etapa": etapa, "etapas_feitas": feitas, "etapas_total": total,
        "percentual": percentual(feitas, total),
        "erro": erro[:_MAX_ERRO_EXIBIDO] if erro else None,
    }


def execucoes(limite: int = LIMITE_EXECUCOES) -> dict:
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = %s", (STATEMENT_TIMEOUT_MS,))
            cur.execute(_SQL, (limite,))
            lista = [_execucao(linha) for linha in cur.fetchall()]
    finally:
        conn.close()
    return {"execucoes": lista, "em_andamento": any(e["estado"] == "running" for e in lista)}
