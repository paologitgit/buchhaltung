"""Dauerhaftes Adressbuch in SQLite.

Importiert die vom Gig-Finder exportierten CSV-Dateien und speichert die
Adressen dauerhaft. Duplikate (gleicher Name + PLZ, oder gleiche E-Mail)
werden beim Import übersprungen; fehlende Felder bestehender Einträge
werden dabei ergänzt.
"""
import csv
import io
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "GIGFINDER_DB",
    os.path.join(os.path.dirname(__file__), "..", "data", "adressbuch.sqlite3"),
)

FIELDS = ["name", "kategorie", "adresse", "plz", "ort", "email",
          "kontakt_name", "telefon", "website", "beschreibung", "eignung",
          "quelle"]

# CSV-Spaltentitel (wie im Export aus storage.py) -> Datenbankfeld
_LABEL_TO_FIELD = {
    "Name": "name",
    "Kategorie": "kategorie",
    "Adresse": "adresse",
    "PLZ": "plz",
    "Ort": "ort",
    "E-Mail": "email",
    "Kontaktperson": "kontakt_name",
    "Telefon": "telefon",
    "Website": "website",
    "Beschreibung": "beschreibung",
    "Eignung (1-5)": "eignung",
    "Quelle": "quelle",
    # "Distanz (km)" wird bewusst ignoriert – sie gilt nur relativ zur Suche
}

_EXPORT_COLUMNS = [
    ("name", "Name"), ("kategorie", "Kategorie"), ("adresse", "Adresse"),
    ("plz", "PLZ"), ("ort", "Ort"), ("email", "E-Mail"),
    ("kontakt_name", "Kontaktperson"), ("telefon", "Telefon"),
    ("website", "Website"), ("beschreibung", "Beschreibung"),
    ("eignung", "Eignung (1-5)"), ("quelle", "Quelle"),
    ("importiert_am", "Importiert am"),
]


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS adressen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            kategorie TEXT DEFAULT '',
            adresse TEXT DEFAULT '',
            plz TEXT DEFAULT '',
            ort TEXT DEFAULT '',
            email TEXT DEFAULT '',
            kontakt_name TEXT DEFAULT '',
            telefon TEXT DEFAULT '',
            website TEXT DEFAULT '',
            beschreibung TEXT DEFAULT '',
            eignung TEXT DEFAULT '',
            quelle TEXT DEFAULT '',
            importiert_am TEXT NOT NULL
        )
    """)
    return conn


def _find_duplicate(conn: sqlite3.Connection, entry: dict) -> sqlite3.Row | None:
    if entry.get("email"):
        row = conn.execute(
            "SELECT * FROM adressen WHERE lower(email) = ? AND email != ''",
            (entry["email"].lower(),)).fetchone()
        if row:
            return row
    return conn.execute(
        "SELECT * FROM adressen WHERE lower(name) = ? AND plz = ?",
        (entry["name"].lower(), entry.get("plz", ""))).fetchone()


def import_csv(data: bytes) -> dict:
    """Importiert eine Gig-Finder-CSV. Liefert {"neu", "ergaenzt", "uebersprungen", "fehler"}."""
    text = data.decode("utf-8-sig", errors="replace")
    first_line = text.splitlines()[0] if text.splitlines() else ""
    delimiter = ";" if first_line.count(";") >= first_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    if not reader.fieldnames or "Name" not in [f.strip() for f in reader.fieldnames]:
        raise ValueError(
            "Die Datei sieht nicht wie ein Gig-Finder-Export aus "
            "(Spalte «Name» fehlt).")

    stats = {"neu": 0, "ergaenzt": 0, "uebersprungen": 0, "fehler": 0}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect() as conn:
        for row in reader:
            entry = {}
            for label, value in row.items():
                field = _LABEL_TO_FIELD.get((label or "").strip())
                if field:
                    entry[field] = (value or "").strip()
            if not entry.get("name"):
                stats["fehler"] += 1
                continue

            existing = _find_duplicate(conn, entry)
            if existing is None:
                conn.execute(
                    f"INSERT INTO adressen ({', '.join(FIELDS)}, importiert_am) "
                    f"VALUES ({', '.join('?' * len(FIELDS))}, ?)",
                    [entry.get(f, "") for f in FIELDS] + [now])
                stats["neu"] += 1
            else:
                # fehlende Felder des bestehenden Eintrags ergänzen
                updates = {f: entry[f] for f in FIELDS
                           if entry.get(f) and not existing[f]}
                if updates:
                    conn.execute(
                        f"UPDATE adressen SET {', '.join(f'{f} = ?' for f in updates)} "
                        f"WHERE id = ?",
                        list(updates.values()) + [existing["id"]])
                    stats["ergaenzt"] += 1
                else:
                    stats["uebersprungen"] += 1
    return stats


def list_all() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM adressen ORDER BY plz, lower(name)").fetchall()
    return [dict(r) for r in rows]


def delete(entry_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM adressen WHERE id = ?", (entry_id,))


def to_csv() -> bytes:
    """Ganzes Adressbuch als CSV (Semikolon, UTF-8-BOM für Excel)."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow([label for _, label in _EXPORT_COLUMNS])
    for entry in list_all():
        writer.writerow([entry.get(field, "") for field, _ in _EXPORT_COLUMNS])
    return buf.getvalue().encode("utf-8-sig")
