"""Schweizer PLZ-Verzeichnis mit Koordinaten (Quelle: GeoNames, CC-BY 4.0)."""
import csv
import os

_DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "plz_ch.csv")
_index: dict[str, dict] | None = None


def _load() -> dict[str, dict]:
    global _index
    if _index is None:
        _index = {}
        with open(_DATA_FILE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                _index[row["plz"]] = {
                    "plz": row["plz"],
                    "ort": row["ort"],
                    "kanton": row["kanton"],
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                }
    return _index


def lookup(plz: str) -> dict | None:
    """Liefert Ort, Kanton und Koordinaten zu einer Schweizer PLZ, sonst None."""
    return _load().get(plz.strip())
