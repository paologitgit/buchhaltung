"""Locations aus OpenStreetMap über die Overpass API (kostenlos, kein Key nötig)."""
import logging

import requests

log = logging.getLogger(__name__)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def _build_query(selectors: list[str], lat: float, lon: float, radius_m: int) -> str:
    parts = []
    for sel in selectors:
        for kind in ("node", "way", "relation"):
            parts.append(f'{kind}{sel}(around:{radius_m},{lat},{lon});')
    body = "\n".join(parts)
    return f"[out:json][timeout:90];\n(\n{body}\n);\nout center tags;"


def search(selectors: list[str], lat: float, lon: float, radius_m: int,
           category_key: str) -> list[dict]:
    """Sucht Orte mit den gegebenen OSM-Tags im Umkreis und normalisiert sie."""
    if not selectors:
        return []
    query = _build_query(selectors, lat, lon, radius_m)
    data = None
    for url in OVERPASS_URLS:
        try:
            resp = requests.post(url, data={"data": query}, timeout=120,
                                 headers={"User-Agent": "gig-finder/1.0"})
            resp.raise_for_status()
            data = resp.json()
            break
        except requests.RequestException as exc:
            log.warning("Overpass %s fehlgeschlagen: %s", url, exc)
    if data is None:
        return []

    results = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        lat_ = el.get("lat") or el.get("center", {}).get("lat")
        lon_ = el.get("lon") or el.get("center", {}).get("lon")
        addr = " ".join(filter(None, [
            tags.get("addr:street", ""), tags.get("addr:housenumber", ""),
        ])).strip()
        results.append({
            "name": name,
            "kategorie": category_key,
            "adresse": addr,
            "plz": tags.get("addr:postcode", ""),
            "ort": tags.get("addr:city", ""),
            "lat": lat_,
            "lon": lon_,
            "website": tags.get("website") or tags.get("contact:website") or "",
            "email": tags.get("email") or tags.get("contact:email") or "",
            "telefon": tags.get("phone") or tags.get("contact:phone") or "",
            "quelle": "OSM",
        })
    return results
