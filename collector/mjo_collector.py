"""MJO daily collector — NOAA CPC RMM index (phase 1-8 + amplitude)."""
import json
import time
from datetime import date

import requests

URL = "http://www.bom.gov.au/climate/mjo/graphics/rmm.74toRealtime.txt"
ORIGEM = "BOM_MJO_RMM"
_MISSING = 999.0
_MISSING_LARGE = 1e30


def classificar_mjo(phase: int, amplitude: float) -> str:
    if amplitude < 1.0:
        return "FRACO"
    if phase in (5, 6, 7):
        return "FAVORAVEL_ELNINO"
    if phase in (1, 2, 3):
        return "FAVORAVEL_LANINA"
    return "ATIVO"


_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bom.gov.au/climate/mjo/",
    "Accept": "text/plain, */*",
}


def baixar_dados() -> str:
    for tentativa in range(1, 4):
        try:
            r = requests.get(URL, headers=_HEADERS, timeout=30)
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


def parse_rmm(texto: str) -> list:
    """Parse NOAA CPC RMM file into (date, rmm1, rmm2, phase, amplitude) tuples.

    Expected format (space-separated):
      year  month  day  RMM1  RMM2  phase  amplitude  [source]
    Missing values represented as 999 or 1E36.
    """
    registros = []
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or not linha[0].isdigit():
            continue
        partes = linha.split()
        if len(partes) < 7:
            continue
        try:
            ano = int(partes[0])
            mes = int(partes[1])
            dia = int(partes[2])
            rmm1 = float(partes[3])
            rmm2 = float(partes[4])
            phase = int(float(partes[5]))
            amplitude = float(partes[6])
        except (ValueError, IndexError):
            continue
        if abs(rmm1) >= _MISSING_LARGE or abs(rmm2) >= _MISSING_LARGE or amplitude >= _MISSING_LARGE:
            continue
        if abs(rmm1) >= _MISSING or abs(rmm2) >= _MISSING or amplitude >= _MISSING:
            continue
        if not (1 <= phase <= 8):
            continue
        try:
            d = date(ano, mes, dia)
        except ValueError:
            continue
        registros.append((d, rmm1, rmm2, phase, amplitude))
    return registros


def inserir_registros(conn, registros: list, raw_payload_id: int) -> int:
    total = 0
    with conn.cursor() as cursor:
        for d, rmm1, rmm2, phase, amplitude in registros:
            cursor.execute(
                """
                INSERT INTO climate.mjo_daily
                    (data_referencia, rmm1, rmm2, phase, amplitude, classificacao, fonte, payload_bruto)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (data_referencia) DO UPDATE SET
                    rmm1          = EXCLUDED.rmm1,
                    rmm2          = EXCLUDED.rmm2,
                    phase         = EXCLUDED.phase,
                    amplitude     = EXCLUDED.amplitude,
                    classificacao = EXCLUDED.classificacao,
                    fonte         = EXCLUDED.fonte,
                    payload_bruto = EXCLUDED.payload_bruto,
                    criado_em     = NOW();
                """,
                (
                    d, rmm1, rmm2, phase, amplitude,
                    classificar_mjo(phase, amplitude),
                    ORIGEM,
                    json.dumps({"raw_payload_id": str(raw_payload_id)}),
                ),
            )
            total += 1
    return total
