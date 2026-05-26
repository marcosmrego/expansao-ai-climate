from fastapi import APIRouter

from app.services.climate_alert_repository import get_active_alerts


router = APIRouter(
    prefix="/api/climate",
    tags=["Climate Alerts"]
)


@router.get("/alerts")
def listar_alertas():
    alertas = get_active_alerts(20)

    return {
        "total": len(alertas),
        "items": alertas
    }