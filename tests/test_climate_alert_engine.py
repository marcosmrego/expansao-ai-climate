from app.services.climate_alert_engine import classify_oni_alert, generate_alerts_from_oni


# --- El Niño ---

def test_el_nino_warning():
    """ONI entre 0.5 e 1.4 → WARNING"""
    alerts = classify_oni_alert(current_oni=0.8, previous_oni=0.6)
    match = next(a for a in alerts if a["alert_type"] == "EL_NINO_CONDITION")
    assert match["severity"] == "WARNING"


def test_el_nino_critical():
    """ONI >= 1.5 → CRITICAL"""
    alerts = classify_oni_alert(current_oni=1.7, previous_oni=1.4)
    match = next(a for a in alerts if a["alert_type"] == "EL_NINO_CONDITION")
    assert match["severity"] == "CRITICAL"


def test_el_nino_critical_very_strong():
    """ONI >= 2.0 também deve ser CRITICAL"""
    alerts = classify_oni_alert(current_oni=2.3, previous_oni=1.9)
    match = next(a for a in alerts if a["alert_type"] == "EL_NINO_CONDITION")
    assert match["severity"] == "CRITICAL"


# --- La Niña ---

def test_la_nina_warning():
    """ONI entre -0.5 e -1.4 → WARNING"""
    alerts = classify_oni_alert(current_oni=-0.8, previous_oni=-0.6)
    match = next(a for a in alerts if a["alert_type"] == "LA_NINA_CONDITION")
    assert match["severity"] == "WARNING"


def test_la_nina_critical():
    """ONI <= -1.5 → CRITICAL"""
    alerts = classify_oni_alert(current_oni=-1.6, previous_oni=-1.3)
    match = next(a for a in alerts if a["alert_type"] == "LA_NINA_CONDITION")
    assert match["severity"] == "CRITICAL"


# --- Neutro ---

def test_neutral_condition():
    alerts = classify_oni_alert(current_oni=0.1, previous_oni=0.2)
    match = next(a for a in alerts if a["alert_type"] == "NEUTRAL_CONDITION")
    assert match["severity"] == "INFO"


# --- Tendências ---

def test_trend_up_info():
    """Variação 0.2 a 0.29 → INFO"""
    alerts = classify_oni_alert(current_oni=0.5, previous_oni=0.25)
    match = next(a for a in alerts if a["alert_type"] == "ONI_TREND_UP")
    assert match["severity"] == "INFO"


def test_trend_up_warning():
    """Variação >= 0.3 → WARNING"""
    alerts = classify_oni_alert(current_oni=0.8, previous_oni=0.4)
    match = next(a for a in alerts if a["alert_type"] == "ONI_TREND_UP")
    assert match["severity"] == "WARNING"


def test_trend_down_info():
    """Variação -0.2 a -0.29 → INFO"""
    alerts = classify_oni_alert(current_oni=-0.5, previous_oni=-0.25)
    match = next(a for a in alerts if a["alert_type"] == "ONI_TREND_DOWN")
    assert match["severity"] == "INFO"


def test_trend_down_warning():
    """Variação <= -0.3 → WARNING"""
    alerts = classify_oni_alert(current_oni=-0.8, previous_oni=-0.4)
    match = next(a for a in alerts if a["alert_type"] == "ONI_TREND_DOWN")
    assert match["severity"] == "WARNING"


def test_no_trend_when_stable():
    """Variação < 0.2 não gera alerta de tendência"""
    alerts = classify_oni_alert(current_oni=0.3, previous_oni=0.25)
    types = [a["alert_type"] for a in alerts]
    assert "ONI_TREND_UP" not in types
    assert "ONI_TREND_DOWN" not in types


# --- Estrutura ---

def test_generate_alerts_structure():
    result = generate_alerts_from_oni(current_oni=0.6, previous_oni=0.3)
    assert "generated_at" in result
    assert "current_oni" in result
    assert "previous_oni" in result
    assert isinstance(result["alerts"], list)
    assert len(result["alerts"]) > 0


def test_each_alert_has_required_fields():
    result = generate_alerts_from_oni(current_oni=1.8, previous_oni=1.4)
    for alert in result["alerts"]:
        assert "alert_type" in alert
        assert "severity" in alert
        assert alert["severity"] in ("INFO", "WARNING", "CRITICAL")
        assert "title" in alert
        assert "message" in alert
        assert "source" in alert
