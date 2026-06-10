from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

import os
import time
import logging
import requests as _requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from database.db import conectar
from app.routes.climate_alerts import router as climate_alert_router
from app.routes.zhora import router as zhora_router
from app.routes.collect import router as collect_router


class _TTLCache:
    def __init__(self, ttl: int = 3600):
        self._store: dict = {}
        self._ttl = ttl

    def get(self, key: str):
        entry = self._store.get(key)
        if entry and time.monotonic() < entry[1]:
            return entry[0]
        self._store.pop(key, None)
        return None

    def set(self, key: str, value) -> None:
        self._store[key] = (value, time.monotonic() + self._ttl)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


_cache = _TTLCache(ttl=3600)


class StatusResponse(BaseModel):
    oni: float
    classificacao: str
    nino34: float
    fase: str


class HistoryItem(BaseModel):
    periodo: str
    oni: float
    classificacao: str


class AnalysisResponse(BaseModel):
    oni: float
    nino34: float
    analysis: str


class TrendResponse(BaseModel):
    atual: float
    anterior: float
    variacao: float
    tendencia: str


class UpdateResponse(BaseModel):
    ultima_atualizacao: Optional[str]
    fonte: str


class SoiStatusResponse(BaseModel):
    soi: float
    classificacao: str
    fase: str


class SoiHistoryItem(BaseModel):
    periodo: str
    soi: float
    classificacao: str


class IndexStatusResponse(BaseModel):
    value: float
    classificacao: str
    fase: str


class MjoResponse(BaseModel):
    phase: int
    amplitude: float
    classificacao: str
    fase: str
    data_referencia: str


class Co2Response(BaseModel):
    co2_ppm: float
    data_referencia: str


class IceResponse(BaseModel):
    extent_mkm2: float
    area_mkm2: Optional[float]
    data_referencia: str


class PredictionResponse(BaseModel):
    prediction: str


class PlainResponse(BaseModel):
    plain: str


class IodResponse(BaseModel):
    dmi: float
    classificacao: str
    fase: str
    data_referencia: str


app = FastAPI(
    title="Expansao AI Climate API"
)


ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "https://climate.expansao-ai.com.br"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


app.include_router(climate_alert_router)
app.include_router(zhora_router)
app.include_router(collect_router)


@app.get("/health")
def health():
    try:
        conn = conectar()
        conn.close()
        return {"status": "ok"}
    except Exception as e:
        logger.error("Health check falhou: %s", e)
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get("/climate/status", response_model=StatusResponse)
def climate_status():
    cached = _cache.get("status")
    if cached:
        return cached

    conn = conectar()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                o.oni,
                o.classificacao,
                s.nino_34_anom,
                CASE
                    WHEN o.classificacao = 'EL_NINO' THEN 'El Niño'
                    WHEN o.classificacao = 'LA_NINA' THEN 'La Niña'
                    ELSE 'Neutro'
                END AS fase
            FROM (
                SELECT oni, classificacao
                FROM climate.noaa_oni
                WHERE oni > -99
                ORDER BY data_referencia DESC
                LIMIT 1
            ) o
            CROSS JOIN (
                SELECT nino_34_anom
                FROM climate.noaa_sst_indices
                ORDER BY data_referencia DESC
                LIMIT 1
            ) s
        """)

        r = cursor.fetchone()

        if r is None:
            raise HTTPException(status_code=404, detail="Sem dados de status disponíveis")

        result = {
            "oni": float(r[0]),
            "classificacao": r[1],
            "nino34": float(r[2]),
            "fase": r[3]
        }
        _cache.set("status", result)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro em /climate/status: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar status climático")
    finally:
        conn.close()


@app.get("/climate/history", response_model=list[HistoryItem])
def climate_history():
    cached = _cache.get("history")
    if cached:
        return cached

    conn = conectar()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                to_char(data_referencia, 'YYYY-MM'),
                oni,
                classificacao
            FROM climate.noaa_oni
            WHERE oni > -99
            ORDER BY data_referencia DESC
            LIMIT 24
        """)

        rows = cursor.fetchall()

        dados = []

        for r in reversed(rows):
            dados.append({
                "periodo": r[0],
                "oni": float(r[1]),
                "classificacao": r[2]
            })

        _cache.set("history", dados)
        return dados

    except Exception as e:
        logger.error("Erro em /climate/history: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar histórico ONI")
    finally:
        conn.close()


@app.get("/climate/analysis", response_model=AnalysisResponse)
def climate_analysis():
    cached = _cache.get("analysis")
    if cached:
        return cached

    from app.services.zhora_service import get_latest_insight

    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT o.oni, s.nino_34_anom
            FROM (
                SELECT oni FROM climate.noaa_oni
                WHERE oni > -99 ORDER BY data_referencia DESC LIMIT 1
            ) o
            CROSS JOIN (
                SELECT nino_34_anom FROM climate.noaa_sst_indices
                ORDER BY data_referencia DESC LIMIT 1
            ) s
        """)
        r = cursor.fetchone()
        oni = float(r[0]) if r else 0.0
        nino34 = float(r[1]) if r else 0.0
    except Exception as e:
        logger.error("Erro ao consultar dados para análise: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar dados climáticos")
    finally:
        conn.close()

    insight = get_latest_insight()
    if insight is None:
        # Fallback enquanto nenhum insight AI foi gerado ainda
        if oni >= 0.5:
            insight = "Indicadores oceânicos compatíveis com El Niño. Execute POST /api/collect/insight para ativar a análise com IA."
        elif oni <= -0.5:
            insight = "Indicadores oceânicos compatíveis com La Niña. Execute POST /api/collect/insight para ativar a análise com IA."
        else:
            insight = "ENSO segue em neutralidade. Execute POST /api/collect/insight para ativar a análise com IA."

    result = {"oni": oni, "nino34": nino34, "analysis": insight}
    _cache.set("analysis", result)
    return result


@app.get("/climate/trend", response_model=TrendResponse)
def climate_trend():
    cached = _cache.get("trend")
    if cached:
        return cached

    conn = conectar()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT oni
            FROM climate.noaa_oni
            WHERE oni > -99
            ORDER BY data_referencia DESC
            LIMIT 2
        """)

        rows = cursor.fetchall()

        atual = float(rows[0][0])
        anterior = float(rows[1][0])
        variacao = round(atual - anterior, 2)

        tendencia = "ESTAVEL"

        if variacao > 0.05:
            tendencia = "SUBINDO"
        elif variacao < -0.05:
            tendencia = "CAINDO"

        result = {
            "atual": atual,
            "anterior": anterior,
            "variacao": variacao,
            "tendencia": tendencia
        }
        _cache.set("trend", result)
        return result

    except Exception as e:
        logger.error("Erro em /climate/trend: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao calcular tendência ONI")
    finally:
        conn.close()


@app.get("/climate/update", response_model=UpdateResponse)
def climate_update():
    cached = _cache.get("update")
    if cached:
        return cached

    conn = conectar()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                to_char(MAX(data_referencia), 'YYYY-MM')
            FROM climate.noaa_oni
            WHERE oni > -99
        """)

        ultima = cursor.fetchone()[0]

        result = {
            "ultima_atualizacao": ultima,
            "fonte": "NOAA"
        }
        _cache.set("update", result)
        return result

    except Exception as e:
        logger.error("Erro em /climate/update: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar última atualização")
    finally:
        conn.close()


@app.get("/climate/freshness")
def climate_freshness():
    """Return the timestamp of the most recent data ingestion across all tables."""
    cached = _cache.get("freshness")
    if cached:
        return cached
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MAX(ts) FROM (
                SELECT MAX(criado_em) AS ts FROM climate.noaa_co2_daily
                UNION ALL SELECT MAX(criado_em) FROM climate.nsidc_arctic_ice_daily
                UNION ALL SELECT MAX(criado_em) FROM climate.mjo_daily
                UNION ALL SELECT MAX(created_at)  FROM climate.operational_context
            ) t
        """)
        ts = cursor.fetchone()[0]
        result = {"ultima_coleta": ts.strftime("%d/%m/%Y às %H:%Mh UTC") if ts else "—"}
        _cache.set("freshness", result)
        return result
    except Exception as e:
        logger.error("Erro em /climate/freshness: %s", e)
        return {"ultima_coleta": "—"}
    finally:
        conn.close()


@app.post("/api/notify/staleness")
def notify_staleness_check():
    """Check if any data source is stale (>36h) and notify Slack."""
    from datetime import datetime, timezone, timedelta
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MAX(ts) FROM (
                SELECT MAX(criado_em) AS ts FROM climate.noaa_co2_daily
                UNION ALL SELECT MAX(criado_em) FROM climate.nsidc_arctic_ice_daily
                UNION ALL SELECT MAX(criado_em) FROM climate.mjo_daily
            ) t
        """)
        row = cursor.fetchone()
        if not row or not row[0]:
            return {"status": "unknown"}

        last_ts = row[0]
        if last_ts.tzinfo is None:
            from datetime import timezone as _tz
            last_ts = last_ts.replace(tzinfo=_tz.utc)
        now = datetime.now(timezone.utc)
        hours_ago = (now - last_ts).total_seconds() / 3600

        if hours_ago > 36:
            try:
                from app.services.slack_service import notify_staleness
                notify_staleness(
                    indicator="Indicadores diários (CO₂/Gelo/MJO)",
                    last_update=last_ts.strftime("%d/%m/%Y %H:%Mh UTC"),
                    hours=hours_ago,
                )
            except Exception:
                pass
            return {"status": "stale", "hours": round(hours_ago, 1), "notified": True}

        return {"status": "ok", "hours": round(hours_ago, 1)}
    except Exception as e:
        logger.error("Erro em staleness check: %s", e)
        return {"status": "error"}
    finally:
        conn.close()


@app.get("/climate/soi", response_model=SoiStatusResponse)
def climate_soi():
    cached = _cache.get("soi")
    if cached:
        return cached

    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                soi,
                classificacao,
                CASE
                    WHEN classificacao = 'EL_NINO' THEN 'El Niño'
                    WHEN classificacao = 'LA_NINA' THEN 'La Niña'
                    ELSE 'Neutro'
                END AS fase
            FROM climate.noaa_soi
            WHERE soi > -99
            ORDER BY data_referencia DESC
            LIMIT 1
        """)
        r = cursor.fetchone()
        if r is None:
            raise HTTPException(status_code=404, detail="Sem dados SOI disponíveis")
        result = {"soi": float(r[0]), "classificacao": r[1], "fase": r[2]}
        _cache.set("soi", result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro em /climate/soi: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar SOI")
    finally:
        conn.close()


@app.get("/climate/soi/history", response_model=list[SoiHistoryItem])
def climate_soi_history():
    cached = _cache.get("soi_history")
    if cached:
        return cached

    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                to_char(data_referencia, 'YYYY-MM'),
                soi,
                classificacao
            FROM climate.noaa_soi
            WHERE soi > -99
            ORDER BY data_referencia DESC
            LIMIT 24
        """)
        rows = cursor.fetchall()
        dados = [
            {"periodo": r[0], "soi": float(r[1]), "classificacao": r[2]}
            for r in reversed(rows)
        ]
        _cache.set("soi_history", dados)
        return dados
    except Exception as e:
        logger.error("Erro em /climate/soi/history: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar histórico SOI")
    finally:
        conn.close()


_PDO_FASE = {"POSITIVO": "Fase quente", "NEGATIVO": "Fase fria", "NEUTRO": "Neutro"}
_NAO_FASE = {"POSITIVO": "Fase positiva", "NEGATIVO": "Fase negativa", "NEUTRO": "Neutro"}
_AMO_FASE = {"QUENTE": "Fase quente", "FRIO": "Fase fria", "NEUTRO": "Transição"}
_QBO_FASE = {"OESTE": "Oesteira (QBO-W)", "LESTE": "Lesteira (QBO-E)", "NEUTRO": "Transição"}


@app.get("/climate/pdo", response_model=IndexStatusResponse)
def climate_pdo():
    cached = _cache.get("pdo")
    if cached:
        return cached
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pdo, classificacao FROM climate.noaa_pdo
            WHERE pdo > -99 ORDER BY data_referencia DESC LIMIT 1
        """)
        r = cursor.fetchone()
        if r is None:
            raise HTTPException(status_code=404, detail="Sem dados PDO disponíveis")
        result = {"value": float(r[0]), "classificacao": r[1], "fase": _PDO_FASE.get(r[1], r[1])}
        _cache.set("pdo", result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro em /climate/pdo: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar PDO")
    finally:
        conn.close()


@app.get("/climate/nao", response_model=IndexStatusResponse)
def climate_nao():
    cached = _cache.get("nao")
    if cached:
        return cached
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT nao, classificacao FROM climate.noaa_nao
            WHERE nao > -99 ORDER BY data_referencia DESC LIMIT 1
        """)
        r = cursor.fetchone()
        if r is None:
            raise HTTPException(status_code=404, detail="Sem dados NAO disponíveis")
        result = {"value": float(r[0]), "classificacao": r[1], "fase": _NAO_FASE.get(r[1], r[1])}
        _cache.set("nao", result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro em /climate/nao: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar NAO")
    finally:
        conn.close()


@app.get("/climate/amo", response_model=IndexStatusResponse)
def climate_amo():
    cached = _cache.get("amo")
    if cached:
        return cached
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT amo, classificacao FROM climate.noaa_amo
            WHERE amo > -99 ORDER BY data_referencia DESC LIMIT 1
        """)
        r = cursor.fetchone()
        if r is None:
            raise HTTPException(status_code=404, detail="Sem dados AMO disponíveis")
        result = {"value": float(r[0]), "classificacao": r[1], "fase": _AMO_FASE.get(r[1], r[1])}
        _cache.set("amo", result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro em /climate/amo: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar AMO")
    finally:
        conn.close()


@app.get("/climate/qbo", response_model=IndexStatusResponse)
def climate_qbo():
    cached = _cache.get("qbo")
    if cached:
        return cached
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT qbo, classificacao FROM climate.noaa_qbo
            WHERE qbo > -999 ORDER BY data_referencia DESC LIMIT 1
        """)
        r = cursor.fetchone()
        if r is None:
            raise HTTPException(status_code=404, detail="Sem dados QBO disponíveis")
        result = {"value": float(r[0]), "classificacao": r[1], "fase": _QBO_FASE.get(r[1], r[1])}
        _cache.set("qbo", result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro em /climate/qbo: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar QBO")
    finally:
        conn.close()


_IOD_FASE = {
    "POSITIVO": "Positivo — seca no Índico leste, chuvas no Índico oeste",
    "NEGATIVO": "Negativo — chuvas no Índico leste, seca no Índico oeste",
    "NEUTRO":   "Neutro",
}


@app.get("/climate/iod", response_model=IodResponse)
def climate_iod():
    cached = _cache.get("iod")
    if cached:
        return cached
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT dmi, classificacao, to_char(data_referencia, 'YYYY-MM-DD')
            FROM climate.noaa_iod
            ORDER BY data_referencia DESC LIMIT 1
        """)
        r = cursor.fetchone()
        if r is None:
            raise HTTPException(status_code=404, detail="Sem dados IOD disponíveis")
        result = {
            "dmi": float(r[0]),
            "classificacao": r[1],
            "fase": _IOD_FASE.get(r[1], r[1]),
            "data_referencia": r[2],
        }
        _cache.set("iod", result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro em /climate/iod: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar IOD")
    finally:
        conn.close()


@app.get("/climate/sst/history")
def climate_sst_history():
    """Return last 12 months of SST anomalies for all 4 Niño regions."""
    cached = _cache.get("sst_history")
    if cached:
        return cached
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT to_char(data_referencia, 'YYYY-MM'),
                   nino_12_anom, nino_3_anom, nino_34_anom, nino_4_anom
            FROM (
                SELECT data_referencia, nino_12_anom, nino_3_anom,
                       nino_34_anom, nino_4_anom
                FROM climate.noaa_sst_indices
                WHERE nino_34_anom > -99
                ORDER BY data_referencia DESC
                LIMIT 12
            ) t ORDER BY data_referencia ASC
        """)
        rows = cursor.fetchall()
        result = [
            {
                "periodo": r[0],
                "nino12": float(r[1]) if r[1] else 0.0,
                "nino3":  float(r[2]) if r[2] else 0.0,
                "nino34": float(r[3]) if r[3] else 0.0,
                "nino4":  float(r[4]) if r[4] else 0.0,
            }
            for r in rows
        ]
        _cache.set("sst_history", result)
        return result
    except Exception as e:
        logger.error("Erro em /climate/sst/history: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar histórico SST")
    finally:
        conn.close()


class ModulationHistoryItem(BaseModel):
    data_referencia: str
    value: float
    classificacao: str


def _modulation_history(cache_key: str, table: str, col: str, missing_filter: str):
    cached = _cache.get(cache_key)
    if cached:
        return cached
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT to_char(data_referencia, 'YYYY-MM'), {col}, classificacao
            FROM (
                SELECT data_referencia, {col}, classificacao
                FROM climate.{table}
                WHERE {missing_filter}
                ORDER BY data_referencia DESC
                LIMIT 60
            ) t ORDER BY data_referencia ASC
        """)
        rows = cursor.fetchall()
        dados = [{"data_referencia": r[0], "value": float(r[1]), "classificacao": r[2]}
                 for r in rows]
        _cache.set(cache_key, dados)
        return dados
    except Exception as e:
        logger.error("Erro em history %s: %s", cache_key, e)
        raise HTTPException(status_code=500, detail=f"Erro ao consultar histórico {cache_key}")
    finally:
        conn.close()


@app.get("/climate/pdo/history", response_model=list[ModulationHistoryItem])
def climate_pdo_history():
    return _modulation_history("pdo_history", "noaa_pdo", "pdo", "pdo > -99")


@app.get("/climate/nao/history", response_model=list[ModulationHistoryItem])
def climate_nao_history():
    return _modulation_history("nao_history", "noaa_nao", "nao", "nao > -99")


@app.get("/climate/amo/history", response_model=list[ModulationHistoryItem])
def climate_amo_history():
    return _modulation_history("amo_history", "noaa_amo", "amo", "amo > -99")


@app.get("/climate/qbo/history", response_model=list[ModulationHistoryItem])
def climate_qbo_history():
    return _modulation_history("qbo_history", "noaa_qbo", "qbo", "qbo > -999")


@app.get("/climate/iod/history", response_model=list[ModulationHistoryItem])
def climate_iod_history():
    return _modulation_history("iod_history", "noaa_iod", "dmi", "dmi > -99")


class MjoHistoryItem(BaseModel):
    data_referencia: str
    rmm1: float
    rmm2: float
    phase: int
    amplitude: float
    classificacao: str


class Co2HistoryItem(BaseModel):
    data_referencia: str
    co2_ppm: float


class IceHistoryItem(BaseModel):
    data_referencia: str
    extent_mkm2: float


_MJO_FASE = {
    "FRACO":             "Inativo (amplitude < 1.0)",
    "ATIVO":             "Ativo",
    "FAVORAVEL_ELNINO":  "Favorável El Niño (fases 5–7)",
    "FAVORAVEL_LANINA":  "Favorável La Niña (fases 1–3)",
}


@app.get("/climate/mjo", response_model=MjoResponse)
def climate_mjo():
    cached = _cache.get("mjo")
    if cached:
        return cached
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT phase, amplitude, classificacao,
                   to_char(data_referencia, 'YYYY-MM-DD')
            FROM climate.mjo_daily
            ORDER BY data_referencia DESC
            LIMIT 1
        """)
        r = cursor.fetchone()
        if r is None:
            raise HTTPException(status_code=404, detail="Sem dados MJO disponíveis")
        result = {
            "phase": int(r[0]),
            "amplitude": float(r[1]),
            "classificacao": r[2],
            "fase": _MJO_FASE.get(r[2], r[2]),
            "data_referencia": r[3],
        }
        _cache.set("mjo", result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro em /climate/mjo: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar MJO")
    finally:
        conn.close()


@app.get("/climate/co2", response_model=Co2Response)
def climate_co2():
    cached = _cache.get("co2")
    if cached:
        return cached
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT co2_ppm, to_char(data_referencia, 'YYYY-MM-DD')
            FROM climate.noaa_co2_daily
            WHERE data_referencia > NOW() - INTERVAL '30 days'
            ORDER BY data_referencia DESC
            LIMIT 1
        """)
        r = cursor.fetchone()
        if r is None:
            raise HTTPException(status_code=404, detail="Sem dados CO₂ disponíveis")
        result = {"co2_ppm": float(r[0]), "data_referencia": r[1]}
        _cache.set("co2", result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro em /climate/co2: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar CO₂")
    finally:
        conn.close()


@app.get("/climate/arctic_ice", response_model=IceResponse)
def climate_arctic_ice():
    cached = _cache.get("arctic_ice")
    if cached:
        return cached
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT extent_mkm2, area_mkm2, to_char(data_referencia, 'YYYY-MM-DD')
            FROM climate.nsidc_arctic_ice_daily
            WHERE data_referencia > NOW() - INTERVAL '30 days'
            ORDER BY data_referencia DESC
            LIMIT 1
        """)
        r = cursor.fetchone()
        if r is None:
            raise HTTPException(status_code=404, detail="Sem dados de gelo Ártico disponíveis")
        result = {
            "extent_mkm2": float(r[0]),
            "area_mkm2": float(r[1]) if r[1] is not None else None,
            "data_referencia": r[2],
        }
        _cache.set("arctic_ice", result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro em /climate/arctic_ice: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar gelo Ártico")
    finally:
        conn.close()


@app.get("/climate/antarctic_ice", response_model=IceResponse)
def climate_antarctic_ice():
    cached = _cache.get("antarctic_ice")
    if cached:
        return cached
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT extent_mkm2, area_mkm2, to_char(data_referencia, 'YYYY-MM-DD')
            FROM climate.nsidc_antarctic_ice_daily
            WHERE data_referencia > NOW() - INTERVAL '30 days'
            ORDER BY data_referencia DESC
            LIMIT 1
        """)
        r = cursor.fetchone()
        if r is None:
            raise HTTPException(status_code=404, detail="Sem dados de gelo Antártico disponíveis")
        result = {
            "extent_mkm2": float(r[0]),
            "area_mkm2": float(r[1]) if r[1] is not None else None,
            "data_referencia": r[2],
        }
        _cache.set("antarctic_ice", result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro em /climate/antarctic_ice: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar gelo Antártico")
    finally:
        conn.close()


@app.get("/climate/mjo/history", response_model=list[MjoHistoryItem])
def climate_mjo_history():
    cached = _cache.get("mjo_history")
    if cached:
        return cached
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT to_char(data_referencia, 'YYYY-MM-DD'), rmm1, rmm2, phase, amplitude, classificacao
            FROM (
                SELECT data_referencia, rmm1, rmm2, phase, amplitude, classificacao
                FROM climate.mjo_daily
                WHERE amplitude < 900
                ORDER BY data_referencia DESC
                LIMIT 60
            ) t
            ORDER BY data_referencia ASC
        """)
        rows = cursor.fetchall()
        dados = [
            {
                "data_referencia": r[0], "rmm1": float(r[1]), "rmm2": float(r[2]),
                "phase": int(r[3]), "amplitude": float(r[4]), "classificacao": r[5],
            }
            for r in rows
        ]
        _cache.set("mjo_history", dados)
        return dados
    except Exception as e:
        logger.error("Erro em /climate/mjo/history: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar histórico MJO")
    finally:
        conn.close()


@app.get("/climate/co2/history", response_model=list[Co2HistoryItem])
def climate_co2_history():
    cached = _cache.get("co2_history")
    if cached:
        return cached
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT to_char(data_referencia, 'YYYY-MM-DD'), co2_ppm
            FROM climate.noaa_co2_daily
            WHERE data_referencia > NOW() - INTERVAL '5 years'
            ORDER BY data_referencia ASC
        """)
        rows = cursor.fetchall()
        dados = [{"data_referencia": r[0], "co2_ppm": float(r[1])} for r in rows]
        _cache.set("co2_history", dados)
        return dados
    except Exception as e:
        logger.error("Erro em /climate/co2/history: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar histórico CO₂")
    finally:
        conn.close()


@app.get("/climate/arctic_ice/history", response_model=list[IceHistoryItem])
def climate_arctic_ice_history():
    cached = _cache.get("arctic_ice_history")
    if cached:
        return cached
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT to_char(data_referencia, 'YYYY-MM-DD'), extent_mkm2
            FROM climate.nsidc_arctic_ice_daily
            WHERE data_referencia > NOW() - INTERVAL '3 years'
            ORDER BY data_referencia ASC
        """)
        rows = cursor.fetchall()
        dados = [{"data_referencia": r[0], "extent_mkm2": float(r[1])} for r in rows]
        _cache.set("arctic_ice_history", dados)
        return dados
    except Exception as e:
        logger.error("Erro em /climate/arctic_ice/history: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar histórico gelo Ártico")
    finally:
        conn.close()


@app.get("/climate/antarctic_ice/history", response_model=list[IceHistoryItem])
def climate_antarctic_ice_history():
    cached = _cache.get("antarctic_ice_history")
    if cached:
        return cached
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT to_char(data_referencia, 'YYYY-MM-DD'), extent_mkm2
            FROM climate.nsidc_antarctic_ice_daily
            WHERE data_referencia > NOW() - INTERVAL '3 years'
            ORDER BY data_referencia ASC
        """)
        rows = cursor.fetchall()
        dados = [{"data_referencia": r[0], "extent_mkm2": float(r[1])} for r in rows]
        _cache.set("antarctic_ice_history", dados)
        return dados
    except Exception as e:
        logger.error("Erro em /climate/antarctic_ice/history: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar histórico gelo Antártico")
    finally:
        conn.close()


@app.get("/climate/prediction", response_model=PredictionResponse)
def climate_prediction():
    cached = _cache.get("prediction")
    if cached:
        return cached

    from app.services.zhora_service import get_latest_prediction

    prediction = get_latest_prediction()
    if prediction is None:
        prediction = "Nenhuma análise preditiva disponível. Execute POST /api/collect/prediction para gerar a primeira."

    result = {"prediction": prediction}
    _cache.set("prediction", result)
    return result


@app.get("/climate/plain", response_model=PlainResponse)
def climate_plain():
    cached = _cache.get("plain")
    if cached:
        return cached

    from app.services.zhora_service import get_latest_plain

    plain = get_latest_plain()
    if plain is None:
        plain = "Nenhum resumo disponível ainda. Execute POST /api/collect/prediction para gerar."

    result = {"plain": plain}
    _cache.set("plain", result)
    return result


@app.get("/climate/insight_plain", response_model=PlainResponse)
def climate_insight_plain():
    cached = _cache.get("insight_plain")
    if cached:
        return cached

    from app.services.zhora_service import get_latest_insight_plain

    plain = get_latest_insight_plain()
    if plain is None:
        plain = "Resumo ainda não gerado. Execute POST /api/collect/insight para gerar."

    result = {"plain": plain}
    _cache.set("insight_plain", result)
    return result


@app.get("/climate/seismic")
def climate_seismic(days: int = 30, min_mag: float = 5.5, climate_only: bool = False):
    """Return recent seismic/volcanic events. days=30, min_mag=5.5 by default."""
    cache_key = f"seismic_{days}_{min_mag}_{climate_only}"
    cached = _cache.get(cache_key)
    if cached:
        return cached
    conn = conectar()
    try:
        cursor = conn.cursor()
        where = "data_referencia > NOW() - INTERVAL '%s days' AND magnitude >= %s"
        params = [days, min_mag]
        if climate_only:
            where += " AND climate_relevant = TRUE"
        cursor.execute(f"""
            SELECT to_char(data_referencia,'YYYY-MM-DD'), timestamp_utc,
                   latitude, longitude, depth_km, magnitude, magnitude_type,
                   event_type, place, title, climate_relevant, alert_level
            FROM climate.seismic_events
            WHERE {where}
            ORDER BY magnitude DESC
            LIMIT 200
        """, params)
        rows = cursor.fetchall()
        result = [
            {
                "data_referencia": r[0], "timestamp_utc": r[1].isoformat() if r[1] else None,
                "latitude": float(r[2]) if r[2] else None,
                "longitude": float(r[3]) if r[3] else None,
                "depth_km": float(r[4]) if r[4] else None,
                "magnitude": float(r[5]),
                "magnitude_type": r[6], "event_type": r[7],
                "place": r[8], "title": r[9],
                "climate_relevant": r[10], "alert_level": r[11],
            }
            for r in rows
        ]
        _cache.set(cache_key, result)
        return result
    except Exception as e:
        logger.error("Erro em /climate/seismic: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar eventos sísmicos")
    finally:
        conn.close()


_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
_weather_cache = _TTLCache(ttl=600)


def _classify_weather_event(weather_code: int, wind_speed: float) -> str:
    if wind_speed is not None and wind_speed >= 40:
        return "ventania"
    if weather_code in (95, 96, 99):
        return "tempestade"
    if weather_code in (71, 73, 75, 77, 85, 86):
        return "neve"
    if weather_code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "chuva"
    if weather_code in (45, 48):
        return "neblina"
    if weather_code in (2, 3):
        return "nublado"
    return "ensolarado"


@app.get("/weather/local")
def weather_local(lat: float, lon: float):
    cache_key = f"{round(lat, 2)}_{round(lon, 2)}"
    cached = _weather_cache.get(cache_key)
    if cached:
        return cached

    try:
        r = _requests.get(_OPEN_METEO_URL, params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_gusts_10m,is_day",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max",
            "timezone": "auto",
            "forecast_days": 3,
        }, timeout=15)
        r.raise_for_status()
        data = r.json()

        current = data.get("current", {})
        event_type = _classify_weather_event(
            current.get("weather_code", 0),
            current.get("wind_speed_10m"),
        )

        daily = data.get("daily", {})
        dias = daily.get("time", [])
        forecast = []
        for i, dia in enumerate(dias):
            wcode = daily["weather_code"][i]
            wind_max = daily.get("wind_speed_10m_max", [None] * len(dias))[i]
            forecast.append({
                "data": dia,
                "weather_code": wcode,
                "event_type": _classify_weather_event(wcode, wind_max),
                "temp_max": daily["temperature_2m_max"][i],
                "temp_min": daily["temperature_2m_min"][i],
                "precipitation_prob": daily.get("precipitation_probability_max", [None] * len(dias))[i],
            })

        result = {
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "timezone": data.get("timezone"),
            "current": {
                "temperature": current.get("temperature_2m"),
                "humidity": current.get("relative_humidity_2m"),
                "precipitation": current.get("precipitation"),
                "wind_speed": current.get("wind_speed_10m"),
                "wind_gusts": current.get("wind_gusts_10m"),
                "is_day": bool(current.get("is_day")),
                "weather_code": current.get("weather_code"),
            },
            "event_type": event_type,
            "forecast": forecast,
        }
        _weather_cache.set(cache_key, result)
        return result
    except Exception as e:
        logger.error("Erro em /weather/local: %s", e)
        raise HTTPException(status_code=503, detail="Erro ao buscar dados meteorológicos locais")


_CPC_WEEKLY_URL = "https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for"

@app.get("/climate/nino34/weekly")
def nino34_weekly():
    cached = _cache.get("nino34_weekly")
    if cached:
        return cached

    try:
        r = _requests.get(_CPC_WEEKLY_URL, timeout=15)
        r.raise_for_status()
        result = []
        for line in r.text.strip().splitlines():
            parts = line.split()
            if len(parts) < 8:
                continue
            try:
                result.append({
                    "date": parts[0],
                    "nino12_anom": float(parts[2]),
                    "nino3_anom":  float(parts[4]),
                    "nino34_anom": float(parts[6]),
                    "nino4_anom":  float(parts[8]) if len(parts) > 8 else None,
                })
            except (ValueError, IndexError):
                continue
        data = result[-8:]
        _cache.set("nino34_weekly", data)
        return data
    except Exception as e:
        logger.error("Erro em /climate/nino34/weekly: %s", e)
        raise HTTPException(status_code=503, detail="Erro ao buscar dados semanais CPC")


# Serve the dashboard — must be mounted last so API routes take precedence
app.mount("/", StaticFiles(directory="dashboard", html=True), name="dashboard")
