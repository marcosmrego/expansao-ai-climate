import json
import logging
import os
from typing import Optional

import httpx

from database.db import conectar

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

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

            try:
                cur.execute("""
                    SELECT soi, classificacao
                    FROM climate.noaa_soi
                    WHERE soi > -99
                    ORDER BY data_referencia DESC
                    LIMIT 1
                """)
                soi_row = cur.fetchone()
            except Exception:
                soi_row = None
    finally:
        conn.close()

    current_oni = float(oni_rows[0][0]) if oni_rows else None
    previous_oni = float(oni_rows[1][0]) if len(oni_rows) > 1 else None
    classificacao = oni_rows[0][1] if oni_rows else "NEUTRO"
    nino34_anom = float(sst_row[0]) if sst_row else None
    soi = float(soi_row[0]) if soi_row else None
    soi_classificacao = soi_row[1] if soi_row else None

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
        "soi": soi,
        "soi_classificacao": soi_classificacao,
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
    if ctx.get("soi") is not None:
        soi_fase_map = {"EL_NINO": "sinal El Niño", "LA_NINA": "sinal La Niña", "NEUTRO": "neutro"}
        soi_fase = soi_fase_map.get(ctx.get("soi_classificacao", "NEUTRO"), "neutro")
        lines.append(f"- SOI: {ctx['soi']:.2f} ({soi_fase})")

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
                        "soi": ctx.get("soi"),
                        "soi_classificacao": ctx.get("soi_classificacao"),
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


_INSIGHT_PROMPT = (
    "Com base no contexto climático fornecido, escreva um parágrafo técnico de 2 a 4 frases "
    "para uso como insight operacional em um dashboard de monitoramento ENSO. "
    "Inclua os valores numéricos relevantes e interprete a convergência dos indicadores oceânicos "
    "e atmosféricos. Seja direto e objetivo."
)


def generate_insight() -> str:
    """Call Gemini with the current climate context and persist the result as CLIMATE_INSIGHT."""
    ctx = build_climate_context()
    context_text = context_to_text(ctx)
    insight_text = ask_gemini(_INSIGHT_PROMPT, context_text)

    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO climate.operational_context
                    (context_type, content, oni_snapshot, metadata)
                VALUES ('CLIMATE_INSIGHT', %s, %s, %s::jsonb)
                RETURNING id
                """,
                (
                    insight_text,
                    ctx.get("oni"),
                    json.dumps({
                        "classificacao": ctx["classificacao"],
                        "nino34_anom": ctx.get("nino34_anom"),
                        "soi": ctx.get("soi"),
                        "alert_count": len(ctx.get("alerts", [])),
                    }),
                ),
            )
            cur.fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return insight_text


def get_latest_insight() -> Optional[str]:
    """Retrieve the most recent AI-generated operational insight."""
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT content FROM climate.operational_context
                WHERE context_type = 'CLIMATE_INSIGHT'
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def ask_gemini(question: str, context_text: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GOOGLE_API_KEY não configurado. Defina a variável de ambiente."
        )

    url = f"{_GEMINI_BASE}/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "system_instruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            f"CONTEXTO CLIMÁTICO ATUAL:\n{context_text}\n\n"
                            f"PERGUNTA: {question}"
                        )
                    }
                ]
            }
        ],
    }

    try:
        response = httpx.post(url, json=payload, timeout=30.0)
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Gemini retornou erro HTTP {e.response.status_code}: {e.response.text}")
    except Exception as e:
        raise RuntimeError(f"Erro ao chamar Gemini ({GEMINI_MODEL}): {e}")
