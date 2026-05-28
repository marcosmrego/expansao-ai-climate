from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

import os
import time
import logging

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


# Serve the dashboard — must be mounted last so API routes take precedence
app.mount("/", StaticFiles(directory="dashboard", html=True), name="dashboard")
