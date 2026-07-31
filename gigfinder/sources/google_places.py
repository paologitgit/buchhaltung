"""Locations aus der Google Places API (New) – Text Search.

Braucht GOOGLE_PLACES_API_KEY in der Umgebung / .env. Ohne Key wird diese
Quelle einfach übersprungen. Das Gratis-Kontingent von Google (Stand 2026:
mehrere tausend Text-Suchen pro Monat) reicht für den privaten Gebrauch
in der Regel aus.
"""
import logging
import os

import requests

log = logging.getLogger(__name__)

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join([
    "places.displayName", "places.formattedAddress", "places.location",
    "places.websiteUri", "places.nationalPhoneNumber", "places.postalAddress",
])


def api_key() -> str | None:
    return os.environ.get("GOOGLE_PLACES_API_KEY") or None


def search(queries: list[str], lat: float, lon: float, radius_m: int,
           category_key: str) -> list[dict]:
    """Text-Suche pro Suchbegriff mit Standort-Bias auf den Umkreis."""
    key = api_key()
    if not key:
        return []
    results = []
    for q in queries:
        try:
            resp = requests.post(
                SEARCH_URL,
                json={
                    "textQuery": q,
                    "languageCode": "de",
                    "regionCode": "CH",
                    "pageSize": 20,
                    "locationBias": {"circle": {
                        "center": {"latitude": lat, "longitude": lon},
                        "radius": float(min(radius_m, 50000)),
                    }},
                },
                headers={
                    "X-Goog-Api-Key": key,
                    "X-Goog-FieldMask": FIELD_MASK,
                },
                timeout=30,
            )
            resp.raise_for_status()
            places = resp.json().get("places", [])
        except requests.RequestException as exc:
            log.warning("Google Places '%s' fehlgeschlagen: %s", q, exc)
            continue

        for p in places:
            postal = p.get("postalAddress", {})
            loc = p.get("location", {})
            results.append({
                "name": p.get("displayName", {}).get("text", ""),
                "kategorie": category_key,
                "adresse": ", ".join(postal.get("addressLines", []))
                           or p.get("formattedAddress", ""),
                "plz": postal.get("postalCode", ""),
                "ort": postal.get("locality", ""),
                "lat": loc.get("latitude"),
                "lon": loc.get("longitude"),
                "website": p.get("websiteUri", ""),
                "email": "",
                "telefon": p.get("nationalPhoneNumber", ""),
                "quelle": "Google",
            })
    return results
