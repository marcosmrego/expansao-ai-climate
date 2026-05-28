"""MJO daily collector — NOAA PSL VPM index (phase 1-8 + amplitude).

Source: NOAA Physical Sciences Laboratory — Velocity Potential MJO Index (VPM)
URL:    https://psl.noaa.gov/mjo/mjoindex/vpm.1x.CORe.txt
Format: year month day 0 pc1 pc2 amplitude  (no header, space-separated)
Phase computed from atan2(pc2, pc1) using the Wheeler-Hendon convention.
"""
import json
import math
import time
from datetime import date

import requests

URL = "https://psl.noaa.gov/mjo/mjoindex/vpm.1x.CORe.txt"
ORIGEM = "NOAA_PSL_VPM"
_MISSING = 999.0


def _angle_to_phase(pc1: float, pc2: float) -> int:
    """Convert (PC1, PC2) vector to Wheeler-Hendon phase (1-8).

    Phase N has its centre at math angle 90 - (N-1)*45 degrees.
    Phases increase clockwise (consistent with WH2004 convention).
    """
    angle = math.degrees(math.atan2(pc2, pc1))
    return int((90 - angle + 360) % 360 / 45) % 8 + 1


def classificar_mjo(phase: int, amplitude: float) -> str:
    if amplitude < 1.0:
        return "FRACO"
    if phase in (5, 6, 7):
        return "FAVORAVEL_ELNINO"
    if phase in (1, 2, 3):
        return "FAVORAVEL_LANINA"
    return "ATIVO"


def baixar_dados() -> str:
    for tentativa in range(1, 4):
        try:
            r = requests.get(URL, timeout=60)
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
    """Parse NOAA PSL VPM file into (date, pc1, pc2, phase, amplitude) tuples.

    Format (space-separated, no header):
      year  month  day  0  PC1  PC2  amplitude
    Phase is computed from atan2(PC2, PC1).
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
            pc1 = float(partes[4])
            pc2 = float(partes[5])
            amplitude = float(partes[6])
        except (ValueError, IndexError):
            continue
        if abs(pc1) >= _MISSING or abs(pc2) >= _MISSING or abs(amplitude) >= _MISSING:
            continue
        try:
            d = date(ano, mes, dia)
        except ValueError:
            continue
        phase = _angle_to_phase(pc1, pc2)
        registros.append((d, pc1, pc2, phase, amplitude))
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
