import os
import sys

sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "../.."
        )
    )
)

from database.db import conectar


def save_alert(alert):
    conn = conectar()

    try:
        with conn.cursor() as cursor:
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

    except Exception:
        conn.rollback()
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

    finally:
        conn.close()