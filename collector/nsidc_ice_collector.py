"""Sea ice daily collector — NSIDC (Arctic + Antarctic extent)."""
import json
import time
from datetime import date

import requests

URL_ARCTIC = "https://noaadata.apps.nsidc.org/NOAA/G02135/north/daily/data/N_seaice_extent_daily_v3.0.csv"
URL_ANTARCTIC = "https://noaadata.apps.nsidc.org/NOAA/G02135/south/daily/data/S_seaice_extent_daily_v3.0.csv"

ORIGEM_ARCTIC = "NSIDC_ARCTIC_ICE"
ORIGEM_ANTARCTIC = "NSIDC_ANTARCTIC_ICE"

TABLE_ARCTIC = "nsidc_arctic_ice_daily"
TABLE_ANTARCTIC = "nsidc_antarctic_ice_daily"

_MISSING = -9999.0


def baixar_dados(url: str) -> str:
    for tentativa in range(1, 4):
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            if tentativa == 3:
                raise
            print(f"Tentativa {tentativa} falhou: {e}. Aguardando 5s...")
            time.sleep(5)


def salvar_payload_bruto(conn, texto: str, origem: str, url: str) -> int:
    from collector.noaa_psl_base import gerar_hash
    hash_payload = gerar_hash(texto)
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO climate.raw_payload (origem, url, content_type, payload_text, hash_payload)
            VALUES (%s, %s, %s, %s, %s) RETURNING id;
            """,
            (origem, url, "text/csv", texto, hash_payload),
        )
        return cursor.fetchone()[0]


def parse_ice(texto: str) -> list:
    """Parse NSIDC daily sea ice CSV into (date, extent_mkm2, area_mkm2) tuples.

    Format (CSV with header):
      Year,Month,Day,Extent,Area,Source Data
    Extent and Area in million km². Missing: -9999
    """
    registros = []
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or not linha[0].isdigit():
            continue
        partes = linha.split(',')
        if len(partes) < 4:
            continue
        try:
            ano = int(partes[0].strip())
            mes = int(partes[1].strip())
            dia = int(partes[2].strip())
            extent = float(partes[3].strip())
        except (ValueError, IndexError):
            continue
        if extent <= _MISSING:
            continue
        area = None
        if len(partes) >= 5:
            try:
                a = float(partes[4].strip())
                if a > _MISSING:
                    area = a
            except (ValueError, IndexError):
                pass
        try:
            d = date(ano, mes, dia)
        except ValueError:
            continue
        registros.append((d, extent, area))
    return registros


def inserir_registros(conn, registros: list, raw_payload_id: int, tabela: str, origem: str) -> int:
    total = 0
    with conn.cursor() as cursor:
        for d, extent, area in registros:
            cursor.execute(
                f"""
                INSERT INTO climate.{tabela}
                    (data_referencia, extent_mkm2, area_mkm2, fonte, payload_bruto)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (data_referencia) DO UPDATE SET
                    extent_mkm2   = EXCLUDED.extent_mkm2,
                    area_mkm2     = EXCLUDED.area_mkm2,
                    fonte         = EXCLUDED.fonte,
                    payload_bruto = EXCLUDED.payload_bruto,
                    criado_em     = NOW();
                """,
                (d, extent, area, origem, json.dumps({"raw_payload_id": str(raw_payload_id)})),
            )
            total += 1
    return total
