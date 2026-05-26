import logging

from fastapi import APIRouter, HTTPException

from app.services.climate_alert_repository import get_active_alerts

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/climate",
    tags=["Climate Alerts"]
)


@router.get("/alerts")
def listar_alertas():
    try:
        alertas = get_active_alerts(20)
        return {
            "total": len(alertas),
            "items": alertas
        }
    except Exception as e:
        logger.error("Erro em /api/climate/alerts: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar alertas climáticos")