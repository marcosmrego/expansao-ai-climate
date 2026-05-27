import logging
from typing import Optional

from database.db import conectar
from app.services.climate_alert_engine import check_enso_persistence

logger = logging.getLogger(__name__)


def save_alert(alert):
    conn = conectar()

    try:
        with conn.cursor() as cursor:
            # Skip if an active alert of the same type was already created in the last 24h
            cursor.execute(
                """
                SELECT id FROM climate.climate_alerts
                WHERE alert_type = %s
                  AND status = 'ACTIVE'
                  AND created_at > NOW() - INTERVAL '24 hours'
                LIMIT 1;
                """,
                (alert["alert_type"],),
            )
            existing = cursor.fetchone()
            if existing:
                return {"id": existing[0], "skipped": True}

            cursor.execute(
                """
                INSERT INTO climate.climate_alerts (
                    alert_type,
                    severity,
                    title,
                    message,
                    source,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, 'ACTIVE')
                RETURNING id;
                """,
                (
                    alert["alert_type"],
                    alert["severity"],
                    alert["title"],
                    alert["message"],
                    alert.get("source", "NOAA"),
                ),
            )

            alert_id = cursor.fetchone()[0]

        conn.commit()
        return {"id": alert_id}

    except Exception as e:
        logger.error("Erro ao salvar alerta: %s", e)
        conn.rollback()
        raise

    finally:
        conn.close()


def check_and_save_persistence_alert(months: int = 3) -> Optional[dict]:
    """Queries the last `months` ONI values and saves a persistence alert if detected."""
    conn = conectar()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT oni FROM climate.noaa_oni
                WHERE oni > -99
                ORDER BY data_referencia DESC
                LIMIT %s;
                """,
                (months,),
            )
            rows = cursor.fetchall()

        if len(rows) < months:
            return None

        oni_history = [float(r[0]) for r in reversed(rows)]
        alert = check_enso_persistence(oni_history, months)

        if alert:
            return save_alert(alert)
        return None

    except Exception as e:
        logger.error("Erro ao verificar persistência ENSO: %s", e)
        raise
    finally:
        conn.close()


def get_active_alerts(limit=10):
    conn = conectar()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    alert_type,
                    severity,
                    title,
                    message,
                    source,
                    status,
                    created_at,
                    resolved_at
                FROM climate.climate_alerts
                WHERE status = 'ACTIVE'
                ORDER BY created_at DESC
                LIMIT %s;
                """,
                (limit,),
            )

            rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "alert_type": row[1],
                "severity": row[2],
                "title": row[3],
                "message": row[4],
                "source": row[5],
                "status": row[6],
                "created_at": row[7],
                "resolved_at": row[8],
            }
            for row in rows
        ]

    except Exception as e:
        logger.error("Erro ao buscar alertas ativos: %s", e)
        raise
    finally:
        conn.close()