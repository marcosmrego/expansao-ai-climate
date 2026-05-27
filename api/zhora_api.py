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
    allow_methods=["GET"],
    allow_headers=["*"],
)


app.include_router(climate_alert_router)
app.include_router(zhora_router)


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

    conn = conectar()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                o.oni,
                o.classificacao,
                s.nino_34_anom
            FROM
            (
                SELECT
                    oni,
                    classificacao,
                    data_referencia
                FROM climate.noaa_oni
                WHERE oni > -99
                ORDER BY data_referencia DESC
                LIMIT 1
            ) o
            CROSS JOIN
            (
                SELECT
                    nino_34_anom
                FROM climate.noaa_sst_indices
                ORDER BY data_referencia DESC
                LIMIT 1
            ) s
        """)

        r = cursor.fetchone()

        oni = float(r[0])
        nino34 = float(r[2])

        if oni >= 0.5:
            texto = "Indicadores oceânicos compatíveis com El Niño."
        elif oni <= -0.5:
            texto = "Indicadores oceânicos compatíveis com La Niña."
        else:
            texto = "ENSO segue em neutralidade."

        result = {
            "oni": oni,
            "nino34": nino34,
            "analysis": texto
        }
        _cache.set("analysis", result)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro em /climate/analysis: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao gerar análise climática")
    finally:
        conn.close()


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


# Serve the dashboard — must be mounted last so API routes take precedence
app.mount("/", StaticFiles(directory="dashboard", html=True), name="dashboard")
