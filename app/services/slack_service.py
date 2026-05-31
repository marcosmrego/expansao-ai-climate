"""Slack notification service — Incoming Webhook."""
import json
import os
import urllib.request
from datetime import datetime, timezone

WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

_SEVERITY_EMOJI = {
    "CRITICAL": "🔴",
    "WARNING":  "🟡",
    "INFO":     "🔵",
}


def _post(payload: dict) -> bool:
    """Send payload to Slack webhook. Returns True on success."""
    if not WEBHOOK_URL:
        return False
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            WEBHOOK_URL, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def notify_climate_alert(severity: str, title: str, message: str) -> bool:
    """Send a climate alert notification."""
    emoji = _SEVERITY_EMOJI.get(severity, "⚪")
    return _post({
        "text": f"{emoji} *Alerta Climático — {severity}*",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} {title}", "emoji": True}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message}
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn",
                    "text": f"🌍 *Expansão AI Climate* · {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%Mh UTC')}"}]
            }
        ]
    })


def notify_staleness(indicator: str, last_update: str, hours: float) -> bool:
    """Alert when a data source hasn't been updated."""
    return _post({
        "text": f"⚠️ Dado desatualizado: {indicator}",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"⚠️ Dado desatualizado — {indicator}", "emoji": True}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn",
                    "text": f"Última atualização: *{last_update}*\nSem novos dados há *{hours:.0f} horas* (limite: 36h)"}
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn",
                    "text": "🌍 *Expansão AI Climate* · Verificar N8N e endpoints de coleta"}]
            }
        ]
    })


def notify_seismic(magnitude: float, place: str, date: str) -> bool:
    """Alert for significant seismic/volcanic event (M≥7.5)."""
    return _post({
        "text": f"🔴 Evento sísmico crítico: M{magnitude}",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🔴 Terremoto M{magnitude} detectado", "emoji": True}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn",
                    "text": f"*Local:* {place}\n*Data:* {date}\n*Potencial impacto climático* — evento acima de M7.5"}
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn",
                    "text": "🌍 *Expansão AI Climate* · Fonte: USGS FDSN"}]
            }
        ]
    })


def notify_workflow_ok(workflow: str, records: int) -> bool:
    """Confirm successful collection run (optional, for daily summary)."""
    return _post({
        "text": f"✅ Coleta concluída: {workflow} — {records} registros"
    })
