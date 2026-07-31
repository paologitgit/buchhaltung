import pytest

from gigfinder import addressbook


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(addressbook, "DB_PATH", str(tmp_path / "test.sqlite3"))
    yield


CSV_HEADER = ("Name;Kategorie;Adresse;PLZ;Ort;Distanz (km);E-Mail;Kontaktperson;"
              "Telefon;Website;Beschreibung;Eignung (1-5);Quelle\n")


def _csv(*rows: str) -> bytes:
    return ("﻿" + CSV_HEADER + "\n".join(rows)).encode("utf-8")


def test_import_and_list():
    stats = addressbook.import_csv(_csv(
        "Café Blue;Cafés;Marktgasse 1;8400;Winterthur;0.4;info@blue.ch;"
        "Maria Müller;052 111 22 33;https://blue.ch;Nettes Café;4;OSM",
    ))
    assert stats == {"neu": 1, "ergaenzt": 0, "uebersprungen": 0, "fehler": 0}
    entries = addressbook.list_all()
    assert len(entries) == 1
    assert entries[0]["name"] == "Café Blue"
    assert entries[0]["email"] == "info@blue.ch"
    assert "distanz" not in entries[0]  # Distanz wird nicht übernommen


def test_import_skips_duplicates_and_fills_gaps():
    addressbook.import_csv(_csv(
        "Café Blue;Cafés;;8400;Winterthur;;;;;;;;OSM",
    ))
    # gleicher Name+PLZ, bringt jetzt eine E-Mail mit -> ergänzt
    stats = addressbook.import_csv(_csv(
        "Café Blue;Cafés;;8400;Winterthur;;info@blue.ch;;;;;;Google",
    ))
    assert stats["ergaenzt"] == 1 and stats["neu"] == 0
    # exakt gleicher Import nochmals -> übersprungen
    stats = addressbook.import_csv(_csv(
        "Café Blue;Cafés;;8400;Winterthur;;info@blue.ch;;;;;;Google",
    ))
    assert stats["uebersprungen"] == 1
    entries = addressbook.list_all()
    assert len(entries) == 1
    assert entries[0]["email"] == "info@blue.ch"


def test_import_duplicate_by_email_different_plz():
    addressbook.import_csv(_csv("Weinbar Rot;;;8400;Winterthur;;mail@rot.ch;;;;;;OSM"))
    stats = addressbook.import_csv(_csv("Rot Weinbar;;;8408;Winterthur;;mail@rot.ch;;;;;;Google"))
    assert stats["uebersprungen"] == 1
    assert len(addressbook.list_all()) == 1


def test_import_rejects_foreign_csv():
    with pytest.raises(ValueError):
        addressbook.import_csv(b"foo,bar\n1,2\n")


def test_entry_from_location_uses_category_label():
    entry = addressbook.entry_from_location({
        "name": "Café Blue", "kategorie": "cafe", "kategorie_label": "Cafés",
        "plz": "8400", "ort": "Winterthur", "email": "info@blue.ch",
        "eignung": 4, "quelle": "OSM", "distanz_km": 0.4, "lat": 47.5,
    })
    assert entry["kategorie"] == "Cafés"
    assert entry["eignung"] == 4
    assert "distanz_km" not in entry and "lat" not in entry


def test_add_entries_from_locations_skips_duplicates():
    locations = [
        {"name": "Café Blue", "kategorie_label": "Cafés", "plz": "8400",
         "ort": "Winterthur", "email": "info@blue.ch", "eignung": 4},
        {"name": "Weingut Sonnenhof", "kategorie_label": "Weingüter",
         "plz": "8542", "ort": "Wiesendangen", "email": "", "eignung": None},
    ]
    entries = [addressbook.entry_from_location(l) for l in locations]
    assert addressbook.add_entries(entries)["neu"] == 2
    # zweite Übernahme derselben Suche legt nichts doppelt an
    stats = addressbook.add_entries(entries)
    assert stats == {"neu": 0, "ergaenzt": 0, "uebersprungen": 2, "fehler": 0}
    assert len(addressbook.list_all()) == 2


def test_already_saved_flags():
    addressbook.import_csv(_csv("Café Blue;Cafés;;8400;Winterthur;;info@blue.ch;;;;;;OSM"))
    flags = addressbook.already_saved([
        {"name": "Café Blue", "plz": "8400", "email": ""},        # Name + PLZ
        {"name": "Anderer Name", "plz": "9999", "email": "info@blue.ch"},  # E-Mail
        {"name": "Neue Bar", "plz": "3000", "email": "neu@bar.ch"},
    ])
    assert flags == [True, True, False]


def test_already_saved_on_empty_list():
    assert addressbook.already_saved([]) == []


def test_delete_and_export():
    addressbook.import_csv(_csv(
        "A-Lokal;;;8000;Zürich;;a@a.ch;;;;;;OSM",
        "B-Lokal;;;3000;Bern;;b@b.ch;;;;;;OSM",
    ))
    entries = addressbook.list_all()
    assert len(entries) == 2
    addressbook.delete(entries[0]["id"])
    remaining = addressbook.list_all()
    assert len(remaining) == 1
    csv_out = addressbook.to_csv().decode("utf-8-sig")
    assert csv_out.startswith("Name;")
    assert remaining[0]["name"] in csv_out
