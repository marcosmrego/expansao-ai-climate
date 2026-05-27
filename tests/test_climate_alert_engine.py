from app.services.climate_alert_engine import (
    classify_oni_alert,
    check_enso_persistence,
    check_sst_oni_combined,
    generate_alerts_from_oni,
)


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


# --- Persistência ENSO ---

def test_persistence_el_nino_warning():
    """3 meses consecutivos com ONI entre 0.5 e 1.4 → WARNING"""
    alert = check_enso_persistence([0.6, 0.7, 0.8])
    assert alert is not None
    assert alert["alert_type"] == "ENSO_PERSISTENCE"
    assert alert["severity"] == "WARNING"
    assert "El Niño" in alert["title"]


def test_persistence_el_nino_critical():
    """3 meses com pelo menos um ONI >= 1.5 → CRITICAL"""
    alert = check_enso_persistence([0.8, 1.2, 1.6])
    assert alert is not None
    assert alert["severity"] == "CRITICAL"


def test_persistence_la_nina_warning():
    """3 meses consecutivos com ONI entre -0.5 e -1.4 → WARNING"""
    alert = check_enso_persistence([-0.6, -0.7, -0.8])
    assert alert is not None
    assert alert["alert_type"] == "ENSO_PERSISTENCE"
    assert alert["severity"] == "WARNING"
    assert "La Niña" in alert["title"]


def test_persistence_la_nina_critical():
    """3 meses com pelo menos um ONI <= -1.5 → CRITICAL"""
    alert = check_enso_persistence([-0.8, -1.2, -1.6])
    assert alert is not None
    assert alert["severity"] == "CRITICAL"


def test_persistence_not_triggered_when_broken():
    """Série interrompida por mês neutro não deve gerar alerta"""
    alert = check_enso_persistence([0.7, 0.1, 0.8])
    assert alert is None


def test_persistence_not_triggered_below_threshold():
    """Valores abaixo de 0.5 não disparam persistência"""
    alert = check_enso_persistence([0.3, 0.4, 0.4])
    assert alert is None


def test_persistence_requires_minimum_months():
    """Histórico menor que months não gera alerta"""
    alert = check_enso_persistence([0.8, 0.9], months=3)
    assert alert is None


def test_persistence_custom_months():
    """Persistência de 5 meses quando months=5"""
    alert = check_enso_persistence([0.6, 0.7, 0.8, 0.9, 1.0], months=5)
    assert alert is not None
    assert "5 meses" in alert["title"]


# --- SST + ONI combinados ---

def test_sst_oni_combined_triggers_warning():
    """ONI subindo + Niño 3.4 acima do limiar → WARNING"""
    alert = check_sst_oni_combined(current_oni=0.8, previous_oni=0.5, nino34_anom=0.7)
    assert alert is not None
    assert alert["alert_type"] == "SST_ONI_COMBINED_WARNING"
    assert alert["severity"] == "WARNING"


def test_sst_oni_no_alert_when_nino34_below_threshold():
    """ONI subindo mas Niño 3.4 frio → sem alerta"""
    alert = check_sst_oni_combined(current_oni=0.8, previous_oni=0.5, nino34_anom=0.3)
    assert alert is None


def test_sst_oni_no_alert_when_oni_stable():
    """Niño 3.4 aquecido mas ONI estável → sem alerta"""
    alert = check_sst_oni_combined(current_oni=0.6, previous_oni=0.55, nino34_anom=0.8)
    assert alert is None


def test_sst_oni_no_alert_when_oni_falling():
    """ONI caindo mesmo com Niño 3.4 aquecido → sem alerta"""
    alert = check_sst_oni_combined(current_oni=0.3, previous_oni=0.6, nino34_anom=0.9)
    assert alert is None


def test_sst_oni_custom_nino34_threshold():
    """Threshold customizado de 1.0 não dispara com Niño 3.4 = 0.7"""
    alert = check_sst_oni_combined(
        current_oni=0.8, previous_oni=0.5, nino34_anom=0.7, nino34_threshold=1.0
    )
    assert alert is None


def test_sst_oni_message_contains_values():
    """Mensagem deve incluir os valores observados"""
    alert = check_sst_oni_combined(current_oni=0.9, previous_oni=0.6, nino34_anom=0.8)
    assert "0.8" in alert["message"]
    assert "0.3" in alert["message"]  # variação


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
