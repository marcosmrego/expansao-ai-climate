import sys
import os

sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            ".."
        )
    )
)

from app.services.climate_alert_engine import generate_alerts_from_oni
from app.services.climate_alert_repository import save_alert, get_active_alerts


result = generate_alerts_from_oni(
    current_oni=0.11,
    previous_oni=-0.15
)

for alert in result["alerts"]:
    saved = save_alert(alert)
    print("Alerta salvo:", saved)

print("Alertas ativos:")
print(get_active_alerts())