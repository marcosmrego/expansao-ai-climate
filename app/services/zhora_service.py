import json
import logging
import os
from typing import Optional

import httpx

from database.db import conectar

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

_SYSTEM_PROMPT = (
    "Você é Zhora, assistente especialista em análise climática do projeto Expansão AI Climate.\n"
    "Responda sempre em português, de forma técnica e objetiva.\n"
    "Baseie suas respostas exclusivamente no contexto fornecido — não invente dados."
)


def build_climate_context() -> dict:
    """Query DB for current ONI, trend, Niño 3.4 and active alerts."""
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT oni, classificacao
                FROM climate.noaa_oni
                WHERE oni > -99
                ORDER BY data_referencia DESC
                LIMIT 2
            """)
            oni_rows = cur.fetchall()

            cur.execute("""
                SELECT nino_34_anom
                FROM climate.noaa_sst_indices
                ORDER BY data_referencia DESC
                LIMIT 1
            """)
            sst_row = cur.fetchone()

            cur.execute("""
                SELECT severity, title, message
                FROM climate.climate_alerts
                WHERE status = 'ACTIVE'
                ORDER BY created_at DESC
                LIMIT 5
            """)
            alert_rows = cur.fetchall()
    finally:
        conn.close()

    current_oni = float(oni_rows[0][0]) if oni_rows else None
    previous_oni = float(oni_rows[1][0]) if len(oni_rows) > 1 else None
    classificacao = oni_rows[0][1] if oni_rows else "NEUTRO"
    nino34_anom = float(sst_row[0]) if sst_row else None

    trend = None
    if current_oni is not None and previous_oni is not None:
        var = round(current_oni - previous_oni, 2)
        if var > 0.05:
            trend = "SUBINDO"
        elif var < -0.05:
            trend = "CAINDO"
        else:
            trend = "ESTÁVEL"

    return {
        "oni": current_oni,
        "classificacao": classificacao,
        "nino34_anom": nino34_anom,
        "trend": trend,
        "alerts": [
            {"severity": r[0], "title": r[1], "message": r[2]}
            for r in alert_rows
        ],
    }


def context_to_text(ctx: dict) -> str:
    fase_map = {"EL_NINO": "El Niño", "LA_NINA": "La Niña", "NEUTRO": "Neutro"}
    fase = fase_map.get(ctx["classificacao"], ctx["classificacao"])

    lines = [
        f"- ONI atual: {ctx['oni']:.2f}" if ctx["oni"] is not None else "- ONI atual: indisponível",
        f"- Fase ENSO: {fase}",
    ]
    if ctx["nino34_anom"] is not None:
        lines.append(f"- Anomalia Niño 3.4: {ctx['nino34_anom']:.2f} °C")
    if ctx["trend"]:
        lines.append(f"- Tendência ONI: {ctx['trend']}")

    if ctx["alerts"]:
        lines.append("\nAlertas ativos:")
        for a in ctx["alerts"]:
            lines.append(f"  [{a['severity']}] {a['title']} — {a['message']}")
    else:
        lines.append("\nNenhum alerta ativo no momento.")

    return "\n".join(lines)


def save_context_snapshot(ctx: dict) -> int:
    """Persist a climate context snapshot to the operational_context table."""
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO climate.operational_context
                    (context_type, content, oni_snapshot, metadata)
                VALUES ('CLIMATE_SUMMARY', %s, %s, %s::jsonb)
                RETURNING id
                """,
                (
                    context_to_text(ctx),
                    ctx.get("oni"),
                    json.dumps({
                        "classificacao": ctx["classificacao"],
                        "nino34_anom": ctx.get("nino34_anom"),
                        "trend": ctx.get("trend"),
                        "alert_count": len(ctx.get("alerts", [])),
                    }),
                ),
            )
            row_id = cur.fetchone()[0]
        conn.commit()
        return row_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_latest_context() -> Optional[str]:
    """Retrieve the most recent CLIMATE_SUMMARY snapshot text."""
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT content FROM climate.operational_context
                WHERE context_type = 'CLIMATE_SUMMARY'
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def ask_ollama(question: str, context_text: str) -> str:
    prompt = (
        f"{_SYSTEM_PROMPT}\n\n"
        f"CONTEXTO CLIMÁTICO ATUAL:\n{context_text}\n\n"
        f"PERGUNTA: {question}"
    )
    try:
        response = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()["response"]
    except httpx.ConnectError:
        raise RuntimeError(
            f"Ollama não está acessível em {OLLAMA_URL}. "
            "Verifique se o serviço está rodando."
        )
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Ollama retornou erro HTTP {e.response.status_code}.")
