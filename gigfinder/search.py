"""Orchestriert eine Suche: Quellen abfragen, deduplizieren, Websites
scrapen, optional mit Claude anreichern."""
import logging
import math
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import claude_enrich, plz, scrape
from .categories import BY_KEY
from .sources import google_places, osm

log = logging.getLogger(__name__)

MAX_LOCATIONS = 120       # harte Obergrenze pro Suche
SCRAPE_WORKERS = 8
ENRICH_WORKERS = 4


def _distance_km(lat1, lon1, lat2, lon2) -> float:
    """Haversine-Distanz in Kilometern."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _dedupe(locations: list[dict]) -> list[dict]:
    """Gleicher Name in unmittelbarer Nähe = gleiche Location.

    OSM-Einträge werden bevorzugt verworfen, wenn ein Google-Eintrag mehr
    Daten (Website/Telefon) mitbringt – und umgekehrt ergänzt.
    """
    kept: list[dict] = []
    for loc in locations:
        duplicate = None
        for k in kept:
            if k["name"].strip().lower() != loc["name"].strip().lower():
                continue
            if None in (k["lat"], k["lon"], loc["lat"], loc["lon"]):
                duplicate = k
                break
            if _distance_km(k["lat"], k["lon"], loc["lat"], loc["lon"]) < 0.3:
                duplicate = k
                break
        if duplicate is None:
            kept.append(loc)
        else:
            # fehlende Felder aus dem Duplikat übernehmen
            for field in ("website", "email", "telefon", "adresse", "plz", "ort"):
                if not duplicate.get(field) and loc.get(field):
                    duplicate[field] = loc[field]
    return kept


def run_search(plz_code: str, radius_km: int, category_keys: list[str],
               use_google: bool = True, use_claude: bool = True,
               progress=None) -> dict:
    """Führt die komplette Suche aus und liefert das Resultat-Dict.

    `progress` ist ein optionales Callable(str) für Status-Updates.
    """
    def report(msg: str):
        log.info(msg)
        if progress:
            progress(msg)

    center = plz.lookup(plz_code)
    if center is None:
        raise ValueError(f"Unbekannte Schweizer PLZ: {plz_code}")
    radius_m = int(radius_km * 1000)

    # 1. Quellen abfragen
    locations: list[dict] = []
    for key in category_keys:
        cat = BY_KEY.get(key)
        if not cat:
            continue
        report(f"Suche {cat['label']} …")
        locations.extend(osm.search(cat["osm"], center["lat"], center["lon"],
                                    radius_m, key))
        if use_google and google_places.api_key():
            locations.extend(google_places.search(cat["google"], center["lat"],
                                                  center["lon"], radius_m, key))

    # 2. Distanz berechnen, Umkreis filtern, deduplizieren
    for loc in locations:
        if loc["lat"] is not None and loc["lon"] is not None:
            loc["distanz_km"] = round(_distance_km(center["lat"], center["lon"],
                                                   loc["lat"], loc["lon"]), 1)
        else:
            loc["distanz_km"] = None
    locations = [l for l in locations
                 if l["distanz_km"] is None or l["distanz_km"] <= radius_km]
    locations = _dedupe(locations)
    locations.sort(key=lambda l: (l["distanz_km"] is None, l["distanz_km"] or 0))
    locations = locations[:MAX_LOCATIONS]
    for loc in locations:
        loc["kategorie_label"] = BY_KEY[loc["kategorie"]]["label"]
        loc.setdefault("kontakt_name", "")
        loc.setdefault("beschreibung", "")
        loc.setdefault("eignung", None)

    # 3. Websites parallel scrapen
    with_site = [l for l in locations if l.get("website")]
    report(f"{len(locations)} Locations gefunden – lese {len(with_site)} Websites …")
    with ThreadPoolExecutor(max_workers=SCRAPE_WORKERS) as pool:
        futures = {pool.submit(scrape.scrape, l["website"]): l for l in with_site}
        for fut in as_completed(futures):
            loc = futures[fut]
            try:
                data = fut.result()
            except Exception as exc:  # Scraper darf die Suche nie abbrechen
                log.warning("Scrape %s: %s", loc.get("website"), exc)
                continue
            if data["email"] and not loc["email"]:
                loc["email"] = data["email"]
            if data["telefon"] and not loc["telefon"]:
                loc["telefon"] = data["telefon"]
            if data["kontakt_name"]:
                loc["kontakt_name"] = data["kontakt_name"]
            loc["scrape_text"] = data["text"]

    # 4. Optional: Claude-Anreicherung
    hinweise: list[str] = []
    if use_claude and not claude_enrich.available():
        hinweise.append(
            "Beschreibungen übersprungen: Es ist kein ANTHROPIC_API_KEY "
            "konfiguriert (siehe README).")
    elif use_claude:
        candidates = [l for l in locations if l.get("scrape_text")]
        ohne_text = len(locations) - len(candidates)
        report(f"Claude beschreibt {len(candidates)} Locations …")
        fehler: dict[str, int] = {}
        erfolge = 0
        with ThreadPoolExecutor(max_workers=ENRICH_WORKERS) as pool:
            futures = {pool.submit(claude_enrich.enrich, l): l for l in candidates}
            for fut in as_completed(futures):
                loc = futures[fut]
                try:
                    data = fut.result()
                except claude_enrich.EnrichmentError as exc:
                    log.warning("Claude %s: %s", loc.get("name"), exc)
                    fehler[str(exc)] = fehler.get(str(exc), 0) + 1
                    continue
                except Exception as exc:
                    log.exception("Claude %s", loc.get("name"))
                    meldung = f"Unerwarteter Fehler: {exc}"
                    fehler[meldung] = fehler.get(meldung, 0) + 1
                    continue
                if not data:
                    continue
                erfolge += 1
                loc["beschreibung"] = data.get("beschreibung", "")
                loc["eignung"] = data.get("eignung")
                if data.get("email") and not loc["email"]:
                    loc["email"] = data["email"].lower()
                if data.get("kontakt_name") and not loc["kontakt_name"]:
                    loc["kontakt_name"] = data["kontakt_name"]

        for meldung, anzahl in sorted(fehler.items(), key=lambda x: -x[1])[:3]:
            hinweise.append(
                f"Beschreibung für {anzahl} Location(s) fehlgeschlagen – {meldung}")
        if erfolge == 0 and not fehler and ohne_text:
            hinweise.append(
                "Keine Beschreibungen möglich: Für die gefundenen Locations "
                "liess sich keine Website auslesen.")

    for loc in locations:
        loc.pop("scrape_text", None)

    report("Fertig.")
    return {
        "plz": plz_code,
        "ort": center["ort"],
        "kanton": center["kanton"],
        "radius_km": radius_km,
        "kategorien": category_keys,
        "locations": locations,
        "hinweise": hinweise,
    }
