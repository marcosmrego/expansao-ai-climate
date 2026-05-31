import logging
from typing import Optional

from database.db import conectar
from app.services.climate_alert_engine import (
    check_enso_persistence,
    check_sst_oni_combined,
    classify_soi_alert,
    check_soi_oni_agreement,
    classify_pdo_alert,
    check_pdo_oni_agreement,
    classify_nao_alert,
    classify_amo_alert,
    classify_qbo_alert,
)

logger = logging.getLogger(__name__)

# When a new alert of type X is created, resolve any active alerts of the listed types.
_RESOLVES_ON_CREATE = {
    "EL_NINO_CONDITION":         ["LA_NINA_CONDITION", "NEUTRAL_CONDITION"],
    "LA_NINA_CONDITION":         ["EL_NINO_CONDITION", "NEUTRAL_CONDITION"],
    "NEUTRAL_CONDITION":         ["EL_NINO_CONDITION", "LA_NINA_CONDITION",
                                  "ENSO_PERSISTENCE", "SST_ONI_COMBINED_WARNING"],
    "SOI_EL_NINO_SIGNAL":        ["SOI_LA_NINA_SIGNAL", "SOI_NEUTRAL"],
    "SOI_LA_NINA_SIGNAL":        ["SOI_EL_NINO_SIGNAL", "SOI_NEUTRAL"],
    "SOI_NEUTRAL":               ["SOI_EL_NINO_SIGNAL", "SOI_LA_NINA_SIGNAL"],
    "ONI_TREND_UP":              ["ONI_TREND_DOWN"],
    "ONI_TREND_DOWN":            ["ONI_TREND_UP"],
    "SOI_TREND_UP":              ["SOI_TREND_DOWN"],
    "SOI_TREND_DOWN":            ["SOI_TREND_UP"],
    "ONI_SOI_EL_NINO_AGREEMENT": ["ONI_SOI_LA_NINA_AGREEMENT"],
    "ONI_SOI_LA_NINA_AGREEMENT": ["ONI_SOI_EL_NINO_AGREEMENT"],
    "PDO_WARM_PHASE":            ["PDO_COOL_PHASE", "PDO_NEUTRAL"],
    "PDO_COOL_PHASE":            ["PDO_WARM_PHASE", "PDO_NEUTRAL"],
    "PDO_NEUTRAL":               ["PDO_WARM_PHASE", "PDO_COOL_PHASE"],
    "PDO_ONI_EL_NINO_BOOST":    ["PDO_ONI_LA_NINA_BOOST"],
    "PDO_ONI_LA_NINA_BOOST":    ["PDO_ONI_EL_NINO_BOOST"],
    "NAO_POSITIVE":              ["NAO_NEGATIVE", "NAO_NEUTRAL"],
    "NAO_NEGATIVE":              ["NAO_POSITIVE", "NAO_NEUTRAL"],
    "NAO_NEUTRAL":               ["NAO_POSITIVE", "NAO_NEGATIVE"],
    "AMO_WARM_PHASE":            ["AMO_COOL_PHASE", "AMO_NEUTRAL"],
    "AMO_COOL_PHASE":            ["AMO_WARM_PHASE", "AMO_NEUTRAL"],
    "AMO_NEUTRAL":               ["AMO_WARM_PHASE", "AMO_COOL_PHASE"],
    "QBO_WESTERLY":              ["QBO_EASTERLY", "QBO_NEUTRAL"],
    "QBO_EASTERLY":              ["QBO_WESTERLY", "QBO_NEUTRAL"],
    "QBO_NEUTRAL":               ["QBO_WESTERLY", "QBO_EASTERLY"],
}


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

            # Auto-resolve conflicting alert types in the same transaction
            conflicting = _RESOLVES_ON_CREATE.get(alert["alert_type"], [])
            if conflicting:
                cursor.execute(
                    """
                    UPDATE climate.climate_alerts
                    SET status = 'RESOLVED', resolved_at = NOW()
                    WHERE alert_type = ANY(%s)
                      AND status = 'ACTIVE';
                    """,
                    (conflicting,),
                )

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

        # Notifica Slack para alertas CRITICAL
        if alert.get("severity") == "CRITICAL":
            try:
                from app.services.slack_service import notify_climate_alert
                notify_climate_alert(
                    severity=alert["severity"],
                    title=alert["title"],
                    message=alert["message"],
                )
            except Exception:
                pass

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


def check_and_save_sst_oni_alert() -> Optional[dict]:
    """Queries latest ONI trend and Niño 3.4 anomaly; saves alert if combined signal detected."""
    conn = conectar()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT oni FROM climate.noaa_oni
                WHERE oni > -99
                ORDER BY data_referencia DESC
                LIMIT 2;
                """
            )
            oni_rows = cursor.fetchall()

            if len(oni_rows) < 2:
                return None

            cursor.execute(
                """
                SELECT nino_34_anom FROM climate.noaa_sst_indices
                ORDER BY data_referencia DESC
                LIMIT 1;
                """
            )
            sst_row = cursor.fetchone()

        if not sst_row:
            return None

        current_oni = float(oni_rows[0][0])
        previous_oni = float(oni_rows[1][0])
        nino34_anom = float(sst_row[0])

        alert = check_sst_oni_combined(current_oni, previous_oni, nino34_anom)

        if alert:
            return save_alert(alert)
        return None

    except Exception as e:
        logger.error("Erro ao verificar sinal combinado SST+ONI: %s", e)
        raise
    finally:
        conn.close()


def check_and_save_soi_alerts() -> dict:
    """Query last 2 SOI values + latest ONI, run SOI alert classification and ONI+SOI agreement check."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT soi FROM climate.noaa_soi
                WHERE soi > -99
                ORDER BY data_referencia DESC
                LIMIT 2;
                """
            )
            soi_rows = cursor.fetchall()

            if len(soi_rows) < 2:
                return {"saved": 0, "skipped": True, "reason": "insufficient SOI data"}

            cursor.execute(
                """
                SELECT oni FROM climate.noaa_oni
                WHERE oni > -99
                ORDER BY data_referencia DESC
                LIMIT 1;
                """
            )
            oni_row = cursor.fetchone()

    except Exception as e:
        logger.error("Erro ao consultar dados SOI: %s", e)
        raise
    finally:
        conn.close()

    current_soi = float(soi_rows[0][0])
    previous_soi = float(soi_rows[1][0])

    saved_ids = []

    for alert in classify_soi_alert(current_soi, previous_soi):
        result = save_alert(alert)
        if not result.get("skipped"):
            saved_ids.append(result["id"])

    if oni_row:
        agreement = check_soi_oni_agreement(current_soi, float(oni_row[0]))
        if agreement:
            result = save_alert(agreement)
            if not result.get("skipped"):
                saved_ids.append(result["id"])

    return {"saved": len(saved_ids), "ids": saved_ids}


def check_and_save_pdo_alerts() -> dict:
    """Query latest PDO + ONI, run PDO classification and PDO×ONI convergence check."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT pdo FROM climate.noaa_pdo WHERE pdo > -99 ORDER BY data_referencia DESC LIMIT 1;"
            )
            pdo_row = cursor.fetchone()
            if not pdo_row:
                return {"saved": 0, "skipped": True, "reason": "no PDO data"}

            cursor.execute(
                "SELECT oni FROM climate.noaa_oni WHERE oni > -99 ORDER BY data_referencia DESC LIMIT 1;"
            )
            oni_row = cursor.fetchone()
    finally:
        conn.close()

    pdo = float(pdo_row[0])
    saved_ids = []

    for alert in classify_pdo_alert(pdo):
        result = save_alert(alert)
        if not result.get("skipped"):
            saved_ids.append(result["id"])

    if oni_row:
        agreement = check_pdo_oni_agreement(pdo, float(oni_row[0]))
        if agreement:
            result = save_alert(agreement)
            if not result.get("skipped"):
                saved_ids.append(result["id"])

    return {"saved": len(saved_ids), "ids": saved_ids}


def check_and_save_nao_alerts() -> dict:
    """Query latest NAO and run classification."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT nao FROM climate.noaa_nao WHERE nao > -99 ORDER BY data_referencia DESC LIMIT 1;"
            )
            row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        return {"saved": 0, "skipped": True, "reason": "no NAO data"}

    saved_ids = []
    for alert in classify_nao_alert(float(row[0])):
        result = save_alert(alert)
        if not result.get("skipped"):
            saved_ids.append(result["id"])

    return {"saved": len(saved_ids), "ids": saved_ids}


def check_and_save_amo_alerts() -> dict:
    """Query latest AMO and run classification."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT amo FROM climate.noaa_amo WHERE amo > -99 ORDER BY data_referencia DESC LIMIT 1;"
            )
            row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        return {"saved": 0, "skipped": True, "reason": "no AMO data"}

    alert = classify_amo_alert(float(row[0]))
    if not alert:
        return {"saved": 0}

    result = save_alert(alert)
    return {"saved": 0 if result.get("skipped") else 1, "ids": [] if result.get("skipped") else [result["id"]]}


def check_and_save_qbo_alerts() -> dict:
    """Query latest QBO and run classification."""
    conn = conectar()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT qbo FROM climate.noaa_qbo WHERE qbo > -999 ORDER BY data_referencia DESC LIMIT 1;"
            )
            row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        return {"saved": 0, "skipped": True, "reason": "no QBO data"}

    alert = classify_qbo_alert(float(row[0]))
    if not alert:
        return {"saved": 0}

    result = save_alert(alert)
    return {"saved": 0 if result.get("skipped") else 1, "ids": [] if result.get("skipped") else [result["id"]]}


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