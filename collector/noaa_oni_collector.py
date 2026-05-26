import os
import sys
import hashlib
import json
from datetime import date

import requests
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.db import conectar


URL = "https://psl.noaa.gov/data/correlation/oni.data"
ORIGEM = "NOAA_PSL_ONI"

load_dotenv()


def baixar_dados():
    response = requests.get(URL, timeout=30)
    response.raise_for_status()
    return response.text


def gerar_hash(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def classificar_oni(valor):
    if valor >= 0.5:
        return "EL_NINO"
    if valor <= -0.5:
        return "LA_NINA"
    return "NEUTRO"


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

        if len(partes) != 13:
            continue

        ano = int(partes[0])

        for mes in range(1, 13):
            valor = float(partes[mes])

            if valor <= -99:
                continue
            
            registros.append(
                {
                    "ano": ano,
                    "mes": mes,
                    "data_referencia": date(ano, mes, 1),
                    "oni": valor,
                    "classificacao": classificar_oni(valor),
                }
            )

    return registros


def inserir_registros(conn, registros, raw_payload_id):
    total = 0

    with conn.cursor() as cursor:
        for r in registros:
            cursor.execute(
                """
                INSERT INTO climate.noaa_oni (
                    data_referencia,
                    ano,
                    mes,
                    oni,
                    classificacao,
                    fonte,
                    payload_bruto
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ano, mes)
                DO UPDATE SET
                    oni = EXCLUDED.oni,
                    classificacao = EXCLUDED.classificacao,
                    fonte = EXCLUDED.fonte,
                    payload_bruto = EXCLUDED.payload_bruto,
                    criado_em = NOW();
                """,
                (
                    r["data_referencia"],
                    r["ano"],
                    r["mes"],
                    r["oni"],
                    r["classificacao"],
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
        print(f"Registros ONI processados: {total}")

    except Exception as erro:
        conn.rollback()
        print(f"Erro na coleta ONI: {erro}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()