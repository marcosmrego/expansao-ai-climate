import hashlib
import json
import time
from datetime import date

import requests
from dotenv import load_dotenv

from database.db import conectar
from app.services.climate_alert_repository import check_and_save_soi_alerts
from app.services.zhora_service import build_climate_context, save_context_snapshot


URL = "https://psl.noaa.gov/data/correlation/soi.data"
ORIGEM = "NOAA_PSL_SOI"

load_dotenv()


def baixar_dados(tentativas=3, espera=5):
    for tentativa in range(1, tentativas + 1):
        try:
            response = requests.get(URL, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            if tentativa == tentativas:
                raise
            print(f"Tentativa {tentativa} falhou: {e}. Aguardando {espera}s...")
            time.sleep(espera)


def gerar_hash(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def classificar_soi(valor):
    """SOI is inverted vs ONI: negative = El Niño signal, positive = La Niña signal."""
    if valor <= -1.0:
        return "EL_NINO"
    if valor >= 1.0:
        return "LA_NINA"
    return "NEUTRO"


def salvar_payload_bruto(conn, texto):
    hash_payload = gerar_hash(texto)
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO climate.raw_payload (
                origem, url, content_type, payload_text, hash_payload
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (ORIGEM, URL, "text/plain", texto, hash_payload),
        )
        return cursor.fetchone()[0]


def parse_linhas(texto):
    registros = []
    for linha in texto.splitlines():
        partes = linha.split()
        if len(partes) != 13:
            continue
        try:
            ano = int(partes[0])
        except ValueError:
            continue
        for mes in range(1, 13):
            try:
                valor = float(partes[mes])
            except ValueError:
                continue
            if valor <= -99:
                continue
            registros.append(
                {
                    "ano": ano,
                    "mes": mes,
                    "data_referencia": date(ano, mes, 1),
                    "soi": valor,
                    "classificacao": classificar_soi(valor),
                }
            )
    return registros


def inserir_registros(conn, registros, raw_payload_id):
    total = 0
    with conn.cursor() as cursor:
        for r in registros:
            cursor.execute(
                """
                INSERT INTO climate.noaa_soi (
                    data_referencia, ano, mes, soi, classificacao, fonte, payload_bruto
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ano, mes)
                DO UPDATE SET
                    soi = EXCLUDED.soi,
                    classificacao = EXCLUDED.classificacao,
                    fonte = EXCLUDED.fonte,
                    payload_bruto = EXCLUDED.payload_bruto,
                    criado_em = NOW();
                """,
                (
                    r["data_referencia"],
                    r["ano"],
                    r["mes"],
                    r["soi"],
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
        print(f"Registros SOI processados: {total}")

        result = check_and_save_soi_alerts()
        saved = result.get("saved", 0)
        if saved:
            print(f"Alertas SOI gerados: {saved} (ids={result.get('ids')})")
        else:
            print("Nenhum alerta SOI novo.")

        ctx = build_climate_context()
        snapshot_id = save_context_snapshot(ctx)
        print(f"Contexto operacional atualizado: snapshot_id={snapshot_id}")

    except Exception as erro:
        conn.rollback()
        print(f"Erro na coleta SOI: {erro}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
