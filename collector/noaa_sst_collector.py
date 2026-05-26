import os
import sys
import hashlib
import json
from datetime import date

import requests
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.db import conectar


URL = "https://www.cpc.ncep.noaa.gov/data/indices/ersst5.nino.mth.91-20.ascii"
ORIGEM = "NOAA_CPC_ERSST5_NINO"


load_dotenv()


def baixar_dados():
    response = requests.get(URL, timeout=30)
    response.raise_for_status()
    return response.text


def gerar_hash(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def salvar_payload_bruto(conn, texto):
    hash_payload = gerar_hash(texto)

    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO climate.raw_payload (
                origem,
                url,
                content_type,
                payload_text,
                hash_payload
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                ORIGEM,
                URL,
                "text/plain",
                texto,
                hash_payload,
            ),
        )

        return cursor.fetchone()[0]


def parse_linhas(texto):
    registros = []

    linhas = texto.splitlines()

    for linha in linhas[1:]:
        partes = linha.split()

        if len(partes) != 10:
            continue

        ano = int(partes[0])
        mes = int(partes[1])

        registros.append(
            {
                "ano": ano,
                "mes": mes,
                "data_referencia": date(ano, mes, 1),
                "nino_12_temp": float(partes[2]),
                "nino_12_anom": float(partes[3]),
                "nino_3_temp": float(partes[4]),
                "nino_3_anom": float(partes[5]),
                "nino_4_temp": float(partes[6]),
                "nino_4_anom": float(partes[7]),
                "nino_34_temp": float(partes[8]),
                "nino_34_anom": float(partes[9]),
            }
        )

    return registros


def inserir_registros(conn, registros, raw_payload_id):
    total = 0

    with conn.cursor() as cursor:
        for r in registros:
            cursor.execute(
                """
                INSERT INTO climate.noaa_sst_indices (
                    data_referencia,
                    ano,
                    mes,
                    nino_12_temp,
                    nino_12_anom,
                    nino_3_temp,
                    nino_3_anom,
                    nino_4_temp,
                    nino_4_anom,
                    nino_34_temp,
                    nino_34_anom,
                    fonte,
                    payload_bruto
                )
                VALUES (
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s,
                    %s
                )
                ON CONFLICT (ano, mes)
                DO UPDATE SET
                    nino_12_temp = EXCLUDED.nino_12_temp,
                    nino_12_anom = EXCLUDED.nino_12_anom,
                    nino_3_temp = EXCLUDED.nino_3_temp,
                    nino_3_anom = EXCLUDED.nino_3_anom,
                    nino_4_temp = EXCLUDED.nino_4_temp,
                    nino_4_anom = EXCLUDED.nino_4_anom,
                    nino_34_temp = EXCLUDED.nino_34_temp,
                    nino_34_anom = EXCLUDED.nino_34_anom,
                    fonte = EXCLUDED.fonte,
                    payload_bruto = EXCLUDED.payload_bruto,
                    criado_em = NOW();
                """,
                (
                    r["data_referencia"],
                    r["ano"],
                    r["mes"],
                    r["nino_12_temp"],
                    r["nino_12_anom"],
                    r["nino_3_temp"],
                    r["nino_3_anom"],
                    r["nino_4_temp"],
                    r["nino_4_anom"],
                    r["nino_34_temp"],
                    r["nino_34_anom"],
                    ORIGEM,
                    json.dumps({"raw_payload_id": str(raw_payload_id)}),
                ),
            )
            total += 1

    return total


def main():
    conn = conectar()

    try:
        texto = baixar_dados()
        registros = parse_linhas(texto)

        raw_payload_id = salvar_payload_bruto(conn, texto)
        total = inserir_registros(conn, registros, raw_payload_id)

        conn.commit()

        print(f"Payload salvo: {raw_payload_id}")
        print(f"Registros processados: {total}")

    except Exception as erro:
        conn.rollback()
        print(f"Erro na coleta: {erro}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()