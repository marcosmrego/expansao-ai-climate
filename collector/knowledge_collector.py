"""Coleta artigos climáticos de feeds RSS públicos para a knowledge_base."""

import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests
from dotenv import load_dotenv

from database.db import conectar

load_dotenv()

# Feeds RSS públicos — fontes confiáveis, sem restrição de scraping
RSS_SOURCES = [
    {
        "name": "NOAA Climate.gov ENSO",
        "url": "https://www.climate.gov/feeds/news-features/enso.rss",
        "topics": ["clima", "noaa", "enso"],
    },
    {
        "name": "NOAA Climate.gov Highlights",
        "url": "https://www.climate.gov/feeds/news-features/highlights.rss",
        "topics": ["clima", "noaa"],
    },
    {
        "name": "NASA Earth Observatory",
        "url": "https://earthobservatory.nasa.gov/feeds/earth-observatory.rss",
        "topics": ["clima", "nasa", "satellite"],
    },
    {
        "name": "Carbon Brief",
        "url": "https://www.carbonbrief.org/feed",
        "topics": ["clima", "co2", "aquecimento"],
    },
    {
        "name": "Climate Central",
        "url": "https://www.climatecentral.org/rss",
        "topics": ["clima", "impactos"],
    },
    {
        "name": "The Guardian — Climate Crisis",
        "url": "https://www.theguardian.com/environment/climate-crisis/rss",
        "topics": ["clima", "impactos", "aquecimento"],
    },
    {
        "name": "ScienceDaily Earth & Climate",
        "url": "https://www.sciencedaily.com/rss/earth_climate/climate.xml",
        "topics": ["clima", "ciencia", "pesquisa"],
    },
    {
        "name": "Copernicus Climate",
        "url": "https://climate.copernicus.eu/rss.xml",
        "topics": ["clima", "copernicus", "enso"],
    },
]

# Palavras-chave para classificar como relevante para ENSO/clima
_ENSO_KEYWORDS = {
    "enso", "el niño", "el nino", "la niña", "la nina", "oni", "sst",
    "pacific", "pacífico", "nino", "niño", "ocean", "oceano",
    "climate", "clima", "drought", "seca", "flood", "enchente",
    "temperature", "temperatura", "anomaly", "anomalia",
    "precipitation", "precipitação", "monsoon", "monção",
}


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str).astimezone(timezone.utc)
    except Exception:
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None


def _detect_topics(title: str, summary: str) -> list[str]:
    text = (title + " " + (summary or "")).lower()
    found = [kw for kw in _ENSO_KEYWORDS if kw in text]
    return found or ["clima"]


def _strip_tags(text: str | None) -> str:
    if not text:
        return ""
    try:
        return ET.fromstring(f"<x>{text}</x>").itertext().__next__() or ""
    except Exception:
        # fallback simples
        import re
        return re.sub(r"<[^>]+>", " ", text).strip()


def coletar_feed(source: dict) -> list[dict]:
    try:
        r = requests.get(source["url"], timeout=15, headers={"User-Agent": "ClimateBot/1.0"})
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as e:
        print(f"  [ERRO] {source['name']}: {e}")
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = []

    # RSS 2.0
    for item in root.findall(".//item"):
        title   = (item.findtext("title") or "").strip()
        url     = (item.findtext("link") or "").strip()
        summary = _strip_tags(item.findtext("description") or "")
        pub     = _parse_date(item.findtext("pubDate"))
        if not url or not title:
            continue
        items.append({"title": title, "url": url, "summary": summary[:1000], "published_at": pub})

    # Atom
    for entry in root.findall(".//atom:entry", ns):
        title   = (entry.findtext("atom:title", namespaces=ns) or "").strip()
        url     = ""
        for link in entry.findall("atom:link", ns):
            if link.get("rel", "alternate") == "alternate" or not link.get("rel"):
                url = link.get("href", "")
                break
        summary = _strip_tags(entry.findtext("atom:summary", namespaces=ns) or "")
        pub     = _parse_date(entry.findtext("atom:updated", namespaces=ns) or
                              entry.findtext("atom:published", namespaces=ns))
        if not url or not title:
            continue
        items.append({"title": title, "url": url, "summary": summary[:1000], "published_at": pub})

    return items


def inserir_artigos(conn, source: dict, artigos: list[dict]) -> int:
    cur = conn.cursor()
    inseridos = 0
    for a in artigos:
        h = _url_hash(a["url"])
        topics = _detect_topics(a["title"], a.get("summary", ""))
        try:
            cur.execute("""
                INSERT INTO climate.knowledge_base
                    (url, url_hash, source, title, summary, published_at, topics)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url_hash) DO NOTHING
            """, (
                a["url"], h, source["name"],
                a["title"], a.get("summary"), a.get("published_at"),
                topics,
            ))
            if cur.rowcount:
                inseridos += 1
        except Exception as e:
            print(f"  [WARN] insert: {e}")
    conn.commit()
    return inseridos


def main() -> dict:
    conn = conectar()
    total = 0
    resultados = {}
    try:
        for source in RSS_SOURCES:
            print(f"Coletando: {source['name']} ...")
            artigos = coletar_feed(source)
            n = inserir_artigos(conn, source, artigos)
            print(f"  → {len(artigos)} encontrados, {n} novos")
            resultados[source["name"]] = {"found": len(artigos), "new": n}
            total += n
    finally:
        conn.close()

    print(f"\nTotal inserido: {total} artigos")
    return {"total_new": total, "sources": resultados}


if __name__ == "__main__":
    main()
