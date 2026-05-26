from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import os
import sys

sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            ".."
        )
    )
)

from database.db import conectar

from app.routes.climate_alerts import router as climate_alert_router


app = FastAPI(
    title="Expansao AI Climate API"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(
    climate_alert_router
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/climate/status")
def climate_status():

    conn = conectar()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM climate.vw_enso_status
        """)

        r = cursor.fetchone()

        return {
            "oni": float(r[2]),
            "classificacao": r[3],
            "nino34": float(r[6]),
            "fase": r[8]
        }

    finally:
        conn.close()


@app.get("/climate/history")
def climate_history():

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

        return dados

    finally:
        conn.close()


@app.get("/climate/analysis")
def climate_analysis():

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

        return {
            "oni": oni,
            "nino34": nino34,
            "analysis": texto
        }

    finally:
        conn.close()


@app.get("/climate/trend")
def climate_trend():

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

        return {
            "atual": atual,
            "anterior": anterior,
            "variacao": variacao,
            "tendencia": tendencia
        }

    finally:
        conn.close()


@app.get("/climate/update")
def climate_update():

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

        return {
            "ultima_atualizacao": ultima,
            "fonte": "NOAA"
        }

    finally:
        conn.close()