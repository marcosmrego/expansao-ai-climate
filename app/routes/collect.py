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


@router.post("/pdo")
def collect_pdo(x_api_key: str = Header(default="")):
    _auth(x_api_key)
    try:
        from collector.noaa_pdo_collector import classificar_pdo
        from collector.noaa_psl_base import baixar_dados, salvar_payload_bruto, parse_noaa_psl_monthly, inserir_registros_mensais
        from app.services.climate_alert_repository import check_and_save_pdo_alerts
        from database.db import conectar

        conn = conectar()
        try:
            from collector.noaa_pdo_collector import URL, ORIGEM
            texto = baixar_dados(URL)
            registros = parse_noaa_psl_monthly(texto)
            raw_payload_id = salvar_payload_bruto(conn, texto, ORIGEM, URL)
            total = inserir_registros_mensais(conn, registros, raw_payload_id, "noaa_pdo", "pdo", classificar_pdo, ORIGEM)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        alert_result = check_and_save_pdo_alerts()
        return {"status": "ok", "records": total, "alerts": alert_result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro na coleta PDO: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/nao")
def collect_nao(x_api_key: str = Header(default="")):
    _auth(x_api_key)
    try:
        from collector.noaa_nao_collector import classificar_nao, URL, ORIGEM
        from collector.noaa_psl_base import baixar_dados, salvar_payload_bruto, parse_noaa_psl_monthly, inserir_registros_mensais
        from app.services.climate_alert_repository import check_and_save_nao_alerts
        from database.db import conectar

        conn = conectar()
        try:
            texto = baixar_dados(URL)
            registros = parse_noaa_psl_monthly(texto)
            raw_payload_id = salvar_payload_bruto(conn, texto, ORIGEM, URL)
            total = inserir_registros_mensais(conn, registros, raw_payload_id, "noaa_nao", "nao", classificar_nao, ORIGEM)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        alert_result = check_and_save_nao_alerts()
        return {"status": "ok", "records": total, "alerts": alert_result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro na coleta NAO: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/amo")
def collect_amo(x_api_key: str = Header(default="")):
    _auth(x_api_key)
    try:
        from collector.noaa_amo_collector import classificar_amo, URL, ORIGEM
        from collector.noaa_psl_base import baixar_dados, salvar_payload_bruto, parse_noaa_psl_monthly, inserir_registros_mensais
        from app.services.climate_alert_repository import check_and_save_amo_alerts
        from database.db import conectar

        conn = conectar()
        try:
            texto = baixar_dados(URL)
            registros = parse_noaa_psl_monthly(texto)
            raw_payload_id = salvar_payload_bruto(conn, texto, ORIGEM, URL)
            total = inserir_registros_mensais(conn, registros, raw_payload_id, "noaa_amo", "amo", classificar_amo, ORIGEM)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        alert_result = check_and_save_amo_alerts()
        return {"status": "ok", "records": total, "alerts": alert_result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro na coleta AMO: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/qbo")
def collect_qbo(x_api_key: str = Header(default="")):
    _auth(x_api_key)
    try:
        from collector.noaa_qbo_collector import classificar_qbo, URL, ORIGEM
        from collector.noaa_psl_base import baixar_dados, salvar_payload_bruto, parse_noaa_psl_monthly, inserir_registros_mensais
        from app.services.climate_alert_repository import check_and_save_qbo_alerts
        from database.db import conectar

        conn = conectar()
        try:
            texto = baixar_dados(URL)
            registros = parse_noaa_psl_monthly(texto)
            raw_payload_id = salvar_payload_bruto(conn, texto, ORIGEM, URL)
            total = inserir_registros_mensais(conn, registros, raw_payload_id, "noaa_qbo", "qbo", classificar_qbo, ORIGEM)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        alert_result = check_and_save_qbo_alerts()
        return {"status": "ok", "records": total, "alerts": alert_result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro na coleta QBO: %s", e)
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
