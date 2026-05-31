import json
import logging
import os
from typing import Optional

import anthropic

from database.db import conectar

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

_SYSTEM_PROMPT = (
    "Você é Zhora, assistente de inteligência climática do projeto Expansão AI Climate.\n"
    "Responda sempre em português, equilibrando precisão científica com linguagem acessível.\n"
    "Regras:\n"
    "1. Comece com uma conclusão prática e direta — o que a pessoa precisa saber para agir.\n"
    "2. Quando mencionar índices numéricos (ONI, PDO, IOD etc.), explique o que significam na prática, não apenas o valor.\n"
    "3. Para perguntas sobre impacto regional ou agrícola, priorize recomendações concretas em linguagem de produtor rural.\n"
    "4. Use os termos técnicos apenas quando necessário e sempre com uma breve explicação entre parênteses.\n"
    "5. Evite listar números brutos sem contexto — traduza-os em impacto real.\n"
    "6. Baseie-se exclusivamente no contexto climático fornecido — não invente dados."
)


def build_climate_context() -> dict:
    """Query DB for current climate indicators (monthly + daily) and active alerts."""
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

            def _fetch_latest(table, col, missing=-99.0):
                try:
                    cur.execute(
                        f"SELECT {col}, classificacao FROM climate.{table} "
                        f"WHERE {col} > {missing} ORDER BY data_referencia DESC LIMIT 1"
                    )
                    return cur.fetchone()
                except Exception:
                    return None

            def _fetch_latest_daily(table, cols):
                try:
                    cols_str = ", ".join(cols)
                    cur.execute(
                        f"SELECT {cols_str} FROM climate.{table} "
                        f"WHERE data_referencia > NOW() - INTERVAL '30 days' "
                        f"ORDER BY data_referencia DESC LIMIT 1"
                    )
                    return cur.fetchone()
                except Exception:
                    return None

            pdo_row = _fetch_latest("noaa_pdo", "pdo")
            nao_row = _fetch_latest("noaa_nao", "nao")
            amo_row = _fetch_latest("noaa_amo", "amo")
            qbo_row = _fetch_latest("noaa_qbo", "qbo", missing=-999.0)
            iod_row = _fetch_latest("noaa_iod", "dmi")

            mjo_row      = _fetch_latest_daily("mjo_daily",               ["phase", "amplitude", "classificacao"])
            co2_row      = _fetch_latest_daily("noaa_co2_daily",          ["co2_ppm", "data_referencia"])
            arctic_row   = _fetch_latest_daily("nsidc_arctic_ice_daily",  ["extent_mkm2", "data_referencia"])
            antarctic_row = _fetch_latest_daily("nsidc_antarctic_ice_daily", ["extent_mkm2", "data_referencia"])

            # Eventos sísmicos climate-relevant dos últimos 90 dias
            try:
                cur.execute("""
                    SELECT magnitude, event_type, place,
                           to_char(data_referencia,'YYYY-MM-DD'), climate_relevant
                    FROM climate.seismic_events
                    WHERE data_referencia > NOW() - INTERVAL '90 days'
                      AND climate_relevant = TRUE
                    ORDER BY magnitude DESC
                    LIMIT 5
                """)
                seismic_rows = cur.fetchall()
            except Exception:
                seismic_rows = []

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
        "pdo": float(pdo_row[0]) if pdo_row else None,
        "pdo_classificacao": pdo_row[1] if pdo_row else None,
        "nao": float(nao_row[0]) if nao_row else None,
        "nao_classificacao": nao_row[1] if nao_row else None,
        "amo": float(amo_row[0]) if amo_row else None,
        "amo_classificacao": amo_row[1] if amo_row else None,
        "qbo": float(qbo_row[0]) if qbo_row else None,
        "qbo_classificacao": qbo_row[1] if qbo_row else None,
        "iod": float(iod_row[0]) if iod_row else None,
        "iod_classificacao": iod_row[1] if iod_row else None,
        "mjo_phase": int(mjo_row[0]) if mjo_row else None,
        "mjo_amplitude": float(mjo_row[1]) if mjo_row else None,
        "mjo_classificacao": mjo_row[2] if mjo_row else None,
        "co2_ppm": float(co2_row[0]) if co2_row else None,
        "co2_date": str(co2_row[1]) if co2_row else None,
        "arctic_ice_mkm2": float(arctic_row[0]) if arctic_row else None,
        "arctic_ice_date": str(arctic_row[1]) if arctic_row else None,
        "antarctic_ice_mkm2": float(antarctic_row[0]) if antarctic_row else None,
        "antarctic_ice_date": str(antarctic_row[1]) if antarctic_row else None,
        "seismic_events": [
            {"magnitude": float(r[0]), "event_type": r[1],
             "place": r[2], "date": r[3], "climate_relevant": r[4]}
            for r in seismic_rows
        ],
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

    if ctx.get("pdo") is not None:
        pdo_fase = {"POSITIVO": "fase quente", "NEGATIVO": "fase fria", "NEUTRO": "neutro"}.get(
            ctx.get("pdo_classificacao", "NEUTRO"), "neutro"
        )
        lines.append(f"- PDO: {ctx['pdo']:.2f} ({pdo_fase})")
    if ctx.get("nao") is not None:
        nao_fase = {"POSITIVO": "fase positiva", "NEGATIVO": "fase negativa", "NEUTRO": "neutro"}.get(
            ctx.get("nao_classificacao", "NEUTRO"), "neutro"
        )
        lines.append(f"- NAO: {ctx['nao']:.2f} ({nao_fase})")
    if ctx.get("amo") is not None:
        amo_fase = {"QUENTE": "fase quente", "FRIO": "fase fria", "NEUTRO": "transição"}.get(
            ctx.get("amo_classificacao", "NEUTRO"), "transição"
        )
        lines.append(f"- AMO: {ctx['amo']:.4f} ({amo_fase})")
    if ctx.get("qbo") is not None:
        qbo_fase = {"OESTE": "oesteira/QBO-W", "LESTE": "lesteira/QBO-E", "NEUTRO": "transição"}.get(
            ctx.get("qbo_classificacao", "NEUTRO"), "transição"
        )
        lines.append(f"- QBO: {ctx['qbo']:.1f} m/s ({qbo_fase})")
    if ctx.get("iod") is not None:
        iod_fase = {"POSITIVO": "positivo (seca Índico leste)", "NEGATIVO": "negativo (chuvas Índico leste)", "NEUTRO": "neutro"}.get(
            ctx.get("iod_classificacao", "NEUTRO"), "neutro"
        )
        lines.append(f"- IOD/DMI: {ctx['iod']:+.4f} ({iod_fase})")

    if ctx.get("mjo_phase") is not None:
        mjo_cls_map = {
            "FRACO": "inativo (amp < 1.0)",
            "FAVORAVEL_ELNINO": "favorável El Niño (fases 5-7)",
            "FAVORAVEL_LANINA": "favorável La Niña (fases 1-3)",
            "ATIVO": "ativo",
        }
        mjo_desc = mjo_cls_map.get(ctx.get("mjo_classificacao", ""), ctx.get("mjo_classificacao", ""))
        lines.append(f"- MJO: fase {ctx['mjo_phase']}, amplitude {ctx['mjo_amplitude']:.2f} ({mjo_desc})")

    if ctx.get("co2_ppm") is not None:
        lines.append(f"- CO₂ atmosférico: {ctx['co2_ppm']:.2f} ppm (Mauna Loa)")

    if ctx.get("arctic_ice_mkm2") is not None:
        lines.append(f"- Gelo Ártico: {ctx['arctic_ice_mkm2']:.3f} milhões km²")

    if ctx.get("antarctic_ice_mkm2") is not None:
        lines.append(f"- Gelo Antártico: {ctx['antarctic_ice_mkm2']:.3f} milhões km²")

    seismic = ctx.get("seismic_events", [])
    if seismic:
        lines.append("\nEventos sísmicos relevantes (últimos 90 dias):")
        for e in seismic:
            etype = "Erupção vulcânica" if "volcanic" in (e.get("event_type") or "") else "Terremoto"
            lines.append(f"  {etype} M{e['magnitude']:.1f} — {e['place']} ({e['date']})")

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
                        "pdo": ctx.get("pdo"),
                        "pdo_classificacao": ctx.get("pdo_classificacao"),
                        "nao": ctx.get("nao"),
                        "nao_classificacao": ctx.get("nao_classificacao"),
                        "amo": ctx.get("amo"),
                        "amo_classificacao": ctx.get("amo_classificacao"),
                        "qbo": ctx.get("qbo"),
                        "qbo_classificacao": ctx.get("qbo_classificacao"),
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
    "e atmosféricos. Seja direto e objetivo. "
    "IMPORTANTE: escreva somente texto corrido, sem formatação markdown, sem asteriscos, "
    "sem títulos com #, sem bullet points. Apenas texto puro."
)


def generate_insight() -> str:
    """Generate and persist both a technical insight and a plain-language summary."""
    ctx = build_climate_context()
    context_text = context_to_text(ctx)
    insight_text = _strip_headers(ask_claude(_INSIGHT_PROMPT, context_text))
    plain_text = _gerar_resumo_simples(insight_text)

    meta = json.dumps({
        "classificacao": ctx["classificacao"],
        "nino34_anom": ctx.get("nino34_anom"),
        "soi": ctx.get("soi"),
        "pdo": ctx.get("pdo"),
        "nao": ctx.get("nao"),
        "amo": ctx.get("amo"),
        "qbo": ctx.get("qbo"),
        "iod": ctx.get("iod"),
        "alert_count": len(ctx.get("alerts", [])),
    })
    oni_snap = ctx.get("oni")

    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO climate.operational_context
                    (context_type, content, oni_snapshot, metadata)
                VALUES ('CLIMATE_INSIGHT', %s, %s, %s::jsonb)
                """,
                (insight_text, oni_snap, meta),
            )
            if plain_text:
                cur.execute(
                    """
                    INSERT INTO climate.operational_context
                        (context_type, content, oni_snapshot, metadata)
                    VALUES ('CLIMATE_INSIGHT_PLAIN', %s, %s, %s::jsonb)
                    """,
                    (plain_text, oni_snap, meta),
                )
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
                ORDER BY created_at DESC LIMIT 1
                """
            )
            row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_latest_insight_plain() -> Optional[str]:
    """Retrieve the most recent plain-language insight summary."""
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT content FROM climate.operational_context
                WHERE context_type = 'CLIMATE_INSIGHT_PLAIN'
                ORDER BY created_at DESC LIMIT 1
                """
            )
            row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


_PREDICTION_PROMPT = (
    "Com base no contexto climático atual fornecido, elabore uma análise preditiva técnica "
    "para os próximos 1 a 3 meses. "
    "Considere a convergência entre: fase ENSO atual (ONI, SOI), moduladores de baixa frequência "
    "(PDO, AMO, NAO, QBO), oscilação intra-sazonal (MJO), CO₂ atmosférico e extensão do gelo polar. "
    "Identifique quais sinais reforçam ou contradizem a tendência ENSO atual. "
    "Escreva 4 a 6 frases técnicas em português. "
    "Texto corrido, sem formatação markdown, sem asteriscos, sem títulos, sem bullet points."
)

_PLAIN_SYSTEM = (
    "Você é um comunicador de ciência climática especializado em traduzir conceitos complexos "
    "para o público geral. Responda sempre em português, de forma clara, direta e acessível. "
    "Nunca use siglas, termos técnicos ou jargão científico."
)

_PLAIN_PROMPT = (
    "Leia a análise climática abaixo e reescreva-a em 2 a 3 frases simples para alguém que "
    "não entende nada de meteorologia. Fale sobre o que as pessoas podem esperar do clima nos "
    "próximos meses: mais chuva, mais calor, secas, tempestades — algo que faça sentido no "
    "dia a dia. Sem siglas, sem termos técnicos.\n\nANÁLISE:\n"
)


import re as _re


def _strip_headers(text: str) -> str:
    """Remove markdown headers and section label lines Claude tends to add."""
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if _re.match(r"^(SEÇÃO|BLOCO|SECTION)\s+\d", stripped, _re.IGNORECASE):
            continue
        cleaned.append(line)
    result = "\n".join(cleaned).strip()
    return _re.sub(r"\n{3,}", "\n\n", result)


def _gerar_resumo_simples(technical: str) -> str:
    """Call Claude with a plain-language system prompt to simplify the technical analysis."""
    if not ANTHROPIC_API_KEY:
        return ""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        msg = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=300,
            system=_PLAIN_SYSTEM,
            messages=[{"role": "user", "content": _PLAIN_PROMPT + technical}],
        )
        return _strip_headers(msg.content[0].text)
    except Exception:
        return ""


def generate_prediction() -> str:
    """Generate and persist both a technical and a plain-language climate prediction."""
    ctx = build_climate_context()
    context_text = context_to_text(ctx)
    technical = _strip_headers(ask_claude(_PREDICTION_PROMPT, context_text))
    plain = _gerar_resumo_simples(technical)

    meta = json.dumps({
        "classificacao": ctx["classificacao"],
        "nino34_anom": ctx.get("nino34_anom"),
        "soi": ctx.get("soi"),
        "pdo": ctx.get("pdo"),
        "nao": ctx.get("nao"),
        "amo": ctx.get("amo"),
        "qbo": ctx.get("qbo"),
        "mjo_phase": ctx.get("mjo_phase"),
        "mjo_amplitude": ctx.get("mjo_amplitude"),
        "co2_ppm": ctx.get("co2_ppm"),
        "arctic_ice_mkm2": ctx.get("arctic_ice_mkm2"),
        "antarctic_ice_mkm2": ctx.get("antarctic_ice_mkm2"),
        "alert_count": len(ctx.get("alerts", [])),
    })
    oni_snap = ctx.get("oni")

    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO climate.operational_context
                    (context_type, content, oni_snapshot, metadata)
                VALUES ('CLIMATE_PREDICTION', %s, %s, %s::jsonb)
                """,
                (technical, oni_snap, meta),
            )
            if plain:
                cur.execute(
                    """
                    INSERT INTO climate.operational_context
                        (context_type, content, oni_snapshot, metadata)
                    VALUES ('CLIMATE_PLAIN', %s, %s, %s::jsonb)
                    """,
                    (plain, oni_snap, meta),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return technical


def get_latest_prediction() -> Optional[str]:
    """Retrieve the most recent technical predictive analysis."""
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT content FROM climate.operational_context
                WHERE context_type = 'CLIMATE_PREDICTION'
                ORDER BY created_at DESC LIMIT 1
                """
            )
            row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_latest_plain() -> Optional[str]:
    """Retrieve the most recent plain-language climate summary."""
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT content FROM climate.operational_context
                WHERE context_type = 'CLIMATE_PLAIN'
                ORDER BY created_at DESC LIMIT 1
                """
            )
            row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def ask_claude(question: str, context_text: str) -> str:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY não configurado. Defina a variável de ambiente."
        )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    try:
        message = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"CONTEXTO CLIMÁTICO ATUAL:\n{context_text}\n\n"
                        f"PERGUNTA: {question}"
                    ),
                }
            ],
        )
        return message.content[0].text
    except anthropic.APIStatusError as e:
        raise RuntimeError(f"Anthropic retornou erro {e.status_code}: {e.message}")
    except Exception as e:
        raise RuntimeError(f"Erro ao chamar Claude ({ANTHROPIC_MODEL}): {e}")
