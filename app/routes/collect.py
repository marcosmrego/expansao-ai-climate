import logging
import os

from fastapi import APIRouter, Header, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/collect", tags=["Collectors"])

_COLLECTOR_SECRET = os.getenv("COLLECTOR_SECRET", "")


def _auth(x_api_key: str):
    if _COLLECTOR_SECRET and x_api_key != _COLLECTOR_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/oni")
def collect_oni(x_api_key: str = Header(default="")):
    _auth(x_api_key)
    try:
        from collector.noaa_oni_collector import (
            baixar_dados, parse_linhas, salvar_payload_bruto, inserir_registros,
        )
        from app.services.climate_alert_repository import check_and_save_persistence_alert
        from database.db import conectar

        conn = conectar()
        try:
            texto = baixar_dados()
            registros = parse_linhas(texto)
            raw_payload_id = salvar_payload_bruto(conn, texto)
            total = inserir_registros(conn, registros, raw_payload_id)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        alert_result = check_and_save_persistence_alert(months=3)
        return {"status": "ok", "records": total, "alert": alert_result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro na coleta ONI: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sst")
def collect_sst(x_api_key: str = Header(default="")):
    _auth(x_api_key)
    try:
        from collector.noaa_sst_collector import (
            baixar_dados, parse_linhas, salvar_payload_bruto, inserir_registros,
        )
        from app.services.climate_alert_repository import check_and_save_sst_oni_alert
        from database.db import conectar

        conn = conectar()
        try:
            texto = baixar_dados()
            registros = parse_linhas(texto)
            raw_payload_id = salvar_payload_bruto(conn, texto)
            total = inserir_registros(conn, registros, raw_payload_id)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        alert_result = check_and_save_sst_oni_alert()
        return {"status": "ok", "records": total, "alert": alert_result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro na coleta SST: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/soi")
def collect_soi(x_api_key: str = Header(default="")):
    _auth(x_api_key)
    try:
        from collector.noaa_soi_collector import (
            baixar_dados, parse_linhas, salvar_payload_bruto, inserir_registros,
        )
        from app.services.climate_alert_repository import check_and_save_soi_alerts
        from database.db import conectar

        conn = conectar()
        try:
            texto = baixar_dados()
            registros = parse_linhas(texto)
            raw_payload_id = salvar_payload_bruto(conn, texto)
            total = inserir_registros(conn, registros, raw_payload_id)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        alert_result = check_and_save_soi_alerts()
        return {"status": "ok", "records": total, "alerts": alert_result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro na coleta SOI: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/insight")
def collect_insight(x_api_key: str = Header(default="")):
    """Generate and persist an AI insight from the current climate context."""
    _auth(x_api_key)
    try:
        from app.services.zhora_service import generate_insight
        insight = generate_insight()
        return {"status": "ok", "insight": insight}

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Erro ao gerar insight: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
