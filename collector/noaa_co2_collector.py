"""CO₂ daily collector — NOAA GML Mauna Loa Observatory."""
import json
import time
from datetime import date

import requests

URL = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_daily_mlo.txt"
ORIGEM = "NOAA_GML_CO2"
_MISSING = -999.0


def baixar_dados() -> str:
    for tentativa in range(1, 4):
        try:
            r = requests.get(URL, timeout=30)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            if tentativa == 3:
                raise
            print(f"Tentativa {tentativa} falhou: {e}. Aguardando 5s...")
            time.sleep(5)


def salvar_payload_bruto(conn, texto: str) -> int:
    from collector.noaa_psl_base import gerar_hash
    hash_payload = gerar_hash(texto)
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO climate.raw_payload (origem, url, content_type, payload_text, hash_payload)
            VALUES (%s, %s, %s, %s, %s) RETURNING id;
            """,
            (ORIGEM, URL, "text/plain", texto, hash_payload),
        )
        return cursor.fetchone()[0]


def parse_co2(texto: str) -> list:
    """Parse NOAA GML daily CO₂ file into (date, co2_ppm) tuples.

    Format (after # header lines):
      year  month  day  decimal_date  co2_ppm
    Missing: -999.99
    """
    registros = []
    for linha in texto.splitlines():
        if linha.startswith('#') or not linha.strip():
            continue
        partes = linha.split()
        if len(partes) < 5:
            continue
        try:
            ano = int(partes[0])
            mes = int(partes[1])
            dia = int(partes[2])
            co2 = float(partes[4])
        except (ValueError, IndexError):
            continue
        if co2 <= _MISSING:
            continue
        try:
            d = date(ano, mes, dia)
        except ValueError:
            continue
        registros.append((d, co2))
    return registros


def inserir_registros(conn, registros: list, raw_payload_id: int) -> int:
    total = 0
    with conn.cursor() as cursor:
        for d, co2 in registros:
            cursor.execute(
                """
                INSERT INTO climate.noaa_co2_daily
                    (data_referencia, co2_ppm, fonte, payload_bruto)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (data_referencia) DO UPDATE SET
                    co2_ppm       = EXCLUDED.co2_ppm,
                    fonte         = EXCLUDED.fonte,
                    payload_bruto = EXCLUDED.payload_bruto,
                    criado_em     = NOW();
                """,
                (d, co2, ORIGEM, json.dumps({"raw_payload_id": str(raw_payload_id)})),
            )
            total += 1
    return total
