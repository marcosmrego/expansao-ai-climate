from app.services.climate_alert_engine import classify_oni_alert, generate_alerts_from_oni


def test_el_nino_condition():
    alerts = classify_oni_alert(current_oni=0.7, previous_oni=0.5)
    types = [a["alert_type"] for a in alerts]
    assert "EL_NINO_CONDITION" in types


def test_la_nina_condition():
    alerts = classify_oni_alert(current_oni=-0.8, previous_oni=-0.6)
    types = [a["alert_type"] for a in alerts]
    assert "LA_NINA_CONDITION" in types


def test_neutral_condition():
    alerts = classify_oni_alert(current_oni=0.1, previous_oni=0.2)
    types = [a["alert_type"] for a in alerts]
    assert "NEUTRAL_CONDITION" in types


def test_trend_up_alert():
    alerts = classify_oni_alert(current_oni=0.8, previous_oni=0.5)
    types = [a["alert_type"] for a in alerts]
    assert "ONI_TREND_UP" in types


def test_trend_down_alert():
    alerts = classify_oni_alert(current_oni=-0.8, previous_oni=-0.5)
    types = [a["alert_type"] for a in alerts]
    assert "ONI_TREND_DOWN" in types


def test_no_trend_alert_when_stable():
    alerts = classify_oni_alert(current_oni=0.3, previous_oni=0.25)
    types = [a["alert_type"] for a in alerts]
    assert "ONI_TREND_UP" not in types
    assert "ONI_TREND_DOWN" not in types


def test_generate_alerts_structure():
    result = generate_alerts_from_oni(current_oni=0.6, previous_oni=0.3)
    assert "generated_at" in result
    assert "current_oni" in result
    assert "previous_oni" in result
    assert isinstance(result["alerts"], list)
    assert len(result["alerts"]) > 0


def test_each_alert_has_required_fields():
    result = generate_alerts_from_oni(current_oni=0.6, previous_oni=0.3)
    for alert in result["alerts"]:
        assert "alert_type" in alert
        assert "severity" in alert
        assert "title" in alert
        assert "message" in alert
        assert "source" in alert
