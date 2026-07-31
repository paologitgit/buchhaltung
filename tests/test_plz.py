from gigfinder import plz


def test_lookup_known_plz():
    aarau = plz.lookup("5000")
    assert aarau is not None
    assert aarau["ort"] == "Aarau"
    assert aarau["kanton"] == "AG"
    assert 47.0 < aarau["lat"] < 48.0
    assert 7.5 < aarau["lon"] < 8.5


def test_lookup_strips_whitespace():
    assert plz.lookup(" 8400 ") is not None


def test_lookup_unknown_plz():
    assert plz.lookup("0000") is None
    assert plz.lookup("abcd") is None
