import logging
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Path, Query

from app.services import brasil_deforestation_calc as dc
from app.services import brasil_deforestation_service as dsvc
from app.services import brasil_fire_calc as calc
from app.services import brasil_fire_service as svc
from app.services import brasil_reservoir_service as rsvc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/brasil", tags=["Brasil"])

Nivel = Literal["brasil", "uf", "bioma"]
_BBOX_LIMITES = (-180.0, -90.0, 180.0, 90.0)


def _periodo_ou_422(periodo: str) -> str:
    try:
        calc.parse_periodo(periodo)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return periodo


def _bbox_ou_422(bbox: Optional[str]) -> Optional[tuple]:
    if not bbox:
        return None
    try:
        oeste, sul, leste, norte = (float(v) for v in bbox.split(","))
    except ValueError:
        raise HTTPException(status_code=422, detail="bbox deve ser oeste,sul,leste,norte")
    dentro = (-180 <= oeste <= leste <= 180) and (-90 <= sul <= norte <= 90)
    if not dentro:
        raise HTTPException(status_code=422, detail="bbox fora dos limites")
    return (oeste, sul, leste, norte)


@router.get("/focos/resumo")
def focos_resumo(nivel: Nivel = "uf", periodo: str = Query("30d", max_length=8)):
    _periodo_ou_422(periodo)
    try:
        return svc.resumo(nivel, periodo)
    except Exception as e:
        logger.exception("Erro em /api/brasil/focos/resumo")
        raise HTTPException(status_code=500, detail="Erro ao consultar focos")


@router.get("/focos/serie")
def focos_serie(
    nivel: Nivel = "brasil",
    codigo: str = Query("BR", max_length=20),
    periodo: str = Query("365d", max_length=8),
):
    _periodo_ou_422(periodo)
    if not calc.codigo_valido(nivel, codigo):
        raise HTTPException(status_code=422, detail="código inválido para o nível")
    try:
        return svc.serie(nivel, codigo, periodo)
    except Exception as e:
        logger.exception("Erro em /api/brasil/focos/serie")
        raise HTTPException(status_code=500, detail="Erro ao consultar série de focos")


@router.get("/focos/mapa")
def focos_mapa(
    periodo: str = Query("7d", max_length=8),
    bbox: Optional[str] = Query(None, max_length=60),
    zoom: int = Query(4, ge=0, le=18),
    limite: int = Query(svc.LIMITE_PONTOS_PADRAO, ge=1, le=svc.LIMITE_PONTOS_MAX),
    somente_ref: bool = False,
):
    _periodo_ou_422(periodo)
    caixa = _bbox_ou_422(bbox)
    try:
        return svc.mapa(periodo, caixa, zoom, limite, somente_ref)
    except Exception as e:
        logger.exception("Erro em /api/brasil/focos/mapa")
        raise HTTPException(status_code=500, detail="Erro ao consultar mapa de focos")


@router.get("/status")
def brasil_status():
    try:
        return svc.status()
    except Exception as e:
        logger.exception("Erro em /api/brasil/status")
        raise HTTPException(status_code=500, detail="Erro ao consultar status das fontes")


SistemaReservatorio = Literal["SIN", "NORDESTE", "CANTAREIRA", "DF", "RMBH"]
FaixaReservatorio = Literal["critico", "baixo", "medio", "bom", "alto"]
OrdemReservatorio = Literal["volume", "-volume", "nome", "variacao", "-variacao"]


@router.get("/reservatorios/resumo")
def reservatorios_resumo():
    try:
        return rsvc.resumo()
    except Exception:
        logger.exception("Erro em /api/brasil/reservatorios/resumo")
        raise HTTPException(status_code=500, detail="Erro ao consultar reservatórios")


@router.get("/reservatorios")
def reservatorios_lista(
    sistema: Optional[SistemaReservatorio] = None,
    uf: Optional[str] = Query(None, min_length=2, max_length=2, pattern="^[A-Za-z]{2}$"),
    faixa: Optional[FaixaReservatorio] = None,
    q: Optional[str] = Query(None, max_length=60),
    ordem: OrdemReservatorio = "-volume",
    offset: int = Query(0, ge=0, le=10000),
    limite: int = Query(50, ge=1, le=rsvc.LIMITE_LISTA_MAX),
):
    try:
        return rsvc.listar(sistema, uf.upper() if uf else None, faixa, q, ordem, offset, limite)
    except Exception:
        logger.exception("Erro em /api/brasil/reservatorios")
        raise HTTPException(status_code=500, detail="Erro ao consultar reservatórios")


@router.get("/reservatorios/{reservatorio_id}/serie")
def reservatorio_serie(reservatorio_id: int = Path(ge=1, le=10_000_000), periodo: str = Query("5y", max_length=8)):
    if periodo not in rsvc.PERIODOS_SERIE:
        raise HTTPException(status_code=422, detail=f"período deve ser um de {', '.join(rsvc.PERIODOS_SERIE)}")
    try:
        resultado = rsvc.serie(reservatorio_id, periodo)
    except Exception:
        logger.exception("Erro em /api/brasil/reservatorios/{id}/serie")
        raise HTTPException(status_code=500, detail="Erro ao consultar série do reservatório")
    if resultado is None:
        raise HTTPException(status_code=404, detail="Reservatório não encontrado")
    return resultado


ProjetoDeter = Literal["deter-amz", "deter-cerrado"]
PeriodoAlertas = Literal["30d", "90d", "365d"]
GrupoClasse = Literal["desmatamento", "corte_seletivo", "degradacao", "queimada", "mineracao", "outras"]


@router.get("/desmatamento/resumo")
def desmatamento_resumo(projeto: ProjetoDeter = "deter-amz", periodo: PeriodoAlertas = "90d"):
    """Alertas DETER no período, por grupo e UF, e acumulado do ano PRODES corrente."""
    try:
        return dsvc.resumo(projeto, periodo)
    except Exception:
        logger.exception("Erro em /api/brasil/desmatamento/resumo")
        raise HTTPException(status_code=500, detail="Erro ao consultar desmatamento")


@router.get("/desmatamento/serie")
def desmatamento_serie(projeto: ProjetoDeter = "deter-amz", meses: int = Query(36, ge=1, le=dsvc.MESES_SERIE_MAX)):
    """Área mensal de desmatamento (corte raso) detectada pelo DETER."""
    try:
        return dsvc.serie(projeto, meses)
    except Exception:
        logger.exception("Erro em /api/brasil/desmatamento/serie")
        raise HTTPException(status_code=500, detail="Erro ao consultar série de desmatamento")


@router.get("/desmatamento/taxa")
def desmatamento_taxa(projeto: ProjetoDeter = "deter-amz"):
    """Soma anual dos polígonos PRODES por ano e, no último ano, por UF."""
    try:
        return dsvc.taxas(projeto)
    except Exception:
        logger.exception("Erro em /api/brasil/desmatamento/taxa")
        raise HTTPException(status_code=500, detail="Erro ao consultar a série anual do PRODES")


@router.get("/desmatamento/alertas")
def desmatamento_alertas(
    projeto: ProjetoDeter = "deter-amz",
    periodo: PeriodoAlertas = "30d",
    uf: Optional[str] = Query(None, min_length=2, max_length=2, pattern="^[A-Za-z]{2}$"),
    grupo: Optional[GrupoClasse] = None,
    limite: int = Query(50, ge=1, le=dsvc.LIMITE_ALERTAS_MAX),
):
    """Alertas mais recentes (maiores primeiro dentro do mesmo dia)."""
    uf = uf.upper() if uf else None
    if uf and uf not in dc.UFS:
        raise HTTPException(status_code=422, detail="UF inválida")
    try:
        return dsvc.ultimos_alertas(projeto, periodo, uf, grupo, limite)
    except Exception:
        logger.exception("Erro em /api/brasil/desmatamento/alertas")
        raise HTTPException(status_code=500, detail="Erro ao consultar alertas de desmatamento")

