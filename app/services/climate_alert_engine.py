from datetime import datetime, timezone
from typing import List, Dict, Any


def classify_oni_alert(current_oni: float, previous_oni: float) -> List[Dict[str, Any]]:
    alerts = []

    variation = round(current_oni - previous_oni, 2)

    if current_oni >= 0.5:
        alerts.append({
            "alert_type": "EL_NINO_CONDITION",
            "severity": "WARNING",
            "title": "Possível condição de El Niño",
            "message": (
                f"O índice ONI está em {current_oni}, acima do limite de 0.5. "
                "Isso pode indicar condição favorável ao El Niño, dependendo da persistência nos próximos períodos."
            ),
            "source": "NOAA"
        })

    elif current_oni <= -0.5:
        alerts.append({
            "alert_type": "LA_NINA_CONDITION",
            "severity": "WARNING",
            "title": "Possível condição de La Niña",
            "message": (
                f"O índice ONI está em {current_oni}, abaixo do limite de -0.5. "
                "Isso pode indicar condição favorável à La Niña, dependendo da persistência nos próximos períodos."
            ),
            "source": "NOAA"
        })

    else:
        alerts.append({
            "alert_type": "NEUTRAL_CONDITION",
            "severity": "INFO",
            "title": "Condição climática neutra",
            "message": (
                f"O índice ONI está em {current_oni}, dentro da faixa neutra entre -0.5 e 0.5."
            ),
            "source": "NOAA"
        })

    if variation >= 0.2:
        alerts.append({
            "alert_type": "ONI_TREND_UP",
            "severity": "INFO",
            "title": "Tendência de aquecimento",
            "message": (
                f"O ONI subiu de {previous_oni} para {current_oni}, uma variação de {variation}. "
                "Isso indica aquecimento recente na região monitorada do Pacífico."
            ),
            "source": "NOAA"
        })

    elif variation <= -0.2:
        alerts.append({
            "alert_type": "ONI_TREND_DOWN",
            "severity": "INFO",
            "title": "Tendência de resfriamento",
            "message": (
                f"O ONI caiu de {previous_oni} para {current_oni}, uma variação de {variation}. "
                "Isso indica resfriamento recente na região monitorada do Pacífico."
            ),
            "source": "NOAA"
        })

    return alerts


def generate_alerts_from_oni(current_oni: float, previous_oni: float) -> Dict[str, Any]:
    alerts = classify_oni_alert(current_oni, previous_oni)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_oni": current_oni,
        "previous_oni": previous_oni,
        "alerts": alerts
    }