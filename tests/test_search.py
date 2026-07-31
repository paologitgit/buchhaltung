from gigfinder.search import _dedupe, _distance_km


def _loc(name, lat, lon, **kw):
    base = {"name": name, "kategorie": "bar_pub", "adresse": "", "plz": "",
            "ort": "", "lat": lat, "lon": lon, "website": "", "email": "",
            "telefon": "", "quelle": "OSM"}
    base.update(kw)
    return base


def test_distance_zurich_bern():
    d = _distance_km(47.3769, 8.5417, 46.9480, 7.4474)
    assert 90 < d < 105


def test_dedupe_merges_nearby_same_name():
    a = _loc("Café Blue", 47.5000, 8.7000, quelle="OSM")
    b = _loc("café blue", 47.5001, 8.7001, quelle="Google",
             website="https://cafeblue.ch", telefon="052 111 22 33")
    result = _dedupe([a, b])
    assert len(result) == 1
    assert result[0]["website"] == "https://cafeblue.ch"
    assert result[0]["telefon"] == "052 111 22 33"


def test_dedupe_keeps_distinct_locations():
    a = _loc("Café Blue", 47.5000, 8.7000)
    b = _loc("Café Blue", 47.6000, 8.9000)  # gleicher Name, 15+ km entfernt
    c = _loc("Anderes Lokal", 47.5000, 8.7000)
    assert len(_dedupe([a, b, c])) == 3
