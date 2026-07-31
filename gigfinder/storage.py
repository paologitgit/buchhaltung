"""Suchergebnisse als JSON ablegen und als CSV exportieren."""
import csv
import io
import json
import os
import re
import uuid
from datetime import datetime, timezone

SEARCH_DIR = os.environ.get(
    "GIGFINDER_DATA_DIR",
    os.path.join(os.path.dirname(__file__), "..", "data", "searches"),
)

CSV_COLUMNS = [
    ("name", "Name"),
    ("kategorie_label", "Kategorie"),
    ("adresse", "Adresse"),
    ("plz", "PLZ"),
    ("ort", "Ort"),
    ("distanz_km", "Distanz (km)"),
    ("email", "E-Mail"),
    ("kontakt_name", "Kontaktperson"),
    ("telefon", "Telefon"),
    ("website", "Website"),
    ("beschreibung", "Beschreibung"),
    ("eignung", "Eignung (1-5)"),
    ("quelle", "Quelle"),
]

_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def save(result: dict) -> str:
    os.makedirs(SEARCH_DIR, exist_ok=True)
    search_id = uuid.uuid4().hex
    result = dict(result, id=search_id,
                  erstellt=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    with open(os.path.join(SEARCH_DIR, f"{search_id}.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    return search_id


def load(search_id: str) -> dict | None:
    if not _ID_RE.match(search_id):
        return None
    path = os.path.join(SEARCH_DIR, f"{search_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def to_csv(result: dict) -> bytes:
    """Semikolon-getrennt mit UTF-8-BOM, damit Excel (Schweiz) es sauber öffnet."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow([label for _, label in CSV_COLUMNS])
    for loc in result.get("locations", []):
        writer.writerow([loc.get(field) if loc.get(field) is not None else ""
                         for field, _ in CSV_COLUMNS])
    return buf.getvalue().encode("utf-8-sig")
