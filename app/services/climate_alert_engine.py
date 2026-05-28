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


# SOI thresholds (note: SOI is INVERTED vs ONI — negative SOI = El Niño signal)
_SOI_THRESHOLD = 1.0
_SOI_STRONG_THRESHOLD = 1.8
_SOI_TREND_INFO = 0.3
_SOI_TREND_WARNING = 0.5


def _soi_severity(soi: float) -> str:
    return "CRITICAL" if abs(soi) >= _SOI_STRONG_THRESHOLD else "WARNING"


def classify_soi_alert(current_soi: float, previous_soi: float) -> List[Dict[str, Any]]:
    """
    Classifies SOI-based alerts.
    SOI is inverted vs ONI: negative SOI = El Niño signal, positive = La Niña signal.
    """
    alerts = []
    variation = round(current_soi - previous_soi, 2)

    if current_soi <= -_SOI_THRESHOLD:
        severity = _soi_severity(current_soi)
        prefix = "Sinal forte de" if severity == "CRITICAL" else "Sinal atmosférico de"
        detail = (
            f", abaixo do limiar forte de -{_SOI_STRONG_THRESHOLD}."
            if severity == "CRITICAL"
            else f", abaixo do limite de -{_SOI_THRESHOLD}."
        )
        alerts.append({
            "alert_type": "SOI_EL_NINO_SIGNAL",
            "severity": severity,
            "title": f"{prefix} El Niño (SOI)",
            "message": (
                f"O Índice de Oscilação Sul (SOI) está em {current_soi}{detail} "
                "SOI negativo indica pressão atmosférica mais baixa em Darwin, favorecendo o aquecimento do Pacífico."
            ),
            "source": "NOAA"
        })

    elif current_soi >= _SOI_THRESHOLD:
        severity = _soi_severity(current_soi)
        prefix = "Sinal forte de" if severity == "CRITICAL" else "Sinal atmosférico de"
        detail = (
            f", acima do limiar forte de {_SOI_STRONG_THRESHOLD}."
            if severity == "CRITICAL"
            else f", acima do limite de {_SOI_THRESHOLD}."
        )
        alerts.append({
            "alert_type": "SOI_LA_NINA_SIGNAL",
            "severity": severity,
            "title": f"{prefix} La Niña (SOI)",
            "message": (
                f"O Índice de Oscilação Sul (SOI) está em {current_soi}{detail} "
                "SOI positivo indica pressão atmosférica mais alta em Darwin, favorecendo o resfriamento do Pacífico."
            ),
            "source": "NOAA"
        })

    else:
        alerts.append({
            "alert_type": "SOI_NEUTRAL",
            "severity": "INFO",
            "title": "SOI em neutralidade",
            "message": (
                f"O Índice de Oscilação Sul (SOI) está em {current_soi}, "
                f"dentro da faixa neutra entre -{_SOI_THRESHOLD} e {_SOI_THRESHOLD}."
            ),
            "source": "NOAA"
        })

    if variation <= -_SOI_TREND_WARNING:
        alerts.append({
            "alert_type": "SOI_TREND_DOWN",
            "severity": "WARNING",
            "title": "SOI em queda acelerada (sinal El Niño)",
            "message": (
                f"O SOI caiu de {previous_soi} para {current_soi}, variação de {variation}. "
                "Queda acelerada no SOI pode indicar desenvolvimento ou intensificação de El Niño."
            ),
            "source": "NOAA"
        })
    elif variation <= -_SOI_TREND_INFO:
        alerts.append({
            "alert_type": "SOI_TREND_DOWN",
            "severity": "INFO",
            "title": "Tendência de queda no SOI",
            "message": (
                f"O SOI caiu de {previous_soi} para {current_soi}, variação de {variation}. "
                "Indica pressão atmosférica favorecendo condições de El Niño."
            ),
            "source": "NOAA"
        })
    elif variation >= _SOI_TREND_WARNING:
        alerts.append({
            "alert_type": "SOI_TREND_UP",
            "severity": "WARNING",
            "title": "SOI em alta acelerada (sinal La Niña)",
            "message": (
                f"O SOI subiu de {previous_soi} para {current_soi}, variação de +{variation}. "
                "Alta acelerada no SOI pode indicar desenvolvimento ou intensificação de La Niña."
            ),
            "source": "NOAA"
        })
    elif variation >= _SOI_TREND_INFO:
        alerts.append({
            "alert_type": "SOI_TREND_UP",
            "severity": "INFO",
            "title": "Tendência de alta no SOI",
            "message": (
                f"O SOI subiu de {previous_soi} para {current_soi}, variação de +{variation}. "
                "Indica pressão atmosférica favorecendo condições de La Niña."
            ),
            "source": "NOAA"
        })

    return alerts


def check_soi_oni_agreement(soi: float, oni: float) -> Optional[Dict[str, Any]]:
    """
    Returns an alert when SOI and ONI both signal the same ENSO phase.
    Convergence of oceanic (ONI) and atmospheric (SOI) signals is the
    most robust criterion for confirming an active ENSO event.
    """
    oni_el_nino = oni >= _ONI_THRESHOLD
    oni_la_nina = oni <= -_ONI_THRESHOLD
    soi_el_nino = soi <= -_SOI_THRESHOLD
    soi_la_nina = soi >= _SOI_THRESHOLD

    if oni_el_nino and soi_el_nino:
        severity = (
            "CRITICAL"
            if oni >= _ONI_STRONG_THRESHOLD or abs(soi) >= _SOI_STRONG_THRESHOLD
            else "WARNING"
        )
        return {
            "alert_type": "ONI_SOI_EL_NINO_AGREEMENT",
            "severity": severity,
            "title": "Convergência ONI + SOI: El Niño confirmado",
            "message": (
                f"ONI ({oni}) e SOI ({soi}) apontam simultaneamente para El Niño. "
                "A convergência oceânica e atmosférica é o critério mais robusto de confirmação do evento."
            ),
            "source": "NOAA"
        }

    if oni_la_nina and soi_la_nina:
        severity = (
            "CRITICAL"
            if abs(oni) >= _ONI_STRONG_THRESHOLD or soi >= _SOI_STRONG_THRESHOLD
            else "WARNING"
        )
        return {
            "alert_type": "ONI_SOI_LA_NINA_AGREEMENT",
            "severity": severity,
            "title": "Convergência ONI + SOI: La Niña confirmada",
            "message": (
                f"ONI ({oni}) e SOI ({soi}) apontam simultaneamente para La Niña. "
                "A convergência oceânica e atmosférica confirma o evento La Niña."
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


# ── PDO ──────────────────────────────────────────────────────────────────────
_PDO_THRESHOLD = 0.5
_PDO_STRONG_THRESHOLD = 1.5


def classify_pdo_alert(pdo: float) -> List[Dict[str, Any]]:
    """PDO positive (warm) amplifies El Niño; negative (cool) amplifies La Niña."""
    if pdo >= _PDO_THRESHOLD:
        severity = "CRITICAL" if pdo >= _PDO_STRONG_THRESHOLD else "WARNING"
        label = " — sinal forte" if severity == "CRITICAL" else ""
        return [{
            "alert_type": "PDO_WARM_PHASE",
            "severity": severity,
            "title": f"PDO em fase quente{label}",
            "message": (
                f"O Índice de Oscilação Decadal do Pacífico (PDO) está em {pdo:.2f}, "
                f"acima do limiar de +{_PDO_THRESHOLD}. "
                "A fase quente do PDO amplifica eventos El Niño e atenua La Niña."
            ),
            "source": "NOAA",
        }]

    if pdo <= -_PDO_THRESHOLD:
        severity = "CRITICAL" if pdo <= -_PDO_STRONG_THRESHOLD else "WARNING"
        label = " — sinal forte" if severity == "CRITICAL" else ""
        return [{
            "alert_type": "PDO_COOL_PHASE",
            "severity": severity,
            "title": f"PDO em fase fria{label}",
            "message": (
                f"O Índice de Oscilação Decadal do Pacífico (PDO) está em {pdo:.2f}, "
                f"abaixo do limiar de -{_PDO_THRESHOLD}. "
                "A fase fria do PDO amplifica eventos La Niña e atenua El Niño."
            ),
            "source": "NOAA",
        }]

    return [{
        "alert_type": "PDO_NEUTRAL",
        "severity": "INFO",
        "title": "PDO em fase neutra",
        "message": (
            f"O Índice de Oscilação Decadal do Pacífico (PDO) está em {pdo:.2f}, "
            f"dentro da faixa neutra entre -{_PDO_THRESHOLD} e +{_PDO_THRESHOLD}."
        ),
        "source": "NOAA",
    }]


def check_pdo_oni_agreement(pdo: float, oni: float) -> Optional[Dict[str, Any]]:
    """Convergence of PDO and ONI on the same ENSO phase = amplified event signal."""
    pdo_warm = pdo >= _PDO_THRESHOLD
    pdo_cool = pdo <= -_PDO_THRESHOLD
    oni_el_nino = oni >= _ONI_THRESHOLD
    oni_la_nina = oni <= -_ONI_THRESHOLD

    if pdo_warm and oni_el_nino:
        severity = (
            "CRITICAL"
            if pdo >= _PDO_STRONG_THRESHOLD or oni >= _ONI_STRONG_THRESHOLD
            else "WARNING"
        )
        return {
            "alert_type": "PDO_ONI_EL_NINO_BOOST",
            "severity": severity,
            "title": "Amplificação El Niño: PDO quente + ONI positivo",
            "message": (
                f"PDO ({pdo:.2f}) e ONI ({oni:.2f}) convergem para El Niño. "
                "A fase quente do PDO amplifica o evento, aumentando impactos climáticos globais."
            ),
            "source": "NOAA",
        }

    if pdo_cool and oni_la_nina:
        severity = (
            "CRITICAL"
            if pdo <= -_PDO_STRONG_THRESHOLD or oni <= -_ONI_STRONG_THRESHOLD
            else "WARNING"
        )
        return {
            "alert_type": "PDO_ONI_LA_NINA_BOOST",
            "severity": severity,
            "title": "Amplificação La Niña: PDO frio + ONI negativo",
            "message": (
                f"PDO ({pdo:.2f}) e ONI ({oni:.2f}) convergem para La Niña. "
                "A fase fria do PDO potencializa o evento e seus impactos globais."
            ),
            "source": "NOAA",
        }

    return None


# ── NAO ──────────────────────────────────────────────────────────────────────
_NAO_THRESHOLD = 0.5


def classify_nao_alert(nao: float) -> List[Dict[str, Any]]:
    """NAO positive = stronger westerlies; negative = weaker westerlies/blocking."""
    if nao >= _NAO_THRESHOLD:
        return [{
            "alert_type": "NAO_POSITIVE",
            "severity": "INFO",
            "title": "NAO em fase positiva",
            "message": (
                f"O Índice da Oscilação do Atlântico Norte (NAO) está em {nao:.2f}. "
                "Fase positiva indica ventos de oeste mais intensos, favorecendo invernos "
                "suaves e úmidos no noroeste da Europa."
            ),
            "source": "NOAA",
        }]

    if nao <= -_NAO_THRESHOLD:
        return [{
            "alert_type": "NAO_NEGATIVE",
            "severity": "WARNING",
            "title": "NAO em fase negativa",
            "message": (
                f"O Índice da Oscilação do Atlântico Norte (NAO) está em {nao:.2f}. "
                "Fase negativa associada a invernos mais frios no noroeste da Europa "
                "e maior frequência de bloqueios atmosféricos."
            ),
            "source": "NOAA",
        }]

    return [{
        "alert_type": "NAO_NEUTRAL",
        "severity": "INFO",
        "title": "NAO em fase neutra",
        "message": (
            f"O Índice da Oscilação do Atlântico Norte (NAO) está em {nao:.2f}, "
            f"dentro da faixa neutra entre -{_NAO_THRESHOLD} e +{_NAO_THRESHOLD}."
        ),
        "source": "NOAA",
    }]


# ── AMO ──────────────────────────────────────────────────────────────────────
_AMO_THRESHOLD = 0.1


def classify_amo_alert(amo: float) -> Optional[Dict[str, Any]]:
    """AMO warm phase = more Atlantic hurricanes and Sahel drought."""
    if amo >= _AMO_THRESHOLD:
        return {
            "alert_type": "AMO_WARM_PHASE",
            "severity": "WARNING",
            "title": "AMO em fase quente",
            "message": (
                f"A Oscilação Multidecadal do Atlântico (AMO) está em {amo:.4f}. "
                "Fase quente favorece maior atividade de furacões no Atlântico "
                "e secas no Sahel."
            ),
            "source": "NOAA",
        }

    if amo <= -_AMO_THRESHOLD:
        return {
            "alert_type": "AMO_COOL_PHASE",
            "severity": "INFO",
            "title": "AMO em fase fria",
            "message": (
                f"A Oscilação Multidecadal do Atlântico (AMO) está em {amo:.4f}. "
                "Fase fria associada à menor atividade de furacões e maior precipitação "
                "no Sahel."
            ),
            "source": "NOAA",
        }

    return {
        "alert_type": "AMO_NEUTRAL",
        "severity": "INFO",
        "title": "AMO em transição de fase",
        "message": (
            f"A Oscilação Multidecadal do Atlântico (AMO) está em {amo:.4f}, "
            "próximo à neutralidade."
        ),
        "source": "NOAA",
    }


# ── QBO ──────────────────────────────────────────────────────────────────────
_QBO_THRESHOLD = 5.0


def classify_qbo_alert(qbo: float) -> Optional[Dict[str, Any]]:
    """QBO in m/s at 30mb. Positive = westerly (QBO-W); negative = easterly (QBO-E)."""
    if qbo >= _QBO_THRESHOLD:
        return {
            "alert_type": "QBO_WESTERLY",
            "severity": "INFO",
            "title": "QBO em fase oesteira",
            "message": (
                f"A Oscilação Quasi-Bienal (QBO) está em {qbo:.1f} m/s — fase oesteira (positiva). "
                "Ventos estratosféricos de oeste; modulação indireta na intensidade de ciclones."
            ),
            "source": "NOAA",
        }

    if qbo <= -_QBO_THRESHOLD:
        return {
            "alert_type": "QBO_EASTERLY",
            "severity": "INFO",
            "title": "QBO em fase lesteira",
            "message": (
                f"A Oscilação Quasi-Bienal (QBO) está em {qbo:.1f} m/s — fase lesteira (negativa). "
                "Ventos estratosféricos de leste; associada a maior atividade de furacões no Atlântico."
            ),
            "source": "NOAA",
        }

    return {
        "alert_type": "QBO_NEUTRAL",
        "severity": "INFO",
        "title": "QBO em transição de fase",
        "message": (
            f"A Oscilação Quasi-Bienal (QBO) está em {qbo:.1f} m/s, "
            "próxima à transição entre fase oesteira e lesteira."
        ),
        "source": "NOAA",
    }
