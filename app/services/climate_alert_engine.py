from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# NOAA ONI thresholds
_ONI_THRESHOLD = 0.5         # Limiar de detecção El Niño / La Niña
_ONI_STRONG_THRESHOLD = 1.5  # Evento forte → CRITICAL

# Trend thresholds
_TREND_WARNING = 0.3  # Variação brusca → WARNING
_TREND_INFO = 0.2     # Variação normal → INFO


def _enso_severity(oni: float) -> str:
    return "CRITICAL" if abs(oni) >= _ONI_STRONG_THRESHOLD else "WARNING"


def classify_oni_alert(current_oni: float, previous_oni: float) -> List[Dict[str, Any]]:
    alerts = []

    variation = round(current_oni - previous_oni, 2)

    if current_oni >= _ONI_THRESHOLD:
        severity = _enso_severity(current_oni)
        prefix = "Evento forte de" if severity == "CRITICAL" else "Possível condição de"
        detail = (
            f", acima do limiar de El Niño forte ({_ONI_STRONG_THRESHOLD})."
            if severity == "CRITICAL"
            else f", acima do limite de {_ONI_THRESHOLD}."
        )
        alerts.append({
            "alert_type": "EL_NINO_CONDITION",
            "severity": severity,
            "title": f"{prefix} El Niño",
            "message": (
                f"O índice ONI está em {current_oni}{detail} "
                "Isso pode indicar condição favorável ao El Niño, dependendo da persistência nos próximos períodos."
            ),
            "source": "NOAA"
        })

    elif current_oni <= -_ONI_THRESHOLD:
        severity = _enso_severity(current_oni)
        prefix = "Evento forte de" if severity == "CRITICAL" else "Possível condição de"
        detail = (
            f", abaixo do limiar de La Niña forte (-{_ONI_STRONG_THRESHOLD})."
            if severity == "CRITICAL"
            else f", abaixo do limite de -{_ONI_THRESHOLD}."
        )
        alerts.append({
            "alert_type": "LA_NINA_CONDITION",
            "severity": severity,
            "title": f"{prefix} La Niña",
            "message": (
                f"O índice ONI está em {current_oni}{detail} "
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
                f"O índice ONI está em {current_oni}, "
                f"dentro da faixa neutra entre -{_ONI_THRESHOLD} e {_ONI_THRESHOLD}."
            ),
            "source": "NOAA"
        })

    if variation >= _TREND_WARNING:
        alerts.append({
            "alert_type": "ONI_TREND_UP",
            "severity": "WARNING",
            "title": "Aquecimento acelerado detectado",
            "message": (
                f"O ONI subiu de {previous_oni} para {current_oni}, variação rápida de +{variation}. "
                "Aquecimento acelerado pode indicar intensificação do evento climático."
            ),
            "source": "NOAA"
        })
    elif variation >= _TREND_INFO:
        alerts.append({
            "alert_type": "ONI_TREND_UP",
            "severity": "INFO",
            "title": "Tendência de aquecimento",
            "message": (
                f"O ONI subiu de {previous_oni} para {current_oni}, uma variação de +{variation}. "
                "Isso indica aquecimento recente na região monitorada do Pacífico."
            ),
            "source": "NOAA"
        })
    elif variation <= -_TREND_WARNING:
        alerts.append({
            "alert_type": "ONI_TREND_DOWN",
            "severity": "WARNING",
            "title": "Resfriamento acelerado detectado",
            "message": (
                f"O ONI caiu de {previous_oni} para {current_oni}, variação rápida de {variation}. "
                "Resfriamento acelerado pode indicar intensificação do evento climático."
            ),
            "source": "NOAA"
        })
    elif variation <= -_TREND_INFO:
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


def check_enso_persistence(
    oni_history: List[float],
    months: int = 3
) -> Optional[Dict[str, Any]]:
    """
    Returns a persistence alert if the last `months` values are consistently
    above _ONI_THRESHOLD (El Niño) or below -_ONI_THRESHOLD (La Niña).
    oni_history must be ordered from oldest to newest.
    """
    if len(oni_history) < months:
        return None

    recent = oni_history[-months:]

    if all(v >= _ONI_THRESHOLD for v in recent):
        severity = "CRITICAL" if max(recent) >= _ONI_STRONG_THRESHOLD else "WARNING"
        valores = ", ".join(str(v) for v in recent)
        return {
            "alert_type": "ENSO_PERSISTENCE",
            "severity": severity,
            "title": f"Persistência de El Niño — {months} meses consecutivos",
            "message": (
                f"O índice ONI permaneceu acima de {_ONI_THRESHOLD} por {months} meses consecutivos "
                f"(valores: {valores}). "
                "A persistência é o critério oficial da NOAA para caracterizar formalmente um evento El Niño."
            ),
            "source": "NOAA"
        }

    if all(v <= -_ONI_THRESHOLD for v in recent):
        severity = "CRITICAL" if min(recent) <= -_ONI_STRONG_THRESHOLD else "WARNING"
        valores = ", ".join(str(v) for v in recent)
        return {
            "alert_type": "ENSO_PERSISTENCE",
            "severity": severity,
            "title": f"Persistência de La Niña — {months} meses consecutivos",
            "message": (
                f"O índice ONI permaneceu abaixo de -{_ONI_THRESHOLD} por {months} meses consecutivos "
                f"(valores: {valores}). "
                "A persistência é o critério oficial da NOAA para caracterizar formalmente um evento La Niña."
            ),
            "source": "NOAA"
        }

    return None


def check_sst_oni_combined(
    current_oni: float,
    previous_oni: float,
    nino34_anom: float,
    nino34_threshold: float = 0.5,
) -> Optional[Dict[str, Any]]:
    """
    Returns a WARNING if ONI is trending up (variation >= _TREND_INFO)
    AND Niño 3.4 anomaly is above nino34_threshold.
    """
    variation = round(current_oni - previous_oni, 2)

    if variation >= _TREND_INFO and nino34_anom > nino34_threshold:
        return {
            "alert_type": "SST_ONI_COMBINED_WARNING",
            "severity": "WARNING",
            "title": "Sinal combinado: ONI em alta + Niño 3.4 aquecido",
            "message": (
                f"O índice ONI está em tendência de alta (variação de +{variation}) "
                f"e a anomalia do Niño 3.4 está em {nino34_anom}°C, "
                f"acima do limiar de {nino34_threshold}°C. "
                "Esse sinal combinado pode indicar desenvolvimento ou intensificação de El Niño."
            ),
            "source": "NOAA"
        }

    return None


def generate_alerts_from_oni(current_oni: float, previous_oni: float) -> Dict[str, Any]:
    alerts = classify_oni_alert(current_oni, previous_oni)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_oni": current_oni,
        "previous_oni": previous_oni,
        "alerts": alerts
    }
