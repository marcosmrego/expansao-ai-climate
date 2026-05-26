"""
Integration tests — require a live PostgreSQL database.
Run with: pytest tests/test_save_alerts.py -m integration
"""
import pytest

from app.services.climate_alert_engine import generate_alerts_from_oni
from app.services.climate_alert_repository import save_alert, get_active_alerts


@pytest.mark.integration
def test_save_and_retrieve_alert():
    result = generate_alerts_from_oni(current_oni=0.6, previous_oni=0.3)
    assert len(result["alerts"]) > 0

    alert = result["alerts"][0]
    saved = save_alert(alert)

    assert "id" in saved
    assert isinstance(saved["id"], int)

    active = get_active_alerts(limit=5)
    assert isinstance(active, list)
    ids = [a["id"] for a in active]
    assert saved["id"] in ids
