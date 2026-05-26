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

result = generate_alerts_from_oni(
    current_oni=0.11,
    previous_oni=-0.15
)

print(result)