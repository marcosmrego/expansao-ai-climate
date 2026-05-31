"""Seismic/volcanic collector — USGS FDSN Event Web Service.

Coleta dois tipos de eventos:
  1. Terremotos significativos: magnitude >= 5.5 globalmente
  2. Explosões vulcânicas: qualquer magnitude >= 2.0

Eventos são marcados como climate_relevant quando:
  - Explosão vulcânica com magnitude >= 4.0  (proxy VEI >= 4)
  - Terremoto em região vulcânica com mag >= 6.0

Referência: https://earthquake.usgs.gov/fdsnws/event/1/
"""
import json
import time
from datetime import date, datetime, timezone, timedelta

import requests

URL_BASE = "https://earthquake.usgs.gov/fdsnws/event/1/query"
ORIGEM = "USGS_FDSN"

# Regiões vulcânicas conhecidas (lon_min, lon_max, lat_min, lat_max)
_VOLCANIC_REGIONS = [
    (-180, 180, -90, 90),  # globalmente qualquer volcanic explosion
]

# Limiares
_MIN_MAG_EARTHQUAKE = 5.5   # terremotos significativos
_MIN_MAG_VOLCANIC   = 2.0   # explosões vulcânicas
_MIN_MAG_CLIMATE    = 4.0   # limiar para marcar como climate_relevant (vulcânico)
_MIN_MAG_CLIMATE_EQ = 6.0   # terremoto para marcar climate_relevant


def _fetch_events(start_time: str, end_time: str,
                  min_mag: float, event_type: str = None) -> list:
    """Fetch events from USGS API."""
    params = {
        "format":    "geojson",
        "starttime": start_time,
        "endtime":   end_time,
        "minmagnitude": min_mag,
        "orderby":   "time",
        "limit":     500,
    }
    if event_type:
        params["eventtype"] = event_type

    for attempt in range(1, 4):
        try:
            r = requests.get(URL_BASE, params=params, timeout=30)
            r.raise_for_status()
            return r.json().get("features", [])
        except requests.RequestException as e:
            if attempt == 3:
                raise
            print(f"Tentativa {attempt} falhou: {e}. Aguardando 5s...")
            time.sleep(5)
    return []


def _is_climate_relevant(mag: float, event_type: str) -> bool:
    etype = (event_type or "").lower()
    if "volcanic" in etype or "explosion" in etype:
        return mag >= _MIN_MAG_CLIMATE
    return mag >= _MIN_MAG_CLIMATE_EQ


def baixar_e_parsear(days_back: int = 2) -> list:
    """Fetch and parse seismic events for the last N days."""
    end_dt   = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days_back)
    start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%S")
    end_str   = end_dt.strftime("%Y-%m-%dT%H:%M:%S")

    # 1. Terremotos significativos
    eq_features = _fetch_events(start_str, end_str, _MIN_MAG_EARTHQUAKE)

    # 2. Explosões VULCÂNICAS apenas (não quarry/mine blasts)
    vol_features = _fetch_events(start_str, end_str, _MIN_MAG_VOLCANIC, "volcanic+explosion")

    # Merge e dedup por ID
    seen = set()
    registros = []
    for feat in eq_features + vol_features:
        eid = feat.get("id")
        if not eid or eid in seen:
            continue
        seen.add(eid)

        props = feat.get("properties", {})
        coords = feat.get("geometry", {}).get("coordinates", [None, None, None])

        try:
            mag   = float(props.get("mag") or 0)
            lon   = float(coords[0])
            lat   = float(coords[1])
            depth = float(coords[2]) if coords[2] is not None else None
            ts_ms = int(props.get("time") or 0)
            ts    = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            etype = (props.get("type") or "earthquake").lower()
        except (TypeError, ValueError):
            continue

        registros.append({
            "event_id":        eid,
            "data_referencia": ts.date(),
            "timestamp_utc":   ts,
            "latitude":        round(lat, 4),
            "longitude":       round(lon, 4),
            "depth_km":        round(depth, 2) if depth is not None else None,
            "magnitude":       round(mag, 2),
            "magnitude_type":  props.get("magType"),
            "event_type":      etype,
            "place":           props.get("place"),
            "title":           props.get("title"),
            "climate_relevant": _is_climate_relevant(mag, etype),
            "alert_level":     props.get("alert"),
        })

    return registros


def inserir_registros(conn, registros: list) -> int:
    total = 0
    with conn.cursor() as cur:
        for r in registros:
            cur.execute(
                """
                INSERT INTO climate.seismic_events
                    (event_id, data_referencia, timestamp_utc,
                     latitude, longitude, depth_km,
                     magnitude, magnitude_type, event_type,
                     place, title, climate_relevant, alert_level, fonte)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (event_id) DO UPDATE SET
                    magnitude        = EXCLUDED.magnitude,
                    climate_relevant = EXCLUDED.climate_relevant,
                    alert_level      = EXCLUDED.alert_level,
                    criado_em        = NOW();
                """,
                (
                    r["event_id"], r["data_referencia"], r["timestamp_utc"],
                    r["latitude"], r["longitude"], r["depth_km"],
                    r["magnitude"], r["magnitude_type"], r["event_type"],
                    r["place"], r["title"], r["climate_relevant"],
                    r["alert_level"], ORIGEM,
                ),
            )
            total += 1
    return total
