"""Focos de calor — INPE Programa Queimadas (dados abertos, sem chave).

Fonte primária da área Brasil. Só o satélite de referência (AQUA_M-T) entra na
série diária comparável (fire_daily_agg); os demais servem ao mapa e ficam poucos dias.
"""
import csv
import io
import logging
import math
import time
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Iterator, Optional

import requests
from psycopg2.extras import execute_values

from collector.run_log import finalizar_execucao, iniciar_execucao

logger = logging.getLogger(__name__)

BASE_URL = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv"
FONTE = "inpe"
RUN_FONTE = "inpe_focos"
SATELITE_REF = "AQUA_M-T"
RETENCAO_PONTOS_DIAS = 730
RETENCAO_NAO_REF_DIAS = 14
ZIP_MAX_BYTES = 300 * 1024 * 1024
LOCK_COLETA_ID = 7_010_001
DIAS_JANELA_RECENTE = 2

_USER_AGENT = "ExpansaoAI-Climate/1.0 (+https://climate.expansao-ai.com.br)"
_TENTATIVAS = 4
_ESPERA_BASE_S = 5
_TIMEOUT_S = 120
_PAGE_SIZE = 2000

_UF_POR_NOME = {
    "ACRE": "AC", "ALAGOAS": "AL", "AMAPA": "AP", "AMAZONAS": "AM", "BAHIA": "BA",
    "CEARA": "CE", "DISTRITO FEDERAL": "DF", "ESPIRITO SANTO": "ES", "GOIAS": "GO",
    "MARANHAO": "MA", "MATO GROSSO": "MT", "MATO GROSSO DO SUL": "MS",
    "MINAS GERAIS": "MG", "PARA": "PA", "PARAIBA": "PB", "PARANA": "PR",
    "PERNAMBUCO": "PE", "PIAUI": "PI", "RIO DE JANEIRO": "RJ",
    "RIO GRANDE DO NORTE": "RN", "RIO GRANDE DO SUL": "RS", "RONDONIA": "RO",
    "RORAIMA": "RR", "SANTA CATARINA": "SC", "SAO PAULO": "SP", "SERGIPE": "SE",
    "TOCANTINS": "TO",
}


@dataclass(frozen=True)
class Foco:
    fonte_id: str
    satelite: str
    detectado_em: datetime
    latitude: float
    longitude: float
    frp: Optional[float]
    risco_fogo: Optional[float]
    dias_sem_chuva: Optional[int]
    precipitacao: Optional[float]
    uf: Optional[str]
    municipio: str
    municipio_id: Optional[int]
    bioma: Optional[str]
    is_ref: bool


@dataclass(frozen=True)
class Agregado:
    focos: int
    frp_soma: float


# ── Normalização ──────────────────────────────────────────────────────────────

def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto)
    return "".join(ch for ch in base if not unicodedata.combining(ch))


def normalizar_uf(nome: str) -> Optional[str]:
    return _UF_POR_NOME.get(_sem_acento((nome or "").strip()).upper())


def slug_bioma(nome: str) -> Optional[str]:
    limpo = _sem_acento((nome or "").strip()).lower()
    return limpo.replace(" ", "-") if limpo else None


def _num(valor, tipo=float):
    """Converte número do CSV; vazio ou sentinela negativa (-999) vira None."""
    try:
        n = int(float(valor)) if tipo is int else float(valor)
    except (TypeError, ValueError):
        return None
    return None if (not math.isfinite(n) or n < 0) else n


def _linha_para_foco(row: dict) -> Optional[Foco]:
    if (row.get("pais") or "").strip().lower() != "brasil":
        return None
    try:
        detectado = datetime.strptime(row["data_hora_gmt"].strip(), "%Y-%m-%d %H:%M:%S")
        lat, lon = float(row["lat"]), float(row["lon"])
        fonte_id = row["id"].strip()
    except (KeyError, ValueError, AttributeError):
        return None
    satelite = (row.get("satelite") or "").strip()
    return Foco(
        fonte_id=fonte_id,
        satelite=satelite,
        detectado_em=detectado.replace(tzinfo=timezone.utc),
        latitude=lat,
        longitude=lon,
        frp=_num(row.get("frp")),
        risco_fogo=_num(row.get("risco_fogo")),
        dias_sem_chuva=_num(row.get("numero_dias_sem_chuva"), int),
        precipitacao=_num(row.get("precipitacao")),
        uf=normalizar_uf(row.get("estado", "")),
        municipio=(row.get("municipio") or "").strip(),
        municipio_id=_num(row.get("municipio_id"), int),
        bioma=slug_bioma(row.get("bioma", "")),
        is_ref=satelite == SATELITE_REF,
    )


def parse_focos(linhas: Iterable[str]) -> Iterator[Foco]:
    """Converte linhas do CSV diário/mensal do INPE; ignora outros países e linhas inválidas."""
    for row in csv.DictReader(_sem_bom(linhas)):
        foco = _linha_para_foco(row)
        if foco is not None:
            yield foco


def _sem_bom(linhas: Iterable[str]) -> Iterator[str]:
    for i, linha in enumerate(linhas):
        yield linha.lstrip("﻿") if i == 0 else linha


def parse_focos_estrito(linhas: list[str]) -> list[Foco]:
    """Como parse_focos, mas falha se havia dados e nenhum foco foi aceito (layout mudou)."""
    focos = list(parse_focos(linhas))
    if len(linhas) > 1 and not focos:
        raise ValueError("CSV do INPE sem registros válidos: layout inesperado?")
    return focos


# ── Agregação (satélite de referência) ────────────────────────────────────────

def _acumular(agg: dict, dia: date, uf: Optional[str], bioma: Optional[str], frp: Optional[float]) -> None:
    chaves = [(dia, "brasil", "BR")]
    if uf:
        chaves.append((dia, "uf", uf))
    if bioma:
        chaves.append((dia, "bioma", bioma))
    for chave in chaves:
        atual = agg.get(chave, Agregado(0, 0.0))
        agg[chave] = Agregado(atual.focos + 1, atual.frp_soma + (frp or 0.0))


def agregar_focos(focos: Iterable[Foco]) -> dict:
    agg: dict = {}
    for f in focos:
        if f.is_ref:
            _acumular(agg, f.detectado_em.date(), f.uf, f.bioma, f.frp)
    return agg


def agregar_anual_ref(linhas: Iterable[str]) -> dict:
    """Agrega o CSV anual do satélite de referência (sem coluna de satélite nem FRP)."""
    agg: dict = {}
    for row in csv.DictReader(linhas):
        if (row.get("pais") or "").strip().lower() != "brasil":
            continue
        try:
            dia = datetime.strptime(row["data_pas"].strip()[:10], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue
        _acumular(agg, dia, normalizar_uf(row.get("estado", "")), slug_bioma(row.get("bioma", "")), None)
    return agg


# ── URLs e download ───────────────────────────────────────────────────────────

def url_diario(dia: date) -> str:
    return f"{BASE_URL}/diario/Brasil/focos_diario_br_{dia:%Y%m%d}.csv"


def url_mensal(ano: int, mes: int) -> str:
    return f"{BASE_URL}/mensal/Brasil/focos_mensal_br_{ano}{mes:02d}.csv"


def url_anual_ref(ano: int) -> str:
    return f"{BASE_URL}/anual/Brasil_sat_ref/focos_br_ref_{ano}.zip"


def janela_recente(hoje: date, dias: int = DIAS_JANELA_RECENTE) -> list[date]:
    return [hoje - timedelta(days=n) for n in range(dias - 1, -1, -1)]


class _ErroDefinitivo(Exception):
    """Erro HTTP 4xx (exceto 404/429): repetir não adianta."""


def _get(url: str, stream: bool = False) -> Optional[requests.Response]:
    """GET com espera progressiva em 429/5xx/rede. Retorna None em 404."""
    for tentativa in range(1, _TENTATIVAS + 1):
        try:
            r = requests.get(url, timeout=_TIMEOUT_S, stream=stream, headers={"User-Agent": _USER_AGENT})
            if r.status_code == 404:
                r.close()
                return None
            if r.status_code == 429 or r.status_code >= 500:
                r.close()
                raise requests.HTTPError(f"HTTP {r.status_code}")
            if r.status_code >= 400:
                r.close()
                raise _ErroDefinitivo(f"HTTP {r.status_code} em {url}")
            r.encoding = "utf-8"
            return r
        except _ErroDefinitivo:
            raise
        except requests.RequestException as e:
            if tentativa == _TENTATIVAS:
                raise
            espera = _ESPERA_BASE_S * 2 ** (tentativa - 1)
            logger.warning("Falha em %s (%s). Nova tentativa em %ss", url, e, espera)
            time.sleep(espera)
    return None


def abrir_linhas(url: str) -> Optional[Iterator[str]]:
    """Linhas do CSV remoto em streaming; None se o arquivo não existe."""
    r = _get(url, stream=True)
    if r is None:
        return None

    def _gen():
        try:
            yield from r.iter_lines(decode_unicode=True)
        finally:
            r.close()

    return (linha for linha in _gen() if linha)


def linhas_zip_anual(ano: int) -> Optional[Iterator[str]]:
    """Linhas do CSV dentro do ZIP anual de referência; None se o ano não existe."""
    r = _get(url_anual_ref(ano))
    if r is None:
        return None
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        info = z.infolist()[0]
        if info.file_size > ZIP_MAX_BYTES:
            raise ValueError(f"arquivo anual excede o limite: {info.file_size} bytes")
        dados = z.read(info).decode("utf-8")
    return iter(dados.splitlines())


# ── Persistência ──────────────────────────────────────────────────────────────

def inserir_focos(conn, focos: Iterable[Foco]) -> int:
    """Upsert idempotente por (fonte, fonte_id). Retorna a quantidade processada."""
    unicos = {f.fonte_id: f for f in focos}  # o mesmo id duas vezes quebraria o upsert
    linhas = [
        (FONTE, f.fonte_id, f.satelite, f.detectado_em, f.latitude, f.longitude, f.frp,
         f.risco_fogo, f.dias_sem_chuva, f.precipitacao, f.uf, f.municipio,
         f.municipio_id, f.bioma, f.is_ref)
        for f in unicos.values()
    ]
    if not linhas:
        return 0
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO climate.fire_hotspot
                (fonte, fonte_id, satelite, detectado_em, latitude, longitude, frp,
                 risco_fogo, dias_sem_chuva, precipitacao, uf, municipio,
                 municipio_id, bioma, is_ref)
            VALUES %s
            ON CONFLICT (fonte, fonte_id) DO UPDATE SET
                frp = EXCLUDED.frp, risco_fogo = EXCLUDED.risco_fogo,
                dias_sem_chuva = EXCLUDED.dias_sem_chuva, precipitacao = EXCLUDED.precipitacao,
                uf = EXCLUDED.uf, municipio = EXCLUDED.municipio,
                municipio_id = EXCLUDED.municipio_id, bioma = EXCLUDED.bioma,
                is_ref = EXCLUDED.is_ref
            """,
            linhas,
            page_size=_PAGE_SIZE,
        )
    return len(linhas)


def gravar_agregados(conn, agg: dict) -> int:
    """Upsert de agregados diários já calculados (usado no backfill histórico)."""
    linhas = [(d, nivel, cod, a.focos, a.frp_soma) for (d, nivel, cod), a in agg.items()]
    if not linhas:
        return 0
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO climate.fire_daily_agg (data, nivel, codigo, focos, frp_soma)
            VALUES %s
            ON CONFLICT (data, nivel, codigo) DO UPDATE SET
                focos = EXCLUDED.focos, frp_soma = EXCLUDED.frp_soma
            """,
            linhas,
            page_size=_PAGE_SIZE,
        )
    return len(linhas)


_SQL_REAGREGAR = """
WITH h AS (
    SELECT (detectado_em AT TIME ZONE 'UTC')::date AS d, uf, bioma, frp
      FROM climate.fire_hotspot
     WHERE is_ref AND detectado_em >= %(ini)s AND detectado_em < %(fim)s
)
INSERT INTO climate.fire_daily_agg (data, nivel, codigo, focos, frp_soma)
SELECT d, 'brasil', 'BR', COUNT(*), COALESCE(SUM(frp), 0) FROM h GROUP BY d
UNION ALL
SELECT d, 'uf', uf, COUNT(*), COALESCE(SUM(frp), 0) FROM h WHERE uf IS NOT NULL GROUP BY d, uf
UNION ALL
SELECT d, 'bioma', bioma, COUNT(*), COALESCE(SUM(frp), 0) FROM h WHERE bioma IS NOT NULL GROUP BY d, bioma
"""


def reagregar_dias(conn, dias: list[date]) -> None:
    """Recalcula o agregado dos dias a partir dos pontos (substitui o que existia)."""
    if not dias:
        return
    ini = datetime.combine(min(dias), datetime.min.time(), tzinfo=timezone.utc)
    fim = datetime.combine(max(dias) + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM climate.fire_daily_agg WHERE data BETWEEN %s AND %s",
            (min(dias), max(dias)),
        )
        cur.execute(_SQL_REAGREGAR, {"ini": ini, "fim": fim})


def aplicar_retencao(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM climate.fire_hotspot
             WHERE (NOT is_ref AND detectado_em < NOW() - make_interval(days => %s))
                OR detectado_em < NOW() - make_interval(days => %s)
            """,
            (RETENCAO_NAO_REF_DIAS, RETENCAO_PONTOS_DIAS),
        )
        return cur.rowcount


# ── Orquestração ──────────────────────────────────────────────────────────────

def carregar_dia(conn, dia: date) -> int:
    """Baixa o CSV diário e grava os pontos. Retorna 0 se o arquivo ainda não existe."""
    linhas = abrir_linhas(url_diario(dia))
    if linhas is None:
        logger.info("Arquivo diário de %s ainda não publicado", dia)
        return 0
    return inserir_focos(conn, parse_focos_estrito(list(linhas)))


def coletar_recente(conn, hoje: Optional[date] = None, dias: int = DIAS_JANELA_RECENTE) -> dict:
    """Coleta incremental: dias recentes (UTC), reagrega e aplica retenção."""
    janela = janela_recente(hoje or datetime.now(timezone.utc).date(), dias)
    if not _obter_lock(conn):
        return {"registros": 0, "janela": [], "removidos": 0, "ignorado": "coleta já em andamento"}
    try:
        return _coletar_janela(conn, janela)
    finally:
        _liberar_lock(conn)


def _obter_lock(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_COLETA_ID,))
        return cur.fetchone()[0]


def _liberar_lock(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_unlock(%s)", (LOCK_COLETA_ID,))
    conn.commit()


def _coletar_janela(conn, janela: list[date]) -> dict:
    run_id = iniciar_execucao(conn, RUN_FONTE, janela[0], janela[-1])
    try:
        total = sum(carregar_dia(conn, d) for d in janela)
        reagregar_dias(conn, janela)
        removidos = aplicar_retencao(conn)
        conn.commit()
    except Exception as e:
        conn.rollback()
        finalizar_execucao(conn, run_id, erro=f"{type(e).__name__}: {e}")
        raise
    finalizar_execucao(conn, run_id, registros=total)
    return {"registros": total, "janela": [janela[0].isoformat(), janela[-1].isoformat()], "removidos": removidos}
