"""Desmatamento — INPE, TerraBrasilis, alertas DETER (WFS do GeoServer).

Coleta incremental por janelas mensais, só atributos (sem geometria). A carga histórica
sai da linha de comando: python -m collector.deter_collector --desde 2016-08-01
"""
import argparse
import logging
import math
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Iterator, Optional
from zoneinfo import ZoneInfo

import requests
from psycopg2.extras import execute_values

from app.services import brasil_deforestation_calc as dc
from collector.run_log import finalizar_execucao, iniciar_execucao, registrar_progresso

logger = logging.getLogger(__name__)

WFS_URL = "https://terrabrasilis.dpi.inpe.br/geoserver/ows"
RUN_FONTE = "deter_desmatamento"
LOCK_COLETA_ID = 7_010_003

CAMADAS = {"deter-amz": "deter-amz:deter_amz", "deter-cerrado": "deter-cerrado-nb:deter_cerrado"}
CAMPOS = "classname,view_date,areamunkm,municipality,uf,sensor,satellite,publish_month"

INICIO_HISTORICO = date(2016, 8, 1)
DIAS_RECUO = 60            # o DETER republica e reclassifica feições recentes
DIAS_PRIMEIRA_COLETA = 90  # coleta diária em banco vazio; o histórico completo sai da CLI
PAGE_SIZE = 2000
_MAX_PAGINAS = 200
_FRACAO_MINIMA_APROVEITADA = 0.5  # abaixo disso, o schema da fonte provavelmente mudou
_TIMEOUT_S = 120
_TENTATIVAS = 4
_ESPERA_BASE_S = 20        # o GeoServer responde 503/504 quando sobrecarregado
_PAUSA_ENTRE_REQUISICOES_S = 3
_MAX_BYTES = 50 * 1024 * 1024
_TEXTO_MAX = 200
_AREA_MAX_KM2 = 100_000.0
_TOLERANCIA_FUTURO = timedelta(days=1)
_STATUS_REPETIVEIS = {429, 500, 502, 503, 504}
_USER_AGENT = "ExpansaoAI-Climate/1.0 (+https://climate.expansao-ai.com.br)"
_FUSO = ZoneInfo("America/Sao_Paulo")
_TOLERANCIA_CONTAGEM_MIN = 2
_TOLERANCIA_CONTAGEM_FRACAO = 0.001


class ContagemDivergente(RuntimeError):
    """A contagem da fonte, do download ou do banco não bate em alguma janela."""


@dataclass(frozen=True)
class Alerta:
    projeto: str
    fonte_id: str
    data_alerta: date
    publicado_em: Optional[date]
    classe: str
    grupo: str
    area_km2: float
    uf: Optional[str]
    municipio: Optional[str]
    sensor: Optional[str]
    satelite: Optional[str]
    experimental: bool


# ── Normalização ──────────────────────────────────────────────────────────────

def _texto(valor) -> Optional[str]:
    limpo = valor.strip()[:_TEXTO_MAX] if isinstance(valor, str) else None
    return limpo or None


def _data(valor) -> Optional[date]:
    try:
        return date.fromisoformat(valor[:10]) if isinstance(valor, str) else None
    except ValueError:
        return None


def _area(valor) -> Optional[float]:
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) and 0 <= n <= _AREA_MAX_KM2 else None


def _uf(valor) -> Optional[str]:
    texto = _texto(valor)
    sigla = texto[:2].upper() if texto else ""
    return sigla if len(sigla) == 2 and sigla.isalpha() else None


def hoje_local() -> date:
    return datetime.now(_FUSO).date()


def normalizar_feature(feature, projeto: str, hoje: Optional[date] = None) -> Optional[Alerta]:
    """Converte uma feição GeoJSON do WFS em Alerta; devolve None se não for utilizável."""
    if not isinstance(feature, dict) or not isinstance(feature.get("properties"), dict):
        return None
    fonte_id = _texto(feature.get("id"))
    props = feature["properties"]
    dia, area, classe = _data(props.get("view_date")), _area(props.get("areamunkm")), _texto(props.get("classname"))
    if not (fonte_id and dia and classe) or area is None:
        return None
    if dia > (hoje or hoje_local()) + _TOLERANCIA_FUTURO:  # data no futuro = erro na fonte
        return None
    return Alerta(
        projeto=projeto, fonte_id=fonte_id, data_alerta=dia, publicado_em=_data(props.get("publish_month")),
        classe=classe, grupo=dc.grupo_classe(classe), area_km2=area, uf=_uf(props.get("uf")),
        municipio=_texto(props.get("municipality")), sensor=_texto(props.get("sensor")),
        satelite=_texto(props.get("satellite")), experimental=dc.experimental(projeto),
    )


# ── Janelas e filtros ─────────────────────────────────────────────────────────

def inicio_incremental(ultima_data: Optional[date]) -> date:
    return ultima_data - timedelta(days=DIAS_RECUO) if ultima_data else INICIO_HISTORICO


def janelas_mensais(inicio: date, fim: date) -> Iterator[tuple[date, date]]:
    """Janelas [início, fim) quebradas nas viradas de mês, cobrindo `fim` inclusive."""
    limite = fim + timedelta(days=1)
    atual = inicio
    while atual < limite:
        proximo = date(atual.year + (atual.month == 12), atual.month % 12 + 1, 1)
        yield atual, min(proximo, limite)
        atual = proximo


def filtro_cql(inicio: date, fim_exclusivo: date) -> str:
    return f"view_date>='{inicio.isoformat()}' AND view_date<'{fim_exclusivo.isoformat()}'"


# ── WFS ───────────────────────────────────────────────────────────────────────

def _consultar(params: dict) -> requests.Response:
    """GET no WFS com retry e backoff (503/504 são comuns) e teto de tamanho."""
    for tentativa in range(1, _TENTATIVAS + 1):
        try:
            r = requests.get(WFS_URL, params=params, timeout=_TIMEOUT_S, stream=True,
                             allow_redirects=False, headers={"User-Agent": _USER_AGENT})
            if r.status_code in _STATUS_REPETIVEIS:
                r.close()
                raise requests.HTTPError(f"HTTP {r.status_code}")
            if r.status_code >= 300:
                r.close()
                raise RuntimeError(f"HTTP {r.status_code} no WFS")
            return _ler_limitado(r)
        except requests.RequestException as e:
            if tentativa == _TENTATIVAS:
                raise
            espera = _ESPERA_BASE_S * 2 ** (tentativa - 1)
            logger.warning("Falha no WFS (%s). Nova tentativa em %ss", e, espera)
            time.sleep(espera)
    raise RuntimeError("inalcançável")


def _ler_limitado(r: requests.Response) -> requests.Response:
    partes, lido = [], 0
    try:
        for bloco in r.iter_content(chunk_size=65536):
            lido += len(bloco)
            if lido > _MAX_BYTES:
                raise RuntimeError(f"resposta acima de {_MAX_BYTES} bytes")
            partes.append(bloco)
    finally:
        r.close()
    r._content = b"".join(partes)
    r._content_consumed = True
    return r


def _pagina(projeto: str, inicio: date, fim_exclusivo: date, indice: int) -> dict:
    resposta = _consultar({
        "service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": CAMADAS[projeto],
        "outputFormat": "application/json", "propertyName": CAMPOS, "sortBy": "view_date",
        "cql_filter": filtro_cql(inicio, fim_exclusivo), "count": PAGE_SIZE, "startIndex": indice,
    })
    try:
        dados = resposta.json()
    except ValueError:
        dados = None
    if not isinstance(dados, dict) or not isinstance(dados.get("features"), list):
        raise RuntimeError(f"{projeto}: resposta do WFS não é uma FeatureCollection")
    return dados


def contar_na_fonte(projeto: str, inicio: date, fim_exclusivo: date) -> int:
    """Total de feições que o WFS declara para a janela (numberMatched), sem baixar as feições."""
    resposta = _consultar({
        "service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": CAMADAS[projeto],
        "outputFormat": "application/json", "propertyName": "view_date", "sortBy": "view_date",
        "cql_filter": filtro_cql(inicio, fim_exclusivo), "count": 1,
    })
    try:
        total = resposta.json().get("numberMatched")
    except (ValueError, AttributeError):
        total = None
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        raise RuntimeError(f"{projeto}: o WFS não informou numberMatched")
    return total


def baixar_janela(projeto: str, inicio: date, fim_exclusivo: date) -> list[dict]:
    """Todas as feições da janela, com cada consulta cabendo em uma página.

    A ordem das feições com o mesmo view_date não é estável entre páginas (duplicaria e pularia
    feições). Por isso, janela que enche uma página é dividida ao meio; só um dia inteiro
    que não cabe em uma página é paginado (caso raro, registrado em log).
    """
    feicoes = _pagina(projeto, inicio, fim_exclusivo, 0)["features"]
    if len(feicoes) < PAGE_SIZE:
        return feicoes
    dias = (fim_exclusivo - inicio).days
    if dias <= 1:
        return _paginar_dia(projeto, inicio, fim_exclusivo, feicoes)
    meio = inicio + timedelta(days=dias // 2)
    time.sleep(_PAUSA_ENTRE_REQUISICOES_S)
    return baixar_janela(projeto, inicio, meio) + baixar_janela(projeto, meio, fim_exclusivo)


def _paginar_dia(projeto: str, inicio: date, fim_exclusivo: date, primeira: list[dict]) -> list[dict]:
    logger.warning("%s: o dia %s não cabe em uma página; paginando (ordem pode não ser estável)", projeto, inicio)
    brutos = list(primeira)
    for pagina in range(1, _MAX_PAGINAS):
        time.sleep(_PAUSA_ENTRE_REQUISICOES_S)
        feicoes = _pagina(projeto, inicio, fim_exclusivo, pagina * PAGE_SIZE)["features"]
        brutos.extend(feicoes)
        if len(feicoes) < PAGE_SIZE:
            return brutos
    raise RuntimeError(f"{projeto}: paginação não terminou em {_MAX_PAGINAS} páginas")


# ── Persistência ──────────────────────────────────────────────────────────────

def gravar_alertas(conn, alertas: Iterable[Alerta]) -> int:
    unicos = {(a.projeto, a.fonte_id): a for a in alertas}
    if not unicos:
        return 0
    linhas = [(a.projeto, a.fonte_id, a.data_alerta, a.publicado_em, a.classe, a.grupo, a.area_km2,
               a.uf, a.municipio, a.sensor, a.satelite, a.experimental) for a in unicos.values()]
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO climate.deforestation_alert
                (projeto, fonte_id, data_alerta, publicado_em, classe, grupo, area_km2,
                 uf, municipio, sensor, satelite, experimental)
            VALUES %s
            ON CONFLICT (projeto, fonte_id) DO UPDATE SET
                data_alerta = EXCLUDED.data_alerta, publicado_em = EXCLUDED.publicado_em,
                classe = EXCLUDED.classe, grupo = EXCLUDED.grupo, area_km2 = EXCLUDED.area_km2,
                uf = EXCLUDED.uf, municipio = EXCLUDED.municipio, sensor = EXCLUDED.sensor,
                satelite = EXCLUDED.satelite, experimental = EXCLUDED.experimental, atualizado_em = NOW()
            """,
            linhas,
            page_size=2000,
        )
    return len(linhas)


def remover_ausentes(conn, projeto: str, inicio: date, fim_exclusivo: date, ids_presentes: list[str]) -> int:
    """Apaga da janela as feições que a fonte deixou de publicar (excluídas ou renumeradas)."""
    with conn.cursor() as cur:
        cur.execute(
            """DELETE FROM climate.deforestation_alert
                WHERE projeto = %s AND data_alerta >= %s AND data_alerta < %s
                  AND NOT (fonte_id = ANY(%s))""",
            (projeto, inicio, fim_exclusivo, ids_presentes))
        return cur.rowcount


def contar_no_banco(conn, projeto: str, inicio: date, fim_exclusivo: date) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT COUNT(*) FROM climate.deforestation_alert
                WHERE projeto = %s AND data_alerta >= %s AND data_alerta < %s""",
            (projeto, inicio, fim_exclusivo))
        return cur.fetchone()[0]


def _ultima_data(conn, projeto: str) -> Optional[date]:
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(data_alerta) FROM climate.deforestation_alert WHERE projeto = %s", (projeto,))
        return cur.fetchone()[0]


# ── Orquestração ──────────────────────────────────────────────────────────────

def contagem_diverge(esperado: int, obtido: int) -> bool:
    """A fonte pode publicar feições entre duas consultas; só diferença acima da tolerância conta."""
    return abs(esperado - obtido) > max(_TOLERANCIA_CONTAGEM_MIN, esperado * _TOLERANCIA_CONTAGEM_FRACAO)


def _conferir_janela(conn, projeto: str, inicio: date, fim_exclusivo: date, baixadas: int, gravadas: int) -> bool:
    """Compara fonte × baixado (download truncado) e banco × gravado (persistência). True se confere."""
    na_fonte = contar_na_fonte(projeto, inicio, fim_exclusivo)
    if contagem_diverge(na_fonte, baixadas):
        logger.error("%s %s: a fonte tem %s feições e foram baixadas %s", projeto, inicio, na_fonte, baixadas)
        return False
    if not baixadas:  # janela vazia na fonte preserva o que já temos; o banco não precisa bater
        return True
    no_banco = contar_no_banco(conn, projeto, inicio, fim_exclusivo)
    if no_banco != gravadas:
        logger.error("%s %s: %s alertas gravados, mas o banco tem %s na janela", projeto, inicio, gravadas, no_banco)
        return False
    return True


def _processar_projeto(conn, projeto: str, hoje: date, desde: Optional[date]) -> int:
    ultima = _ultima_data(conn, projeto)
    if desde is None:
        desde = inicio_incremental(ultima) if ultima else hoje - timedelta(days=DIAS_PRIMEIRA_COLETA)
    total, divergentes = 0, []
    janelas = list(janelas_mensais(desde, hoje))
    for feitas, (inicio, fim_exclusivo) in enumerate(janelas, start=1):
        brutos = baixar_janela(projeto, inicio, fim_exclusivo)
        alertas = [a for a in (normalizar_feature(f, projeto, hoje) for f in brutos) if a]
        _exigir_aproveitamento(projeto, inicio, len(brutos), len(alertas))
        total += gravar_alertas(conn, alertas)
        if brutos:  # janela vazia na fonte não apaga o que já temos (pode ser falha de publicação)
            remover_ausentes(conn, projeto, inicio, fim_exclusivo, [a.fonte_id for a in alertas])
        conn.commit()  # cada janela fica salva; uma falha adiante não perde o já coletado
        if not _conferir_janela(conn, projeto, inicio, fim_exclusivo, len(brutos), len({a.fonte_id for a in alertas})):
            divergentes.append(inicio)
        registrar_progresso(conn, RUN_FONTE, f"{projeto} · {inicio:%Y-%m}", feitas, len(janelas))
        logger.info("%s %s a %s: %s alertas", projeto, inicio, fim_exclusivo, len(alertas))
        time.sleep(_PAUSA_ENTRE_REQUISICOES_S)
    if divergentes:  # as demais janelas já foram salvas; a execução fica marcada com erro
        raise ContagemDivergente(f"{len(divergentes)} janela(s) com contagem divergente, a partir de {divergentes[0]}")
    return total


def _exigir_aproveitamento(projeto: str, inicio: date, recebidas: int, aproveitadas: int) -> None:
    """Falha alto se a fonte devolveu feições mas quase nenhuma é utilizável (schema mudou?)."""
    if recebidas and aproveitadas / recebidas < _FRACAO_MINIMA_APROVEITADA:
        raise RuntimeError(f"{projeto} {inicio}: só {aproveitadas} de {recebidas} feições utilizáveis; schema alterado?")
    if recebidas != aproveitadas:
        logger.warning("%s %s: %s de %s feições descartadas", projeto, inicio, recebidas - aproveitadas, recebidas)


def _obter_lock(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_COLETA_ID,))
        return cur.fetchone()[0]


def _liberar_lock(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_unlock(%s)", (LOCK_COLETA_ID,))
    conn.commit()


def coletar(conn, hoje: Optional[date] = None, desde: Optional[date] = None) -> dict:
    """Coleta incremental dos projetos DETER. Falha de um projeto não derruba o outro."""
    hoje = hoje or hoje_local()
    if not _obter_lock(conn):
        return {"registros": 0, "erros": [], "ignorado": "coleta já em andamento"}
    try:
        run_id = iniciar_execucao(conn, RUN_FONTE, desde, hoje)
        total, erros = 0, []
        for projeto in CAMADAS:
            try:
                total += _processar_projeto(conn, projeto, hoje, desde)
            except Exception as e:  # um projeto fora do ar não pode apagar o outro
                conn.rollback()
                logger.exception("Falha na coleta %s", projeto)
                erros.append(f"{projeto}: {type(e).__name__}")
        finalizar_execucao(conn, run_id, registros=total, erro="; ".join(erros) if erros else None)
        return {"registros": total, "erros": erros}
    finally:
        try:
            conn.rollback()
            _liberar_lock(conn)
        except Exception:  # conexão caída: o lock de sessão some com ela; não mascara o erro original
            logger.warning("Não foi possível liberar o lock da coleta DETER", exc_info=True)


if __name__ == "__main__":
    from database.db import conectar

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desde", type=date.fromisoformat, default=None,
                        help="início da carga (padrão: incremental); histórico completo: 2016-08-01")
    argumentos = parser.parse_args()
    conexao = conectar()
    try:
        print(coletar(conexao, desde=argumentos.desde))
    finally:
        conexao.close()
