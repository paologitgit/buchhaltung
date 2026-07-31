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
