"""Shared utilities for NOAA PSL monthly correlation data files.

Format: first line is header/metadata; subsequent lines:
  YEAR  Jan  Feb  Mar  Apr  May  Jun  Jul  Aug  Sep  Oct  Nov  Dec
Missing values are typically -99, -99.9, or -99.99.
"""
import hashlib
import json
import time
from datetime import date

import requests


def baixar_dados(url: str, tentativas: int = 3, espera: int = 5) -> str:
    for tentativa in range(1, tentativas + 1):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            if tentativa == tentativas:
                raise
            print(f"Tentativa {tentativa} falhou: {e}. Aguardando {espera}s...")
            time.sleep(espera)


def gerar_hash(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def salvar_payload_bruto(conn, texto: str, origem: str, url: str) -> int:
    hash_payload = gerar_hash(texto)
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO climate.raw_payload (origem, url, content_type, payload_text, hash_payload)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (origem, url, "text/plain", texto, hash_payload),
        )
        return cursor.fetchone()[0]


def parse_noaa_psl_monthly(texto: str, missing_threshold: float = -99.0):
    """Parse NOAA PSL monthly correlation files.

    Returns list of (ano, mes, valor) tuples for non-missing values.
    """
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
            if valor <= missing_threshold:
                continue
            registros.append((ano, mes, valor))
    return registros


def inserir_registros_mensais(
    conn,
    registros: list,
    raw_payload_id: int,
    tabela: str,
    coluna_valor: str,
    classificar_fn,
    origem: str,
) -> int:
    """Generic INSERT for NOAA PSL monthly tables using ON CONFLICT DO UPDATE."""
    total = 0
    with conn.cursor() as cursor:
        for ano, mes, valor in registros:
            cursor.execute(
                f"""
                INSERT INTO climate.{tabela} (
                    data_referencia, ano, mes, {coluna_valor}, classificacao, fonte, payload_bruto
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ano, mes) DO UPDATE SET
                    {coluna_valor} = EXCLUDED.{coluna_valor},
                    classificacao = EXCLUDED.classificacao,
                    fonte = EXCLUDED.fonte,
                    payload_bruto = EXCLUDED.payload_bruto,
                    criado_em = NOW();
                """,
                (
                    date(ano, mes, 1),
                    ano,
                    mes,
                    valor,
                    classificar_fn(valor),
                    origem,
                    json.dumps({"raw_payload_id": str(raw_payload_id)}),
                ),
            )
            total += 1
    return total
