"""Reservatórios — ANA, Sistema de Acompanhamento de Reservatórios (SAR).

Coleta diária pela API oficial (ArcGIS FeatureServer, só a última medição) e
backfill histórico pelas páginas públicas do SAR (ver scripts/backfill_sar_historico.py).
"""
import html
import logging
import math
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

import requests
from psycopg2.extras import execute_values

from collector.run_log import finalizar_execucao, iniciar_execucao

logger = logging.getLogger(__name__)

API_BASE = "https://www.snirh.gov.br/arcgis/rest/services/IG/SAR/FeatureServer"
PAGINA_SIN = "https://www.ana.gov.br/sar0/MedicaoSin"
PAGINA_NORDESTE = "https://www.ana.gov.br/sar0/Medicao"
RUN_FONTE = "sar_reservatorios"
LOCK_COLETA_ID = 7_010_002

CAMADAS = {0: "SIN", 1: "NORDESTE", 2: "DF", 3: "CANTAREIRA", 4: "RMBH"}
FONTE_API = "sar_api"
FONTE_PAGINA = "sar_pagina"

_USER_AGENT = "ExpansaoAI-Climate/1.0 (+https://climate.expansao-ai.com.br)"
_TIMEOUT_S = 60
_TENTATIVAS = 3
_ESPERA_BASE_S = 5
_PAGE_SIZE = 1000
_MAX_PAGINAS = 100
_MAX_BYTES = 25 * 1024 * 1024
_PCT_MIN, _PCT_MAX = 0.0, 150.0
_TOLERANCIA_FUTURO = timedelta(days=1)
_FUSO = ZoneInfo("America/Sao_Paulo")
_COTA_MIN, _COTA_MAX = -10.0, 5000.0
_VAZAO_MIN, _VAZAO_MAX = 0.0, 1_000_000.0
_VOLUME_MAX = 1_000_000.0


@dataclass(frozen=True)
class Reservatorio:
    id: int
    nome: str
    sistema: str
    uf: Optional[str]
    municipio: Optional[str]
    bacia: Optional[str]
    capacidade_hm3: Optional[float]
    latitude: Optional[float]
    longitude: Optional[float]


@dataclass(frozen=True)
class Leitura:
    reservatorio_id: int
    data: date
    volume_pct: Optional[float]
    volume_hm3: Optional[float]
    cota_m: Optional[float]
    afluencia_m3s: Optional[float]
    defluencia_m3s: Optional[float]
    fonte: str


# ── Normalização ──────────────────────────────────────────────────────────────

def _num(valor) -> Optional[float]:
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def _num_br(texto: str) -> Optional[float]:
    """'1.234,56' -> 1234.56; '85.5' -> 85.5; '85,3 %' -> 85.3; vazio ou inválido -> None."""
    limpo = (texto or "").replace("%", "").strip()
    if not limpo:
        return None
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    return _num(limpo)


def _entre(valor, minimo: float, maximo: float) -> Optional[float]:
    n = _num(valor)
    return n if n is not None and minimo <= n <= maximo else None


def _pct(valor) -> Optional[float]:
    return _entre(valor, _PCT_MIN, _PCT_MAX)


def _cota(valor) -> Optional[float]:
    return _entre(valor, _COTA_MIN, _COTA_MAX)


def _vazao(valor) -> Optional[float]:
    return _entre(valor, _VAZAO_MIN, _VAZAO_MAX)


def _volume(valor) -> Optional[float]:
    return _entre(valor, 0.0, _VOLUME_MAX)


def _data_br(texto) -> Optional[date]:
    partes = (texto or "").split()
    try:
        return datetime.strptime(partes[0], "%d/%m/%Y").date() if partes else None
    except ValueError:
        return None


def _chave_nome(nome: str) -> str:
    base = unicodedata.normalize("NFKD", html.unescape(nome or ""))
    return " ".join("".join(ch for ch in base if not unicodedata.combining(ch)).upper().split())


def hoje_local() -> date:
    return datetime.now(_FUSO).date()


_TEXTO_MAX = 200


def _texto(valor) -> Optional[str]:
    limpo = valor.strip()[:_TEXTO_MAX] if isinstance(valor, str) else None
    return limpo or None


def normalizar_feature(
    attrs: dict, sistema: str, hoje: Optional[date] = None
) -> tuple[Optional[Reservatorio], Optional[Leitura]]:
    """Converte atributos do FeatureServer em (reservatório, leitura)."""
    try:
        rid = int(attrs["SAR_ID"])
    except (KeyError, TypeError, ValueError):
        return None, None
    nome = _texto(attrs.get("SAR_NM"))
    if not nome:
        return None, None
    uf = _texto(attrs.get("SAR_SG_UF"))
    reservatorio = Reservatorio(
        id=rid, nome=nome, sistema=sistema,
        uf=uf[:2].upper() if uf else None,
        municipio=_texto(attrs.get("SAR_NM_MUNICIPIO")),
        bacia=_texto(attrs.get("SAR_NM_BACIA")),
        capacidade_hm3=_volume(attrs.get("SAR_QT_CAPACIDADE")),
        latitude=_entre(attrs.get("SAR_NU_LATITUDE"), -90.0, 90.0),
        longitude=_entre(attrs.get("SAR_NU_LONGITUDE"), -180.0, 180.0),
    )
    return reservatorio, _leitura_da_feature(attrs, rid, sistema, hoje or hoje_local())


def _leitura_da_feature(attrs: dict, rid: int, sistema: str, hoje: date) -> Optional[Leitura]:
    dia = _data_br(attrs.get("SAR_DT_ULTIMA_MEDICAO"))
    if dia is None or dia > hoje + _TOLERANCIA_FUTURO:  # data no futuro = erro de digitação na fonte
        return None
    # No SIN o percentual útil vem em SAR_VO_UTIL_ULTIMA; nos demais, em SAR_PC_VOLUME.
    primeiro, segundo = ("SAR_VO_UTIL_ULTIMA", "SAR_PC_VOLUME") if sistema == "SIN" else ("SAR_PC_VOLUME", "SAR_VO_UTIL_ULTIMA")
    pct = _pct(attrs.get(primeiro))
    if pct is None:
        pct = _pct(attrs.get(segundo))
    return Leitura(
        reservatorio_id=rid, data=dia, volume_pct=pct,
        volume_hm3=None if sistema == "SIN" else _volume(attrs.get("SAR_VO_ULTIMA")),
        cota_m=_cota(attrs.get("SAR_CO_ULTIMA")),
        afluencia_m3s=_vazao(attrs.get("SAR_ULT_AFLUENCIA")),
        defluencia_m3s=_vazao(attrs.get("SAR_ULT_DEFLUENCIA")),
        fonte=FONTE_API,
    )


# ── Páginas históricas (HTML) ─────────────────────────────────────────────────

_TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")


def _celulas(tr: str) -> list[str]:
    return [html.unescape(_TAG_RE.sub("", c)).strip() for c in _TD_RE.findall(tr)]


def parse_pagina_historico(
    texto: str, reservatorio_id: int, sistema: str, nome_esperado: Optional[str] = None
) -> list[Leitura]:
    """Extrai leituras diárias da tabela de resultados do SAR (SIN ou Nordeste).

    Descarta linhas de outro reservatório (caso a página ignore o filtro).
    """
    leituras: dict[date, Leitura] = {}
    for tr in _TR_RE.findall(texto):
        celulas = _celulas(tr)
        if not _linha_do_reservatorio(celulas, reservatorio_id, sistema, nome_esperado):
            continue
        leitura = _leitura_da_linha(celulas, reservatorio_id, sistema)
        if leitura is not None:
            leituras[leitura.data] = leitura
    return list(leituras.values())


def _linha_do_reservatorio(c: list[str], rid: int, sistema: str, nome_esperado: Optional[str]) -> bool:
    if sistema == "SIN":
        return len(c) < 1 or c[0] == str(rid)
    if nome_esperado and len(c) >= 2:
        return _chave_nome(c[1]) == _chave_nome(nome_esperado)
    return True


def _leitura_da_linha(c: list[str], rid: int, sistema: str) -> Optional[Leitura]:
    """SIN: id, nome, cota, afluência, defluência, vertida, turbinada, natural, volume útil %, incremental, data.
    Nordeste: estado, nome, capacidade, cota, volume hm³, volume %, data."""
    if sistema == "SIN" and len(c) >= 11:
        dia = _data_br(c[10])
        if dia is None:
            return None
        return Leitura(rid, dia, _pct(_num_br(c[8])), None, _cota(_num_br(c[2])),
                       _vazao(_num_br(c[3])), _vazao(_num_br(c[4])), FONTE_PAGINA)
    if sistema == "NORDESTE" and len(c) >= 7:
        dia = _data_br(c[6])
        if dia is None:
            return None
        return Leitura(rid, dia, _pct(_num_br(c[5])), _volume(_num_br(c[4])), _cota(_num_br(c[3])),
                       None, None, FONTE_PAGINA)
    return None


def baixar_historico(
    reservatorio_id: int, sistema: str, inicio: date, fim: date, nome: Optional[str] = None
) -> list[Leitura]:
    """Consulta a página pública do SAR (um reservatório, intervalo de datas)."""
    pagina = PAGINA_SIN if sistema == "SIN" else PAGINA_NORDESTE
    params = {
        "dropDownListEstados": "", "dropDownListReservatorios": str(reservatorio_id),
        "dataInicial": inicio.strftime("%d/%m/%Y"), "dataFinal": fim.strftime("%d/%m/%Y"),
        "button": "Buscar",
    }
    r = _get(pagina, params=params, timeout=120)
    r.encoding = "utf-8"
    leituras = parse_pagina_historico(r.text, reservatorio_id, sistema, nome)
    if not leituras:
        logger.warning("Página do SAR sem leituras para o reservatório %s", reservatorio_id)
    return leituras


# ── API (FeatureServer) ───────────────────────────────────────────────────────

class _ErroDefinitivo(Exception):
    """Erro HTTP 4xx (exceto 429): repetir não adianta."""


def _ler_limitado(r: requests.Response) -> requests.Response:
    """Lê o corpo com teto de tamanho (a fonte é externa)."""
    partes, lido = [], 0
    try:
        for bloco in r.iter_content(chunk_size=65536):
            lido += len(bloco)
            if lido > _MAX_BYTES:
                raise _ErroDefinitivo(f"resposta acima de {_MAX_BYTES} bytes")
            partes.append(bloco)
    finally:
        r.close()
    r._content = b"".join(partes)
    r._content_consumed = True
    return r


def _get(url: str, params: Optional[dict] = None, timeout: int = _TIMEOUT_S) -> requests.Response:
    for tentativa in range(1, _TENTATIVAS + 1):
        try:
            r = requests.get(url, params=params, timeout=timeout, stream=True,
                             allow_redirects=False, headers={"User-Agent": _USER_AGENT})
            if r.status_code == 429 or r.status_code >= 500:
                r.close()
                raise requests.HTTPError(f"HTTP {r.status_code}")
            if r.status_code >= 300:
                r.close()
                raise _ErroDefinitivo(f"HTTP {r.status_code} em {url}")
            return _ler_limitado(r)
        except _ErroDefinitivo:
            raise
        except requests.RequestException as e:
            if tentativa == _TENTATIVAS:
                raise
            espera = _ESPERA_BASE_S * 2 ** (tentativa - 1)
            logger.warning("Falha em %s (%s). Nova tentativa em %ss", url, e, espera)
            time.sleep(espera)
    raise RuntimeError("inalcançável")


def baixar_camada(camada: int) -> list[dict]:
    """Todos os atributos de uma camada do SAR, paginando pelo limite do servidor."""
    atributos: list[dict] = []
    offset = 0
    for _ in range(_MAX_PAGINAS):
        r = _get(f"{API_BASE}/{camada}/query", params={
            "where": "1=1", "outFields": "*", "returnGeometry": "false", "f": "json",
            "resultOffset": offset, "resultRecordCount": _PAGE_SIZE, "orderByFields": "SAR_ID",
        })
        dados = r.json()
        if "error" in dados:
            raise RuntimeError(f"SAR camada {camada}: {dados['error'].get('message', 'erro')}")
        pagina = [f["attributes"] for f in dados.get("features", [])
                  if isinstance(f, dict) and isinstance(f.get("attributes"), dict)]
        atributos.extend(pagina)
        if not pagina or not dados.get("exceededTransferLimit"):
            if not atributos:  # camadas do SAR nunca ficam vazias; vazio = fonte em atualização
                raise RuntimeError(f"SAR camada {camada}: resposta sem registros")
            return atributos
        offset += len(pagina)
    raise RuntimeError(f"SAR camada {camada}: paginação não terminou em {_MAX_PAGINAS} páginas")


# ── Persistência ──────────────────────────────────────────────────────────────

def gravar_reservatorios(conn, reservatorios: Iterable[Reservatorio]) -> int:
    unicos = {r.id: r for r in reservatorios}
    if not unicos:
        return 0
    linhas = [(r.id, r.nome, r.sistema, r.uf, r.municipio, r.bacia, r.capacidade_hm3, r.latitude, r.longitude)
              for r in unicos.values()]
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO climate.reservoir (id, nome, sistema, uf, municipio, bacia, capacidade_hm3, latitude, longitude)
            VALUES %s
            ON CONFLICT (id) DO UPDATE SET
                nome = EXCLUDED.nome,
                uf = COALESCE(EXCLUDED.uf, climate.reservoir.uf),
                municipio = COALESCE(EXCLUDED.municipio, climate.reservoir.municipio),
                bacia = COALESCE(EXCLUDED.bacia, climate.reservoir.bacia),
                capacidade_hm3 = COALESCE(EXCLUDED.capacidade_hm3, climate.reservoir.capacidade_hm3),
                latitude = COALESCE(EXCLUDED.latitude, climate.reservoir.latitude),
                longitude = COALESCE(EXCLUDED.longitude, climate.reservoir.longitude),
                atualizado_em = NOW()
            """,
            linhas,
        )
    return len(linhas)


def gravar_leituras(conn, leituras: Iterable[Leitura]) -> int:
    unicas = {(l.reservatorio_id, l.data): l for l in leituras}
    if not unicas:
        return 0
    linhas = [(l.reservatorio_id, l.data, l.volume_pct, l.volume_hm3, l.cota_m,
               l.afluencia_m3s, l.defluencia_m3s, l.fonte) for l in unicas.values()]
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO climate.reservoir_reading
                (reservoir_id, data, volume_pct, volume_hm3, cota_m, afluencia_m3s, defluencia_m3s, fonte)
            VALUES %s
            ON CONFLICT (reservoir_id, data) DO UPDATE SET
                volume_pct = COALESCE(EXCLUDED.volume_pct, climate.reservoir_reading.volume_pct),
                volume_hm3 = COALESCE(EXCLUDED.volume_hm3, climate.reservoir_reading.volume_hm3),
                cota_m = COALESCE(EXCLUDED.cota_m, climate.reservoir_reading.cota_m),
                afluencia_m3s = COALESCE(EXCLUDED.afluencia_m3s, climate.reservoir_reading.afluencia_m3s),
                defluencia_m3s = COALESCE(EXCLUDED.defluencia_m3s, climate.reservoir_reading.defluencia_m3s),
                fonte = EXCLUDED.fonte
            """,
            linhas,
            page_size=2000,
        )
    return len(linhas)


# ── Orquestração ──────────────────────────────────────────────────────────────

def _processar_camada(conn, camada: int, sistema: str, vistos: dict, hoje: date) -> int:
    pares = []
    for atributos in baixar_camada(camada):
        reservatorio, leitura = normalizar_feature(atributos, sistema, hoje)
        if reservatorio is None:
            continue
        if vistos.setdefault(reservatorio.id, sistema) != sistema:
            logger.warning("ID %s repetido nos sistemas %s e %s; ignorado em %s",
                           reservatorio.id, vistos[reservatorio.id], sistema, sistema)
            continue
        pares.append((reservatorio, leitura))
    gravar_reservatorios(conn, (r for r, _ in pares))
    total = gravar_leituras(conn, (l for _, l in pares if l and l.volume_pct is not None))
    conn.commit()
    return total


def _obter_lock(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_COLETA_ID,))
        return cur.fetchone()[0]


def _liberar_lock(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_unlock(%s)", (LOCK_COLETA_ID,))
    conn.commit()


def coletar_atual(conn, hoje: Optional[date] = None) -> dict:
    """Coleta a última medição de todos os sistemas. Falha de uma camada não derruba as outras."""
    hoje = hoje or hoje_local()
    if not _obter_lock(conn):
        return {"registros": 0, "erros": [], "ignorado": "coleta já em andamento"}
    try:
        run_id = iniciar_execucao(conn, RUN_FONTE, hoje, hoje)
        total, erros, vistos = 0, [], {}
        for camada, sistema in CAMADAS.items():
            try:
                total += _processar_camada(conn, camada, sistema, vistos, hoje)
            except Exception as e:  # uma camada fora do ar não pode apagar as demais
                conn.rollback()
                logger.exception("Falha na camada %s do SAR", sistema)
                erros.append(f"{sistema}: {type(e).__name__}")
        finalizar_execucao(conn, run_id, registros=total, erro="; ".join(erros) if erros else None)
        return {"registros": total, "erros": erros}
    finally:
        conn.rollback()
        _liberar_lock(conn)
